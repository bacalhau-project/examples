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
# ]
# ///

import argparse
import ipaddress
import json
import os
import tempfile
from datetime import datetime

import duckdb
import requests
from google.cloud import bigquery
from google.oauth2 import service_account
from natsort import natsorted, ns


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


def main(input_file, query):
    # Create an in-memory DuckDB database
    con = duckdb.connect(database=":memory:", read_only=False)

    usingTempFile = False
    # If file is .gz, decompress it into a temporary file
    if input_file.endswith(".gz"):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as temp:
            os.system(f"gunzip -c {input_file} > {temp.name}")
            input_file = temp.name
            usingTempFile = True

    # Load credentials from the mounted file
    credentials = service_account.Credentials.from_service_account_file(
        "/var/logs/logs_to_process/log_uploader_credentials.json",
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )

    # Create BigQuery client
    bq_client = bigquery.Client(credentials=credentials)

    # Generate metadata
    try:
        projectID = getProjectMetadata("project-id")
        region = getInstanceMetadata("zone").split("/")[3]
        nodeName = getInstanceMetadata("name")
        provider = detect_cloud_provider()
    except:
        # If metadata service is not available, use defaults
        projectID = "unknown"
        region = "unknown"
        nodeName = "unknown"
        provider = "unknown"

    syncTime = datetime.now().strftime("%Y%m%d%H%M%S")

    # Create a temporary table in DuckDB with the JSON data
    columns = {
        "id": "varchar",
        "@timestamp": "varchar",
        "@version": "varchar",
        "message": "varchar",
    }

    # First create a temporary table with the data
    temp_table = "temp_log_data"
    raw_query = f"""
    CREATE TABLE {temp_table} AS 
    SELECT 
        '{projectID}' as project_id,
        '{region}' as region,
        '{nodeName}' as nodeName,
        '{syncTime}' as sync_time,
        id as remote_log_id,
        CAST("@timestamp" AS TIMESTAMP) as timestamp,
        "@version" as version,
        message,
        '{provider}' as provider,
        hostname() as hostname,
        CASE 
            WHEN message LIKE '%ERROR%' OR message LIKE '%FATAL%' THEN 'emergency'
            WHEN message LIKE '%WARN%' THEN 'warning'
            ELSE 'info'
        END as alert_level
    FROM read_json(?, auto_detect=true, columns={columns})
    """
    con.execute(raw_query, [input_file])

    # Now apply the user's query to filter/transform the data
    if query:
        result_table = "filtered_results"
        con.execute(f"CREATE TABLE {result_table} AS {query}")
    else:
        result_table = temp_table

    # Check if we should aggregate
    should_aggregate = os.environ.get("AGGREGATE_LOGS", "false").lower() == "true"

    if should_aggregate:
        # Create aggregated table
        agg_table = "aggregated_results"
        con.execute(f"""
        CREATE TABLE {agg_table} AS
        SELECT 
            project_id,
            region,
            nodeName,
            provider,
            hostname,
            date_trunc('minute', timestamp) - 
                (date_part('minute', timestamp)::integer % 5) * interval '1 minute' as time_window,
            COUNT(*) as log_count,
            array_agg(message) as messages
        FROM {result_table}
        WHERE alert_level != 'emergency'
        GROUP BY 
            project_id, region, nodeName, provider, hostname,
            date_trunc('minute', timestamp) - 
                (date_part('minute', timestamp)::integer % 5) * interval '1 minute'
        """)

        # Export aggregated results to BigQuery
        agg_table_id = f"{projectID}.log_analytics.log_aggregates"
        df_agg = con.execute(f"SELECT * FROM {agg_table}").df()

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        job = bq_client.load_table_from_dataframe(
            df_agg, agg_table_id, job_config=job_config
        )
        job.result()
        print(f"Loaded {len(df_agg)} aggregated rows into {agg_table_id}")

        # Export emergency events separately
        emergency_table = "emergency_results"
        con.execute(f"""
        CREATE TABLE {emergency_table} AS
        SELECT *
        FROM {result_table}
        WHERE alert_level = 'emergency'
        """)

        emergency_table_id = f"{projectID}.log_analytics.emergency_logs"
        df_emergency = con.execute(f"SELECT * FROM {emergency_table}").df()

        if len(df_emergency) > 0:
            job = bq_client.load_table_from_dataframe(
                df_emergency, emergency_table_id, job_config=job_config
            )
            job.result()
            print(
                f"Loaded {len(df_emergency)} emergency events into {emergency_table_id}"
            )
    else:
        # Export the regular results to BigQuery
        table_id = f"{projectID}.log_analytics.log_results"
        df = con.execute(f"SELECT * FROM {result_table}").df()

        # Sanitize IP addresses if present
        if "public_ip" in df.columns:
            df["public_ip"] = df["public_ip"].apply(sanitize_ip)

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
        job.result()
        print(f"Loaded {len(df)} rows into {table_id}")

    # Cleanup
    if usingTempFile:
        os.unlink(input_file)


if __name__ == "__main__":
    # Print a header to a list of files that are available to process
    print("Files available to process (in /var/log/logs_to_process):")
    print("--------------------")

    # Print all files in /var/log/logs_to_process to stdout with absolute paths.
    # If there are no files, print a message that "No files are available to process."
    files = os.listdir("/var/log/logs_to_process")
    if len(files) == 0:
        print("No files are available to process.")
    else:
        f = natsorted(files, alg=ns.IGNORECASE)
        for file in f:
            print(f"/var/log/logs_to_process/{file}")

    print("\n")

    print("Environment Variables")
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
