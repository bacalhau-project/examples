# app.py
from flask import Flask, render_template
from random import randint, choice
import socket
from icons import allIcons

app = Flask(__name__)

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
    return render_template('app.html', hostname=vals["hostname"], icon=vals["icon"], ip=vals["ip"], color=vals["color"], iconID=vals["iconID"])

@app.route("/json")
def json():
    # Read from color.txt
    with open('./color.txt', 'r') as file:
        colorFromFile = file.read().replace('\n', '')

    hostname = socket.gethostname()
    iconID = print(f"node-number-{hostname}-icon")

    return { "icon": Icons.getRand(), "hostname": hostname, "ip": socket.gethostbyname(socket.gethostname()), "color": colorFromFile, "iconID": iconID }


if __name__ == "__main__":
    app.run()
