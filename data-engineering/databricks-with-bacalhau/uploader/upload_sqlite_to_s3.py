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
from pathlib import Path

import boto3
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export sensor log from SQLite to Parquet and upload to S3"
    )
    parser.add_argument(
        "--sqlite", required=True,
        help="Path to the SQLite database file"
    )
    parser.add_argument(
        "--table", default=None,
        help="Name of the table or SQL query to read (use --query to specify a custom SQL)"
    )
    parser.add_argument(
        "--query", default=None,
        help="Custom SQL query to read data"
    )
    parser.add_argument(
        "--bucket", required=True,
        help="S3 bucket name to upload to"
    )
    parser.add_argument(
        "--prefix", default="",
        help="Key prefix (folder) in the bucket"
    )
    parser.add_argument(
        "--region", default=None,
        help="AWS region (for S3 client initialization)"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing object if it exists"
    )
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        logging.error(f"SQLite file not found: {sqlite_path}")
        sys.exit(1)

    logging.info("Reading data from SQLite: %s", sqlite_path)
    try:
        df = read_data(str(sqlite_path), args.query, args.table)
    except Exception as e:
        logging.error("Failed to read from SQLite: %s", e)
        sys.exit(1)

    if df.empty:
        logging.warning("No data read from source. Exiting.")
        sys.exit(0)

    logging.info("Converting DataFrame with %d rows to Parquet", len(df))
    buffer = io.BytesIO()
    try:
        df.to_parquet(buffer, index=False)
    except Exception as e:
        logging.error("Failed to serialize to Parquet: %s", e)
        sys.exit(1)

    base_name = sqlite_path.stem
    key_name = f"{args.prefix.rstrip('/')}/{base_name}.parquet" if args.prefix else f"{base_name}.parquet"
    key_name = key_name.lstrip('/')
    logging.info("Uploading Parquet to s3://%s/%s", args.bucket, key_name)

    try:
        upload_buffer(buffer, args.bucket, key_name, args.region, overwrite=args.overwrite)
        logging.info("Upload successful")
    except Exception as e:
        logging.error("Failed to upload to S3: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()