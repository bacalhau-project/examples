#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=2.0.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0"
# ]
# ///
"""Test uploading sensor data to Databricks"""

import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import databricks.sql
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

console = Console()

def test_upload():
    """Test uploading a small batch of sensor data"""
    
    # Connect to SQLite
    console.print("[yellow]Connecting to SQLite database...[/yellow]")
    conn = sqlite3.connect("sensor_data.db")
    cursor = conn.cursor()
    
    # Get sample data
    cursor.execute("""
        SELECT id, timestamp, sensor_id, temperature, humidity, pressure
        FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    console.print(f"[green]✓ Found {len(rows)} records in SQLite[/green]")
    
    # Display sample data
    table = Table(title="Sample Sensor Data")
    table.add_column("ID", style="cyan")
    table.add_column("Timestamp", style="magenta")
    table.add_column("Sensor", style="green")
    table.add_column("Temp (°C)", style="yellow")
    table.add_column("Humidity (%)", style="blue")
    
    for row in rows[:5]:
        table.add_row(
            str(row[0]),
            row[1][:19],  # Truncate timestamp
            row[2],
            f"{row[3]:.2f}",
            f"{row[4]:.2f}"
        )
    
    console.print(table)
    
    # Connect to Databricks
    console.print("\n[yellow]Connecting to Databricks...[/yellow]")
    try:
        with databricks.sql.connect(
            server_hostname=os.getenv('DATABRICKS_HOST').replace('https://', '').rstrip('/'),
            http_path=os.getenv('DATABRICKS_HTTP_PATH'),
            access_token=os.getenv('DATABRICKS_TOKEN')
        ) as db_conn:
            with db_conn.cursor() as db_cursor:
                # Check if database exists
                db_cursor.execute(f"USE CATALOG main")
                db_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DATABRICKS_DATABASE')}")
                db_cursor.execute(f"USE {os.getenv('DATABRICKS_DATABASE')}")
                console.print(f"[green]✓ Using database: {os.getenv('DATABRICKS_DATABASE')}[/green]")
                
                # Create table if not exists
                db_cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_data_raw (
                        id BIGINT,
                        timestamp STRING,
                        sensor_id STRING,
                        temperature DOUBLE,
                        humidity DOUBLE,
                        pressure DOUBLE
                    )
                """)
                console.print("[green]✓ Table sensor_data_raw ready[/green]")
                
                # Insert sample data
                console.print("\n[yellow]Uploading data...[/yellow]")
                for row in rows:
                    db_cursor.execute("""
                        INSERT INTO sensor_data_raw 
                        (id, timestamp, sensor_id, temperature, humidity, pressure)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, row)
                
                console.print(f"[green]✓ Successfully uploaded {len(rows)} records![/green]")
                
                # Verify upload
                db_cursor.execute("SELECT COUNT(*) FROM sensor_data_raw")
                count = db_cursor.fetchone()[0]
                console.print(f"\n[cyan]Total records in Databricks table: {count}[/cyan]")
                
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return False
    
    conn.close()
    return True

if __name__ == "__main__":
    test_upload()