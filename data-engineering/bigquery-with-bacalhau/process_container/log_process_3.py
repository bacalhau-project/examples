#!/usr/bin/env python3
import argparse
import ipaddress
import os
import warnings
from datetime import datetime

import duckdb
import pandas as pd
import yaml
from google.cloud import bigquery
from google.oauth2 import service_account

# Suppress numpy deprecation warning from DuckDB
warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core")

# Expected schemas for BigQuery tables
EMERGENCY_SCHEMA = [
    bigquery.SchemaField("project_id", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("nodeName", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("hostname", "STRING"),
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
    bigquery.SchemaField("version", "STRING"),
    bigquery.SchemaField("message", "STRING"),
    bigquery.SchemaField("remote_log_id", "STRING"),
    bigquery.SchemaField("alert_level", "STRING"),
    bigquery.SchemaField("ip", "STRING"),
    bigquery.SchemaField("sync_time", "TIMESTAMP"),
]

AGGREGATES_SCHEMA = [
    bigquery.SchemaField("project_id", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("nodeName", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("hostname", "STRING"),
    bigquery.SchemaField("time_window", "TIMESTAMP"),
    bigquery.SchemaField("ok_count", "INT64"),
    bigquery.SchemaField("redirect_count", "INT64"),
    bigquery.SchemaField("not_found_count", "INT64"),
    bigquery.SchemaField("system_error_count", "INT64"),
    bigquery.SchemaField("total_count", "INT64"),
    bigquery.SchemaField("total_bytes", "INT64"),
    bigquery.SchemaField("avg_bytes", "FLOAT64"),
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
    # Load configuration
    project_id = os.environ.get("PROJECT_ID", "")
    if project_id == "":
        raise ValueError("PROJECT_ID environment variable is not set")

    dataset = os.environ.get("DATASET", "log_analytics")
    table = os.environ.get("TABLE", "log_results")

    credentials_path = os.environ.get("CREDENTIALS_PATH", "credentials.json")

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
                    column8 as user_agent
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
    df["project_id"] = project_id
    df["region"] = metadata["region"]
    df["nodeName"] = metadata["node_name"]
    df["hostname"] = metadata["node_name"]
    df["provider"] = metadata["provider"]
    df["sync_time"] = datetime.utcnow()

    # Handle emergency logs (status 500+)
    emergency_df = df[df["status"] >= 500].copy()
    if len(emergency_df) > 0:
        # Prepare emergency logs according to schema
        emergency_df["version"] = "1.0"
        emergency_df["message"] = emergency_df.apply(
            lambda x: f"{x['method']} {x['path']} returned {x['status']}", axis=1
        )
        emergency_df["remote_log_id"] = f"{project_id}.log_analytics.emergency_logs"
        emergency_df["alert_level"] = "ERROR"

        # Ensure correct columns and order
        emergency_df = emergency_df[[col.name for col in EMERGENCY_SCHEMA]]

        # Upload emergency logs to BigQuery
        emergency_table_id = f"{project_id}.{dataset}.emergency_logs"
        emergency_job_config = bigquery.LoadJobConfig(
            schema=EMERGENCY_SCHEMA,
            write_disposition="WRITE_APPEND",
            create_disposition="CREATE_NEVER",
        )
        job = bq_client.load_table_from_dataframe(
            emergency_df, emergency_table_id, job_config=emergency_job_config
        )
        job.result()
        print(f"Uploaded {len(emergency_df)} emergency logs to {emergency_table_id}")

    # Aggregate logs by time window
    df["time_window"] = pd.to_datetime(df["timestamp"]).dt.floor("h")
    agg_df = (
        df.groupby(["time_window"])
        .agg(
            ok_count=("status_category", lambda x: (x == "OK").sum()),
            redirect_count=("status_category", lambda x: (x == "Redirect").sum()),
            not_found_count=("status_category", lambda x: (x == "Not Found").sum()),
            system_error_count=(
                "status_category",
                lambda x: (x == "SystemError").sum(),
            ),
            total_count=("status_category", "count"),
            total_bytes=("bytes", "sum"),
            avg_bytes=("bytes", "mean"),
        )
        .reset_index()
    )

    # Add metadata to aggregated data
    agg_df["project_id"] = project_id
    agg_df["region"] = metadata["region"]
    agg_df["nodeName"] = metadata["node_name"]
    agg_df["hostname"] = metadata["node_name"]
    agg_df["provider"] = metadata["provider"]

    # Ensure correct columns and order for aggregates
    agg_df = agg_df[[col.name for col in AGGREGATES_SCHEMA]]

    # Upload aggregated data to BigQuery
    agg_table_id = f"{project_id}.{dataset}.log_aggregates"
    agg_job_config = bigquery.LoadJobConfig(
        schema=AGGREGATES_SCHEMA,
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",
    )

    job = bq_client.load_table_from_dataframe(
        agg_df, agg_table_id, job_config=agg_job_config
    )
    job.result()
    print(f"Uploaded {len(agg_df)} aggregated log entries to {agg_table_id}")

    # Print sample of aggregated data
    print("\nSample of aggregated data:")
    print(
        agg_df[
            [
                "time_window",
                "ok_count",
                "redirect_count",
                "not_found_count",
                "system_error_count",
                "total_count",
                "total_bytes",
                "avg_bytes",
            ]
        ]
        .head()
        .to_string()
    )

    if len(emergency_df) > 0:
        print("\nSample of emergency logs:")
        print(
            emergency_df[
                [
                    "timestamp",
                    "message",
                    "alert_level",
                    "ip",
                ]
            ]
            .head()
            .to_string()
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and aggregate log data")
    parser.add_argument("input_file", help="Path to the input log file")
    args = parser.parse_args()
    main(args.input_file)
