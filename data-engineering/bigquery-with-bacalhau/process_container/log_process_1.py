#!/usr/bin/env python3
import argparse
import ipaddress
import os
import re
import warnings
from datetime import datetime

import duckdb
import pandas as pd
import yaml
from faker import Faker
from google.cloud import bigquery
from google.oauth2 import service_account

# Initialize Faker
fake = Faker()

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


def main(input_file):
    if CREDENTIALS_PATH == "":
        raise ValueError("CREDENTIALS_PATH environment variable is not set")

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(f"Credentials file not found at {CREDENTIALS_PATH}")

    project_id = os.environ.get("PROJECT_ID", "")
    if project_id == "":
        raise ValueError("PROJECT_ID environment variable is not set")

    dataset = os.environ.get("DATASET", "log_analytics")
    table = os.environ.get("TABLE", "log_results")

    # Load credentials and create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    bq_client = bigquery.Client(credentials=credentials)

    # Create DuckDB connection and load log file
    con = duckdb.connect()

    # Load and preprocess the log data
    metadata = get_metadata()
    df = con.execute(
        """
            WITH logs as (
                FROM read_csv_auto(?, delim=' ')
                SELECT 
                    column0 as ip,
                    -- ignore column1, it's just a hyphen
                    column2 as user_id,
                    column3.replace('[','').replace(']','').strptime('%Y-%m-%dT%H:%M:%S.%f%z') as ts,
                    column4 as request,
                    column5 as status,
                    column6 as bytes,
                    column7 as referer,
                    column8 as user_agent,
            )
            SELECT * FROM logs
            """,
        [input_file],
    ).df()

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["ts"], format="%Y-%m-%dT%H:%M:%S.%f%z")
    df = df.drop(columns=["ts"])

    # Parse request into method, path, protocol
    request_parts = df["request"].apply(parse_request)
    df["method"] = request_parts.str[0]
    df["path"] = request_parts.str[1]
    df["protocol"] = request_parts.str[2]
    df = df.drop(columns=["request"])

    # Add status category
    df["status_category"] = df["status"].apply(get_status_category)

    # Add metadata columns
    df["project_id"] = metadata["project_id"]
    df["region"] = metadata["region"]
    df["nodeName"] = metadata["node_name"]
    df["hostname"] = metadata["node_name"]
    df["provider"] = metadata["provider"]
    df["sync_time"] = datetime.utcnow()

    # Upload to BigQuery
    table_id = f"{project_id}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        schema=EXPECTED_SCHEMA,
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",
    )

    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"Uploaded {len(df)} rows to {table_id}")

    # Print sample of processed data
    print("\nSample of processed data:")
    print(
        df[
            [
                "timestamp",
                "method",
                "path",
                "status",
                "status_category",
                "bytes",
                "referer",
                "user_agent",
            ]
        ]
        .head()
        .to_string()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    args = parser.parse_args()
    main(args.input_file)
