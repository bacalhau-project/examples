import glob
import json
import os
import random
import sqlite3
from ast import parse
from datetime import datetime, timezone
from email.mime import image
from pathlib import Path
from re import U
from typing import List, Tuple

import regex as re
import ruamel.yaml as yaml
from dateutil import parser
from flask import Flask, request

tableName = "images"


class DBResponse:
    def __init__(self, message: str, status: int, numberOfImages: int = 0, lastUpdated: datetime = datetime.min):
        self.message = message
        self.status = status
        self.numberOfImages = numberOfImages
        if lastUpdated == datetime.min:
            self.lastUpdated = minDate()
        else:
            self.lastUpdated = lastUpdated

    def __str__(self) -> str:
        return json.dumps(self.__dict__)

    def __repr__(self) -> str:
        return str(self)


class Image:
    def __init__(self, id: str, prompt: str, imageFileName: str, createdAt: datetime):
        self.id = id
        self.prompt = prompt
        self.imageFileName = imageFileName
        self.createdAt = createdAt

    def __str__(self):
        # Return str as a YAML document
        return json.dumps(self.__dict__)

    def __repr__(self):
        return self.__str__()


def dbstats(c: sqlite3.Cursor) -> DBResponse:
    c.execute("SELECT * FROM images")

    rowsQuery = "SELECT Count() FROM %s" % tableName
    c.execute(rowsQuery)
    rawCount = c.fetchone()
    if rawCount[0] == 0:
        return DBResponse(message="No images in database", status=200, numberOfImages=0, lastUpdated=minDate())

    numberOfImages = rawCount[0]

    # Get the date of the newest image from the DB
    newestImageQuery = "SELECT createdAt FROM %s ORDER BY createdAt DESC LIMIT 1" % tableName
    c.execute(newestImageQuery)
    newestImageDate = c.fetchone()[0]

    # Return JSON details about the database
    return DBResponse(message="Database stats", status=200, numberOfImages=numberOfImages, lastUpdated=newestImageDate)


def resetDB(c: sqlite3.Cursor, key: str, imagesDir: str):
    # if key != os.environ.get("SQLITE_KEY") or key is None:
    #     return DBResponse(message="Invalid key", status=401, numberOfImages=-1, lastUpdated=minDate())

    c.execute("DROP TABLE IF EXISTS images")
    c.execute(
        """CREATE TABLE images (
              id TEXT NOT NULL PRIMARY KEY,
prompt TEXT NOT NULL,
imageFileName TEXT NOT NULL,
createdAt DATE NOT NULL)"""
    )

    updateDB(c, imagesDir, None)

    c.connection.commit()

    return dbstats(c)


def updateDB(c: sqlite3.Cursor, imagesDir: str, lastProcessedDate: str):
    ensureImagesTableExists(c=c, imagesDir=imagesDir)

    if lastProcessedDate is None:
        lastProcessedDate = str(minDate())

    # Get list of all files in imagesDir and subdirectories named 'metadata', ordered by modification date
    metadataFiles = filter(os.path.isfile, glob.glob(imagesDir + "/**/metadata", recursive=True))

    try:
        lastProcessedDateParsed = parser.parse(lastProcessedDate)
    except parser.ParserError as e:
        lastProcessedDateParsed = parser.parse(lastProcessedDate, fuzzy=True)

    # Filter metadata files by modification date to be larger than maxDate
    metadataFiles = filter(lambda x: os.path.getmtime(x) > lastProcessedDateParsed.timestamp(), metadataFiles)

    # Walk the images directory and return a list of metadata
    for file in metadataFiles:
        with Path(file).open() as f:
            try:
                # Load metadata from metadata json file
                o = yaml.safe_load(f)
            except:
                # For some reason, the metadata file is not valid YAML - move on
                continue

            stdoutContent = ""
            if "JobState" in o and "Nodes" in o["JobState"]:
                nodes = o["JobState"]["Nodes"]
                for node in nodes:
                    n = nodes[node]
                    if "Shards" in n:
                        for shardIndex in n["Shards"]:
                            s = n["Shards"][shardIndex]
                            if "RunOutput" in s and "stdout" in s["RunOutput"]:
                                # Get the prompt: field from Annotations (if it exists)
                                prompt = "NO-PROMPT-GIVEN"
                                if "Docker" in o["Spec"] and "Entrypoint" in o["Spec"]["Docker"]:
                                    prompt = (
                                        o["Spec"]["Docker"]["Entrypoint"][5]
                                        if len(o["Spec"]["Docker"]["Entrypoint"]) > 5
                                        else "NO-PROMPT-GIVEN"
                                    )

                                # See if the image in the imagesDir / id / image0.png exists
                                imageFileName = "image0.png"
                                id = o["ID"]
                                imageFilePath = Path(imagesDir) / id / imageFileName

                                # See if imageFilePath exists
                                if not imageFilePath.exists():
                                    continue

                                image = Image(
                                    id=id,
                                    prompt=prompt,
                                    imageFileName=imageFileName,
                                    createdAt=parser.parse(o["CreatedAt"]),
                                )
                                upsertImageIntoDB(c, image)

    return dbstats(c)


def getNewestImageFromDB(c: sqlite3.Cursor, imagesDir: str) -> Image:
    ensureImagesTableExists(c, imagesDir=imagesDir)

    c.execute("SELECT * FROM images ORDER BY createdAt DESC LIMIT 1")
    row = c.fetchone()

    image = None
    if row is None:
        image = Image(id="NO-IMAGE", prompt="NO-IMAGE", imageFileName="NO-IMAGE", createdAt=minDate())
    else:
        image = Image(row[0], row[1], row[2], row[3])

    return image


def getOneImageByNumber(c: sqlite3.Cursor, imagesDir: str, imageNumber: str) -> Image:
    ensureImagesTableExists(c, imagesDir=imagesDir)

    # Confirm imageNumber is an int
    try:
        imageNumber = int(imageNumber)
    except ValueError:
        imageNumber = -1

    if imageNumber < 0:
        c.execute("SELECT count(*) FROM images")
        row = c.fetchone()

        # Get a random image from the entire catalog
        imageNumber = random.randint(0, row[0] - 1)
    else:
        # Ensure the image number is an int and is not negative
        imageNumber = int(imageNumber)

    c.execute(
        """SELECT * FROM ( 
            SELECT id, prompt, imageFileName, createdAt, row_number() 
            OVER (ORDER BY createdAt DESC) AS rn 
            FROM images) as imagesWithNumber
            WHERE rn = ?""",
        (imageNumber,),
    )
    row = c.fetchone()

    image = None
    if row is None:
        image = Image(id="NO-IMAGE", prompt="NO-IMAGE", imageFileName="NO-IMAGE", createdAt=minDate())
    else:
        image = Image(row[0], row[1], row[2], row[3])

    return image


def upsertImageIntoDB(c: sqlite3.Cursor, image: Image):
    # Upsert image into image table
    c.execute(
        "INSERT OR REPLACE INTO images (id, prompt, imageFileName, createdAt) VALUES (?, ?, ?, ?)",
        (image.id, image.prompt, image.imageFileName, image.createdAt),
    )
    c.connection.commit()


def ensureImagesTableExists(c: sqlite3.Cursor, imagesDir: str):
    # Test to see if the images table exists, otherwise resetDB
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='images'")
    if c.fetchone() is None:
        resetDB(os.environ.get("SQLITE_KEY"), imagesDir)


def getCursor() -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    conn = sqlite3.connect("website.db")
    return conn, conn.cursor()


def minDate() -> datetime:
    return datetime(1900, 1, 1, 1, 1, 1, 0, tzinfo=timezone.utc).isoformat()
