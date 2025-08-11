#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sql-connector",
#   "python-dotenv",
#   "rich",
# ]
# ///

"""
Run the Auto Loader setup directly using SQL commands.

This bypasses the notebook upload and runs the setup directly.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid

from databricks import sql
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

console = Console()

# Configuration
CATALOG = "expanso_databricks_workspace"
DATABASE = "sensor_data"
MAX_DEMO_DURATION_HOURS = 24


def get_connection():
    """Create Databricks SQL connection."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/").replace("https://", "")
    token = os.getenv("DATABRICKS_TOKEN", "")
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
    
    if not all([host, token, http_path]):
        console.print("[red]Error: DATABRICKS_HOST, DATABRICKS_TOKEN, and DATABRICKS_HTTP_PATH must be set[/red]")
        sys.exit(1)
    
    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token
    )


def execute_sql(conn, query: str, description: str = None):
    """Execute SQL query."""
    if description:
        console.print(f"[blue]→[/blue] {description}")
    
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        console.print("[green]✓[/green] Success")
        return cursor
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise
    finally:
        if not cursor.description:  # No results to fetch
            cursor.close()


def main():
    """Run Auto Loader setup."""
    console.print(Panel.fit("[bold blue]Auto Loader Setup (Direct SQL)[/bold blue]"))
    
    # Generate demo ID
    demo_id = f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    demo_start_time = datetime.now(timezone.utc)
    demo_end_time = demo_start_time + timedelta(hours=MAX_DEMO_DURATION_HOURS)
    
    console.print(f"\n[bold]Demo Configuration:[/bold]")
    console.print(f"  Demo ID: [yellow]{demo_id}[/yellow]")
    console.print(f"  Start Time: {demo_start_time}")
    console.print(f"  Auto-shutdown: {demo_end_time}")
    console.print(f"  Duration: {MAX_DEMO_DURATION_HOURS} hours")
    
    # Connect to Databricks
    console.print("\n[bold]Connecting to Databricks...[/bold]")
    conn = get_connection()
    
    try:
        # Create database
        execute_sql(conn, f"CREATE DATABASE IF NOT EXISTS {CATALOG}.{DATABASE}", 
                   "Creating database")
        execute_sql(conn, f"USE {CATALOG}.{DATABASE}", 
                   "Setting current database")
        
        # Create ingestion table
        console.print("\n[bold]Creating tables...[/bold]")
        
        ingestion_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{DATABASE}.sensor_readings_ingestion (
            sensor_id STRING,
            timestamp TIMESTAMP,
            temperature DOUBLE,
            humidity DOUBLE,
            pressure DOUBLE,
            battery_level DOUBLE,
            signal_strength INT,
            location_lat DOUBLE,
            location_lon DOUBLE,
            firmware_version STRING,
            _ingested_at TIMESTAMP,
            _pipeline_stage STRING,
            _demo_id STRING
        ) USING DELTA
        """
        
        execute_sql(conn, ingestion_table_sql, "Creating ingestion table")
        
        # Note about Auto Loader
        console.print("\n[yellow]Note: Auto Loader streams must be created in a notebook environment.[/yellow]")
        console.print("This script has created the necessary tables.")
        console.print("\nTo complete the setup, you can either:")
        console.print("1. Upload and run the notebook manually in Databricks UI")
        console.print("2. Use the notebook upload script (once we fix the cluster issue)")
        
        # Summary
        console.print(f"\n[bold green]✅ Tables created successfully![/bold green]")
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Demo ID: {demo_id}")
        console.print(f"  Catalog: {CATALOG}")
        console.print(f"  Database: {DATABASE}")
        console.print(f"  Table: sensor_readings_ingestion")
        
        console.print("\n[bold]Next Steps:[/bold]")
        console.print("1. Upload test data:")
        console.print("   cd databricks-uploader")
        console.print("   uv run -s test-upload.py")
        console.print("\n2. Query results:")
        console.print(f"   SELECT COUNT(*) FROM {CATALOG}.{DATABASE}.sensor_readings_ingestion")
        
        return demo_id
        
    finally:
        conn.close()


if __name__ == "__main__":
    demo_id = main()
    # Save demo ID for later use
    with open(".last_demo_id", "w") as f:
        f.write(demo_id)