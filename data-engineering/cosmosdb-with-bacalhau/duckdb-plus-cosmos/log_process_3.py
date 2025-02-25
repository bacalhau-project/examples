#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "pandas",
#     "psycopg2-binary",
#     "pyyaml",
#     "ipaddress",
# ]
# ///

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
import psycopg2
import yaml
from psycopg2.extras import execute_values

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
def upload_to_postgres(
    conn: psycopg2.extensions.connection, df: pd.DataFrame, table_name: str
) -> None:
    """Upload dataframe to PostgreSQL with retry logic."""
    with conn.cursor() as cur:
        # Convert DataFrame to list of tuples
        values = [tuple(x) for x in df.to_numpy()]

        # Generate the INSERT query
        columns = df.columns.tolist()
        query = f"""
            INSERT INTO log_analytics.{table_name} (
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
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "region": os.environ.get("REGION", "unknown"),
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

        # Initialize aggregation accumulators
        total_emergency = 0
        total_rows = 0
        failed_chunks = []
        chunk_num = 0

        # Pre-create categorical values for status
        status_categories = ["Unknown", "OK", "Redirect", "Not Found", "SystemError"]

        # Initialize aggregation DataFrame with correct schema and data types
        agg_df = pd.DataFrame(
            {
                "time_window": pd.Series(dtype="datetime64[ns]"),
                "ok_count": pd.Series(dtype="int64"),
                "redirect_count": pd.Series(dtype="int64"),
                "not_found_count": pd.Series(dtype="int64"),
                "system_error_count": pd.Series(dtype="int64"),
                "total_count": pd.Series(dtype="int64"),
                "total_bytes": pd.Series(dtype="int64"),
                "avg_bytes": pd.Series(dtype="float64"),
            }
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
                        column7 as referrer,
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

                        # Create emergency DataFrame
                        emergency_df = pd.DataFrame(
                            {
                                "project_id": metadata["project_id"],
                                "region": metadata["region"],
                                "nodeName": metadata["node_name"],
                                "provider": metadata["provider"],
                                "hostname": metadata["hostname"],
                                "timestamp": df.loc[emergency_mask, "timestamp"],
                                "version": "1.0",
                                "message": message_components[emergency_mask],
                                "remote_log_id": "emergency_logs",
                                "alert_level": "ERROR",
                                "ip": df.loc[emergency_mask, "ip"],
                                "sync_time": datetime.now(UTC),
                            }
                        )

                        # Upload emergency chunk to PostgreSQL
                        upload_to_postgres(conn, emergency_df, "emergency_logs")
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
                df["time_window"] = (
                    df["timestamp"].dt.floor("h").dt.tz_localize(None)
                )  # Remove timezone info

                # Calculate status counts directly with explicit types
                status_counts = pd.DataFrame(
                    {
                        "ok_count": pd.Series(
                            [(df["status_category"] == "OK").sum()], dtype="int64"
                        ),
                        "redirect_count": pd.Series(
                            [(df["status_category"] == "Redirect").sum()], dtype="int64"
                        ),
                        "not_found_count": pd.Series(
                            [(df["status_category"] == "Not Found").sum()],
                            dtype="int64",
                        ),
                        "system_error_count": pd.Series(
                            [(df["status_category"] == "SystemError").sum()],
                            dtype="int64",
                        ),
                        "total_count": pd.Series([len(df)], dtype="int64"),
                    }
                )

                # Calculate bytes statistics with explicit types
                bytes_stats = pd.DataFrame(
                    {
                        "total_bytes": pd.Series([df["bytes"].sum()], dtype="int64"),
                        "avg_bytes": pd.Series([df["bytes"].mean()], dtype="float64"),
                    }
                )

                # Combine all aggregations with explicit time_window type
                chunk_agg = pd.DataFrame(
                    {
                        "time_window": pd.Series(
                            [df["time_window"].iloc[0]], dtype="datetime64[ns]"
                        ),
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
                agg_df["project_id"] = metadata["project_id"]
                agg_df["region"] = metadata["region"]
                agg_df["nodeName"] = metadata["node_name"]
                agg_df["hostname"] = metadata["hostname"]
                agg_df["provider"] = metadata["provider"]

                # Upload aggregated data to PostgreSQL
                upload_to_postgres(conn, agg_df, "log_aggregates")
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
        if "conn" in locals():
            conn.close()
        if "agg_df" in locals():
            del agg_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and aggregate log data")
    parser.add_argument("--config", help="Path to config.yaml file", required=False)
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

    main(args.config, args.input_file)
