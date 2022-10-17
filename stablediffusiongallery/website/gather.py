import json
import os
from typing import List


def GatherMetadata() -> List:
    returnList = []

    # Walk the images directory and return a list of metadata
    for root, dirs, files in os.walk("/var/www/pintura-cloud/images"):
        # If file is metadata, add to list
        for file in files:
            if file.name == "metadata":
                # Load metadata from metadata json file
                json.load(file)
