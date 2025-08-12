#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0",
#     "pyyaml>=6.0"
# ]
# ///
"""Run the data pipeline to upload sensor data to S3"""

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

console = Console()


class SensorDataPipeline:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.s3 = boto3.client("s3")
        self.state_file = Path("databricks-uploader/state/last_timestamp.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def get_last_timestamp(self):
        """Get the last processed timestamp"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                return data.get("last_timestamp", "2000-01-01 00:00:00")
        return "2000-01-01 00:00:00"

    def save_last_timestamp(self, timestamp):
        """Save the last processed timestamp"""
        with open(self.state_file, "w") as f:
            json.dump({"last_timestamp": timestamp}, f)

    def get_pipeline_type(self):
        """Get current pipeline type from configuration database"""
        # Use separate config database
        config_db = Path("databricks-uploader/state/pipeline_config.db")

        if not config_db.exists():
            console.print("[yellow]Pipeline config not found, using default 'raw'[/yellow]")
            return "raw"

        conn = sqlite3.connect(str(config_db))
        cursor = conn.cursor()

        try:
            # Get the most recent pipeline configuration
            cursor.execute("""
                SELECT pipeline_type FROM pipeline_config 
                WHERE is_active = 1
                ORDER BY id DESC LIMIT 1
            """)
            result = cursor.fetchone()
            return result[0] if result else "raw"
        except:
            return "raw"
        finally:
            conn.close()

    def get_bucket_for_pipeline(self, pipeline_type):
        """Get S3 bucket based on pipeline type"""
        bucket_map = {
            "raw": os.getenv("S3_BUCKET_RAW"),
            "schematized": os.getenv("S3_BUCKET_SCHEMATIZED"),
            "filtered": os.getenv("S3_BUCKET_FILTERED"),
            "aggregated": os.getenv("S3_BUCKET_AGGREGATED"),
        }
        return bucket_map.get(pipeline_type, os.getenv("S3_BUCKET_RAW"))

    def process_batch(self):
        """Process a batch of sensor data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get table name
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%sensor%'")
        tables = cursor.fetchall()

        if not tables:
            console.print("[red]No sensor tables found![/red]")
            return False

        table_name = tables[0][0]

        # Get new data
        last_timestamp = self.get_last_timestamp()
        query = f"""
            SELECT * FROM {table_name} 
            WHERE timestamp > ? 
            ORDER BY timestamp 
            LIMIT 1000
        """

        cursor.execute(query, (last_timestamp,))
        rows = cursor.fetchall()

        if not rows:
            console.print("[yellow]No new data to process[/yellow]")
            return False

        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]

        # Convert to JSON
        data = []
        max_timestamp = last_timestamp

        for row in rows:
            record = dict(zip(columns, row, strict=False))
            data.append(record)
            if "timestamp" in record and record["timestamp"] > max_timestamp:
                max_timestamp = record["timestamp"]

        # Get pipeline type and bucket
        pipeline_type = self.get_pipeline_type()
        bucket = self.get_bucket_for_pipeline(pipeline_type)

        console.print(f"[cyan]Processing {len(data)} records for {pipeline_type} pipeline[/cyan]")

        # Upload to S3
        timestamp = datetime.now().strftime("%Y/%m/%d/%H%M%S")
        key = f"{pipeline_type}/{timestamp}/sensor_data.json"

        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json",
            )
            console.print(f"[green]✓ Uploaded to s3://{bucket}/{key}[/green]")

            # Save state
            self.save_last_timestamp(max_timestamp)

            # Display summary
            table = Table(title=f"Upload Summary - {pipeline_type.upper()}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Records Processed", str(len(data)))
            table.add_row("S3 Bucket", bucket)
            table.add_row("S3 Key", key)
            table.add_row("Last Timestamp", max_timestamp)

            console.print(table)

        except Exception as e:
            console.print(f"[red]Upload failed: {e}[/red]")
            return False

        conn.close()
        return True


def main():
    """Main pipeline runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run sensor data pipeline")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument(
        "--interval", type=int, default=60, help="Interval in seconds (default: 60)"
    )
    args = parser.parse_args()

    # Find database
    db_paths = ["sample-sensor/data/sensor_data.db", "sample-sensor/data/sensor_data.db"]

    db_path = None
    for path in db_paths:
        if Path(path).exists():
            db_path = path
            break

    if not db_path:
        console.print("[red]No database found![/red]")
        return

    console.print(f"[green]Using database: {db_path}[/green]")

    pipeline = SensorDataPipeline(db_path)

    if args.once:
        pipeline.process_batch()
    else:
        console.print(f"[cyan]Running continuously every {args.interval} seconds[/cyan]")
        console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

        while True:
            try:
                pipeline.process_batch()
                time.sleep(args.interval)
            except KeyboardInterrupt:
                console.print("\n[yellow]Pipeline stopped[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
