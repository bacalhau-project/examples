#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "pyyaml>=6.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
SQLite to S3 Uploader for Databricks

Reads data from SQLite and uploads to S3 buckets for Databricks Auto Loader ingestion.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
import yaml
from dotenv import load_dotenv

# Import pipeline manager for atomic pipeline type management
sys.path.append(str(Path(__file__).parent))
from pipeline_manager import PipelineManager


class SQLiteToS3Uploader:
    def __init__(self, config_path: str):
        """Initialize uploader with configuration."""
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.state_dir = Path(self.config.get("state_dir", "state"))
        self.state_file = self.state_dir / "s3-uploader" / "upload_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize pipeline manager for atomic pipeline type management
        pipeline_db_path = self.state_dir / "pipeline_config.db"
        self.pipeline_manager = PipelineManager(str(pipeline_db_path))

        # Get current pipeline configuration
        pipeline_config = self.pipeline_manager.get_current_config()
        self.current_pipeline_type = pipeline_config["type"]

        # Pipeline type to bucket mapping
        self.pipeline_bucket_map = {
            "raw": "ingestion",
            "ingestion": "ingestion",
            "schematized": "validated",
            "validated": "validated",
            "filtered": "enriched",
            "enriched": "enriched",
            "emergency": "aggregated",
            "aggregated": "aggregated",
        }

        # Print startup information
        print("\n" + "=" * 60)
        print("🚀 DATABRICKS S3 UPLOADER - STARTUP INFORMATION")
        print("=" * 60)
        print(f"📁 Configuration file: {Path(self.config_path).absolute()}")
        print(f"📂 State directory: {self.state_dir.absolute()}")
        print(f"📄 State file: {self.state_file.absolute()}")
        print(f"🗄️  SQLite database: {Path(self.config['sqlite']).absolute()}")
        print(f"📊 SQLite table: {self.config.get('sqlite_table', 'sensor_readings')}")
        print(f"🔧 Pipeline DB: {pipeline_db_path.absolute()}")
        print(
            f"🚦 Current pipeline type: {self.current_pipeline_type} (from {pipeline_config['source']})"
        )
        print(
            f"🪣  Target S3 bucket: {self.pipeline_bucket_map.get(self.current_pipeline_type, 'ingestion')}"
        )
        print(f"⏱️  Upload interval: {self.config.get('upload_interval', 15)} seconds")
        print(f"📦 Batch size: {self.config.get('batch_size', 500)} records")
        print(f"🔄 Run once: {self.config.get('once', False)}")
        print("\n📝 To change pipeline type (atomic operation):")
        print(
            f"   uv run -s pipeline_manager.py --db {pipeline_db_path} set --type <type>"
        )
        print("   Available types: raw, validated, enriched, aggregated")
        print("=" * 60 + "\n")

        # S3 client with explicit credentials ONLY - NO SSO
        s3_config = self.config.get("s3_configuration", {})

        # Check for AWS credentials in multiple sources
        aws_access_key = None
        aws_secret_key = None
        aws_region = s3_config.get("region", "us-west-2")
        creds_source = None

        # Priority 1: Check for credential files on disk (for Docker containers)
        creds_dir = Path(s3_config.get("credentials_dir", "/bacalhau_data/credentials"))
        local_creds_dir = Path("credentials")  # For local testing

        # Try production path first, then local path
        for check_dir in [creds_dir, local_creds_dir]:
            if check_dir.exists():
                # Check for expanso-s3-env.sh file
                env_file = check_dir / "expanso-s3-env.sh"
                if env_file.exists():
                    print(f"📁 Found credentials file: {env_file}")
                    # Parse the shell script for credentials
                    with open(env_file, "r") as f:
                        for line in f:
                            if line.startswith("export AWS_ACCESS_KEY_ID="):
                                aws_access_key = (
                                    line.split("=", 1)[1].strip().strip("'\"")
                                )
                            elif line.startswith("export AWS_SECRET_ACCESS_KEY="):
                                aws_secret_key = (
                                    line.split("=", 1)[1].strip().strip("'\"")
                                )
                            elif line.startswith("export AWS_DEFAULT_REGION="):
                                aws_region = line.split("=", 1)[1].strip().strip("'\"")
                    if aws_access_key and aws_secret_key:
                        creds_source = f"file: {env_file}"
                        break

        # Priority 2: Config file
        if not aws_access_key:
            aws_access_key = s3_config.get("access_key_id")
            aws_secret_key = s3_config.get("secret_access_key")
            if aws_access_key and aws_secret_key:
                creds_source = "config file"

        # Priority 3: Environment variables
        if not aws_access_key:
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            if aws_access_key and aws_secret_key:
                creds_source = "environment variables"

        # REQUIRE explicit credentials - no SSO fallback
        if not aws_access_key or not aws_secret_key:
            print("\n" + "❌" * 30)
            print("ERROR: AWS credentials are REQUIRED")
            print("Please provide credentials via one of these methods:")
            print(
                "1. Credential file: credentials/expanso-s3-env.sh (for local testing)"
            )
            print(
                "2. Credential file: /bacalhau_data/credentials/expanso-s3-env.sh (for Docker)"
            )
            print(
                "3. Config file: s3_configuration.access_key_id and s3_configuration.secret_access_key"
            )
            print(
                "4. Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
            )
            print("\nThis uploader does NOT support AWS SSO login.")
            print("❌" * 30 + "\n")
            sys.exit(1)

        print(f"🔐 Using explicit AWS credentials from {creds_source} (no SSO)")
        self.s3_client = boto3.client(
            "s3",
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        print(f"📋 Loaded config from {config_path}")
        print(f"   SQLite path: {config.get('sqlite', 'NOT SET')}")
        print(f"   SQLite table: {config.get('sqlite_table', 'NOT SET')}")

        # Override with environment variables if present
        if os.getenv("SQLITE_PATH"):
            print(
                f"   ⚠️  Overriding SQLite path with env var: {os.getenv('SQLITE_PATH')}"
            )
            config["sqlite"] = os.getenv("SQLITE_PATH")
        if os.getenv("SQLITE_TABLE"):
            print(
                f"   ⚠️  Overriding SQLite table with env var: {os.getenv('SQLITE_TABLE')}"
            )
            config["sqlite_table"] = os.getenv("SQLITE_TABLE")
        if os.getenv("AWS_REGION"):
            config["s3_configuration"]["region"] = os.getenv("AWS_REGION")

        return config

    def _load_state(self) -> Dict[str, Any]:
        """Load last upload state."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {}

    def _save_state(self, state: Dict[str, Any]):
        """Save upload state."""
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _get_new_data(self, last_timestamp: Optional[str] = None) -> list:
        """Get new data from SQLite since last timestamp."""
        import sqlite3

        # Path is relative to current working directory
        db_path = Path(self.config["sqlite"])

        if not db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {db_path} (looking in {Path.cwd()})"
            )

        table = self.config["sqlite_table"]
        timestamp_col = self.config["timestamp_col"]

        print(f"📂 Using database: {db_path.absolute()}")
        print(f"📊 Reading from table: {table}")

        # Connect to SQLite
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = f"SELECT * FROM {table}"
        params = []

        if last_timestamp:
            query += f" WHERE {timestamp_col} > ?"
            params.append(last_timestamp)

        query += f" ORDER BY {timestamp_col} LIMIT ?"
        params.append(self.config.get("max_batch_size", 500))

        # Execute query
        try:
            cursor.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                # List available tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                raise ValueError(
                    f"Table '{table}' not found. Available tables: {tables}"
                )
            else:
                conn.close()
                raise

        conn.close()
        return rows

    def _upload_to_s3(self, data: list, bucket: str, dry_run: bool = False) -> bool:
        """Upload data to S3 bucket."""
        if not data:
            return True

        # Generate S3 key with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
        key = f"ingestion/{timestamp}/data.json"

        # Prepare data
        upload_data = {
            "metadata": {
                "source": self.config["sqlite"],
                "table": self.config["sqlite_table"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_count": len(data),
            },
            "records": data,
        }

        if dry_run:
            print(f"[DRY RUN] Would upload {len(data)} records to s3://{bucket}/{key}")
            return True

        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(upload_data),
                ContentType="application/json",
            )
            print(f"✅ Uploaded {len(data)} records to s3://{bucket}/{key}")
            return True

        except Exception as e:
            print(f"❌ Failed to upload to S3: {e}")
            return False

    def run_once(self, dry_run: bool = False):
        """Run one upload cycle."""
        # Check for pipeline type changes
        pipeline_config = self.pipeline_manager.get_current_config()
        if pipeline_config["type"] != self.current_pipeline_type:
            old_type = self.current_pipeline_type
            new_type = pipeline_config["type"]
            old_bucket = self.pipeline_bucket_map.get(old_type, "unknown")
            new_bucket = self.pipeline_bucket_map.get(new_type, "unknown")

            print("\n" + "🔄" * 30)
            print(f"🚨 PIPELINE STATE CHANGE DETECTED!")
            print(f"   Previous: {old_type} → {old_bucket} bucket")
            print(f"   Current:  {new_type} → {new_bucket} bucket")
            print(f"   Changed at: {pipeline_config['created_at']}")
            print(f"   Changed by: {pipeline_config['source']}")
            print("🔄" * 30 + "\n")

            self.current_pipeline_type = new_type

        # Load state
        state = self._load_state()
        last_timestamp = state.get("last_timestamp")

        # Get new data
        print(f"🔍 Checking for new data since: {last_timestamp or 'beginning'}")
        data = self._get_new_data(last_timestamp)

        if not data:
            print(f"✅ No new data to upload (Pipeline: {self.current_pipeline_type})")
            return

        print(f"📊 Found {len(data)} new records")

        # Get bucket based on current pipeline type
        bucket_key = self.pipeline_bucket_map.get(
            self.current_pipeline_type, "ingestion"
        )
        bucket = self.config["s3_configuration"]["buckets"].get(bucket_key)

        if not bucket:
            print(
                f"❌ No bucket configured for pipeline type: {self.current_pipeline_type}"
            )
            return

        # Print detailed upload information
        print("\n" + "-" * 60)
        print(f"📤 UPLOAD OPERATION")
        print(f"   Pipeline Type: {self.current_pipeline_type}")
        print(f"   Target Bucket: {bucket_key} → {bucket}")
        print(f"   Records Count: {len(data)}")
        print(
            f"   Time Range: {data[0].get(self.config['timestamp_col'])} to {data[-1].get(self.config['timestamp_col'])}"
        )
        print("-" * 60)

        success = self._upload_to_s3(data, bucket, dry_run)

        if success and not dry_run:
            # Update state with last timestamp
            timestamp_col = self.config["timestamp_col"]
            last_record = data[-1]
            new_timestamp = last_record.get(timestamp_col)

            state["last_timestamp"] = new_timestamp
            state["last_upload"] = datetime.now(timezone.utc).isoformat()
            state["records_uploaded"] = state.get("records_uploaded", 0) + len(data)
            state["last_pipeline_type"] = self.current_pipeline_type

            self._save_state(state)

            # Record execution in pipeline manager
            s3_location = f"s3://{bucket}/{self.current_pipeline_type}/"
            job_id = f"uploader-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            self.pipeline_manager.record_execution(
                pipeline_type=self.current_pipeline_type,
                records_processed=len(data),
                s3_locations=[s3_location],
                job_id=job_id,
            )

            # Print upload summary
            print("\n✅ UPLOAD COMPLETED SUCCESSFULLY")
            print(f"   Pipeline Version: {self.current_pipeline_type}")
            print(f"   Records Uploaded: {len(data)}")
            print(f"   Destination: {s3_location}")
            print(f"   Job ID: {job_id}")
            print(f"   Last Timestamp: {new_timestamp}")
            print(f"   Total Records (all-time): {state['records_uploaded']}")
            print("-" * 60 + "\n")

    def run_continuous(self):
        """Run continuously with interval."""
        interval = self.config.get("upload_interval", 15)
        print(f"🔄 Starting continuous mode. Checking every {interval} seconds...")

        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"❌ Error in upload cycle: {e}")

            print(f"💤 Sleeping for {interval} seconds...")
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="Upload SQLite data to S3 for Databricks"
    )
    parser.add_argument(
        "--config", required=True, help="Path to configuration YAML file"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without uploading",
    )

    args = parser.parse_args()

    # Validate config file exists
    if not os.path.exists(args.config):
        print(f"❌ Config file not found: {args.config}")
        sys.exit(1)

    # Create uploader
    uploader = SQLiteToS3Uploader(args.config)

    # Run
    if args.once or args.dry_run:
        uploader.run_once(dry_run=args.dry_run)
    else:
        uploader.run_continuous()


if __name__ == "__main__":
    main()
