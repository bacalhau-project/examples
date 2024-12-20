# app.py
import concurrent.futures  # noqa: E402
import datetime  # noqa: E402
import json as JSON  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import sqlite3  # noqa: E402
import subprocess
import time  # noqa: E402
from functools import wraps  # noqa: E402
from io import TextIOWrapper  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import List  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

import gevent
import gevent.monkey
import gevent.queue
import grequests  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from faker import Faker  # noqa: E402
from flask import Flask, jsonify, render_template, request  # noqa: E402
from flask_socketio import SocketIO  # noqa: E402

fake = Faker()

out = []
CONNECTIONS = 100
TIMEOUT = 1
NUM_REQUESTS = 1000

GUNICORN_PORT = 14041

SQLITE_FILE = "sqlite.db"

TOKENARGUMENT = "token"  # The token argument to be passed in the request

VARIABLES = {"site": "", TOKENARGUMENT: "", "serverip": ""}


def connect_to_sqlite(sqlite_file) -> sqlite3.Connection:
    if not os.path.exists(sqlite_file):
        print(f"Creating {sqlite_file}...")
        conn = sqlite3.connect(sqlite_file)
        c = conn.cursor()
        c.execute(
            "CREATE TABLE sites (id INTEGER PRIMARY KEY, site TEXT, ip TEXT, last_updated TEXT)"
        )
        conn.commit()

    return sqlite3.connect(sqlite_file)


def write_to_sqlite(
    conn, site: str, good_ips: list, bad_ips: list = [], clear_first=False
):
    c = conn.cursor()
    if clear_first:
        c.execute("DELETE FROM sites where site = ?", (site,))
        conn.commit()

    for ip in good_ips:
        c.execute(
            "INSERT INTO sites (site, ip, last_updated) VALUES (?, ?, ?)",
            (site, ip, time.time()),
        )
    conn.commit()

    for ip in bad_ips:
        c.execute(
            "DELETE from sites where site = ? and ip = ?",
            (site, ip),
        )
    conn.commit()


def read_from_sqlite(conn, site_name) -> list:
    c = conn.cursor()
    c.execute("SELECT * FROM sites where site = ?", (site_name,))
    rows = c.fetchall()
    return rows


def get_http_content(url, timeout) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "":
        url = "http://" + url

    return requests.get(url=url, timeout=timeout).text


def load_url(url, timeout) -> dict:
    ip_and_port = urlparse(url).netloc
    ip = ip_and_port.split(":")[0]
    try:
        site_response = get_http_content(url, timeout)
        if site_response is None:
            return {"ip": ip}
        # Parse the JSON response
        site_response_parsed = JSON.loads(site_response)
        return site_response_parsed
    except Exception as e:
        print(f"Timeout on {url}: {e}")
        return {"ip": ip}


def populate_variables(f):
    @wraps(f)
    def decoratorFn(*args, **kwargs):
        if request.method == "GET":
            # Handle GET request with query parameters
            if request.args:
                for k, v in request.args.items():
                    if k.lower() in VARIABLES:
                        VARIABLES[k.lower()] = v.lower()
        elif request.method == "POST":
            # Handle POST request with JSON data
            data = request.json
            if data:
                for k, v in data.items():
                    if k.lower() in VARIABLES:
                        VARIABLES[k.lower()] = v.lower()
            else:
                return jsonify(error="No JSON data found in request"), 400

        return f(*args, **kwargs)

    return decoratorFn


def validate_token(f):
    @wraps(f)
    def decoratorFn(*args, **kwargs):
        load_dotenv(Path(__file__).parent / ".env")

        tokenFromFile = str(os.environ.get(TOKENARGUMENT.upper()))

        postedToken = str(VARIABLES[TOKENARGUMENT])

        if not postedToken:
            return f"No token posted in {VARIABLES}"
        elif not confirm_token_matches(tokenFromFile, postedToken):
            return f"Invalid token: {postedToken}"

        return f(*args, **kwargs)

    return decoratorFn


# Broken out so that we can mock more easily
def confirm_token_matches(tokenFromFile, postedToken) -> bool:
    return tokenFromFile == postedToken


def get_site_config_path(site_name):
    path = Path(__file__).parent / "sites" / f"{site_name}.conf"
    if not os.path.exists(path):
        print(f"Site config file {site_name} does not exist in {path}")
        return None
    return path


def open_site_config(site_name, mode) -> TextIOWrapper | None:
    path = get_site_config_path(site_name)
    if not path:
        return None
    return open(path, mode)


# Return a set of IPs
def execute_refresh(site_name) -> tuple[List[str], List[str]]:
    print(f"Refreshing {site_name}")

    # See if the config file is in the directory - if not, throw an error
    config_file_path = get_site_config_path(site_name)
    if not config_file_path:
        print(f"Site config file {site_name} does not exist. Creating...")
        config_file_path = Path(__file__).parent / "sites" / f"{site_name}.conf"
        with open(config_file_path, "w") as f:
            f.write("")
        print(f"Created {config_file_path}")

    conn = sqlite3.connect(SQLITE_FILE)

    # First load all the current IPs from the sqlite database
    # IP addresses are 'server 10.128.0.15:GUNICORN_PORT' and end with a ";"
    read_ips = set()
    for row in read_from_sqlite(conn, site_name):
        read_ips.add(f"http://{row[2]}:{GUNICORN_PORT}/json")
    read_ips_list = list(read_ips)

    good = []
    bad = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONNECTIONS) as executor:
        number_of_urls = len(read_ips_list)
        future_to_url = (
            executor.submit(load_url, read_ips_list[i % number_of_urls], TIMEOUT)
            for i in range(number_of_urls * 3)  # Doing it 3x just in case 1 fails
        )

        for future in concurrent.futures.as_completed(future_to_url):
            try:
                data = future.result()
                # If data is not empty, add it to the good list
                if data and "nodeID" in data:
                    good.append(data)
                else:
                    bad.append(data)
            except Exception as exc:
                print(str(type(exc)))

    print(f"Good: {len(good)}")
    print(f"Bad: {len(bad)}")

    # Print line break
    print()

    # Collect all the IPs - make them unique
    good_ips = set()
    for g in good:
        # Get hostname from URL that looks like https://10.0.0.1:14041
        good_ips.add(g["ip"])

    bad_ips = set()
    for b in bad:
        bad_ips.add(b["ip"])

    # Print the unique IPs, separated by a newline
    print(f"Unique Good IPs: {len(good_ips)}")
    print("\n".join(good_ips))

    print(f"Unique Bad IPs: {len(bad_ips)}")
    print("\n".join(bad_ips))

    return list(good_ips), list(bad_ips)


@populate_variables
@validate_token
def get_sites():
    # Return a json response of all sites - all sites are of the form sites/SITENAME.conf
    # Get a list of all the files and the contents

    sites = {}
    all_site_files = os.listdir("/sites")
    for site in all_site_files:
        with open(f"/sites/{site}") as f:
            sites[site] = f.read()

    return sites


@populate_variables
@validate_token
def update_sites():
    print("Received POST request to /update")
    print("Request data:", request.data)
    print("Request JSON:", request.json)
    # Add more debug statements as needed

    # Get the site that needs to be updated
    site = VARIABLES["site"]

    if VARIABLES["serverip"] != "":
        requestIP = VARIABLES["serverip"]
    else:
        return "Please provide a server IP in 'serverip' request."

    conn = connect_to_sqlite(SQLITE_FILE)
    write_to_sqlite(conn, site, [requestIP])

    # Print out all IPs from DB for site:
    print(f"IPs for {site}:")
    for row in read_from_sqlite(conn, site):
        print(row[2])

    return f"Updated {site} with {requestIP}"


@populate_variables
@validate_token
def regen_sites():
    # Get the site that needs to be regenerated
    site = VARIABLES["site"]
    if not site:
        return "Please provide a site"

    site_file_name = f"./sites/{site}.conf"

    # See if site exists in /sites
    if not os.path.exists(site_file_name):
        return f"Site config file {site} does not exist"

    good_ips, bad_ips = execute_refresh(f"{site}")

    conn = connect_to_sqlite(SQLITE_FILE)

    write_to_sqlite(conn, site, good_ips, bad_ips, clear_first=False)

    # Delete all the IPs from the sqlite database that match this site

    # Truncate and replace sites/SITENAME.conf with the new IPs
    # Each line should be:
    # server <IP>:14041;
    # Overwrite the existing file
    with open(site_file_name, "w") as f:
        for ip in good_ips:
            f.write(f"server {ip}:14041;\n")

    # Restart nginx
    os.system("sudo nginx -s reload")

    return f"Regenerated {site} with {len(good_ips)} IPs. Deleted {len(bad_ips)} IPs."


@populate_variables
def index():
    # If Host: dashboard.justicons.org
    if request.host == "dashboard.justicons.org":
        return dashboard()
    else:
        return "Hello, ItsADash.work!"


def dashboard():
    return "Dashboard"


def justicons_dashboard():
    return render_justicons_dashboard()


def render_justicons_dashboard():
    return render_template("justicons_dashboard.html")


def somanycars_dashboard():
    return render_somanycars_dashboard()


def render_somanycars_dashboard():
    return render_template("somanycars_dashboard.html")


def sqlite_stats():
    # For every site in './sites', get the number of IPs
    sites = {}
    for site in os.listdir("./sites"):
        with open(f"./sites/{site}") as f:
            # Get the site name without the .conf. it will be similar to "example.com.conf" and should result in "example.com"
            site_name = site.rsplit(".", 1)[0]
            sites[site_name] = {}
            sites[site_name]["number_of_ips_in_nginx"] = len(f.readlines())

    for site_name in sites.keys():
        conn = connect_to_sqlite(SQLITE_FILE)
        rows = read_from_sqlite(conn, site_name)
        sites[site_name]["servers"] = rows

    return render_template("sqlite_stats.html", sites=sites)


def kill_processes_in_close_wait():
    # Detect if we need sudo to run the lsof command
    try:
        subprocess.run(["lsof"], check=True, text=True, capture_output=True)
        sudo_string = ""
    except Exception as e:
        print(f"Error running lsof command: {e}")
        sudo_string = "sudo "

    try:
        # Running lsof command to find processes with sockets in CLOSE_WAIT state
        command = f"{sudo_string}lsof -i | grep CLOSE_WAIT"

        # Run the command and get the output, stop printing it to stdout or console
        result = subprocess.run(
            command, shell=True, text=True, capture_output=True, timeout=5
        )

        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and "CLOSE_WAIT" in line and "python" in line.lower():
                print(f"Killing process: {line}")
                parts = line.split()
                pid = parts[1]  # Process ID
                subprocess.run(
                    [f"{sudo_string}", "kill", "-9", pid],
                    check=True,
                    text=True,
                    capture_output=True,
                )

    except subprocess.CalledProcessError as e:
        print("Failed to find or kill processes:", e)


flaskApp = Flask("itsadash", static_url_path="/static")
# In the background start a process to find and kill processes in CLOSE_WAIT state
# gevent.spawn(kill_processes_in_close_wait)

flaskApp.config.from_pyfile("config.py")
try:
    os.makedirs(flaskApp.instance_path)
except OSError:
    pass

flaskApp.add_url_rule("/", view_func=index, methods=["GET"])
flaskApp.add_url_rule("/update", view_func=update_sites, methods=["POST"])
flaskApp.add_url_rule("/regen", view_func=regen_sites, methods=["POST"])
flaskApp.add_url_rule(
    "/justicons_dashboard", view_func=justicons_dashboard, methods=["GET"]
)
flaskApp.add_url_rule(
    "/somanycars_dashboard", view_func=somanycars_dashboard, methods=["GET"]
)
flaskApp.add_url_rule("/sqlite_stats", view_func=sqlite_stats, methods=["GET"])

socketio = SocketIO(flaskApp, debug=True, cors_allowed_origins="*", async_mode="gevent")


globalJustIconsQueue = gevent.queue.Queue(100)
runningJustIconsQueue = gevent.queue.Queue(1)
runJustIconsEventLoop = gevent.queue.Queue(1)


@socketio.on("start_justicons_socket")
def websocket_service_justicons_start(data):
    runJustIconsEventLoop.put(True)
    print("Starting justicons event loop...")
    while not runJustIconsEventLoop.empty():
        if globalJustIconsQueue.qsize() < 40 and not runningJustIconsQueue.qsize():
            socketio.start_background_task(
                fetchBulkJustIcons, "http://justicons.org/json"
            )
        for _ in range(5):
            if not globalJustIconsQueue.empty():
                data = globalJustIconsQueue.get()
                socketio.emit("node", data.text)
        socketio.sleep(1)


@socketio.on("stop_justicons_socket")
def websocket_service_justicons_stop():
    runJustIconsEventLoop.get()
    print("Stopping justicons event loop...")


globalSoManyCarsQueue = gevent.queue.Queue(100)
runningSoManyCarsQueue = gevent.queue.Queue(1)
runSoManyCarsEventLoop = gevent.queue.Queue(1)


@socketio.on("start_somanycars_socket")
def websocket_service_somanycars_start(data):
    runSoManyCarsEventLoop.put(True)
    print("Starting somanycars event loop...")
    while not runSoManyCarsEventLoop.empty():
        if globalSoManyCarsQueue.qsize() < 40 and not runningSoManyCarsQueue.qsize():
            socketio.start_background_task(
                fetchBulkSoManyCars, "http://somanycars.org/json"
            )
        for _ in range(5):
            if not globalSoManyCarsQueue.empty():
                data = globalSoManyCarsQueue.get()
                if data is not None and hasattr(data, "text"):
                    socketio.emit("node", data.text)
        socketio.sleep(1)


@socketio.on("stop_somanycars_socket")
def websocket_service_somanycars_stop():
    runSoManyCarsEventLoop.get()
    print("Stopping somanycars event loop...")


def fetchBulkJustIcons(url):
    try:
        runningJustIconsQueue.put(True)
        requests = [grequests.get(url) for _ in range(200)]
        results = grequests.map(requests)
        for result in results:
            globalJustIconsQueue.put(result)
    finally:
        if not runningJustIconsQueue.empty():
            runningJustIconsQueue.get()


def fetchBulkSoManyCars(url):
    # Get file logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler("somanycars.log"))

    try:
        runningSoManyCarsQueue.put(True)
        # requests = [grequests.get(url) for _ in range(12)]
        # results = grequests.map(requests)

        results = []
        for i in range(12):
            start_time = datetime.datetime.now()
            results.append(requests.get(url, stream=False))
            end_time = datetime.datetime.now()
            logger.info(
                f"Request {i} took {end_time - start_time} to complete - {results[i].status_code}"
            )

        for result in results:
            globalSoManyCarsQueue.put(result)
    except Exception as e:
        logger.error(f"Error in fetchBulkSoManyCars function: {e}")
    finally:
        while not runningSoManyCarsQueue.empty():
            runningSoManyCarsQueue.get()


if __name__ == "__main__":
    socketio.run(flaskApp, debug=True, cors_allowed_origins="*", async_mode="gevent")
