import json
import time
import datetime
from datetime import datetime as dt
from random import choice, choices
import uuid
import argparse
import os
from faker import Faker
from pathlib import Path
import numpy as np
import sys


def parse_line(line, line_tuples):
    try:
        datetimestamp = dt.strptime(
            line.split("[")[1].split("]")[0], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        line_tuples.append((datetimestamp, line.strip("\n")))

    except Exception as e:
        print(f"Error parsing line: {line}")
        print(e)
        return


def main(log_directory, appname):
    # If /node/sample_access.log doesn't exist, run the generate_sample_logs.py script
    if not os.path.exists("/node/sample_access.log"):
        os.system(f"{sys.executable} /node/generate_sample_logs.py")

    with open("/node/sample_access.log", "r") as sample_log_file:
        lines = sample_log_file.readlines()
        line_tuples = []
        for line in lines:
            cols = line.split(sep=" ")
            num_cols = len(cols)

            if num_cols == 9:
                parse_line(line, line_tuples)
            elif num_cols == 18:
                parse_line(" ".join(cols[:9]), line_tuples)
                parse_line(" ".join(cols[9:]), line_tuples)
            else:
                continue

        full_array = np.array(line_tuples)
        full_array = np.array(sorted(full_array, key=lambda x: x[0]))

    # Load existing log entries
    log_file_path = os.path.join(log_directory, f"{appname}_access_logs.log")
    last_printed_time = full_array[0][0]

    # Adding 4 hours so we get a bunch of logs right now.
    last_real_time = dt.now(last_printed_time.tzinfo) - datetime.timedelta(hours=4)

    # In a loop, every second, print out the set number of log entries since the last second
    while True:
        # Get the current time
        current_real_time = dt.now(last_printed_time.tzinfo)
        real_time_diff = current_real_time - last_real_time
        end_time = last_printed_time + real_time_diff

        # Get the log entries since the last time we printed
        log_entries_to_print = full_array[
            (full_array[:, 0] > last_printed_time) & (full_array[:, 0] <= end_time)
        ]

        log_entries_string = "\n".join(log_entries_to_print[:, 1])
        with open(log_file_path, "a") as filehandle:
            if log_entries_string:
                filehandle.write(log_entries_string)
                filehandle.write("\n")

        last_printed_time = end_time
        last_real_time = current_real_time

        # If the last printed time is bigger than the last in full_array, set last_printed_time to the first in full_array
        if last_printed_time >= full_array[-1][0]:
            last_printed_time = full_array[0][0]

        # Sleep for 1 second
        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate fake log entries and save them to a specified directory."
    )
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        nargs="?",
        help="The directory to save the log file.",
        default=".",
    )
    parser.add_argument(
        "-n",
        "--appname",
        type=str,
        nargs="?",
        help="The application name for the log.",
        default="aperitivo",
    )
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    main(args.directory, args.appname)
