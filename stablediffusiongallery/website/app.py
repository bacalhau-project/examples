import json
import os
from email.policy import default
from pathlib import Path

import db
import gather
import jsonpickle
from flask import Flask, abort, render_template, request

app = Flask(__name__)

trusted_ips = ["127.0.0.1", "localhost"]
defaultImagesDir = "/var/www/pintura-cloud/images"


@app.route("/")
def index():
    imagesDir = os.environ.get("IMAGES_DIR", defaultImagesDir)
    id = ""
    metadataStore = gather.GatherMetadata(imagesDir, id)
    print("\n\n\n" + os.getcwd() + "\n\n\n")
    return render_template("index.html", images=metadataStore)


@app.route("/catalog", methods=["GET"])
def catalog():
    imagesDir = os.environ.get("IMAGES_DIR", defaultImagesDir)

    id = ""
    if "id" in request.args:
        id = request.args["id"]

    metadataStore = gather.GatherMetadata(imagesDir, id)

    return metadataStore


@app.route("/dbstats")
def dbstats():
    try:
        conn, c = db.getCursor()
        return jsonpickle.encode(db.dbstats(c))
    finally:
        conn.close()


@app.route("/resetdb", methods=["GET"])
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


def localIPonly():
    remote = request.remote_addr
    if remote not in trusted_ips:
        abort(403)  # Forbidden


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
