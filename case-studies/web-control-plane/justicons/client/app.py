# app.py
import random
import socket
from pathlib import Path
from random import randint

from flask import Flask, render_template
from flask_cors import CORS

from icons import allIcons

app = Flask(__name__)
CORS(app)


def loadIcons():
    return allIcons


class Icons:
    # Load all icons from icons.txt which has one icon per line, surrounded by single quotes
    allIcons = loadIcons()

    @staticmethod
    def getRand():
        return Icons.allIcons[randint(0, len(Icons.allIcons))]

    @staticmethod
    def get(i):
        Icons.allIcons[i % len(Icons.allIcons)]


@app.route("/")
def index():
    vals = json()
    return render_template(
        "app.html",
        hostname=vals["hostname"],
        icon=vals["icon"],
        ip=vals["ip"],
        color=vals["color"],
        iconID=vals["iconID"],
        hashCode=vals["hashCode"],
        zone=vals["zone"],
        region=vals["region"],
    )


@app.route("/json-test")
def json_testing():
    return json(testing=True)


@app.route("/json")
def json(testing):
    if testing:
        testNode = test_node()
        ip = testNode["ip"]
        hostname = testNode["hostname"]
        zone = testNode["zone"]
        region = testNode["region"]
    else:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(socket.gethostname())
        node_info = Path("/etc/bacalhau-node-info")
        zone = "N/A"
        region = "N/A"
        if node_info.exists():
            # Read from /etc/bacalhau-node-info and get ZONE= and REGION=
            with open(node_info, "r") as file:
                lines = file.readlines()
                for line in lines:
                    if "ZONE=" in line:
                        zone = line.split("=")[1].replace("\n", "")
                    if "REGION=" in line:
                        region = line.split("=")[1].replace("\n", "")

    with open("./color.txt", "r") as file:
        colorFromFile = file.read().replace("\n", "")

    iconID = f"node-number-{hostname}-icon"
    hashCodeValue = generateHashCode(hostname)

    return generate_node(
        icon=Icons.getRand(),
        hostname=hostname,
        ip=ip,
        color=colorFromFile,
        iconID=iconID,
        hashCode=hashCodeValue,
        zone=zone,
        region=region,
    )


def generateHashCode(str):
    hash_value = 0
    for char in str:
        hash_value = (hash_value << 5) - hash_value + ord(char)

    # Convert hash to a positive integer (assuming hash is signed)
    hash_int = hash_value & 0xFFFFFFFF
    # Convert integer to base 36 string
    base36_string = base36_encode(hash_int)
    # Pad the string to have at least 7 characters with leading zeros
    padded_string = base36_string.zfill(7)
    return padded_string


def base36_encode(integer):
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    base36 = ""
    sign = ""
    if integer < 0:
        sign = "-"
        integer = -integer
    while integer != 0:
        integer, i = divmod(integer, 36)
        base36 = alphabet[i] + base36
    return sign + base36 if sign else base36


def test_node():
    n = random.choice(TEST_NODES_STATICS)
    return {"ip": n[0], "hostname": n[1], "region": n[2], "zone": n[3]}


def generate_node(icon, hostname, ip, color, iconID, hashCode, zone, region):
    return {
        "icon": icon,
        "hostname": hostname,
        "ip": ip,
        "color": color,
        "iconID": iconID,
        "hashCode": hashCode,
        "zone": zone,
        "region": region,
    }


TEST_NODES_STATICS = (
    ["256.256.256.1", "silva-odonnell.net", "us-west1", "us-west1-a"],
    ["256.256.256.2", "campbell.org", "us-west1", "us-west1-a"],
    ["256.256.256.3", "archer-patel.org", "us-west1", "us-west1-b"],
    ["256.256.256.4", "collins.com", "us-west1", "us-west1-b"],
    ["256.256.256.5", "rivera.com", "us-east1", "us-east1-a"],
    ["256.256.256.6", "bowman.info", "us-east1", "us-east1-a"],
    ["256.256.256.7", "green.com", "us-east1", "us-east1-b"],
    ["256.256.256.8", "turner.com", "us-east1", "us-east1-b"],
    ["256.256.256.9", "cortez.com", "eu-west1", "eu-west1-a"],
    ["256.256.256.10", "snyder.com", "eu-west1", "eu-west1-a"],
    ["256.256.256.11", "harrell.com", "eu-west1", "eu-west1-b"],
    ["256.256.256.12", "mclean.net", "eu-west1", "eu-west1-b"],
)


if __name__ == "__main__":
    # Take a port number from the environment if it's there
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(port=port)
