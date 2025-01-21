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
    bigquery.SchemaField("remote_log_id", "STRING"),
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
    bigquery.SchemaField("version", "STRING"),
    bigquery.SchemaField("message", "STRING"),
    bigquery.SchemaField("alert_level", "STRING"),
    bigquery.SchemaField("hostname", "STRING"),
    bigquery.SchemaField("provider", "STRING"),
    bigquery.SchemaField("ip", "STRING"),
]


def generate_fake_ip():
    """Generate a fake IP address."""
    return fake.ipv4()


def get_metadata():
    """Get or generate metadata about the current environment."""
    return {
        "project_id": os.environ.get("PROJECT_ID", "unknown"),
        "region": os.environ.get("REGION", "unknown"),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "provider": os.environ.get("CLOUD_PROVIDER", "unknown"),
    }


def sanitize_ip(ip_str):
    """
    Sanitize IP address by masking the host portion while preserving network information.
    For IPv4: Preserve the first three octets
    For IPv6: Preserve the first four segments (network portion)
    """
    if not ip_str:
        return None
    try:
        ip = ipaddress.ip_address(ip_str)
        if isinstance(ip, ipaddress.IPv4Address):
            network = ipaddress.ip_network(f"{ip}/24", strict=False)
            return str(network.network_address)
        else:  # IPv6
            # Get the /64 network address
            network = ipaddress.ip_network(f"{ip}/64", strict=False)
            return str(network.network_address)
    except:
        return None


def main(input_file, query):
    print(f"Processing {input_file} with query: {query}")

    # Load credentials and create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    bq_client = bigquery.Client(credentials=credentials)

    # Create DuckDB connection and load log file
    con = duckdb.connect()

    # Register helper functions
    con.create_function(
        "extract_alert_level",
        lambda msg: msg.split("]")[0].split("[")[-1].strip()
        if "[" in msg and "]" in msg
        else "INFO",
        ["VARCHAR"],
        "VARCHAR",
        null_handling="SPECIAL",
    )

    # Register IP generation and sanitization functions
    con.create_function(
        "generate_fake_ip",
        generate_fake_ip,
        [],
        "VARCHAR",
        null_handling="SPECIAL",
    )

    con.create_function(
        "sanitize_ip",
        sanitize_ip,
        ["VARCHAR"],
        "VARCHAR",
        null_handling="SPECIAL",
    )

    # Load and preprocess the log data
    metadata = get_metadata()
    con.execute(
        """
        CREATE TABLE log_data AS 
        SELECT 
            ? || '.log_analytics.log_results' as remote_log_id,
            CAST(REGEXP_REPLACE("@timestamp", 'Z$', '') AS TIMESTAMP) as timestamp,
            "@version" as version,
            message,
            extract_alert_level(message) as alert_level
        FROM read_json_auto(?)
    """,
        [metadata["project_id"], input_file],
    )

    # Execute the user's query
    df = con.execute(query).df()

    # Add metadata columns
    df["project_id"] = metadata["project_id"]
    df["region"] = metadata["region"]
    df["nodeName"] = metadata["node_name"]
    df["hostname"] = metadata["node_name"]
    df["provider"] = metadata["provider"]
    df["sync_time"] = datetime.utcnow()

    # Generate and sanitize IPs for each row
    df["ip"] = [generate_fake_ip() for _ in range(len(df))]

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

    # Print sample of processed data in debug mode
    print("\nSample of processed data:")
    print(df.head().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    parser.add_argument("query", help="DuckDB query to execute")
    args = parser.parse_args()
    main(args.input_file, args.query)
