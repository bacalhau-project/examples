'''aggregate.py – aggregate data in flight trackers into a pipe-delimited
database file.

Requirements:
* take data from a flight tracker TSV and compute aggregated statistics per route
* append aggregate statistics into a pipe-delimited text file
'''

import os
import os.path
import csv
import sys

def analyse(filename: str) -> str:
    with open(filename, 'r', encoding='utf-8') as f:
        max_mph = 0
        max_alt = 0

        for record in csv.DictReader(f, delimiter="\t"):
            mph = record["mph "].replace(",", "")
            if mph != "":
                max_mph = max(max_mph, int(mph))
            alt = record["meters "].replace(",", "")
            if alt != "":
                max_alt = max(max_alt, int(alt))

    flight_id, rest = os.path.split(filename)
    assert type(flight_id) is str
    assert type(rest) is str

    _, flight_id = os.path.split(flight_id)
    date, _ = os.path.splitext(rest.split("_")[-1])

    data = (str(x) for x in [flight_id, date, max_mph, max_alt])
    return "|".join(data)

def relative_files(src: str):
    for root, _, files in os.walk(src):
        for file in files:
            yield os.path.join(root, file)

OutputFilename = sys.argv.pop()
InputDirectory = sys.argv.pop()

OutputThreshold: float
'''Any input files modified before this time are ignored.'''

if os.path.exists(OutputFilename):
    OutputThreshold = os.stat(OutputFilename).st_mtime
else:
    OutputThreshold = 0

with open(OutputFilename, 'a') as output:
    for filename in relative_files(InputDirectory):
        if os.stat(filename).st_mtime < OutputThreshold:
            print("Should already have processed file", filename, file=sys.stderr)
            continue

        name, ext = os.path.splitext(filename)
        if ext != '.tsv':
            print("Not a TSV file", filename, file=sys.stderr)
            continue

        print("Analysing", filename, file=sys.stdout)
        print(analyse(filename), file=output)
