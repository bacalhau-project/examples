import imp
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import db


def GatherMetadata(c: sqlite3.Cursor, max: int = 100) -> List[db.Image]:
    returnList = []

    c.execute(
        "SELECT * FROM images ORDER BY createdAt DESC LIMIT ?",
        (max,),
    )
    for row in c.fetchall():
        returnList.append(db.Image(id=row[0], prompt=row[1], imageFileName=row[2], createdAt=row[3]))

    return returnList


if __name__ == "__main__":
    # ID Filter
    id = sys.argv[1] if len(sys.argv) > 1 else None

    # First arg is the path to the images directory
    imagesDir = sys.argv[2] if len(sys.argv) > 2 else "/var/www/pintura-cloud/images"

    # Gather metadata
    metadata = GatherMetadata(imagesDir)

    print(metadata)
