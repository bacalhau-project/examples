#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "duckdb",
#     "requests",
#     "natsort",
#     "google-cloud-storage",
#     "google-cloud-bigquery",
#     "ipaddress",
#     "numpy",
#     "pandas",
#     "pyarrow",
#     "faker",
# ]
# ///

import argparse
import ipaddress
import json
import os
import tempfile
import warnings
from datetime import datetime
from pathlib import Path

# Suppress numpy deprecation warning from DuckDB
warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core")

import duckdb
import pandas as pd
import requests
from faker import Faker
from google.cloud import bigquery
from google.oauth2 import service_account
from natsort import natsorted, ns

# Initialize Faker
fake = Faker()

# Environment variable configuration with defaults
LOGS_DIR = os.environ.get("LOGS_DIR", "/var/log/logs_to_process")
CREDENTIALS_PATH = os.environ.get(
    "CREDENTIALS_PATH", os.path.join(LOGS_DIR, "log_uploader_credentials.json")
)
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# Expected schemas for BigQuery tables
EXPECTED_SCHEMAS = {
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
    ],
    "log_aggregates": [
        bigquery.SchemaField("project_id", "STRING"),
        bigquery.SchemaField("region", "STRING"),
        bigquery.SchemaField("nodeName", "STRING"),
        bigquery.SchemaField("provider", "STRING"),
        bigquery.SchemaField("hostname", "STRING"),
        bigquery.SchemaField("time_window", "TIMESTAMP"),
        bigquery.SchemaField("info_count", "INTEGER"),
        bigquery.SchemaField("warn_count", "INTEGER"),
        bigquery.SchemaField("error_count", "INTEGER"),
        bigquery.SchemaField("critical_count", "INTEGER"),
        bigquery.SchemaField("emergency_count", "INTEGER"),
        bigquery.SchemaField("alert_count", "INTEGER"),
        bigquery.SchemaField("debug_count", "INTEGER"),
        bigquery.SchemaField("total_count", "INTEGER"),
    ],
    "emergency_logs": [
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
    ],
}


def debug_log(message):
    """Print debug messages if DEBUG is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}")


def validate_table_schema(client, table_id, expected_schema):
    """Validate if a table exists and has the expected schema."""
    try:
        table = client.get_table(table_id)
        actual_schema = table.schema

        # Compare schemas
        schema_matches = True
        missing_fields = []
        mismatched_fields = []

        expected_fields = {field.name: field for field in expected_schema}
        actual_fields = {field.name: field for field in actual_schema}

        for name, expected_field in expected_fields.items():
            if name not in actual_fields:
                missing_fields.append(name)
            elif (
                actual_fields[name].field_type != expected_field.field_type
                or actual_fields[name].mode != expected_field.mode
            ):
                mismatched_fields.append(name)

        return {
            "exists": True,
            "schema_matches": len(missing_fields) == 0 and len(mismatched_fields) == 0,
            "missing_fields": missing_fields,
            "mismatched_fields": mismatched_fields,
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


def sanitize_ip(ip_str):
    """Sanitize IP address by zeroing out last octet for IPv4 or last 64 bits for IPv6."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if isinstance(ip, ipaddress.IPv4Address):
            # Convert to string and replace last octet with 0
            parts = str(ip).split(".")
            parts[-1] = "0"
            return ".".join(parts)
        else:
            # For IPv6, zero out the last 64 bits
            parts = str(ip).split(":")
            return ":".join(parts[:4]) + ":0:0:0:0"
    except:
        return None


def getInstanceMetadata(metadataName):
    url = f"http://metadata.google.internal/computeMetadata/v1/instance/{metadataName}"
    return getMetadata(url)


def getProjectMetadata(metadataName):
    url = f"http://metadata.google.internal/computeMetadata/v1/project/{metadataName}"
    return getMetadata(url)


def getMetadata(metadata_server_url):
    metadata_server_token_url = (
        "http://metadata/computeMetadata/v1/instance/service-accounts/default/token"
    )
    token_request_headers = {"Metadata-Flavor": "Google"}
    token_response = requests.get(
        metadata_server_token_url, headers=token_request_headers
    )
    jwt = token_response.json()["access_token"]

    metadata_request_headers = {
        "Metadata-Flavor": "Google",
        "Authorization": f"Bearer {jwt}",
    }

    return requests.get(metadata_server_url, headers=metadata_request_headers).text


def detect_cloud_provider():
    """Detect the cloud provider by trying metadata endpoints."""

    def try_gcp():
        try:
            headers = {"Metadata-Flavor": "Google"}
            response = requests.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/id",
                headers=headers,
                timeout=1,
            )
            if response.status_code == 200:
                return "gcp"
        except:
            pass
        return None

    def try_aws():
        try:
            # Get IMDSv2 token first
            token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
            token = requests.put(
                "http://169.254.169.254/latest/api/token",
                headers=token_headers,
                timeout=1,
            ).text

            headers = {"X-aws-ec2-metadata-token": token}
            response = requests.get(
                "http://169.254.169.254/latest/meta-data/instance-id",
                headers=headers,
                timeout=1,
            )
            if response.status_code == 200:
                return "aws"
        except:
            pass
        return None

    def try_azure():
        try:
            headers = {"Metadata": "true"}
            response = requests.get(
                "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
                headers=headers,
                timeout=1,
            )
            if response.status_code == 200:
                return "azure"
        except:
            pass
        return None

    # Try each provider
    provider = try_gcp() or try_aws() or try_azure() or "unknown"
    return provider


def generate_fake_ips():
    """Generate a fake public and private IP."""
    return (
        fake.ipv4(),
        f"10.{fake.random_int(0, 255)}.{fake.random_int(0, 255)}.{fake.random_int(1, 254)}",
    )


def main(input_file, query):
    debug_log(f"Starting with input_file={input_file}, query={query}")
    debug_log(f"Using LOGS_DIR={LOGS_DIR}")
    debug_log(f"Using CREDENTIALS_PATH={CREDENTIALS_PATH}")

    usingTempFile = False
    # If file is .gz, decompress it into a temporary file
    if input_file.endswith(".gz"):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as temp:
            os.system(f"gunzip -c {input_file} > {temp.name}")
            input_file = temp.name
            usingTempFile = True

    # Load credentials from the configured path
    debug_log(f"Loading credentials from {CREDENTIALS_PATH}")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
    except Exception as e:
        debug_log(f"Error loading credentials: {str(e)}")
        raise

    # Create BigQuery client
    bq_client = bigquery.Client(credentials=credentials)

    # Generate metadata with override support
    try:
        projectID = os.environ.get("PROJECT_ID") or getProjectMetadata("project-id")
        region = os.environ.get("REGION") or getInstanceMetadata("zone").split("/")[3]
        nodeName = os.environ.get("NODE_NAME") or getInstanceMetadata("name")
        provider = os.environ.get("CLOUD_PROVIDER") or detect_cloud_provider()
        debug_log(
            f"Using metadata: project={projectID}, region={region}, node={nodeName}, provider={provider}"
        )
    except Exception as e:
        debug_log(f"Error getting metadata: {str(e)}, using defaults")
        projectID = os.environ.get("PROJECT_ID", "unknown")
        region = os.environ.get("REGION", "unknown")
        nodeName = os.environ.get("NODE_NAME", "unknown")
        provider = os.environ.get("CLOUD_PROVIDER", "unknown")

    # Validate BigQuery tables only in debug mode
    if DEBUG:
        dataset_id = f"{projectID}.log_analytics"
        print("\nValidating BigQuery Tables:")
        print("---------------------------")

        for table_name, expected_schema in EXPECTED_SCHEMAS.items():
            table_id = f"{dataset_id}.{table_name}"
            result = validate_table_schema(bq_client, table_id, expected_schema)

            if result["exists"]:
                if result["schema_matches"]:
                    print(f"✓ {table_name}: Table exists with correct schema")
                else:
                    print(f"⚠ {table_name}: Table exists but schema mismatch")
                    if result["missing_fields"]:
                        print(
                            f"  Missing fields: {', '.join(result['missing_fields'])}"
                        )
                    if result["mismatched_fields"]:
                        print(
                            f"  Mismatched fields: {', '.join(result['mismatched_fields'])}"
                        )
            else:
                print(f"✗ {table_name}: Table does not exist")
                if "error" in result:
                    print(f"  Error: {result['error']}")

    # Create DuckDB connection and load log file
    debug_log("Creating DuckDB connection and loading log file...")
    con = duckdb.connect()

    # Register functions
    con.create_function(
        "extract_alert_level",
        lambda msg: msg.split("]")[0].split("[")[-1].strip()
        if "[" in msg and "]" in msg
        else "INFO",
        ["VARCHAR"],
        "VARCHAR",
    )

    # Register function to generate fake IPs
    con.create_function(
        "generate_public_ip", lambda: generate_fake_ips()[0], [], "VARCHAR"
    )
    con.create_function(
        "generate_private_ip", lambda: generate_fake_ips()[1], [], "VARCHAR"
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
            generate_public_ip() as public_ip,
            generate_private_ip() as private_ip
        FROM read_json_auto(?)
    """,
        [projectID, input_file],
    )

    # Execute the user's query against the log_data table
    debug_log("Executing query against log data...")
    df = con.execute(query).df()

    # Add metadata columns
    df["project_id"] = projectID
    df["region"] = region
    df["nodeName"] = nodeName
    df["hostname"] = nodeName
    df["provider"] = provider
    df["sync_time"] = datetime.utcnow()

    # Sanitize IP addresses if present
    if "public_ip" in df.columns:
        df["public_ip"] = df["public_ip"].apply(sanitize_ip)
    if "private_ip" in df.columns:
        df["private_ip"] = df["private_ip"].apply(sanitize_ip)

    # Upload to log_results table
    debug_log("Uploading to log_results table...")
    table_id = f"{projectID}.log_analytics.log_results"
    job_config = bigquery.LoadJobConfig(
        schema=EXPECTED_SCHEMAS["log_results"],
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",
        schema_update_options=[],
    )
    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Wait for the job to complete
    print(f"Uploaded {len(df)} rows to {table_id}")

    # Process emergency logs
    if "alert_level" in df.columns:
        debug_log("Processing emergency logs...")
        emergency_df = df[df["alert_level"].isin(["emergency", "critical", "alert"])]
        if not emergency_df.empty:
            table_id = f"{projectID}.log_analytics.emergency_logs"
            job_config = bigquery.LoadJobConfig(
                schema=EXPECTED_SCHEMAS["emergency_logs"],
                write_disposition="WRITE_APPEND",
                create_disposition="CREATE_NEVER",
                schema_update_options=[],
            )
            job = bq_client.load_table_from_dataframe(
                emergency_df, table_id, job_config=job_config
            )
            job.result()
            print(f"Uploaded {len(emergency_df)} emergency logs to {table_id}")

    # Process aggregated logs if requested
    if os.environ.get("AGGREGATE_LOGS", "false").lower() == "true":
        debug_log("Processing log aggregates...")
        # Group by time windows (e.g., hourly)
        df["time_window"] = pd.to_datetime(df["timestamp"]).dt.floor("h")

        # Create pivot table to count by alert level
        agg_df = pd.pivot_table(
            df,
            index=[
                "project_id",
                "region",
                "nodeName",
                "provider",
                "hostname",
                "time_window",
            ],
            columns="alert_level",
            values="message",
            aggfunc="count",
            fill_value=0,
        ).reset_index()

        # Ensure all alert level columns exist with default 0
        for level in [
            "INFO",
            "WARN",
            "ERROR",
            "CRITICAL",
            "EMERGENCY",
            "ALERT",
            "DEBUG",
        ]:
            if level not in agg_df.columns:
                agg_df[level] = 0

        # Rename columns to match schema
        agg_df = agg_df.rename(
            columns={
                "INFO": "info_count",
                "WARN": "warn_count",
                "ERROR": "error_count",
                "CRITICAL": "critical_count",
                "EMERGENCY": "emergency_count",
                "ALERT": "alert_count",
                "DEBUG": "debug_count",
            }
        )

        # Add total count
        agg_df["total_count"] = (
            agg_df["info_count"]
            + agg_df["warn_count"]
            + agg_df["error_count"]
            + agg_df["critical_count"]
            + agg_df["emergency_count"]
            + agg_df["alert_count"]
            + agg_df["debug_count"]
        )

        # Upload aggregated data
        table_id = f"{projectID}.log_analytics.log_aggregates"
        job_config = bigquery.LoadJobConfig(
            schema=EXPECTED_SCHEMAS["log_aggregates"],
            write_disposition="WRITE_APPEND",
            create_disposition="CREATE_NEVER",
            schema_update_options=[],
        )
        job = bq_client.load_table_from_dataframe(
            agg_df, table_id, job_config=job_config
        )
        job.result()
        print(f"Uploaded {len(agg_df)} aggregated log entries to {table_id}")

    # Cleanup
    if usingTempFile:
        os.unlink(input_file)

    debug_log("Processing completed successfully")


if __name__ == "__main__":
    # Print a header to a list of files that are available to process
    print(f"Files available to process (in {LOGS_DIR}):")
    print("--------------------")

    # Print all files in the logs directory to stdout with absolute paths.
    try:
        files = os.listdir(LOGS_DIR)
        if len(files) == 0:
            print("No files are available to process.")
        else:
            f = natsorted(files, alg=ns.IGNORECASE)
            for file in f:
                print(os.path.join(LOGS_DIR, file))
    except Exception as e:
        print(f"Error listing directory {LOGS_DIR}: {str(e)}")

    print("\nEnvironment Variables")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print(f"CREDENTIALS_PATH = {CREDENTIALS_PATH}")
    print(f"DEBUG = {DEBUG}")
    print(f"PROJECT_ID = {os.environ.get('PROJECT_ID', 'not set')}")
    print(f"REGION = {os.environ.get('REGION', 'not set')}")
    print(f"NODE_NAME = {os.environ.get('NODE_NAME', 'not set')}")
    print(f"CLOUD_PROVIDER = {os.environ.get('CLOUD_PROVIDER', 'not set')}")
    print(f"INPUTFILE = {os.environ.get('INPUTFILE')}")
    print(f"QUERY = {os.environ.get('QUERY')}")
    print(f"AGGREGATE_LOGS = {os.environ.get('AGGREGATE_LOGS', 'false')}")

    # If both INPUTFILE and QUERY are set, then use those
    if os.environ.get("INPUTFILE") and os.environ.get("QUERY"):
        print("Both INPUTFILE and QUERY are set, so using those")
        args = argparse.Namespace(
            input_file=os.environ.get("INPUTFILE"), query=os.environ.get("QUERY")
        )
    else:
        # Set up the argument parser
        parser = argparse.ArgumentParser(description="Process log data")
        parser.add_argument("input_file", help="Path to the input log file")
        parser.add_argument("query", help="DuckDB query to execute")

        # Parse the command-line arguments
        args = parser.parse_args()

    # Call the main function
    main(args.input_file, args.query)
