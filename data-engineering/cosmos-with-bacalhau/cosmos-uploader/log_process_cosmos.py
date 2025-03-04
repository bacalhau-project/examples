#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml",
# ]
# ///

import argparse
import json
import logging
import multiprocessing
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import yaml
from azure.cosmos import exceptions
from cosmos_basic_operations import CosmosDBOperations
from cosmos_connection import CosmosDBConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global configuration
DEBUG = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
CONNECTION_TIMEOUT = int(
    os.environ.get("CONNECTION_TIMEOUT", "120")
)  # seconds - timeout for operations
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500000"))  # lines per chunk
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1000"))  # documents per batch
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))  # max worker threads


# Common log format pattern
# Example: 127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326
COMMON_LOG_FORMAT_PATTERN = r'(?P<ip>\S+) (?P<identd>\S+) (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d+) (?P<size>\S+)'
common_log_format_regex = re.compile(COMMON_LOG_FORMAT_PATTERN)

# Combined log format pattern (Common + referrer and user agent)
# Example: 127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/start.html" "Mozilla/4.08 [en] (Win98; I ;Nav)"
COMBINED_LOG_FORMAT_PATTERN = r'(?P<ip>\S+) (?P<identd>\S+) (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d+) (?P<size>\S+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
combined_log_format_regex = re.compile(COMBINED_LOG_FORMAT_PATTERN)


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a log line into a structured document."""
    # Try combined format first
    match = combined_log_format_regex.match(line)
    if match:
        log_data = match.groupdict()
        log_data["format"] = "combined"
        return process_log_data(log_data, line)

    # Try common format
    match = common_log_format_regex.match(line)
    if match:
        log_data = match.groupdict()
        log_data["format"] = "common"
        return process_log_data(log_data, line)

    # If no match, return a basic document with the raw line
    return {
        "id": f"log-{int(time.time())}-{hash(line) & 0xFFFFFFFF}",
        "region": "unknown",
        "raw_line": line,
        "parsed": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "upload_time": datetime.now(timezone.utc).isoformat(),
    }


def process_log_data(log_data: Dict[str, Any], raw_line: str) -> Dict[str, Any]:
    """Process and enrich log data."""
    # Parse the request
    request_parts = log_data.get("request", "").split()
    method = path = protocol = ""
    if len(request_parts) >= 1:
        method = request_parts[0]
    if len(request_parts) >= 2:
        path = request_parts[1]
    if len(request_parts) >= 3:
        protocol = request_parts[2]

    # Parse the timestamp
    timestamp = log_data.get("timestamp", "")
    try:
        # Example format: 10/Oct/2000:13:55:36 -0700
        dt = datetime.strptime(timestamp.split()[0], "%d/%b/%Y:%H:%M:%S")
        timestamp_iso = dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        timestamp_iso = datetime.now(timezone.utc).isoformat()

    # Determine region based on IP (simplified for demo)
    ip = log_data.get("ip", "")
    region = "unknown"
    if ip.startswith("10."):
        region = "internal"
    elif ip.startswith("192.168."):
        region = "local"
    else:
        # For demo purposes, assign regions based on the last octet
        last_octet = int(ip.split(".")[-1]) if "." in ip else 0
        regions = [
            "East US",
            "West US",
            "North Europe",
            "Southeast Asia",
            "Australia East",
        ]
        region = regions[last_octet % len(regions)]

    # Create the document
    document = {
        "id": f"log-{int(time.time())}-{hash(raw_line) & 0xFFFFFFFF}",
        "region": region,
        "raw_line": raw_line,
        "parsed": True,
        "timestamp": timestamp_iso,
        "upload_time": datetime.now(timezone.utc).isoformat(),
        "ip": ip,
        "user": log_data.get("user", "-"),
        "method": method,
        "path": path,
        "protocol": protocol,
        "status": int(log_data.get("status", 0)),
        "size": int(log_data.get("size", 0)) if log_data.get("size", "-") != "-" else 0,
    }

    # Add referrer and user agent if available (combined format)
    if log_data.get("format") == "combined":
        document["referrer"] = log_data.get("referrer", "-")
        document["user_agent"] = log_data.get("user_agent", "-")

    return document


def read_log_file_in_chunks(file_path: str, chunk_size: int) -> List[List[str]]:
    """Read a log file in chunks."""
    chunks = []
    current_chunk = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if line:  # Skip empty lines
                    current_chunk.append(line)

                if len(current_chunk) >= chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = []

            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append(current_chunk)

        logger.info(
            f"Read {sum(len(chunk) for chunk in chunks)} lines from {file_path} in {len(chunks)} chunks"
        )
        return chunks
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        raise


def process_chunk(
    chunk: List[str], operations: CosmosDBOperations, batch_size: int
) -> Tuple[int, float]:
    """Process a chunk of log lines and upload to Cosmos DB."""
    start_time = time.time()

    # Parse log lines into documents
    documents = []
    for line in chunk:
        try:
            document = parse_log_line(line)
            if document:
                documents.append(document)
        except Exception as e:
            logger.error(f"Error parsing log line: {str(e)}")

    # Upload documents in batches
    success_count, ru_consumed = operations.bulk_create(documents, batch_size)

    end_time = time.time()
    duration = end_time - start_time
    rate = len(documents) / duration if duration > 0 else 0

    logger.info(
        f"Processed {len(documents)} documents in {duration:.2f}s ({rate:.2f} docs/s)"
    )
    logger.info(
        f"Successfully uploaded {success_count} documents, consumed {ru_consumed:.2f} RUs"
    )

    return success_count, ru_consumed


def process_log_file(
    file_path: str, config_path: str, chunk_size: int, batch_size: int, max_workers: int
) -> Tuple[int, float]:
    """Process a log file and upload to Cosmos DB."""
    start_time = time.time()

    # Initialize Cosmos DB connection
    cosmos_connection = CosmosDBConnection(config_path)
    operations = CosmosDBOperations(cosmos_connection)

    # Read log file in chunks
    chunks = read_log_file_in_chunks(file_path, chunk_size)

    # Process chunks in parallel
    total_success = 0
    total_ru_consumed = 0.0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_chunk, chunk, operations, batch_size)
            for chunk in chunks
        ]

        for future in as_completed(futures):
            try:
                success_count, ru_consumed = future.result()
                total_success += success_count
                total_ru_consumed += ru_consumed
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")

    end_time = time.time()
    total_duration = end_time - start_time
    total_rate = total_success / total_duration if total_duration > 0 else 0

    logger.info(
        f"Total processing completed: {total_success} documents uploaded in {total_duration:.2f}s "
        f"({total_rate:.2f} docs/s), consumed {total_ru_consumed:.2f} RUs"
    )

    return total_success, total_ru_consumed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process log files and upload to Cosmos DB"
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Path to the configuration file",
        default=os.environ.get("CONFIG_PATH"),
    )
    parser.add_argument(
        "--input",
        dest="input_file",
        help="Path to the input log file",
        default=os.environ.get("INPUT_FILE"),
    )
    parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        type=int,
        help="Number of lines to process in each chunk",
        default=CHUNK_SIZE,
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        help="Number of documents in each batch",
        default=BATCH_SIZE,
    )
    parser.add_argument(
        "--max-workers",
        dest="max_workers",
        type=int,
        help="Maximum number of worker threads",
        default=MAX_WORKERS,
    )

    args = parser.parse_args()

    if not args.config_path:
        logger.error("Configuration path is required")
        return 1

    if not args.input_file:
        logger.error("Input file path is required")
        return 1

    try:
        total_success, total_ru_consumed = process_log_file(
            args.input_file,
            args.config_path,
            args.chunk_size,
            args.batch_size,
            args.max_workers,
        )

        logger.info(
            f"Summary: {total_success} documents uploaded, {total_ru_consumed:.2f} RUs consumed"
        )
        return 0
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
