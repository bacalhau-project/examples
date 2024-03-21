# app.py
import concurrent.futures
import os
import re
import time

import requests
from dotenv import load_dotenv
from flask import Flask, request
from networking import execute_refresh
from justicons_dashboard.render import render_justicons_dashboard

out = []
CONNECTIONS = 100
TIMEOUT = 1
NUM_REQUESTS = 1000


def load_url(url, timeout):
    # Get JSON body from URL
    ans = requests.get(url, timeout=timeout)
    return ans.json()


app = Flask(__name__)

def authenticate_token(putativeToken):
    load_dotenv()

    if not putativeToken or putativeToken != os.environ.get("TOKEN"):
        return False
    return True


@app.route("/sites")
def get_sites():
    if not authenticate_token(request.args.get("token")):
        return "Invalid token"

    # Return a json response of all sites - all sites are of the form sites/SITENAME.conf
    # Get a list of all the files and the contents

    sites = {}
    all_site_files = os.listdir("/sites")
    for site in all_site_files:
        with open(f"/sites/{site}") as f:
            sites[site] = f.read()

    return sites


@app.route("/update", methods=["POST"])
def update_sites():
    if not authenticate_token(request.args.get("token")):
        return "Invalid token"

    # Get the site that needs to be updated
    site = request.args.get("site")

    # Append site IP to the file - /sites/SITENAME.conf is relative to current file
    site_file_name = f"./sites/{site}.conf"

    read_ips = []
    if os.path.exists(site_file_name):
        with open(site_file_name) as f:
            all_file_blob = f.read()
            # Split the file by newline or ;
            read_ips = re.split(r"\n|;", all_file_blob)

    requestIP = request.headers["X-Forwarded-For"]

    # If the IP is already in the file, don't add it
    if requestIP in read_ips:
        return f"IP {requestIP} already in {site_file_name}"

    # Append the IP to read_ips
    read_ips.append(f"server {requestIP}:14041")

    # Dedupe and compress the list
    read_ips = list(set(read_ips))

    write_ips = []
    # If not of the form 'server 10.142.0.28:14041;', with 'server <IP>:14041;', then remove
    for ip in read_ips:
        if re.match(r"server \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:14041", ip):
            write_ips.append(f"{ip};\n")

    # Write the file, truncate and replace
    with open(site_file_name, "w") as f:
        for ip in write_ips:
            f.write(f"{ip}")

    # Restart nginx
    os.system("sudo nginx -s reload")

    all_headers = request.headers
    # Print the updated file
    with open(site_file_name) as f:
        return f"{site_file_name}\n{f.read()}\n\n{all_headers}"


@app.route("/regen", methods=["POST"])
def regen_sites():
    # Print all parameters
    print(request.args)

    putativeToken = request.args.get("token")
    if not authenticate_token(putativeToken):
        return f"Token Value: {putativeToken} => Invalid token"

    # Get the site that needs to be regenerated
    site = request.args.get("site")
    if not site:
        return "Please provide a site"

    site_file_name = f"./sites/{site}.conf"

    # See if site exists in /sites
    if not os.path.exists(site_file_name):
        return f"Site config file {site} does not exist"

    ips = execute_refresh(f"{site}/json")

    # Truncate and replace sites/SITENAME.conf with the new IPs
    # Each line should be:
    # server <IP>:14041;
    with open(site_file_name, "w") as f:
        for ip in ips:
            f.write(f"server {ip}:14041;\n")

    # Restart nginx
    os.system("sudo nginx -s reload")

    return f"Regenerated {site} with {len(ips)} IPs"


@app.route("/")
def index():
    return "Hello, ItsADash.work!"

@app.route("/justicons_dashboard", methods=["GET"])
def justicons_dashboard():
    return render_justicons_dashboard()


if __name__ == "__main__":
    # Get args from command line for URL
    import sys

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # Exit with an error notifying we need a URL
        print("Please provide a URL")
        sys.exit(1)

    # Execute the refresh
    time1 = time.time()
    execute_refresh(url)
    time2 = time.time()

    print(f"Took {time2-time1:.2f} s")
