#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "pandas",
#     "psycopg2-binary",
#     "pyyaml",
#     "faker",
#     "ipaddress",
# ]
# ///

import argparse
import ipaddress
import logging
import os
import random
import re
import socket
import time
import warnings
from datetime import UTC, datetime
from typing import Any, Callable

import duckdb
import pandas as pd
import psycopg2
import yaml
from faker import Faker
from psycopg2.extras import execute_values

# Initialize Faker
fake = Faker()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress numpy deprecation warning from DuckDB
warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core")

# Retry configuration
MAX_RETRIES = 20  # seconds
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 60  # seconds
RETRY_MULTIPLIER = 2
JITTER_FACTOR = 0.1


def with_retries(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to add retry logic with exponential backoff and jitter."""

    def wrapper(*args, **kwargs):
        retry_count = 0
        delay = INITIAL_RETRY_DELAY

        while True:
            try:
                return func(*args, **kwargs)
            except psycopg2.OperationalError as e:
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    logger.error(f"Max retries ({MAX_RETRIES}) exceeded: {str(e)}")
                    raise

                # Add jitter to avoid thundering herd
                jitter = random.uniform(-JITTER_FACTOR * delay, JITTER_FACTOR * delay)
                sleep_time = delay + jitter

                logger.warning(
                    f"Database connection error. Retrying in {sleep_time:.2f} seconds "
                    f"(attempt {retry_count}/{MAX_RETRIES})"
                )

                time.sleep(sleep_time)
                delay = min(delay * RETRY_MULTIPLIER, MAX_RETRY_DELAY)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise

    return wrapper


@with_retries
def upload_to_postgres(conn: psycopg2.extensions.connection, df: pd.DataFrame) -> None:
    """Upload dataframe to PostgreSQL with retry logic."""
    with conn.cursor() as cur:
        # Convert DataFrame to list of tuples
        values = [tuple(x) for x in df.to_numpy()]

        # Generate the INSERT query
        columns = df.columns.tolist()
        query = f"""
            INSERT INTO log_analytics.log_results (
                {", ".join(columns)}
            ) VALUES %s
        """

        # Execute the insert
        execute_values(cur, query, values)
        conn.commit()


def read_config(config_path: str) -> dict:
    """Read configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Validate required fields
    if "postgresql" not in config:
        raise ValueError("Missing 'postgresql' section in config")

    required_fields = ["host", "port", "user", "password", "database"]
    missing = [f for f in required_fields if f not in config["postgresql"]]
    if missing:
        raise ValueError(f"Missing required PostgreSQL fields: {', '.join(missing)}")

    return config["postgresql"]


def get_metadata():
    """Get metadata about the current environment/node."""
    return {
        "project_id": os.environ.get("PROJECT_ID", "unknown"),
        "region": os.environ.get("REGION", "unknown"),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "provider": os.environ.get("CLOUD_PROVIDER", "unknown"),
        "hostname": socket.gethostname(),
    }


def get_status_category(status):
    """Categorize HTTP status code."""
    if 200 <= status <= 299:
        return "OK"
    elif 300 <= status <= 399:
        return "Redirect"
    elif 400 <= status <= 499:
        return "Not Found"
    elif 500 <= status <= 599:
        return "SystemError"
    return "Unknown"


def main(config_path: str = None, input_file: str = None) -> None:
    """
    Main processing function. Prefers environment variables over passed arguments.
    """
    # Get config path from environment or argument
    config_path = (
        os.environ.get("CONFIG_PATH", config_path) or "/var/log/app/config.yaml"
    )
    if not os.path.exists(config_path):
        raise ValueError(f"Config file not found at {config_path}")

    # Get input file from environment or argument
    input_file = os.environ.get("INPUT_FILE", input_file)
    if not input_file:
        raise ValueError(
            "Input file must be provided via INPUT_FILE environment variable or --input-file argument"
        )

    # Get node ID from environment
    node_id = os.environ.get("NODE_ID", "unknown")
    logger.info(f"Starting processing on node {node_id}")

    try:
        # Read configuration
        config = read_config(config_path)
        pg_config = config["postgresql"]

        # Get chunk size from environment or use default
        chunk_size = int(os.environ.get("CHUNK_SIZE", "10000"))

        # Create PostgreSQL connection
        conn = psycopg2.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"],
            sslmode="require",
        )

        # Create DuckDB connection
        con = duckdb.connect()

        # Get metadata once
        metadata = get_metadata()
        total_rows = 0
        chunk_num = 0
        failed_chunks = []

        # Pre-create categorical values for status
        status_categories = ["Unknown", "OK", "Redirect", "Not Found", "SystemError"]

        # Process in chunks
        while True:
            try:
                # Load raw data with minimal processing in SQL
                df = con.execute(
                    """
                    SELECT 
                        column0 as ip,
                        column2 as user_id,
                        column3 as ts_raw,
                        column4 as request,
                        column5::INTEGER as status,
                        column6::INTEGER as bytes,
                        column7 as referer,
                        column8 as user_agent
                    FROM read_csv_auto(?, delim=' ', SAMPLE_SIZE=1000)
                    LIMIT ? OFFSET ?
                    """,
                    [input_file, chunk_size, chunk_num * chunk_size],
                ).df()

                # Break if no more data
                if len(df) == 0:
                    break

                # Process timestamp (vectorized)
                df["timestamp"] = pd.to_datetime(
                    df["ts_raw"].str.strip("[]"),
                    format="%Y-%m-%dT%H:%M:%S.%f%z",
                    utc=True,
                )
                df.drop(columns=["ts_raw"], inplace=True)

                # Process request (vectorized)
                request_parts = df["request"].str.split(expand=True)
                df["method"] = request_parts[0].astype("category")
                df["path"] = request_parts[1]
                df["protocol"] = request_parts[2].astype("category")
                df.drop(columns=["request"], inplace=True)
                del request_parts

                # Add status category (vectorized)
                df["status_category"] = pd.Categorical(
                    ["Unknown"] * len(df), categories=status_categories, ordered=False
                )
                status_map = {
                    range(200, 300): "OK",
                    range(300, 400): "Redirect",
                    range(400, 500): "Not Found",
                    range(500, 600): "SystemError",
                }
                for status_range, category in status_map.items():
                    mask = df["status"].between(
                        status_range.start, status_range.stop - 1
                    )
                    df.loc[mask, "status_category"] = category

                # Add metadata columns (use categorical for repeated values)
                df["project_id"] = metadata["project_id"]
                df["region"] = pd.Categorical([metadata["region"]] * len(df))
                df["nodeName"] = pd.Categorical([metadata["node_name"]] * len(df))
                df["hostname"] = pd.Categorical([metadata["hostname"]] * len(df))
                df["provider"] = pd.Categorical([metadata["provider"]] * len(df))
                df["sync_time"] = datetime.now(UTC)

                # Upload chunk to PostgreSQL
                upload_to_postgres(conn, df)

                total_rows += len(df)
                logger.info(
                    f"Node {node_id}: Processed chunk {chunk_num} ({len(df)} rows)"
                )

            except Exception as e:
                logger.error(f"Error processing chunk {chunk_num}: {str(e)}")
                failed_chunks.append(chunk_num)
                # Continue with next chunk despite errors
            finally:
                # Clean up chunk data
                if "df" in locals():
                    del df

            chunk_num += 1

        if failed_chunks:
            logger.warning(f"Failed chunks: {failed_chunks}")
        logger.info(
            f"Node {node_id}: Uploaded {total_rows} rows to log_analytics.log_results"
        )

    except Exception as e:
        logger.error(f"Fatal error on node {node_id}: {str(e)}")
        raise
    finally:
        # Clean up
        if "con" in locals():
            con.close()
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("--config", help="Path to config.yaml file", required=True)
    parser.add_argument(
        "--input-file",
        help="Path to the input log file (can also be set via INPUT_FILE env var)",
    )
    parser.add_argument(
        "--exit",
        help="Exit immediately (so dependencies are cached)",
        action="store_true",
    )
    args = parser.parse_args()

    if args.exit:
        exit(0)

    input_file = args.input_file or os.environ.get("INPUT_FILE")
    if not input_file:
        raise ValueError(
            "Input file must be provided via --input-file argument or INPUT_FILE environment variable"
        )

    main(args.config, input_file)
