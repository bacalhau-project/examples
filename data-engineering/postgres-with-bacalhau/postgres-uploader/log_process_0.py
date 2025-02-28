#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psycopg2-binary",
#     "pyyaml",
# ]
# ///

import argparse
import logging
import multiprocessing
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import StringIO
from typing import List, Optional

import psycopg2
import yaml

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


def read_config(config_path: str) -> dict:
    """Read configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)
    if "postgresql" not in config:
        raise ValueError("Missing 'postgresql' section in config")
    required_fields = ["host", "port", "user", "password", "database"]
    missing = [f for f in required_fields if f not in config["postgresql"]]
    if missing:
        raise ValueError(f"Missing required PostgreSQL fields: {', '.join(missing)}")
    return config


def get_db_connection(pg_config: dict):
    """Create a new database connection."""
    connect_args = {
        "host": pg_config["host"],
        "port": pg_config["port"],
        "user": pg_config["user"],
        "password": pg_config["password"],
        "database": pg_config["database"],
        "sslmode": "require",
        "connect_timeout": CONNECTION_TIMEOUT,
    }

    try:
        conn = psycopg2.connect(**connect_args)
        # Test the connection
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return conn
    except Exception as e:
        logger.error(f"Error creating database connection: {str(e)}")
        raise


def ensure_schema_and_table(conn, use_unlogged=False):
    """Create schema and table if they don't exist."""
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS log_analytics;")
            conn.commit()

            # Create regular table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_analytics.raw_logs (
                    raw_line TEXT,
                    upload_time TIMESTAMP WITH TIME ZONE
                );
            """)

            # Create unlogged table if requested and it doesn't exist
            if use_unlogged:
                cur.execute("""
                    CREATE UNLOGGED TABLE IF NOT EXISTS log_analytics.raw_logs_unlogged (
                        raw_line TEXT,
                        upload_time TIMESTAMP WITH TIME ZONE
                    );
                """)

            conn.commit()
            logger.info(
                f"Schema and {'unlogged ' if use_unlogged else ''}table ensured"
            )
    except Exception as e:
        logger.error(f"Error creating schema/table: {str(e)}")
        raise


def get_table_indexes(conn, table_name="log_analytics.raw_logs"):
    """Get list of indexes on the specified table."""
    indexes = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'log_analytics' AND tablename = 'raw_logs'
            """)
            indexes = cur.fetchall()
            if indexes:
                logger.info(f"Found {len(indexes)} indexes on {table_name}")
                for idx_name, idx_def in indexes:
                    logger.info(f"  {idx_name}: {idx_def}")
    except Exception as e:
        logger.warning(f"Error getting indexes: {str(e)}")

    return indexes


def disable_indexes(conn, indexes):
    """Temporarily drop indexes for faster loading."""
    if not indexes:
        return []

    dropped_indexes = []
    try:
        with conn.cursor() as cur:
            for idx_name, idx_def in indexes:
                try:
                    logger.info(f"Dropping index {idx_name} for faster loading")
                    cur.execute(f"DROP INDEX IF EXISTS log_analytics.{idx_name}")
                    dropped_indexes.append((idx_name, idx_def))
                except Exception as e:
                    logger.warning(f"Could not drop index {idx_name}: {str(e)}")
            conn.commit()
    except Exception as e:
        logger.error(f"Error disabling indexes: {str(e)}")

    return dropped_indexes


def restore_indexes(conn, dropped_indexes):
    """Restore previously dropped indexes."""
    if not dropped_indexes:
        return

    try:
        with conn.cursor() as cur:
            for idx_name, idx_def in dropped_indexes:
                try:
                    logger.info(f"Restoring index {idx_name}")
                    # Extract the CREATE INDEX statement from the index definition
                    cur.execute(idx_def)
                    conn.commit()
                except Exception as e:
                    logger.error(f"Could not restore index {idx_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Error restoring indexes: {str(e)}")


def upload_batch_with_copy(conn, batch, timestamp, table_name="log_analytics.raw_logs"):
    """Upload a batch of log lines to PostgreSQL using the COPY command for better performance."""
    try:
        with conn.cursor() as cur:
            # Set performance optimizations
            cur.execute(
                "SET statement_timeout = 300000"
            )  # 5 minutes timeout (increased)

            # Try to set synchronous_commit to OFF for better performance
            try:
                cur.execute("SET synchronous_commit TO OFF")
                if DEBUG:
                    logger.debug("Set synchronous_commit to OFF")
            except Exception as e:
                if DEBUG:
                    logger.debug(f"Could not set synchronous_commit: {str(e)}")

            # Try to set work_mem higher
            try:
                cur.execute("SET work_mem = '256MB'")  # Increased from 128MB
            except Exception as e:
                if DEBUG:
                    logger.debug(f"Could not set work_mem: {str(e)}")

            # Create a StringIO object with the data
            csv_data = StringIO()
            for line in batch:
                # Escape tab characters and newlines in the line
                escaped_line = (
                    line.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                )
                # Write line and timestamp to CSV
                csv_data.write(f"{escaped_line}\t{timestamp.isoformat()}\n")

            csv_data.seek(0)

            # Use COPY command with the specified table
            cur.copy_expert(
                f"COPY {table_name} (raw_line, upload_time) FROM STDIN WITH DELIMITER E'\\t'",
                csv_data,
            )

            conn.commit()
            return len(batch)

    except Exception as e:
        logger.error(f"Error using COPY command: {str(e)}")
        # Try to rollback in case of error
        try:
            conn.rollback()
        except:
            pass
        # Re-raise the exception to be handled by the caller
        raise


def upload_chunk(chunk, pg_config, batch_size, use_unlogged=False):
    """Process a chunk of log lines."""
    chunk_timestamp = datetime.now(timezone.utc)
    conn = None
    rows_inserted = 0

    # Determine which table to use
    table_name = (
        "log_analytics.raw_logs_unlogged" if use_unlogged else "log_analytics.raw_logs"
    )

    try:
        # Get a dedicated connection for this chunk
        conn = get_db_connection(pg_config)

        # Process in smaller batches
        for i in range(0, len(chunk), batch_size):
            batch = chunk[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(chunk) + batch_size - 1) // batch_size

            # Always initialize batch_start time regardless of DEBUG mode
            batch_start = time.time()

            if DEBUG:
                logger.debug(
                    f"Inserting batch {batch_num}/{total_batches} ({len(batch)} rows)"
                )

            try:
                # Use COPY for all inserts
                batch_rows = upload_batch_with_copy(
                    conn, batch, chunk_timestamp, table_name
                )
                rows_inserted += batch_rows

                # Calculate batch_time for both DEBUG and non-DEBUG modes
                batch_time = time.time() - batch_start

                if DEBUG:
                    rate = len(batch) / batch_time if batch_time > 0 else 0
                    logger.debug(
                        f"Inserted batch {batch_num}/{total_batches} in {batch_time:.2f}s ({rate:.1f} rows/sec)"
                    )

                # Log performance for slow batches even in non-debug mode
                if not DEBUG and batch_time > 10:
                    rate = len(batch) / batch_time if batch_time > 0 else 0
                    logger.info(
                        f"Batch {batch_num}/{total_batches} took {batch_time:.2f}s ({rate:.1f} rows/sec)"
                    )
            except Exception as e:
                logger.error(
                    f"Error inserting batch {batch_num}/{total_batches}: {str(e)}"
                )
                # Continue with next batch instead of failing the entire chunk
                continue

        return rows_inserted
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        raise
    finally:
        # Close connection when done with this chunk
        if conn:
            try:
                conn.close()
            except:
                pass


def read_log_file_in_chunks(file_path: str, chunk_size: int) -> List[List[str]]:
    """Read a log file and divide into chunks."""
    chunks = []
    current_chunk = []
    line_count = 0

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            current_chunk.append(line)
            line_count += 1

            if len(current_chunk) >= chunk_size:
                chunks.append(current_chunk)
                current_chunk = []

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)

    logger.info(f"Read {line_count} lines into {len(chunks)} chunks")
    return chunks


def main(
    config_path,
    input_file,
    chunk_size,
    max_workers,
    batch_size,
    use_unlogged,
    manage_indexes,
):
    """Main processing function."""
    # Load configuration
    config = read_config(config_path)
    pg_config = config["postgresql"]

    # Determine which table to use
    table_name = (
        "log_analytics.raw_logs_unlogged" if use_unlogged else "log_analytics.raw_logs"
    )

    logger.info(
        f"PostgreSQL config: Host={pg_config['host']}, Port={pg_config['port']}, "
        f"User={pg_config['user']}, Database={pg_config['database']}"
    )
    logger.info(
        f"Using chunk size: {chunk_size}, Max workers: {max_workers}, Batch size: {batch_size}"
    )
    logger.info(
        f"Using {'unlogged' if use_unlogged else 'regular'} table: {table_name}"
    )

    # Set up database schema/table (using a temporary connection)
    conn = get_db_connection(pg_config)
    ensure_schema_and_table(conn, use_unlogged)

    # Handle indexes if requested
    dropped_indexes = []
    if manage_indexes:
        indexes = get_table_indexes(conn)
        if indexes:
            dropped_indexes = disable_indexes(conn, indexes)
            logger.info(
                f"Temporarily dropped {len(dropped_indexes)} indexes for faster loading"
            )

    conn.close()

    # Read log file into chunks
    start_time = time.time()
    chunks = read_log_file_in_chunks(input_file, chunk_size)

    # Process chunks in parallel
    total_rows = 0
    completed_chunks = 0
    failed_chunks = 0

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    upload_chunk, chunk, pg_config, batch_size, use_unlogged
                )
                for chunk in chunks
            ]

            for future in as_completed(futures):
                try:
                    rows = future.result()
                    total_rows += rows
                    completed_chunks += 1

                    # Log progress
                    progress = (completed_chunks + failed_chunks) / len(futures) * 100
                    logger.info(
                        f"Progress: {progress:.1f}% ({completed_chunks}/{len(chunks)} chunks complete)"
                    )

                except Exception as e:
                    failed_chunks += 1
                    logger.error(f"Chunk processing failed: {str(e)}")

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    finally:
        # Restore indexes if we dropped any
        if dropped_indexes:
            logger.info("Restoring dropped indexes...")
            conn = get_db_connection(pg_config)
            restore_indexes(conn, dropped_indexes)
            conn.close()

    # Log final stats
    elapsed = time.time() - start_time
    rate = total_rows / elapsed if elapsed > 0 else 0
    logger.info(
        f"Uploaded {total_rows} rows in {elapsed:.2f}s ({rate:.1f} rows/sec). "
        f"Completed chunks: {completed_chunks}, Failed chunks: {failed_chunks}"
    )

    # If we used unlogged table, suggest how to copy to regular table if needed
    if use_unlogged:
        logger.info(
            "Data was loaded into unlogged table. To copy to regular table if needed:"
        )
        logger.info(
            "INSERT INTO log_analytics.raw_logs SELECT * FROM log_analytics.raw_logs_unlogged;"
        )


if __name__ == "__main__":
    # Calculate default number of workers based on CPU count
    default_workers = min(multiprocessing.cpu_count() * 2, 8)

    # Environment variable defaults
    env_config = os.environ.get("CONFIG_PATH", "")
    env_input_file = os.environ.get("INPUT_FILE", "")
    env_chunk_size = int(os.environ.get("CHUNK_SIZE", "20000"))
    env_max_workers = int(os.environ.get("MAX_WORKERS", str(default_workers)))
    env_batch_size = int(os.environ.get("BATCH_SIZE", "10000"))
    env_use_unlogged = os.environ.get("USE_UNLOGGED", "").lower() in (
        "true",
        "1",
        "yes",
    )
    env_manage_indexes = os.environ.get("MANAGE_INDEXES", "").lower() in (
        "true",
        "1",
        "yes",
    )

    parser = argparse.ArgumentParser(
        description="Upload logs to PostgreSQL - High Performance Version"
    )
    parser.add_argument(
        "--config",
        help=f"Path to config.yaml file (env: CONFIG)",
        default=env_config,
    )
    parser.add_argument(
        "--input-file",
        help=f"Path to the input log file (env: INPUT_FILE)",
        default=env_input_file,
    )
    parser.add_argument(
        "--chunk-size",
        help=f"Number of rows per chunk (env: CHUNK_SIZE)",
        type=int,
        default=env_chunk_size,
    )
    parser.add_argument(
        "--max-workers",
        help=f"Max number of parallel upload workers (env: MAX_WORKERS)",
        type=int,
        default=env_max_workers,
    )
    parser.add_argument(
        "--batch-size",
        help=f"Number of rows per batch within each chunk (larger batches reduce transaction overhead) (env: BATCH_SIZE)",
        type=int,
        default=env_batch_size,
    )
    parser.add_argument(
        "--use-unlogged",
        help=f"Use unlogged table for faster inserts (no WAL overhead) (env: USE_UNLOGGED)",
        action="store_true",
        default=env_use_unlogged,
    )
    parser.add_argument(
        "--manage-indexes",
        help=f"Temporarily drop indexes during loading for better performance (env: MANAGE_INDEXES)",
        action="store_true",
        default=env_manage_indexes,
    )
    parser.add_argument(
        "--debug",
        help=f"Enable debug logging (env: DEBUG)",
        action="store_true",
        default=DEBUG,
    )
    args = parser.parse_args()

    # Validate required input file
    if not args.input_file:
        parser.error("--input-file is required or set INPUT_FILE environment variable")

    # Set debug mode globally
    if args.debug:
        DEBUG = True
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    try:
        main(
            config_path=args.config,
            input_file=args.input_file,
            chunk_size=args.chunk_size,
            max_workers=args.max_workers,
            batch_size=args.batch_size,
            use_unlogged=args.use_unlogged,
            manage_indexes=args.manage_indexes,
        )
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}")
        sys.exit(1)
