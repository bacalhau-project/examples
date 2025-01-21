#!/usr/bin/env python3
import argparse
import ipaddress
import os
import warnings
from datetime import datetime

import duckdb
import pandas as pd
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
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
AGGREGATE_LOGS = os.environ.get("AGGREGATE_LOGS", "false").lower() == "true"

# Expected schemas for BigQuery tables
SCHEMAS = {
    "log_results": [
        bigquery.SchemaField("project_id", "STRING"),
        bigquery.SchemaField("region", "STRING"),
        bigquery.SchemaField("nodeName", "STRING"),
        bigquery.SchemaField("sync_time", "TIMESTAMP"),
        bigquery.SchemaField("remote_log_id", "STRING"),
        bigquery.SchemaField("timestamp", "TIMESTAMP"),
        bigquery.SchemaField("version", "STRING"),
        bigquery.SchemaField("message", "STRING"),
        bigquery.SchemaField("provider", "STRING"),
        bigquery.SchemaField("hostname", "STRING"),
        bigquery.SchemaField("alert_level", "STRING"),
        bigquery.SchemaField("source_module", "STRING"),
        bigquery.SchemaField("event_id", "STRING"),
        bigquery.SchemaField("ip", "STRING"),
    ],
    "emergency_logs": [  # Same schema as log_results
        bigquery.SchemaField("project_id", "STRING"),
        bigquery.SchemaField("region", "STRING"),
        bigquery.SchemaField("nodeName", "STRING"),
        bigquery.SchemaField("sync_time", "TIMESTAMP"),
        bigquery.SchemaField("remote_log_id", "STRING"),
        bigquery.SchemaField("timestamp", "TIMESTAMP"),
        bigquery.SchemaField("version", "STRING"),
        bigquery.SchemaField("message", "STRING"),
        bigquery.SchemaField("provider", "STRING"),
        bigquery.SchemaField("hostname", "STRING"),
        bigquery.SchemaField("alert_level", "STRING"),
        bigquery.SchemaField("source_module", "STRING"),
        bigquery.SchemaField("event_id", "STRING"),
        bigquery.SchemaField("ip", "STRING"),
    ],
    "log_aggregates": [
        bigquery.SchemaField("project_id", "STRING"),
        bigquery.SchemaField("region", "STRING"),
        bigquery.SchemaField("nodeName", "STRING"),
        bigquery.SchemaField("provider", "STRING"),
        bigquery.SchemaField("hostname", "STRING"),
        bigquery.SchemaField("time_window", "TIMESTAMP"),
        bigquery.SchemaField("info_count", "INT64"),
        bigquery.SchemaField("warn_count", "INT64"),
        bigquery.SchemaField("error_count", "INT64"),
        bigquery.SchemaField("critical_count", "INT64"),
        bigquery.SchemaField("emergency_count", "INT64"),
        bigquery.SchemaField("alert_count", "INT64"),
        bigquery.SchemaField("debug_count", "INT64"),
        bigquery.SchemaField("total_count", "INT64"),
    ],
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
    except Exception as e:
        print(f"Error sanitizing IP: {e}")
        return None


def validate_table_schema(client, table_id, expected_schema):
    """Validate if a table exists and has the expected schema."""
    try:
        table = client.get_table(table_id)
        actual_schema = table.schema

        schema_matches = True
        missing_fields = []
        mismatched_fields = []

        expected_fields = {field.name: field for field in expected_schema}
        actual_fields = {field.name: field for field in actual_schema}

        for name, expected_field in expected_fields.items():
            if name not in actual_fields:
                missing_fields.append(name)
            elif actual_fields[name].field_type != expected_field.field_type:
                mismatched_fields.append(name)

        return {
            "exists": True,
            "schema_matches": len(missing_fields) == 0 and len(mismatched_fields) == 0,
            "missing_fields": missing_fields,
            "mismatched_fields": mismatched_fields,
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


def get_metadata():
    """Get or generate metadata about the current environment."""
    return {
        "project_id": os.environ.get("PROJECT_ID", "unknown"),
        "region": os.environ.get("REGION", "unknown"),
        "node_name": os.environ.get("NODE_NAME", "unknown"),
        "provider": os.environ.get("CLOUD_PROVIDER", "unknown"),
    }


def generate_fake_ip():
    """Generate a fake IP address."""
    return fake.ipv4()


def main(input_file, query):
    print(f"Processing {input_file} with query: {query}")

    # Load credentials and create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    bq_client = bigquery.Client(credentials=credentials)

    # Validate table schemas if in debug mode
    metadata = get_metadata()
    if DEBUG:
        for table_name, schema in SCHEMAS.items():
            table_id = f"{metadata['project_id']}.log_analytics.{table_name}"
            print(f"\nValidating {table_name} schema:")
            print("-" * (20 + len(table_name)))
            schema_validation = validate_table_schema(bq_client, table_id, schema)
            if schema_validation["exists"]:
                if schema_validation["schema_matches"]:
                    print("✓ Table exists with correct schema")
                else:
                    print("⚠ Table exists but schema mismatch")
                    if schema_validation["missing_fields"]:
                        print(
                            f"  Missing fields: {', '.join(schema_validation['missing_fields'])}"
                        )
                    if schema_validation["mismatched_fields"]:
                        print(
                            f"  Mismatched fields: {', '.join(schema_validation['mismatched_fields'])}"
                        )
            else:
                print("✗ Table does not exist")
                if "error" in schema_validation:
                    print(f"  Error: {schema_validation['error']}")

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

    con.create_function(
        "extract_source_module",
        lambda msg: msg.split("]")[1].split("[")[0].strip()
        if len(msg.split("]")) > 1 and "[" in msg.split("]")[1]
        else "unknown",
        ["VARCHAR"],
        "VARCHAR",
        null_handling="SPECIAL",
    )

    con.create_function(
        "extract_ip",
        lambda msg: (
            msg.split("ip=")[1].split()[0]
            if "ip=" in msg
            else (msg.split("addr=")[1].split()[0] if "addr=" in msg else None)
        ),
        ["VARCHAR"],
        "VARCHAR",
        null_handling="SPECIAL",
    )

    con.create_function(
        "sanitize_ip", sanitize_ip, ["VARCHAR"], "VARCHAR", null_handling="SPECIAL"
    )

    # Load and preprocess the log data
    con.execute(
        """
        CREATE TABLE log_data AS 
        SELECT 
            ? || '.log_analytics.log_results' as remote_log_id,
            CAST(REGEXP_REPLACE("@timestamp", 'Z$', '') AS TIMESTAMP) as timestamp,
            "@version" as version,
            message,
            extract_alert_level(message) as alert_level,
            extract_source_module(message) as source_module,
            CAST(uuid() AS VARCHAR) as event_id
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
    df["ip"] = [sanitize_ip(generate_fake_ip()) for _ in range(len(df))]

    # Handle emergency logs (CRITICAL, EMERGENCY, or ALERT level)
    emergency_df = df[
        df["alert_level"].str.upper().isin(["CRITICAL", "EMERGENCY", "ALERT"])
    ].copy()  # Add .copy() to avoid SettingWithCopyWarning
    if not emergency_df.empty:
        table_id = f"{metadata['project_id']}.log_analytics.emergency_logs"
        job_config = bigquery.LoadJobConfig(
            schema=SCHEMAS["emergency_logs"],
            write_disposition="WRITE_APPEND",
            create_disposition="CREATE_NEVER",
        )
        job = bq_client.load_table_from_dataframe(
            emergency_df, table_id, job_config=job_config
        )
        job.result()
        print(f"Uploaded {len(emergency_df)} emergency logs to {table_id}")
        print("\nSample of emergency logs:")
        print(emergency_df[["timestamp", "alert_level", "message"]].head().to_string())

    # Handle log aggregation
    # Convert timestamp to datetime if it isn't already
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Create time windows (1-minute intervals)
    df["time_window"] = df["timestamp"].dt.floor("1min")

    # Group by metadata and time window, count by alert level
    agg_df = (
        df.groupby(
            [
                "project_id",
                "region",
                "nodeName",
                "provider",
                "hostname",
                "time_window",
            ]
        )
        .agg(
            info_count=("alert_level", lambda x: sum(x.str.upper() == "INFO")),
            warn_count=("alert_level", lambda x: sum(x.str.upper() == "WARN")),
            error_count=("alert_level", lambda x: sum(x.str.upper() == "ERROR")),
            critical_count=("alert_level", lambda x: sum(x.str.upper() == "CRITICAL")),
            emergency_count=(
                "alert_level",
                lambda x: sum(x.str.upper() == "EMERGENCY"),
            ),
            alert_count=("alert_level", lambda x: sum(x.str.upper() == "ALERT")),
            debug_count=("alert_level", lambda x: sum(x.str.upper() == "DEBUG")),
        )
        .reset_index()
    )

    # Calculate total count
    agg_df["total_count"] = agg_df[
        [
            "info_count",
            "warn_count",
            "error_count",
            "critical_count",
            "emergency_count",
            "alert_count",
            "debug_count",
        ]
    ].sum(axis=1)

    # Upload aggregated data
    table_id = f"{metadata['project_id']}.log_analytics.log_aggregates"
    job_config = bigquery.LoadJobConfig(
        schema=SCHEMAS["log_aggregates"],
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",
    )
    job = bq_client.load_table_from_dataframe(agg_df, table_id, job_config=job_config)
    job.result()
    print(f"Uploaded {len(agg_df)} aggregated log entries to {table_id}")
    print("\nSample of aggregated data:")
    print(
        agg_df[
            [
                "time_window",
                "total_count",
                "error_count",
                "critical_count",
                "emergency_count",
            ]
        ]
        .head()
        .to_string()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    parser.add_argument("query", help="DuckDB query to execute")
    args = parser.parse_args()
    main(args.input_file, args.query)
