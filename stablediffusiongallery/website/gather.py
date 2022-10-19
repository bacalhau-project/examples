import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import regex as re
import ruamel.yaml as yaml
from dateutil import parser


def GatherMetadata(imagesDir: str, id: str) -> List:
    returnList = []

    return returnList


if __name__ == "__main__":
    # ID Filter
    id = sys.argv[1] if len(sys.argv) > 1 else None

    # First arg is the path to the images directory
    imagesDir = sys.argv[2] if len(sys.argv) > 2 else "/var/www/pintura-cloud/images"

    # Gather metadata
    metadata = GatherMetadata(imagesDir, id)

    print(metadata)
