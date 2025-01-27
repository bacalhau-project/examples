#!/usr/bin/env python3
import argparse
import logging
import os
import random
import time
from datetime import UTC, datetime
from typing import Any, Callable

import duckdb
import pandas as pd
from google.api_core import exceptions, retry
from google.cloud import bigquery
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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


def main(input_file: str) -> None:
    node_id = os.environ.get("NODE_ID", "unknown")
    logger.info(f"Starting processing on node {node_id}")

    try:
        credentials_path = os.environ.get("CREDENTIALS_PATH", "credentials.json")
        project_id = os.environ.get("PROJECT_ID", "")
        if project_id == "":
            raise ValueError("PROJECT_ID environment variable is not set")

        dataset = os.environ.get("DATASET", "log_analytics")
        table = os.environ.get("TABLE", "raw_logs")
        chunk_size = int(os.environ.get("CHUNK_SIZE", "10000"))

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

        total_rows = 0
        chunk_num = 0
        failed_chunks = []

        # Process in chunks
        while True:
            try:
                df = con.execute(
                    """
                    SELECT 
                        column0 AS raw_line
                    FROM read_csv(?, delim='\n', columns={'column0': 'VARCHAR'}, header=false)
                    LIMIT ? OFFSET ?
                    """,
                    [input_file, chunk_size, chunk_num * chunk_size],
                ).df()

                # Break if no more data
                if len(df) == 0:
                    break

                # Add upload timestamp (using timezone-aware datetime)
                df["upload_time"] = datetime.now(UTC)

                # Add timestamp efficiently
                df["timestamp"] = df["raw_line"].str.extract(
                    r"^\S+ \S+ \S+ \[(.*?)\]", expand=False
                )
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"], format="%Y-%m-%dT%H:%M:%S.%f%z"
                )

                # Upload chunk to BigQuery
                table_id = f"{project_id}.{dataset}.{table}"
                job_config = bigquery.LoadJobConfig(
                    schema=[
                        bigquery.SchemaField("raw_line", "STRING"),
                        bigquery.SchemaField("upload_time", "TIMESTAMP"),
                    ],
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
        logger.info(
            f"Node {node_id}: Uploaded {total_rows} raw log lines to {table_id}"
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload raw logs to BigQuery")
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
