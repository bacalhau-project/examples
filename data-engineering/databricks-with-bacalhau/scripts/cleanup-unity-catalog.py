#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sdk",
#     "rich",
# ]
# ///

"""
Clean up Unity Catalog tables to prevent LOCATION_OVERLAP errors.
"""

from databricks.sdk import WorkspaceClient
from rich.console import Console

console = Console()
w = WorkspaceClient()

console.print("[bold]Cleaning Unity Catalog Tables[/bold]")
console.print("=" * 60)

CATALOG = "expanso_databricks_workspace"
SCHEMA = "sensor_readings"

# Execute SQL to drop tables
sql_commands = [
    f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.sensor_readings_ingestion",
    f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.sensor_readings_validated",
    f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.sensor_readings_enriched",
    f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.sensor_readings_aggregated",
]

for sql in sql_commands:
    console.print(f"Executing: {sql}")
    # Note: This would need a warehouse ID or cluster to execute
    console.print("  ⚠️ Run this SQL in Databricks notebook instead")

console.print("\n✅ SQL commands listed. Run in Databricks notebook.")
