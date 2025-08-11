#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "databricks-sql-connector",
#   "boto3",
#   "python-dotenv",
#   "rich",
#   "click",
# ]
# ///

"""
Databricks Auto Loader Setup - All-in-One Script

Commands:
  verify    - Check if infrastructure is ready
  setup     - Create tables for data ingestion
  upload    - Upload test data to S3
  query     - Query ingested data
  teardown  - Delete all data and stop streams
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid

import boto3
import click
from databricks.sdk import WorkspaceClient
from databricks import sql as databricks_sql
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Load environment variables
load_dotenv()

console = Console()

# Configuration
CATALOG = "expanso_databricks_workspace"
DATABASE = "sensor_data"
S3_BUCKET_PREFIX = os.getenv("S3_BUCKET_PREFIX", "expanso")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


def get_workspace_client():
    """Create Databricks workspace client."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    
    if not host or not token:
        console.print("[red]Error: DATABRICKS_HOST and DATABRICKS_TOKEN must be set[/red]")
        sys.exit(1)
    
    return WorkspaceClient(host=host, token=token)


def get_sql_connection():
    """Create Databricks SQL connection."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/").replace("https://", "")
    token = os.getenv("DATABRICKS_TOKEN", "")
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
    
    if not all([host, token, http_path]):
        console.print("[red]Error: DATABRICKS_HOST, DATABRICKS_TOKEN, and DATABRICKS_HTTP_PATH must be set[/red]")
        console.print("[yellow]Note: You need a SQL warehouse to run queries. Create one in Databricks UI.[/yellow]")
        return None
    
    return databricks_sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token
    )


@click.group()
def cli():
    """Databricks Auto Loader Setup"""
    pass


@cli.command()
def verify():
    """Verify infrastructure is ready."""
    console.print(Panel.fit("[bold blue]Verifying Databricks Infrastructure[/bold blue]"))
    
    all_good = True
    
    # Check S3 buckets
    console.print("\n[bold]1. Checking S3 Buckets[/bold]")
    s3 = boto3.client('s3', region_name=AWS_REGION)
    
    buckets = [
        f"{S3_BUCKET_PREFIX}-databricks-ingestion-{AWS_REGION}",
        f"{S3_BUCKET_PREFIX}-databricks-validated-{AWS_REGION}",
        f"{S3_BUCKET_PREFIX}-databricks-enriched-{AWS_REGION}",
        f"{S3_BUCKET_PREFIX}-databricks-aggregated-{AWS_REGION}",
        f"{S3_BUCKET_PREFIX}-databricks-checkpoints-{AWS_REGION}",
        f"{S3_BUCKET_PREFIX}-databricks-metadata-{AWS_REGION}",
    ]
    
    for bucket in buckets:
        try:
            s3.head_bucket(Bucket=bucket)
            console.print(f"  ✅ {bucket}")
        except:
            console.print(f"  ❌ {bucket} - Missing")
            all_good = False
    
    # Check Databricks
    console.print("\n[bold]2. Checking Databricks Connection[/bold]")
    try:
        client = get_workspace_client()
        console.print("  ✅ Connected to Databricks")
        
        # Check for storage credential
        creds = client.storage_credentials.list()
        found_cred = False
        for cred in creds:
            # Check for either credential name
            if cred.name in ["s3_storage_for_sensor_data", "expanso-databricks-s3-credential-us-west-2"]:
                console.print(f"  ✅ Storage credential: {cred.name}")
                found_cred = True
                break
        
        if not found_cred:
            console.print("  ❌ No storage credential found")
            console.print("\n  [yellow]Storage credential missing. You have two options:[/yellow]")
            console.print("\n  Option 1: Use existing credential 'expanso-databricks-s3-credential-us-west-2'")
            console.print("  Option 2: Create new credential:")
            console.print(f"    1. Go to: {os.getenv('DATABRICKS_HOST', 'your-databricks-workspace')}")
            console.print("    2. Navigate to: Catalog → External Data → Storage Credentials")
            console.print("    3. Click 'Create credential' with:")
            console.print("       - Name: s3_storage_for_sensor_data")
            console.print("       - Type: AWS IAM Role")
            console.print("       - IAM Role ARN: arn:aws:iam::767397752906:role/databricks-unity-catalog-expanso-role")
            all_good = False
            
        # Check for external locations
        console.print("\n[bold]3. Checking External Locations[/bold]")
        try:
            external_locations = client.external_locations.list()
            location_names = [loc.name for loc in external_locations]
            
            # Check for either set of location names (different workspaces use different conventions)
            expected_locations_v1 = [
                "expanso_ingestion_data",
                "expanso_validated_data", 
                "expanso_enriched_data",
                "expanso_aggregated_data",
                "expanso_checkpoints",
                "expanso_metadata"
            ]
            
            expected_locations_v2 = [
                "expanso_raw_location",
                "expanso_schematized_location",
                "expanso_filtered_location",
                "expanso_emergency_location",
                "expanso_checkpoints_location"
            ]
            
            # Check which set exists
            if "expanso_raw_location" in location_names:
                expected_locations = expected_locations_v2
            else:
                expected_locations = expected_locations_v1
            
            for loc in expected_locations:
                if loc in location_names:
                    console.print(f"  ✅ {loc}")
                else:
                    console.print(f"  ❌ {loc} - Missing")
                    all_good = False
                    
        except Exception as e:
            console.print(f"  ❌ Could not check external locations: {e}")
            all_good = False
            
    except Exception as e:
        console.print(f"  ❌ Databricks connection failed: {e}")
        all_good = False
    
    # Summary
    if all_good:
        console.print("\n[bold green]✅ All infrastructure is ready![/bold green]")
    else:
        console.print("\n[bold red]❌ Some components are missing[/bold red]")
        console.print("\nRun the setup scripts in the scripts/ directory")


@cli.command()
def setup():
    """Create tables for data ingestion."""
    console.print(Panel.fit("[bold blue]Setting Up Tables[/bold blue]"))
    
    conn = get_sql_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        # Create database
        console.print(f"\n[bold]Creating database {CATALOG}.{DATABASE}[/bold]")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {CATALOG}.{DATABASE}")
        cursor.execute(f"USE {CATALOG}.{DATABASE}")
        
        # Create ingestion table
        console.print("\n[bold]Creating sensor_readings_ingestion table[/bold]")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS sensor_readings_ingestion (
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
                _ingested_at TIMESTAMP DEFAULT current_timestamp(),
                _pipeline_stage STRING DEFAULT 'manual',
                _demo_id STRING DEFAULT 'cli_upload'
            ) USING DELTA
        """)
        
        console.print("[green]✅ Table created successfully![/green]")
        console.print(f"\nTable: {CATALOG}.{DATABASE}.sensor_readings_ingestion")
        console.print("\nNote: For Auto Loader (automatic processing), upload and run the notebook in Databricks UI")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        cursor.close()
        conn.close()


@cli.command()
def upload():
    """Upload test data to S3."""
    console.print(Panel.fit("[bold blue]Uploading Test Data[/bold blue]"))
    
    # Generate test data
    import random
    
    records = []
    for i in range(100):
        records.append({
            "sensor_id": f"sensor_{random.randint(1, 10):03d}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature": round(20 + random.random() * 10, 2),
            "humidity": round(40 + random.random() * 20, 2),
            "pressure": round(1000 + random.random() * 20, 2),
            "battery_level": round(random.random() * 100, 2),
            "signal_strength": random.randint(-90, -30),
            "location_lat": round(37.7749 + random.random() * 0.1, 6),
            "location_lon": round(-122.4194 + random.random() * 0.1, 6),
            "firmware_version": f"v1.{random.randint(0, 9)}.{random.randint(0, 9)}"
        })
    
    # Create JSON file
    data = {
        "metadata": {
            "source": "test_generator",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records)
        },
        "records": records
    }
    
    # Upload to S3
    s3 = boto3.client('s3', region_name=AWS_REGION)
    bucket = f"{S3_BUCKET_PREFIX}-databricks-ingestion-{AWS_REGION}"
    key = f"ingestion/{datetime.now().strftime('%Y/%m/%d/%H')}/sensor_data_{int(time.time())}.json"
    
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        
        console.print(f"[green]✅ Uploaded {len(records)} records to S3[/green]")
        console.print(f"   Bucket: {bucket}")
        console.print(f"   Key: {key}")
        
        console.print("\n[yellow]Note: If Auto Loader is running, data will be processed in ~30 seconds[/yellow]")
        console.print("Otherwise, data is ready for manual processing")
        
    except Exception as e:
        console.print(f"[red]Error uploading to S3: {e}[/red]")


@cli.command()
def query():
    """Query ingested data."""
    console.print(Panel.fit("[bold blue]Querying Data[/bold blue]"))
    
    conn = get_sql_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        # Get record count
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT sensor_id) as unique_sensors,
                MIN(_ingested_at) as first_record,
                MAX(_ingested_at) as last_record
            FROM {CATALOG}.{DATABASE}.sensor_readings_ingestion
        """)
        
        result = cursor.fetchone()
        
        if result[0] == 0:
            console.print("[yellow]No data found in table[/yellow]")
            console.print("\nRun 'databricks-setup.py upload' to add test data")
        else:
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  Total records: {result[0]:,}")
            console.print(f"  Unique sensors: {result[1]}")
            console.print(f"  First record: {result[2]}")
            console.print(f"  Last record: {result[3]}")
            
            # Show recent records
            cursor.execute(f"""
                SELECT sensor_id, timestamp, temperature, humidity, _ingested_at
                FROM {CATALOG}.{DATABASE}.sensor_readings_ingestion
                ORDER BY _ingested_at DESC
                LIMIT 5
            """)
            
            console.print("\n[bold]Recent Records:[/bold]")
            table = Table()
            table.add_column("Sensor ID", style="cyan")
            table.add_column("Timestamp", style="green")
            table.add_column("Temp (°C)", style="yellow")
            table.add_column("Humidity (%)", style="blue")
            table.add_column("Ingested At", style="magenta")
            
            for row in cursor.fetchall():
                table.add_row(
                    row[0],
                    str(row[1])[:19],
                    f"{row[2]:.1f}",
                    f"{row[3]:.1f}",
                    str(row[4])[:19]
                )
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        cursor.close()
        conn.close()


@cli.command()
def teardown():
    """Delete all data and stop streams."""
    console.print(Panel.fit("[bold red]Teardown - Delete ALL Data[/bold red]"))
    
    if not click.confirm("This will delete ALL data. Continue?"):
        return
    
    # For notebook execution, we'd need to upload and run the teardown notebook
    console.print("\n[yellow]To properly teardown Auto Loader:[/yellow]")
    console.print("1. Upload databricks-notebooks/02-teardown-all.py to Databricks")
    console.print("2. Run the notebook to stop streams and delete all data")
    
    # We can at least delete table data
    conn = get_sql_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {CATALOG}.{DATABASE}.sensor_readings_ingestion")
            console.print("\n[green]✓ Deleted all data from sensor_readings_ingestion[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    cli()