#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml",
#     "pandas",
#     "numpy",
# ]
# ///

import argparse
import hashlib
import json
import logging
import multiprocessing
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
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

    # If no match, return None to filter out this line
    return None


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

    # Extract path components
    path_components = path.split("/")
    path_depth = len([p for p in path_components if p])

    # Extract file extension if present
    file_extension = ""
    if "." in path.split("/")[-1]:
        file_extension = path.split("/")[-1].split(".")[-1].lower()

    # Parse user agent (if available)
    user_agent = log_data.get("user_agent", "-")
    browser = "unknown"
    os_name = "unknown"
    device_type = "unknown"

    # Simple user agent parsing
    user_agent_lower = user_agent.lower()
    if (
        "mobile" in user_agent_lower
        or "android" in user_agent_lower
        or "iphone" in user_agent_lower
    ):
        device_type = "mobile"
    elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
        device_type = "tablet"
    else:
        device_type = "desktop"

    if "windows" in user_agent_lower:
        os_name = "windows"
    elif "mac" in user_agent_lower or "ios" in user_agent_lower:
        os_name = "apple"
    elif "android" in user_agent_lower:
        os_name = "android"
    elif "linux" in user_agent_lower:
        os_name = "linux"

    if "chrome" in user_agent_lower:
        browser = "chrome"
    elif "firefox" in user_agent_lower:
        browser = "firefox"
    elif "safari" in user_agent_lower and "chrome" not in user_agent_lower:
        browser = "safari"
    elif "edge" in user_agent_lower:
        browser = "edge"
    elif "msie" in user_agent_lower or "trident" in user_agent_lower:
        browser = "ie"

    # Create a unique ID based on the content
    unique_id = hashlib.md5(f"{ip}-{timestamp}-{path}".encode()).hexdigest()

    # Create the document
    document = {
        "id": f"clean-{unique_id}",
        "region": region,
        "timestamp": timestamp_iso,
        "upload_time": datetime.now(timezone.utc).isoformat(),
        "ip": ip,
        "user": log_data.get("user", "-"),
        "method": method,
        "path": path,
        "protocol": protocol,
        "status": int(log_data.get("status", 0)),
        "size": int(log_data.get("size", 0)) if log_data.get("size", "-") != "-" else 0,
        "path_depth": path_depth,
        "file_extension": file_extension,
        "device_type": device_type,
        "os": os_name,
        "browser": browser,
        "hour_of_day": dt.hour if isinstance(dt, datetime) else 0,
        "day_of_week": dt.weekday() if isinstance(dt, datetime) else 0,
        "is_weekend": dt.weekday() >= 5 if isinstance(dt, datetime) else False,
        "is_error": int(log_data.get("status", 0)) >= 400,
        "is_success": 200 <= int(log_data.get("status", 0)) < 300,
        "is_redirect": 300 <= int(log_data.get("status", 0)) < 400,
    }

    # Add referrer if available
    if log_data.get("format") == "combined":
        document["referrer"] = log_data.get("referrer", "-")

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


def clean_and_transform_chunk(chunk: List[str]) -> List[Dict[str, Any]]:
    """Clean and transform a chunk of log lines."""
    # Parse log lines into documents
    documents = []
    for line in chunk:
        try:
            document = parse_log_line(line)
            if document:
                documents.append(document)
        except Exception as e:
            logger.error(f"Error parsing log line: {str(e)}")

    # Convert to DataFrame for easier data manipulation
    if not documents:
        return []

    df = pd.DataFrame(documents)

    # Data cleaning
    # 1. Remove entries with invalid status codes
    df = df[df["status"].between(100, 599)]

    # 2. Remove entries with extremely large sizes (potential errors)
    size_threshold = df["size"].quantile(0.99)  # 99th percentile
    df = df[df["size"] <= size_threshold]

    # 3. Filter out known bot traffic
    bot_patterns = ["bot", "crawler", "spider", "slurp", "baiduspider", "yandex"]
    if "browser" in df.columns:
        for pattern in bot_patterns:
            df = df[~df["browser"].str.contains(pattern, case=False, na=False)]

    # Data transformation
    # 1. Add response time category
    if "size" in df.columns:
        df["response_size_category"] = pd.cut(
            df["size"],
            bins=[0, 1024, 10240, 102400, float("inf")],
            labels=["tiny", "small", "medium", "large"],
        )

    # 2. Add time of day category
    if "hour_of_day" in df.columns:
        df["time_of_day"] = pd.cut(
            df["hour_of_day"],
            bins=[0, 6, 12, 18, 24],
            labels=["night", "morning", "afternoon", "evening"],
        )

    # Convert back to dictionaries
    return df.to_dict("records")


def aggregate_data(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate log data for analytics."""
    if not documents:
        return []

    # Convert to DataFrame
    df = pd.DataFrame(documents)

    # Aggregations to perform
    aggregations = []

    # 1. Traffic by region
    if "region" in df.columns:
        region_counts = df["region"].value_counts().reset_index()
        region_counts.columns = ["region", "count"]
        for _, row in region_counts.iterrows():
            aggregations.append(
                {
                    "id": f"agg-region-{row['region']}-{int(time.time())}",
                    "region": row["region"],
                    "aggregation_type": "region_traffic",
                    "count": int(row["count"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    # 2. Status code distribution
    if "status" in df.columns:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        for _, row in status_counts.iterrows():
            aggregations.append(
                {
                    "id": f"agg-status-{row['status']}-{int(time.time())}",
                    "region": "global",  # Global aggregation
                    "aggregation_type": "status_distribution",
                    "status": int(row["status"]),
                    "count": int(row["count"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    # 3. Traffic by hour of day
    if "hour_of_day" in df.columns:
        hour_counts = df["hour_of_day"].value_counts().reset_index()
        hour_counts.columns = ["hour", "count"]
        for _, row in hour_counts.iterrows():
            aggregations.append(
                {
                    "id": f"agg-hour-{row['hour']}-{int(time.time())}",
                    "region": "global",  # Global aggregation
                    "aggregation_type": "hourly_traffic",
                    "hour": int(row["hour"]),
                    "count": int(row["count"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    # 4. Traffic by browser
    if "browser" in df.columns:
        browser_counts = df["browser"].value_counts().reset_index()
        browser_counts.columns = ["browser", "count"]
        for _, row in browser_counts.iterrows():
            aggregations.append(
                {
                    "id": f"agg-browser-{row['browser']}-{int(time.time())}",
                    "region": "global",  # Global aggregation
                    "aggregation_type": "browser_distribution",
                    "browser": row["browser"],
                    "count": int(row["count"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    # 5. Average response size by path (top 10 paths)
    if "path" in df.columns and "size" in df.columns:
        path_stats = df.groupby("path")["size"].agg(["mean", "count"]).reset_index()
        path_stats = path_stats.sort_values("count", ascending=False).head(10)
        for _, row in path_stats.iterrows():
            aggregations.append(
                {
                    "id": f"agg-path-{hashlib.md5(row['path'].encode()).hexdigest()}-{int(time.time())}",
                    "region": "global",  # Global aggregation
                    "aggregation_type": "path_stats",
                    "path": row["path"],
                    "avg_size": float(row["mean"]),
                    "count": int(row["count"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    return aggregations


def process_chunk(
    chunk: List[str], operations: CosmosDBOperations, batch_size: int
) -> Tuple[int, float]:
    """Process a chunk of log lines, clean, transform, and upload to Cosmos DB."""
    start_time = time.time()

    # Clean and transform the data
    cleaned_documents = clean_and_transform_chunk(chunk)

    # Create aggregations
    aggregated_documents = aggregate_data(cleaned_documents)

    # Combine all documents
    all_documents = cleaned_documents + aggregated_documents

    # Upload documents in batches
    success_count, ru_consumed = operations.bulk_create(all_documents, batch_size)

    end_time = time.time()
    duration = end_time - start_time
    rate = len(all_documents) / duration if duration > 0 else 0

    logger.info(
        f"Processed {len(chunk)} log lines into {len(cleaned_documents)} cleaned documents "
        f"and {len(aggregated_documents)} aggregations in {duration:.2f}s ({rate:.2f} docs/s)"
    )
    logger.info(
        f"Successfully uploaded {success_count} documents, consumed {ru_consumed:.2f} RUs"
    )

    return success_count, ru_consumed


def process_log_file(
    file_path: str, config_path: str, chunk_size: int, batch_size: int, max_workers: int
) -> Tuple[int, float]:
    """Process a log file, clean, transform, and upload to Cosmos DB."""
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
        description="Process, clean, transform log files and upload to Cosmos DB"
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
