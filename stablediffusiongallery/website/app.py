import json
import os
from email.policy import default
from logging.config import valid_ident
from pathlib import Path
from threading import local
from typing import final

import db
import gather
import jsonpickle
from flask import Flask, abort, render_template, request, send_file

app = Flask(__name__)

trusted_ips = ["127.0.0.1", "localhost"]
defaultImagesDir = "/var/www/pintura-cloud/images"


@app.route("/")
def index():
    id = ""
    try:
        conn, c = db.getCursor()
        metadataStore = gather.GatherMetadata(c)
        return render_template("index.html", images=metadataStore)
    finally:
        conn.close()


@app.route("/catalog", methods=["GET"])
def catalog():
    try:
        conn, c = db.getCursor()
        metadataStore = gather.GatherMetadata(c)
        return jsonpickle.encode(metadataStore)
    finally:
        conn.close()


@app.route("/dbstats")
def dbstats():
    try:
        conn, c = db.getCursor()
        return jsonpickle.encode(db.dbstats(c))
    finally:
        conn.close()


@app.route("/resetDB", methods=["POST"])
def resetDB():
    localIPonly()

    try:
        conn, c = db.getCursor()
        key = request.args["key"] if "key" in request.args else None
        imagesDir = os.environ.get("IMAGES_DIR", defaultImagesDir)
        dbStats = db.resetDB(c, key, imagesDir)
        if dbStats.status != 200:
            abort(dbStats.status)
        return jsonpickle.encode(dbStats)
    finally:
        conn.close()


@app.route("/updateDB", methods=["GET"])
def updateDB():
    localIPonly()

    try:
        conn, c = db.getCursor()
        key = request.args["key"] if "key" in request.args else None
        imagesDir = os.environ.get("IMAGES_DIR", defaultImagesDir)

        i = db.getNewestImageFromDB(c, imagesDir)
        lastProcessedDate = i.createdAt if i else None

        dbStats = db.updateDB(c, imagesDir, lastProcessedDate=lastProcessedDate)
        if dbStats.status != 200:
            abort(dbStats.status)
        return jsonpickle.encode(dbStats)
    finally:
        conn.close()


@app.route("/images/<id>/<imageFileName>", methods=["GET", "POST"])
def image(id, imageFileName):
    print(id)
    print(imageFileName)
    return send_file(f"./images/{id}/{imageFileName}")


@app.route("/varz")
def varz():
    localIPonly()
    
    
    return "<pre>" + jsonpickle.encode(os.environ) + "</pre>"


def localIPonly():
    remote = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
    if remote not in trusted_ips:
        abort(403, {"message": f"Unauthorized access from {request.environ}"})  # Forbidden


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
