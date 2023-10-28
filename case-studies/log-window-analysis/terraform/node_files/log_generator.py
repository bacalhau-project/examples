import json
import time
from datetime import datetime
from random import choice, choices
import uuid
import argparse
import os
from faker import Faker
from pathlib import Path

fake = Faker()


class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.last_entry = datetime.now()
        self.count = 1


active_users = {}


def main(log_directory, appname):
    while True:
        log_entry = generate_log_entry()

        # Load existing log entries
        log_file_path = os.path.join(log_directory, f"{appname}_logs.log")
        try:
            with open(log_file_path, "r") as log_file:
                log_entries = json.load(log_file)
        except (FileNotFoundError, json.JSONDecodeError):
            log_entries = []

        # Append new log entry and write back to the file
        log_entries.append(log_entry)
        with open(log_file_path, "w") as log_file:
            json.dump(log_entries, log_file, indent=2)

        # Sleep for 5 seconds before generating another log entry
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fake log entries and save them to a specified directory.")
    parser.add_argument("-d", "--directory", type=str, required=True, help="The directory to save the log file.")
    parser.add_argument("-n", "--appname", type=str, required=True, help="The application name for the log.")
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    main(args.directory, args.appname)


# Generate a full python function that creates a series of log entries of the format:
# {"timestamp": timestamp, "user_id": user_id_hash (randomly created), "label": label, "page": (randomly selected from a list of pages), "ip": ip}
# It should be tab delimited, and the timestamp should be in UTC time. The unique label will be a parameter
# passed into the function. The log entries should always start with "login" and the last one should be "logout"
# The number of the log entries is random length between 1 and 20, in a power law distribution (i.e. 1/2 of the
# log entries will be 1, 1/4 will be 2, 1/8 will be 3, etc.) The length of time betmeen each log entry should be
# random between 1 and 30 seconds.


def generate_log_entry(label):
    with open(Path(__file__).parent / "clean_words_alpha.txt", "r") as word_file:
        word_list = word_file.read().splitlines()

    log_entries

    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "user_id": str(uuid.uuid4()),
        "label": label,
        "page": choice(word_list),
        "ip": fake.ipv4(),
    }

    return log_entry
