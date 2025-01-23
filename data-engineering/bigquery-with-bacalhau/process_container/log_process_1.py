#!/usr/bin/env python3
import argparse
import ipaddress
import os
import warnings
from datetime import datetime

import duckdb
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
]


def get_metadata():
    """Get or generate metadata about the current environment."""
    return {
        "project_id": os.environ.get("PROJECT_ID", "unknown"),
        "region": os.environ.get("REGION", "unknown"),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "provider": os.environ.get("CLOUD_PROVIDER", "unknown"),
    }


def main(input_file):
    # Load credentials and create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=["https://www.googleapis.com/auth/bigquery"]
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
                    column2 as user,
                    column3.replace('[','').replace(' ]','').strptime('%Y/%m/%d:%H:%M:%S') as ts,
                    column4 as http_type,
                    column5 as route,
                    column6 as http_spec,
                    column7 as http_status,
                    column8 as value
            )
            SELECT * FROM logs
            """,
        [input_file],
    ).df()

    # Add metadata columns
    df["project_id"] = metadata["project_id"]
    df["region"] = metadata["region"]
    df["nodeName"] = metadata["node_name"]
    df["hostname"] = metadata["node_name"]
    df["provider"] = metadata["provider"]
    df["sync_time"] = datetime.utcnow()

    # Upload to BigQuery
    table_id = f"{metadata['project_id']}.log_analytics.log_results"
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
    print(df[["timestamp", "method", "path", "status", "bytes"]].head().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    args = parser.parse_args()
    main(args.input_file)
