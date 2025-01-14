#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
# "google-cloud-bigquery",
# "google-oauth",
# "pyyaml",
# "google-api-core",
# ]
# ///

import yaml
from google.cloud import bigquery
from google.oauth2 import service_account

# Load the project-id from the config.yaml file
# If yaml does not exist, warn that they need to run setup.py and configure config.yaml

try:
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
        project_id = config.get("project", {}).get("id", None)
        if not project_id:
            print(
                "config.yaml is missing the project.id field. Please run setup.py and configure config.yaml."
            )
            exit(1)
except FileNotFoundError:
    print("config.yaml not found. Please run setup.py and configure config.yaml.")
    exit(1)

# Setup credentials
credentials = service_account.Credentials.from_service_account_file(
    "credentials.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)


def print_separator():
    print("\n" + "=" * 80 + "\n")


def run_query(client, query, title):
    print(f"Running query: {title}")
    print("\nSQL:")
    print(query)
    print("\nResults:")

    query_job = client.query(query)
    results = query_job.result()

    # Print results in a tabular format
    rows = list(results)
    if not rows:
        print("No results found")
        return

    # Get column names
    columns = [field.name for field in results.schema]

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(getattr(row, col))))

    # Print header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    # Print rows
    for row in rows:
        print(" | ".join(str(getattr(row, col)).ljust(widths[col]) for col in columns))

    print("-" * len(header))
    print(f"Total rows: {len(rows)}")


def main():
    # Load config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Setup credentials
    credentials = service_account.Credentials.from_service_account_file(
        config["credentials"]["path"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    # Create BigQuery client
    client = bigquery.Client(credentials=credentials, project=config["project"]["id"])

    project_id = config["project"]["id"]
    dataset_id = f"{project_id}.{config['bigquery']['dataset_name']}"
    table_id = f"{dataset_id}.{config['bigquery']['table_name']}"

    print_separator()
    print(f"Querying BigQuery table: {table_id}")
    print_separator()

    # Query 1: Show table structure
    schema_query = f"""
    SELECT 
        column_name,
        data_type,
        is_nullable
    FROM {dataset_id}.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = '{config["bigquery"]["table_name"]}'
    ORDER BY ordinal_position
    """
    run_query(client, schema_query, "Table Structure")
    print_separator()

    # Query 2: Count total rows
    count_query = f"""
    SELECT COUNT(*) as total_rows
    FROM `{table_id}`
    """
    run_query(client, count_query, "Total Row Count")
    print_separator()

    # Query 3: Sample recent logs
    recent_logs_query = f"""
    SELECT timestamp, nodeName, message
    FROM `{table_id}`
    ORDER BY timestamp DESC
    LIMIT 5
    """
    run_query(client, recent_logs_query, "Recent Logs")
    print_separator()

    # Query 4: Count logs by node
    node_count_query = f"""
    SELECT 
        nodeName,
        COUNT(*) as log_count
    FROM `{table_id}`
    GROUP BY nodeName
    ORDER BY log_count DESC
    """
    run_query(client, node_count_query, "Logs per Node")


if __name__ == "__main__":
    main()
