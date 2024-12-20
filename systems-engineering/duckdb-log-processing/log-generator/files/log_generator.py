import argparse
import fcntl
import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from random import choice, choices

from faker import Faker

fake = Faker()


def generate_log_entry():
    service_names = ["Auth", "AppStack", "Database"]
    categories = ["[INFO]", "[WARN]", "[CRITICAL]", "[SECURITY]"]

    with open(Path(__file__).parent / "clean_words_alpha.txt", "r") as word_file:
        word_list = word_file.read().splitlines()

    log_entry = {
        "id": str(uuid.uuid4()),
        "@timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "@version": "1.1",
        "message": f"{choice(service_names)} {choice(categories)} {' '.join(choices(word_list, k=5))}",
    }

    return log_entry


def atomic_write_json(file_path, data):
    """Write JSON data atomically using a temporary file and file locking."""
    # Create a temporary file in the same directory
    temp_path = f"{file_path}.tmp"
    
    try:
        # Write to temporary file
        with open(temp_path, 'w') as temp_file:
            # Get an exclusive lock
            fcntl.flock(temp_file.fileno(), fcntl.LOCK_EX)
            json.dump(data, temp_file, indent=2)
            # Ensure all data is written to disk
            temp_file.flush()
            os.fsync(temp_file.fileno())
            
        # Atomic rename
        os.rename(temp_path, file_path)
        
    except Exception as e:
        # Clean up temp file if something goes wrong
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


def main(log_directory, appname):
    while True:
        log_entry = generate_log_entry()
        log_file_path = os.path.join(log_directory, f"{appname}_logs.log")

        try:
            # Read existing entries with file locking
            try:
                with open(log_file_path, "r") as log_file:
                    fcntl.flock(log_file.fileno(), fcntl.LOCK_SH)
                    log_entries = json.load(log_file)
            except (FileNotFoundError, json.JSONDecodeError):
                log_entries = []

            # Append new entry
            log_entries.append(log_entry)
            
            # Write atomically
            atomic_write_json(log_file_path, log_entries)

        except Exception as e:
            print(f"Error writing to log file: {e}")
            continue

        # Sleep for 5 seconds before generating another log entry
        # time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fake log entries and save them to a specified directory.")
    parser.add_argument("-d", "--directory", type=str, required=True, help="The directory to save the log file.")
    parser.add_argument("-n", "--appname", type=str, required=True, help="The application name for the log.")
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    main(args.directory, args.appname)
