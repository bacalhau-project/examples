import os
import tempfile
from typing import TextIO
import uuid

import boto3


def download_data(files: [(str, str)]) -> str:
    """
    Downloads the files in S3 and writes them to a new temporary folder
    before returning the path to the folder.
    """
    temp_dir = tempfile.mkdtemp("", "", "/tmp")
    client = boto3.resource("s3")

    for bkt, key in files:
        target = os.path.join(temp_dir, str(uuid.uuid4()))
        client.meta.client.download_file(bkt, key, target)

    return temp_dir


def merge_file(source: str, output_file: TextIO, skip_header: bool):
    first = True
    with open(source, "r") as f:
        for line in f:
            if first and skip_header:
                first = False
                continue

            output_file.write(line)


def merge_files(directory: str, output_file: str):
    """
    Merge all of the files found in 'directory' into a single file
    called 'output_file'.  Takes care of the leading header line
    ensuring the headers are written only once"""

    filenames = [
        os.path.join(directory, filename) for filename in os.listdir(directory)
    ]

    with open(output_file, "w") as f:
        for i in range(0, len(filenames)):
            filename = filenames[i]
            merge_file(filename, f, i > 0)
