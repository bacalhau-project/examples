#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.0.0",
#     "pyarrow>=12.0.0",
#     "deltalake>=0.11.0",
#     "pyyaml>=6.0"
# ]
"""
Continuously export new sensor log entries from a SQLite database and append them to a Delta Lake table (S3 / ADLS / local).
Parameters and paths are read from a YAML config file, with optional environment variable overrides.
Only command-line flag is --config pointing to the YAML file.
"""
import argparse
import logging
import sys
import sqlite3
import io
import os
import json
import time
from pathlib import Path

import yaml
import re
import pandas as pd
from deltalake import write_deltalake


def parse_args():
    p = argparse.ArgumentParser(description="SQLite → Delta uploader")
    p.add_argument("--config", help="YAML config file (optional)")
    p.add_argument("--sqlite", help="Path to SQLite DB")
    p.add_argument("--storage-uri", help="Delta table URI (s3://… / abfs://… / file:///…)")
    p.add_argument("--state-dir", help="Directory for last-upload state file")
    p.add_argument("--interval", type=int, help="Seconds between cycles (ignored with --once)")
    p.add_argument("--once", action="store_true",
                   help="Upload once and exit (no loop)")
    p.add_argument("--table", help="Override SQLite table name")
    p.add_argument("--timestamp-col", help="Override timestamp column")
    return p.parse_args()


def read_data(sqlite_path, query, table_name):
    conn = sqlite3.connect(sqlite_path)
    try:
        if query:
            df = pd.read_sql_query(query, conn)
        else:
            if not table_name:
                raise ValueError("Must specify --table or --query")
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return df
    finally:
        conn.close()


## removed S3 upload in favor of direct Delta Lake write


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # 1) load YAML if supplied
    cfg = {}
    if args.config:
        cfg = yaml.safe_load(Path(args.config).read_text())
    # 2) assemble params   CLI > ENV > YAML > default
    sqlite_path  = Path(
        args.sqlite or os.getenv("SQLITE_PATH") or cfg.get("sqlite", "")
    )
    storage_uri  = (
        args.storage_uri or os.getenv("STORAGE_URI") or cfg.get("storage_uri")
    )
    # Deprecation shim for old key names
    if not storage_uri:
        storage_uri = os.getenv("TABLE_PATH") or cfg.get("table_path")
    state_dir    = Path(
        args.state_dir or os.getenv("STATE_DIR") or cfg.get("state_dir", "/state")
    )
    interval     = int(
        (args.interval if args.interval is not None else
         os.getenv("UPLOAD_INTERVAL") or cfg.get("interval", 300))
    )
    once         = args.once
    table_name   = args.table or cfg.get("table")
    timestamp_col= args.timestamp_col or cfg.get("timestamp_col")

    # Validate required parameters
    if not sqlite_path or not sqlite_path.is_file():
        logging.error("SQLite file not found: %s", sqlite_path)
        sys.exit(1)
    if not storage_uri:
        logging.error("Delta table URI not specified in config or environment")
        sys.exit(1)

    # Prepare state file directory
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / 'last_upload.json'
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                last_ts = pd.to_datetime(json.load(f).get('last_upload'), utc=True)
        except Exception:
            last_ts = pd.Timestamp('1970-01-01T00:00:00Z')
    else:
        last_ts = pd.Timestamp('1970-01-01T00:00:00Z')

    # Table and timestamp column introspection/override
    if table_name is None:
        # Only run table detection if not provided
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not tables:
            logging.error("No tables found in SQLite database.")
            sys.exit(1)
        if len(tables) > 1:
            logging.error("Multiple tables found in SQLite database: %s", tables)
            sys.exit(1)
        table_name = tables[0]
        logging.info("Detected table: %s", table_name)
    else:
        logging.info("Using user-supplied table: %s", table_name)

    if timestamp_col is None:
        # Only run timestamp detection if not provided
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}');")
        cols = cursor.fetchall()
        conn.close()
        ts_cols = [c[1] for c in cols if c[1].lower() == 'timestamp' or 'date' in (c[2] or '').lower()]
        if not ts_cols:
            logging.error("No suitable timestamp column found in table '%s'", table_name)
            sys.exit(1)
        timestamp_field = ts_cols[0]
        logging.info("Detected timestamp field: %s", timestamp_field)
    else:
        timestamp_field = timestamp_col
        logging.info("Using user-supplied timestamp column: %s", timestamp_field)

    logging.info("Starting continuous upload every %d seconds, initial timestamp=%s", interval, last_ts)
    base_name = sqlite_path.stem
    while True:
        try:
            # Read new data since last timestamp using introspected schema
            sql = f"SELECT * FROM {table_name} WHERE {timestamp_field} > ? ORDER BY {timestamp_field}"
            conn = sqlite3.connect(str(sqlite_path))
            df = pd.read_sql_query(sql, conn, params=[last_ts.isoformat()])
            conn.close()
            if df.empty:
                logging.info("No new records since %s", last_ts)
            else:
                # Append to Delta table
                logging.info("Appending %d new records to Delta table %s", len(df), storage_uri)
                # Pass AWS_REGION via storage_options if set
                storage_opts = {}
                if os.getenv('AWS_REGION'):
                    storage_opts['AWS_REGION'] = os.getenv('AWS_REGION')
                write_deltalake(
                    table_or_uri=storage_uri,
                    data=df,
                    mode='append',
                    storage_options=storage_opts
                )
                # Update state timestamp
                last_ts = df[timestamp_field].max()
                with open(state_file, 'w') as f:
                    json.dump({'last_upload': last_ts.isoformat()}, f)
        except KeyboardInterrupt:
            logging.info("Interrupted by user, exiting.")
            break
        except Exception as e:
            logging.error("Error in upload cycle: %s", e, exc_info=True)
        if once:
            break
        time.sleep(interval)

if __name__ == '__main__':
    main()
