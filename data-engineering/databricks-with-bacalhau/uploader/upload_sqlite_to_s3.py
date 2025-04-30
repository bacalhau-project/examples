#!/usr/bin/env python3
"""
Read sensor logs from a SQLite database, convert to an in-memory Parquet file,
and upload to AWS S3.
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

import boto3
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Continuously export new sensor log entries from SQLite to Parquet and upload to S3"
    )
    parser.add_argument("--sqlite", required=True, help="Path to the SQLite database file")
    parser.add_argument("--table", required=True, help="Name of the table to read (incremental by timestamp)")
    parser.add_argument("--timestamp-field", default="timestamp", help="Column name for the upload timestamp")
    parser.add_argument("--bucket", required=True, help="S3 bucket name to upload to")
    parser.add_argument("--prefix", default="", help="Key prefix (folder) in the bucket")
    parser.add_argument("--region", default=None, help="AWS region (for S3 client initialization)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing object if it exists")
    parser.add_argument("--state-dir", default=os.getenv("STATE_DIR", "/state"), help="Directory to store last upload state")
    parser.add_argument("--interval", type=int, default=int(os.getenv("UPLOAD_INTERVAL", "300")), help="Seconds between upload cycles")
    return parser.parse_args()


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


def upload_buffer(buffer, bucket, key, region, overwrite=False):
    s3 = boto3.client('s3', region_name=region) if region else boto3.client('s3')
    extra_args = {}
    if not overwrite:
        extra_args['ACL'] = 'private'
    buffer.seek(0)
    s3.upload_fileobj(buffer, bucket, key, ExtraArgs=extra_args)


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        logging.error(f"SQLite file not found: {sqlite_path}")
        sys.exit(1)

    # Prepare state file
    state_dir = Path(args.state_dir)
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

    logging.info("Starting continuous upload every %d seconds, initial timestamp=%s", args.interval, last_ts)
    base_name = sqlite_path.stem
    while True:
        try:
            # Read new data
            query = f"SELECT * FROM {args.table} WHERE {args.timestamp_field} > ? ORDER BY {args.timestamp_field}"
            conn = sqlite3.connect(str(sqlite_path))
            df = pd.read_sql_query(query, conn, params=[last_ts.isoformat()])
            conn.close()
            if df.empty:
                logging.info("No new records since %s", last_ts)
            else:
                # Convert to Parquet
                start_ts = df[args.timestamp_field].min()
                end_ts = df[args.timestamp_field].max()
                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False)

                # Upload with timestamped filename
                filename = f"{base_name}_{start_ts.strftime('%Y%m%dT%H%M%SZ')}_{end_ts.strftime('%Y%m%dT%H%M%SZ')}.parquet"
                key_name = f"{args.prefix.rstrip('/')}/{filename}" if args.prefix else filename
                key_name = key_name.lstrip('/')
                logging.info("Uploading %d records to s3://%s/%s", len(df), args.bucket, key_name)
                upload_buffer(buffer, args.bucket, key_name, args.region, overwrite=args.overwrite)
                logging.info("Upload successful: %s", key_name)

                # Update state
                last_ts = end_ts
                with open(state_file, 'w') as f:
                    json.dump({'last_upload': last_ts.isoformat()}, f)
        except KeyboardInterrupt:
            logging.info("Interrupted by user, exiting.")
            break
        except Exception as e:
            logging.error("Error in upload cycle: %s", e, exc_info=True)
        # Wait before next cycle
        time.sleep(args.interval)

if __name__ == '__main__':
    main()