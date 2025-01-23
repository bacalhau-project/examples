#!/usr/bin/env python3
import argparse
import os
from datetime import datetime

import duckdb
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account


def main(input_file):
    credentials_path = os.environ.get("CREDENTIALS_PATH", "credentials.json")
    project_id = os.environ.get("PROJECT_ID", "")
    if project_id == "":
        raise ValueError("PROJECT_ID environment variable is not set")

    dataset = os.environ.get("DATASET", "log_analytics")
    table = os.environ.get("TABLE", "raw_logs")

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"Credentials file not found at {credentials_path}")

    # Load credentials and create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    bq_client = bigquery.Client(credentials=credentials)

    # Create DuckDB connection and load log file
    con = duckdb.connect()

    df = con.execute(
        """
        SELECT 
            column0 AS raw_line
        FROM read_csv(?, delim='\n', columns={'column0': 'VARCHAR'}, header=false)
        """,
        [input_file],
    ).df()

    # Add upload timestamp
    df["upload_time"] = datetime.utcnow()

    # Add timestamp
    df["timestamp"] = df["raw_line"].str.extract(
        r"^\S+ \S+ \S+ \[(.*?)\]", expand=False
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%dT%H:%M:%S.%f%z")

    # Upload to BigQuery
    table_id = f"{project_id}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("raw_line", "STRING"),
            bigquery.SchemaField("upload_time", "TIMESTAMP"),
        ],
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",
    )

    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"Uploaded {len(df)} raw log lines to {table_id}")

    # Print sample of uploaded data
    print("\nSample of uploaded data:")
    print(df.head().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload raw logs to BigQuery")
    parser.add_argument("input_file", help="Path to the input log file")
    args = parser.parse_args()
    main(args.input_file)
