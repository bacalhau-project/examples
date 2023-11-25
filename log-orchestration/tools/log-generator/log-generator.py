import json
import re
from datetime import datetime, timezone
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import argparse
import asyncio

"""
Script to simulate log generation. It reads logs from hourly-separated
log files and produces logs in JSON format at a user-defined rate. The datetime in the logs
is replaced with the current datetime in UTC.

Usage:
    python log_generator.py --rate=2 --input-log-directory="./logs" --output-log-file="./output/generated_logs.log"
"""

# Regular expression to parse the Nginx log line
log_pattern = re.compile(
    r'(?P<remote_addr>\S+) '  # Remote address
    r'\S+ '  # Ignoring ident
    r'(?P<remote_user>\S+) '  # Remote user
    r'\[(?P<time_local>.*?)\] '  # Local time
    r'"(?P<http_method>\S+) '  # HTTP method
    r'(?P<request>[^\s"]+) '  # Request path
    r'(?P<http_version>HTTP/\S+)" '  # HTTP version
    r'(?P<status>\d{3}) '  # Status
    r'(?P<body_bytes_sent>\S+) '  # Body bytes sent
    r'"(?P<http_referer>.*?)" '  # HTTP referer
    r'"(?P<http_user_agent>.*?)"'  # User agent
)


async def main(args):
    rate = args.rate
    source_directory = args.input_log_directory
    output_file_path = args.output_log_file
    await generate_logs(rate, source_directory, output_file_path)


async def generate_logs(rate, source_directory, output_file_path):
    # Initialize logging with TimedRotatingFileHandler to handle file rotation
    logger = logging.getLogger("LogGenerator")
    logger.setLevel(logging.INFO)

    handler = TimedRotatingFileHandler(output_file_path, when="H", backupCount=3, utc=True)
    logger.addHandler(handler)

    # Infinite loop to continuously generate logs
    while True:
        current_hour = datetime.now(timezone.utc).hour
        file_name = os.path.join(source_directory, f"access_hour_{current_hour:02}.log")

        # Use 'with' to ensure the file is properly closed after reading
        with open(file_name, "r") as f:
            # Read and publish each line from the current log file
            for line in f:
                await asyncio.sleep(1 / rate)
                json_log = log_to_json(line)
                logger.info(json_log)


def log_to_json(log_line):
    match = log_pattern.match(log_line)
    if not match:
        print(f"Log line does not match pattern: {log_line}")
        return None
    log_data = match.groupdict()
    # Replace time_local with current time in UTC
    log_data["time_local"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    # Convert status and body_bytes_sent to integers
    log_data['status'] = int(log_data['status'])
    if log_data['body_bytes_sent'].isdigit():
        log_data['body_bytes_sent'] = int(log_data['body_bytes_sent'])
    else:
        log_data['body_bytes_sent'] = 0  # Handle non-numeric values like '-'
    return json.dumps(log_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Log Generator based on pre-existing log files.')
    parser.add_argument('--rate', type=float, required=True, help='Rate of log generation per second')
    parser.add_argument('--input-log-directory', type=str, required=True, help='Directory containing source log files segmented by hour')
    parser.add_argument('--output-log-file', type=str, required=True, help='Full path to the destination log file')
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("Log generation stopped by user.")

