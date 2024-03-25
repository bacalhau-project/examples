# app.py
import concurrent.futures
import json as JSON
import os
import socket
import sqlite3
import time
from functools import wraps
from io import TextIOWrapper
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template

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


def write_to_sqlite(conn, ips: list, site: str, clear_first=False):
    c = conn.cursor()
    if clear_first:
        c.execute("DELETE FROM sites where site = ?", (site,))
        conn.commit()

    for ip in ips:
        c.execute(
            "INSERT INTO sites (site, ip, last_updated) VALUES (?, ?, ?)",
            (site, ip, time.time()),
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
    try:
        site_response = get_http_content(url, timeout)
        if site_response is None:
            return {}
        # Parse the JSON response
        site_response_parsed = JSON.loads(site_response)
        return site_response_parsed
    except (socket.timeout, ConnectionRefusedError):
        print(f"Timeout on {url}")
        return {}


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
def execute_refresh(site_name) -> list:
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
                if data:
                    good.append(data)
                else:
                    bad.append("Bad Query")
            except Exception as exc:
                print(str(type(exc)))
                bad.append("Bad Query")

    print(f"Good: {len(good)}")
    print(f"Bad: {len(bad)}")

    # Print line break
    print()

    # Collect all the IPs - make them unique
    ips = set()
    for g in good:
        # Get hostname from URL that looks like https://10.0.0.1:14041
        ips.add(g["ip"])

    # Print the unique IPs, separated by a newline
    print(f"Unique IPs: {len(ips)}")
    print("\n".join(ips))

    return list(ips)


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
    write_to_sqlite(conn, [requestIP], site)

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

    ips = execute_refresh(f"{site}")

    conn = connect_to_sqlite(SQLITE_FILE)

    write_to_sqlite(conn, ips, site, clear_first=True)

    # Delete all the IPs from the sqlite database that match this site

    # Truncate and replace sites/SITENAME.conf with the new IPs
    # Each line should be:
    # server <IP>:14041;
    # Overwrite the existing file
    with open(site_file_name, "w") as f:
        for ip in ips:
            f.write(f"server {ip}:14041;\n")

    # Restart nginx
    os.system("sudo nginx -s reload")

    return f"Regenerated {site} with {len(ips)} IPs"


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

flaskApp = Flask("itsadash", static_url_path='/static')
flaskApp.config.from_pyfile("config.py")
try:
    os.makedirs(flaskApp.instance_path)
except OSError:
    pass

flaskApp.add_url_rule("/", view_func=index, methods=["GET"])
flaskApp.add_url_rule("/update", view_func=update_sites, methods=["POST"])
flaskApp.add_url_rule("/regen", view_func=regen_sites, methods=["POST"])
flaskApp.add_url_rule("/justicons_dashboard", view_func=justicons_dashboard, methods=["GET"])


if __name__ == "__main__":
    flaskApp.run()
