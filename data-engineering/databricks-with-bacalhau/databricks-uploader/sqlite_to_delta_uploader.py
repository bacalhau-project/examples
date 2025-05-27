#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.0.0",
#     "pyarrow>=12.0.0",
#     "pyyaml>=6.0",
#     "deltalake>=0.17.0"  # Replaced pyspark with deltalake
# ]
# ///
"""
Continuously export new sensor log entries from a SQLite database and append them to a Delta Lake table
on Databricks using its table name.
Parameters and paths are read from a YAML config file, with optional environment variable overrides.
Uses the deltalake library for writing to Databricks.
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import yaml
from deltalake import write_deltalake  # Import write_deltalake

# Removed: from pyspark.sql import SparkSession


def parse_args():
    p = argparse.ArgumentParser(description="SQLite → Databricks Delta uploader")
    p.add_argument("--config", help="YAML config file (optional)")
    p.add_argument("--sqlite", help="Path to SQLite DB")
    # Removed --storage-uri
    p.add_argument(
        "--table", help="Full Databricks Delta table name (e.g., catalog.schema.table)"
    )
    p.add_argument("--state-dir", help="Directory for last-upload state file")
    p.add_argument(
        "--interval", type=int, help="Seconds between cycles (ignored with --once)"
    )
    p.add_argument("--once", action="store_true", help="Upload once and exit (no loop)")
    p.add_argument("--timestamp-col", help="Override timestamp column in SQLite")

    # Databricks specific arguments
    p.add_argument(
        "--databricks-host",
        help="Databricks workspace URL (e.g., https://<your-workspace>.cloud.databricks.com)",
    )
    p.add_argument("--databricks-token", help="Databricks Personal Access Token")
    # Removed --cluster-id as it's not used by deltalake library
    # New arguments for Databricks catalog and schema
    p.add_argument("--databricks-catalog", help="Databricks Catalog name")
    p.add_argument("--databricks-schema", help="Databricks Schema name")
    return p.parse_args()


def read_data(sqlite_path, query, table_name):
    conn = sqlite3.connect(sqlite_path)
    try:
        if query:
            df = pd.read_sql_query(query, conn)
        else:
            if not table_name:  # This table_name is for SQLite, not Databricks
                raise ValueError(
                    "Must specify SQLite table name or query if not auto-detecting for SQLite."
                )
            df = pd.read_sql_query(
                f"SELECT * FROM {table_name}", conn
            )  # table_name here is local SQLite table
        return df
    finally:
        conn.close()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    # 1) load YAML if supplied
    cfg = {}
    if args.config:
        cfg = yaml.safe_load(Path(args.config).read_text())

    # 2) assemble params   CLI > ENV > YAML > default
    sqlite_path = Path(args.sqlite or os.getenv("SQLITE_PATH") or cfg.get("sqlite", ""))

    # Databricks connection parameters
    databricks_host = (
        args.databricks_host
        or os.getenv("DATABRICKS_HOST")
        or cfg.get("databricks_host")
    )
    databricks_token = (
        args.databricks_token
        or os.getenv("DATABRICKS_TOKEN")
        or cfg.get("databricks_token")
    )
    # cluster_id removed as it's not used by deltalake
    # cluster_id = (
    #     args.cluster_id or os.getenv("DATABRICKS_CLUSTER_ID") or cfg.get("cluster_id")
    # )

    # Databricks catalog and schema
    databricks_catalog = (
        args.databricks_catalog
        or os.getenv("DATABRICKS_CATALOG")
        or cfg.get("databricks_catalog")
    )
    databricks_schema = (
        args.databricks_schema
        or os.getenv("DATABRICKS_SCHEMA")
        or cfg.get("databricks_schema")
    )

    # Target Databricks table name
    databricks_table_name = (
        args.table or os.getenv("DATABRICKS_TABLE") or cfg.get("table")
    )

    state_dir = Path(
        args.state_dir or os.getenv("STATE_DIR") or cfg.get("state_dir", "/state")
    )
    interval = int(
        (
            args.interval
            if args.interval is not None
            else os.getenv("UPLOAD_INTERVAL") or cfg.get("interval", 300)
        )
    )
    once = args.once
    # This 'table_name' is for local SQLite source, distinct from 'databricks_table_name'
    # We will rename it to avoid confusion later during introspection.
    sqlite_source_table_name_override = cfg.get(
        "sqlite_table"
    )  # If specified in config, different from databricks target table
    sqlite_timestamp_col_override = args.timestamp_col or cfg.get("timestamp_col")

    # Validate required parameters
    if not sqlite_path or not sqlite_path.is_file():
        logging.error("SQLite file not found: %s", sqlite_path)
        sys.exit(1)
    if not databricks_table_name:
        logging.error("Databricks target table name not specified.")
        sys.exit(1)

    # Make Databricks host and token mandatory
    if not (databricks_host and databricks_token):
        logging.error(
            "Databricks host and token (--databricks-host, --databricks-token, "
            "or ENV vars DATABRICKS_HOST, DATABRICKS_TOKEN, or in config) "
            "must be specified to ensure writing to the cloud."
        )
        sys.exit(1)

    # Validate format of databricks_table_name
    # Ensure it's either a qualified Unity Catalog name (e.g., catalog.schema.table)
    # or a DBFS path (e.g., dbfs:/path/to/table)
    is_qualified_uc_table = databricks_table_name.count(".") >= 2
    is_dbfs_path = databricks_table_name.lower().startswith("dbfs:/")

    if not (is_qualified_uc_table or is_dbfs_path):
        logging.error(
            f"Invalid Databricks target table name: '{databricks_table_name}'.\\n"
            "To ensure writing to the cloud, the table name must be either:\\n"
            "1. A fully qualified Unity Catalog name (e.g., 'catalog.schema.table').\\n"
            "2. A DBFS path (e.g., 'dbfs:/path/to/your/delta_table').\\n"
            "Using a simple name like 'mytable' or a local-like path is not allowed "
            "as it may lead to unintended local writes."
        )
        sys.exit(1)

    # Warnings for Databricks catalog and schema
    if not databricks_catalog:
        logging.warning(
            "Databricks Catalog (DATABRICKS_CATALOG / --databricks-catalog) is not specified. "
            "Ensure your target table name (currently '%s') includes the catalog if required by your Databricks setup, "
            "or set the catalog explicitly.",
            databricks_table_name,
        )
    if not databricks_schema:
        logging.warning(
            "Databricks Schema (DATABRICKS_SCHEMA / --databricks-schema) is not specified. "
            "Ensure your target table name (currently '%s') includes the schema if required by your Databricks setup, "
            "or set the schema explicitly.",
            databricks_table_name,
        )

    logging.info("Using deltalake library for Databricks operations.")

    # Prepare state file directory
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "last_upload.json"
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                last_ts = pd.to_datetime(json.load(f).get("last_upload"), utc=True)
        except Exception:
            last_ts = pd.Timestamp("1970-01-01T00:00:00Z")
    else:
        last_ts = pd.Timestamp("1970-01-01T00:00:00Z")

    # Determine SQLite table name for querying (this is the source table)
    actual_sqlite_table_name = (
        sqlite_source_table_name_override  # Use override if provided
    )
    if not actual_sqlite_table_name:  # If not overridden, try to detect
        conn_sqlite_meta = sqlite3.connect(str(sqlite_path))
        cursor_sqlite_meta = conn_sqlite_meta.cursor()
        cursor_sqlite_meta.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        sqlite_tables = [row[0] for row in cursor_sqlite_meta.fetchall()]
        conn_sqlite_meta.close()
        if not sqlite_tables:
            logging.error("No tables found in SQLite database.")
            sys.exit(1)
        if len(sqlite_tables) > 1:
            logging.warning(
                "Multiple tables found in SQLite database: %s. Using the first one: %s. Consider specifying with --sqlite-table in config.",
                sqlite_tables,
                sqlite_tables[0],
            )
        actual_sqlite_table_name = sqlite_tables[0]
    logging.info("Using SQLite source table: %s", actual_sqlite_table_name)

    # Determine SQLite timestamp column for querying
    actual_sqlite_timestamp_col = sqlite_timestamp_col_override
    if not actual_sqlite_timestamp_col:
        conn_sqlite_meta = sqlite3.connect(str(sqlite_path))
        cursor_sqlite_meta = conn_sqlite_meta.cursor()
        cursor_sqlite_meta.execute(f"PRAGMA table_info('{actual_sqlite_table_name}');")
        cols_sqlite = cursor_sqlite_meta.fetchall()
        conn_sqlite_meta.close()
        ts_cols_sqlite = [
            c[1]
            for c in cols_sqlite
            if c[1].lower() == "timestamp" or "date" in (c[2] or "").lower()
        ]
        if not ts_cols_sqlite:
            logging.error(
                "No suitable timestamp column found in SQLite table '%s'. Please specify via --timestamp-col or config.",
                actual_sqlite_table_name,
            )
            sys.exit(1)
        actual_sqlite_timestamp_col = ts_cols_sqlite[0]
    logging.info("Using SQLite timestamp column: %s", actual_sqlite_timestamp_col)

    logging.info(
        "Starting continuous upload to Databricks table '%s' every %d seconds, initial SQLite timestamp=%s",
        databricks_table_name,
        interval,
        last_ts,
    )

    storage_options = {}
    if databricks_host and databricks_token:
        # Ensure host includes the scheme (e.g., "https://")
        host_for_deltalake = databricks_host
        if not host_for_deltalake.startswith(
            "http://"
        ) and not host_for_deltalake.startswith("https://"):
            logging.warning(
                f"Databricks host '{host_for_deltalake}' does not include http/https scheme. Prepending 'https://'."
            )
            host_for_deltalake = "https://" + host_for_deltalake
        storage_options["DATABRICKS_HOST"] = host_for_deltalake
        storage_options["DATABRICKS_TOKEN"] = databricks_token
    elif databricks_host or databricks_token:  # only one is provided
        logging.warning(
            "Both DATABRICKS_HOST and DATABRICKS_TOKEN should be provided for authenticated access."
        )
    # If neither is provided, deltalake will attempt anonymous access or use other means if available (e.g. env vars)

    while True:
        try:
            # Read new data from SQLite since last timestamp
            sql_query = f"SELECT * FROM {actual_sqlite_table_name} WHERE {actual_sqlite_timestamp_col} > ? ORDER BY {actual_sqlite_timestamp_col}"
            conn_sqlite_data = sqlite3.connect(str(sqlite_path))
            pandas_df = pd.read_sql_query(
                sql_query, conn_sqlite_data, params=[last_ts.isoformat()]
            )
            conn_sqlite_data.close()

            if pandas_df.empty:
                logging.info("No new records from SQLite since %s", last_ts)
            else:
                logging.info(
                    "Read %d new records from SQLite. Appending to Databricks table %s",
                    len(pandas_df),
                    databricks_table_name,
                )

                # Ensure columns with all nulls are cast to a specific type (e.g., string)
                # to avoid SchemaMismatchError: Invalid data type for Delta Lake: Null
                for col in pandas_df.columns:
                    if pandas_df[col].isnull().all():
                        logging.info(
                            f"Column '{col}' contains only null values. Casting to string type."
                        )
                        pandas_df[col] = pandas_df[col].astype(str)

                # Append to Databricks Delta table using deltalake
                # The databricks_table_name should be the fully qualified name, e.g., catalog.schema.table
                # or a DBFS path if not using Unity Catalog.
                write_deltalake(
                    databricks_table_name,
                    pandas_df,
                    mode="append",
                    storage_options=storage_options if storage_options else None,
                    engine="rust",  # Explicitly use rust engine, though it's default
                )

                logging.info(
                    "Successfully appended %d records to Databricks table %s using deltalake",
                    len(pandas_df),
                    databricks_table_name,
                )

                # Update state timestamp
                last_ts_val = pandas_df[
                    actual_sqlite_timestamp_col
                ].max()  # Get max from pandas Series

                # Ensure last_ts is a pandas Timestamp before calling isoformat
                if not isinstance(last_ts_val, pd.Timestamp):
                    last_ts = pd.to_datetime(last_ts_val, utc=True)
                else:
                    last_ts = last_ts_val

                if pd.isna(
                    last_ts
                ):  # handle case where max might be NaT if all values are null (unlikely for timestamp)
                    logging.warning(
                        "Last timestamp from SQLite was NaT, not updating state."
                    )
                else:
                    with open(state_file, "w") as f:
                        json.dump({"last_upload": last_ts.isoformat()}, f)
        except KeyboardInterrupt:
            logging.info("Interrupted by user, exiting.")
            break
        except Exception as e:
            logging.error("Error in upload cycle: %s", e, exc_info=True)

        if once:
            logging.info("Upload once specified, exiting loop.")
            break
        logging.info("Sleeping for %d seconds before next cycle.", interval)
        time.sleep(interval)

    logging.info("Uploader finished.")


if __name__ == "__main__":
    main()
