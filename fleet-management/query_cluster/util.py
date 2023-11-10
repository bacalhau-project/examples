import os
import tempfile
from typing import TextIO
import json
import sys

import boto3


def download_data(files: [(str, str)]) -> str:
    """
    Downloads the files in S3 and writes them to a new temporary folder
    before returning the path to the folder.
    """
    temp_dir = tempfile.mkdtemp("", "", "/tmp")
    client = boto3.resource("s3")

    for bkt, key in files:
        # Key embeds node ID; it will be of the form
        # run-{date}/{jodID}/{nodeID}/stdout

        # Extract node ID from key to use as target filename
        node_id = key.split("/")[-2]
        target = os.path.join(temp_dir, node_id)
        client.meta.client.download_file(bkt, key, target)

    return temp_dir


def merge_file(source: str, output_file: TextIO, last: bool):
    node_id = os.path.basename(source)
    with open(source, "r") as f:
        # Trim first line, which is a banner from osquery
        f.readline()
        # Load subsequent JSON, which is a list of objects
        records = json.load(f)
        count = len(records)
        for record_id in range(0,count):
            record = records[record_id]
            record['nodeID'] = node_id
            output_file.write(json.dumps(record))
            if not(last) and record_id <= count-1:
                output_file.write(",\n")
            else:
                output_file.write("\n")

def merge_files_to(filenames: [str], f: TextIO):
    f.write("[\n")
    for i in range(0, len(filenames)):
        filename = filenames[i]
        merge_file(filename, f, i == len(filenames)-1)
        first = False
    f.write("]\n")

def merge_files(directory: str, output_file: str):
    """
    Merge all of the files found in 'directory' into a single file
    called 'output_file' (or standard output if output_file is None)."""

    filenames = [
        os.path.join(directory, filename) for filename in os.listdir(directory)
    ]

    if output_file != None:
        with open(output_file, "w") as f:
            merge_files_to(filenames, f)
    else:
        merge_files_to(filenames, sys.stdout)
