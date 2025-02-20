#!/usr/bin/env python3
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
import yaml
from faker import Faker
from google.api_core import exceptions, retry
from google.cloud import bigquery
from google.oauth2 import service_account

# Initialize Faker
fake = Faker()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress numpy deprecation warning from DuckDB
warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core")

# Environment configuration
LOGS_DIR = os.environ.get("LOGS_DIR", "/var/log/logs_to_process")
CREDENTIALS_PATH = os.environ.get(
    "CREDENTIALS_PATH", os.path.join(LOGS_DIR, "log_uploader_credentials.json")
)

# Expected schema for BigQuery table
EXPECTED_SCHEMA = [
    bigquery.SchemaField("project_id", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("nodeName", "STRING"),
    bigquery.SchemaField("sync_time", "TIMESTAMP"),
    bigquery.SchemaField("ip", "STRING"),
    bigquery.SchemaField("user_id", "STRING"),
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
    bigquery.SchemaField("method", "STRING"),
    bigquery.SchemaField("path", "STRING"),
    bigquery.SchemaField("protocol", "STRING"),
    bigquery.SchemaField("status", "INTEGER"),
    bigquery.SchemaField("bytes", "INTEGER"),
    bigquery.SchemaField("referer", "STRING"),
    bigquery.SchemaField("user_agent", "STRING"),
    bigquery.SchemaField("hostname", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("status_category", "STRING"),
]

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
            except exceptions.TooManyRequests as e:
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    logger.error(f"Max retries ({MAX_RETRIES}) exceeded: {str(e)}")
                    raise

                # Add jitter to avoid thundering herd
                jitter = random.uniform(-JITTER_FACTOR * delay, JITTER_FACTOR * delay)
                sleep_time = delay + jitter

                logger.warning(
                    f"Rate limit exceeded. Retrying in {sleep_time:.2f} seconds "
                    f"(attempt {retry_count}/{MAX_RETRIES})"
                )

                time.sleep(sleep_time)
                delay = min(delay * RETRY_MULTIPLIER, MAX_RETRY_DELAY)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise

    return wrapper


@with_retries
def upload_to_bigquery(
    bq_client: bigquery.Client,
    df: pd.DataFrame,
    table_id: str,
    job_config: bigquery.LoadJobConfig,
) -> None:
    """Upload dataframe to BigQuery with retry logic."""
    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()


def load_config(config_path):
    """Load configuration from config.yaml."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


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


def parse_request(request):
    """Parse HTTP request string into method, path, and protocol."""
    parts = request.split()
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    return "", "", ""


def main(input_file: str) -> None:
    node_id = os.environ.get("NODE_ID", "unknown")
    logger.info(f"Starting processing on node {node_id}")

    try:
        if CREDENTIALS_PATH == "":
            raise ValueError("CREDENTIALS_PATH environment variable is not set")

        if not os.path.exists(CREDENTIALS_PATH):
            raise FileNotFoundError(f"Credentials file not found at {CREDENTIALS_PATH}")

        project_id = os.environ.get("PROJECT_ID", "")
        if project_id == "":
            raise ValueError("PROJECT_ID environment variable is not set")

        dataset = os.environ.get("DATASET", "log_analytics")
        table = os.environ.get("TABLE", "log_results")
        chunk_size = int(os.environ.get("CHUNK_SIZE", "10000"))

        # Define table_id early
        table_id = f"{project_id}.{dataset}.{table}"

        # Load credentials and create BigQuery client
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        bq_client = bigquery.Client(credentials=credentials)

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
                df["project_id"] = project_id
                df["region"] = pd.Categorical([metadata["region"]] * len(df))
                df["nodeName"] = pd.Categorical([metadata["node_name"]] * len(df))
                df["hostname"] = pd.Categorical([metadata["hostname"]] * len(df))
                df["provider"] = pd.Categorical([metadata["provider"]] * len(df))
                df["sync_time"] = datetime.now(UTC)

                # Upload chunk to BigQuery
                job_config = bigquery.LoadJobConfig(
                    schema=EXPECTED_SCHEMA,
                    write_disposition="WRITE_APPEND",
                    create_disposition="CREATE_NEVER",
                )

                upload_to_bigquery(bq_client, df, table_id, job_config)

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
        logger.info(f"Node {node_id}: Uploaded {total_rows} rows to {table_id}")

    except Exception as e:
        logger.error(f"Fatal error on node {node_id}: {str(e)}")
        raise
    finally:
        # Clean up
        if "con" in locals():
            con.close()
        if "bq_client" in locals():
            bq_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument(
        "--input-file",
        help="Path to the input log file (can also be set via INPUT_FILE env var)",
    )
    args = parser.parse_args()

    input_file = args.input_file or os.environ.get("INPUT_FILE")
    if not input_file:
        raise ValueError(
            "Input file must be provided via --input-file argument or INPUT_FILE environment variable"
        )

    main(input_file)
