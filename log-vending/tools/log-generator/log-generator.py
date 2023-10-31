from datetime import datetime, timezone
import time
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import argparse
import asyncio

"""
Script to simulate log generation. It reads logs from hourly-separated
log files and produces logs at a user-defined rate. The datetime in the logs
is replaced with the current datetime in UTC.

Usage:
    python log_generator.py --rate=2 --input-log-directory="./logs" --output-log-file="./output/generated_logs.log"
"""


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
                current_time = datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S %z")
                updated_line = line.replace(line.split('[')[1].split(']')[0], current_time)
                logger.info(updated_line.strip())


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

