import json
import time
from datetime import datetime
from random import choice, choices
import uuid
import argparse
import os
from faker import Faker

fake = Faker()

def generate_log_entry():
    service_names = ["Auth", "AppStack", "Database"]
    categories = ["[INFO]", "[WARN]", "[CRITICAL]", "[SECURITY]"]

    with open("clean_words_alpha.txt", "r") as word_file:
        word_list = word_file.read().splitlines()

    log_entry = {
        "id": str(uuid.uuid4()),
        "@timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "@version": "1.1",
        "message": f"{choice(service_names)} {choice(categories)} {' '.join(choices(word_list, k=5))}",
    }

    return log_entry

def main(log_directory):
    while True:
        log_entry = generate_log_entry()
        
        # Load existing log entries
        log_file_path = os.path.join(log_directory, "fake_logs.log")
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
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    main(args.directory)
