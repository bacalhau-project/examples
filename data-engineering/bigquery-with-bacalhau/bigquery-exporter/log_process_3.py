#!/usr/bin/env python3
import argparse
import ipaddress
import logging
import os
import random
import socket
import time
import warnings
from datetime import UTC, datetime
from typing import Any, Callable

import duckdb
import pandas as pd
import yaml
from google.api_core import exceptions, retry
from google.cloud import bigquery
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress numpy deprecation warning from DuckDB
warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core")

# Expected schemas for BigQuery tables
EMERGENCY_SCHEMA = [
    bigquery.SchemaField("project_id", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("nodeName", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("hostname", "STRING"),
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
    bigquery.SchemaField("version", "STRING"),
    bigquery.SchemaField("message", "STRING"),
    bigquery.SchemaField("remote_log_id", "STRING"),
    bigquery.SchemaField("alert_level", "STRING"),
    bigquery.SchemaField("ip", "STRING"),
    bigquery.SchemaField("sync_time", "TIMESTAMP"),
]

AGGREGATES_SCHEMA = [
    bigquery.SchemaField("project_id", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("nodeName", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("hostname", "STRING"),
    bigquery.SchemaField("time_window", "TIMESTAMP"),
    bigquery.SchemaField("ok_count", "INT64"),
    bigquery.SchemaField("redirect_count", "INT64"),
    bigquery.SchemaField("not_found_count", "INT64"),
    bigquery.SchemaField("system_error_count", "INT64"),
    bigquery.SchemaField("total_count", "INT64"),
    bigquery.SchemaField("total_bytes", "INT64"),
    bigquery.SchemaField("avg_bytes", "FLOAT64"),
]

# Retry configuration
MAX_RETRIES = 20  # seconds
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 60  # seconds
RETRY_MULTIPLIER = 2
JITTER_FACTOR = 0.1


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


def main(input_file: str) -> None:
    node_id = os.environ.get("NODE_ID", "unknown")
    logger.info(f"Starting processing on node {node_id}")

    try:
        # Load configuration
        project_id = os.environ.get("PROJECT_ID", "")
        if project_id == "":
            raise ValueError("PROJECT_ID environment variable is not set")

        dataset = os.environ.get("DATASET", "log_analytics")
        table = os.environ.get("TABLE", "log_results")
        chunk_size = int(os.environ.get("CHUNK_SIZE", "10000"))

        credentials_path = os.environ.get("CREDENTIALS_PATH", "credentials.json")

        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found at {credentials_path}")

        # Load credentials and create BigQuery client
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        bq_client = bigquery.Client(credentials=credentials)

        # Create DuckDB connection
        con = duckdb.connect()

        # Get metadata once
        metadata = get_metadata()

        # Initialize aggregation accumulators
        total_emergency = 0
        total_rows = 0
        failed_chunks = []
        chunk_num = 0

        # Pre-create categorical values for status
        status_categories = ["Unknown", "OK", "Redirect", "Not Found", "SystemError"]

        # Initialize aggregation DataFrame with correct schema
        agg_df = pd.DataFrame(
            columns=[
                "time_window",
                "ok_count",
                "redirect_count",
                "not_found_count",
                "system_error_count",
                "total_count",
                "total_bytes",
                "avg_bytes",
            ]
        )

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

                # Handle emergency logs (status 500+) without creating copy
                emergency_mask = df["status"] >= 500
                if emergency_mask.any():
                    try:
                        # First create message components before filtering
                        message_components = (
                            df["method"].astype(str)
                            + " "
                            + df["path"].astype(str)
                            + " returned "
                            + df["status"].astype(str)
                        )

                        # Create emergency DataFrame with required columns
                        emergency_df = pd.DataFrame()
                        for field in EMERGENCY_SCHEMA:
                            if field.name in df.columns:
                                emergency_df[field.name] = df.loc[
                                    emergency_mask, field.name
                                ]

                        # Add emergency-specific fields efficiently
                        emergency_df["version"] = "1.0"
                        emergency_df["message"] = message_components[emergency_mask]
                        emergency_df["remote_log_id"] = (
                            f"{project_id}.log_analytics.emergency_logs"
                        )
                        emergency_df["alert_level"] = "ERROR"

                        # Upload emergency chunk to BigQuery
                        emergency_table_id = f"{project_id}.{dataset}.emergency_logs"
                        emergency_job_config = bigquery.LoadJobConfig(
                            schema=EMERGENCY_SCHEMA,
                            write_disposition="WRITE_APPEND",
                            create_disposition="CREATE_NEVER",
                        )
                        upload_to_bigquery(
                            bq_client,
                            emergency_df,
                            emergency_table_id,
                            emergency_job_config,
                        )
                        total_emergency += len(emergency_df)
                    except Exception as e:
                        logger.error(
                            f"Error processing emergency logs in chunk {chunk_num}: {str(e)}"
                        )
                    finally:
                        if "emergency_df" in locals():
                            del emergency_df
                        if "message_components" in locals():
                            del message_components

                # Aggregate chunk data efficiently
                df["time_window"] = df["timestamp"].dt.floor("h")

                # Calculate status counts directly
                status_counts = pd.DataFrame(
                    {
                        "ok_count": [(df["status_category"] == "OK").sum()],
                        "redirect_count": [(df["status_category"] == "Redirect").sum()],
                        "not_found_count": [
                            (df["status_category"] == "Not Found").sum()
                        ],
                        "system_error_count": [
                            (df["status_category"] == "SystemError").sum()
                        ],
                        "total_count": [len(df)],
                    }
                )

                # Calculate bytes statistics
                bytes_stats = pd.DataFrame(
                    {
                        "total_bytes": [df["bytes"].sum()],
                        "avg_bytes": [df["bytes"].mean()],
                    }
                )

                # Combine all aggregations
                chunk_agg = pd.DataFrame(
                    {
                        "time_window": [
                            df["time_window"].iloc[0]
                        ],  # All rows in chunk have same window
                        **status_counts,
                        **bytes_stats,
                    }
                )

                # Update running aggregations
                agg_df = pd.concat([agg_df, chunk_agg], ignore_index=True)
                agg_df = agg_df.groupby("time_window", as_index=False).sum()

                # Recalculate average bytes after grouping
                agg_df["avg_bytes"] = agg_df["total_bytes"] / agg_df["total_count"]

                total_rows += len(df)
                logger.info(
                    f"Node {node_id}: Processed chunk {chunk_num} ({len(df)} rows, {total_emergency} emergency)"
                )

            except Exception as e:
                logger.error(f"Error processing chunk {chunk_num}: {str(e)}")
                failed_chunks.append(chunk_num)
            finally:
                # Clean up chunk data
                if "df" in locals():
                    del df
                if "chunk_agg" in locals():
                    del chunk_agg

            chunk_num += 1

        # Upload final aggregations
        if not agg_df.empty:
            try:
                # Add metadata to aggregated data
                agg_df["project_id"] = project_id
                agg_df["region"] = metadata["region"]
                agg_df["nodeName"] = metadata["node_name"]
                agg_df["hostname"] = metadata["hostname"]
                agg_df["provider"] = metadata["provider"]

                # Ensure correct columns and order for aggregates
                agg_df = agg_df[[col.name for col in AGGREGATES_SCHEMA]]

                # Upload aggregated data to BigQuery
                agg_table_id = f"{project_id}.{dataset}.log_aggregates"
                agg_job_config = bigquery.LoadJobConfig(
                    schema=AGGREGATES_SCHEMA,
                    write_disposition="WRITE_APPEND",
                    create_disposition="CREATE_NEVER",
                )

                upload_to_bigquery(bq_client, agg_df, agg_table_id, agg_job_config)
                logger.info(
                    f"Node {node_id}: Uploaded {len(agg_df)} aggregated log entries"
                )

            except Exception as e:
                logger.error(f"Error processing aggregations: {str(e)}")

        if failed_chunks:
            logger.warning(f"Failed chunks: {failed_chunks}")
        logger.info(
            f"Node {node_id}: Completed processing. Total rows: {total_rows}, Emergency logs: {total_emergency}"
        )

    except Exception as e:
        logger.error(f"Fatal error on node {node_id}: {str(e)}")
        raise
    finally:
        # Clean up
        if "con" in locals():
            con.close()
        if "bq_client" in locals():
            bq_client.close()
        if "agg_df" in locals():
            del agg_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and aggregate log data")
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
