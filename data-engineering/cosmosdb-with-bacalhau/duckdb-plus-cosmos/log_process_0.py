# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "pandas",
#     "psycopg2-binary",
#     "pyyaml",
# ]
# ///

import argparse
import logging
import os
import random
import time
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
            INSERT INTO log_analytics.raw_logs ({", ".join(columns)})
            VALUES %s
        """

        # Execute the insert
        execute_values(cur, query, values)
        conn.commit()


def read_config(config_path: str) -> dict:
    """Read configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Validate required fields
    required_fields = ["host", "port", "user", "password", "database"]
    if "postgresql" not in config:
        raise ValueError("Missing 'postgresql' section in config")

    missing = [f for f in required_fields if f not in config["postgresql"]]
    if missing:
        raise ValueError(f"Missing required PostgreSQL fields: {', '.join(missing)}")

    return config


def main(config_path: str, input_file: str) -> None:
    node_id = os.environ.get("NODE_ID", "unknown")
    logger.info(f"Starting processing on node {node_id}")

    try:
        # Read configuration
        config = read_config(config_path)
        pg_config = config["postgresql"]

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

        chunk_size = int(os.environ.get("CHUNK_SIZE", "10000"))
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
            f"Node {node_id}: Uploaded {total_rows} raw log lines to PostgreSQL"
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
    parser = argparse.ArgumentParser(description="Upload raw logs to PostgreSQL")
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
