#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.28.0",
#     "python-dotenv>=1.0.0",
# ]
# ///

"""
Upload sample schema files to S3 buckets for Auto Loader initialization.
This ensures Auto Loader knows the expected schema for each pipeline stage.
"""

import json
import boto3
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Sample data for each pipeline stage
SAMPLE_DATA = {
    "ingestion": {
        "id": 1,
        "timestamp": "2025-08-18T00:00:00.000+00:00",
        "sensor_id": "SENSOR_SAMPLE",
        "temperature": 22.0,
        "humidity": 60.0,
        "pressure": 101325.0,
        "vibration": 0.5,
        "voltage": 24.0,
        "status_code": 0,
        "anomaly_flag": 0,
        "firmware_version": "1.0.0",
        "model": "SampleModel",
        "manufacturer": "SampleMfg",
        "location": "Sample Location",
        "latitude": 0.0,
        "longitude": 0.0,
        "original_timezone": "+00:00",
        "synced": 0,
    },
    "validated": {
        "id": 1,
        "timestamp": "2025-08-18T00:00:00.000+00:00",
        "sensor_id": "SENSOR_SAMPLE",
        "temperature": 22.0,
        "humidity": 60.0,
        "pressure": 101325.0,
        "vibration": 0.5,
        "voltage": 24.0,
        "status_code": 0,
        "anomaly_flag": 0,
        "anomaly_type": None,
        "firmware_version": "1.0.0",
        "model": "SampleModel",
        "manufacturer": "SampleMfg",
        "location": "Sample Location",
        "latitude": 0.0,
        "longitude": 0.0,
        "original_timezone": "+00:00",
        "synced": 0,
        "validation_status": "valid",
        "validation_timestamp": "2025-08-18T00:00:00.000+00:00",
    },
    "enriched": {
        "id": 1,
        "timestamp": "2025-08-18T00:00:00.000+00:00",
        "sensor_id": "SENSOR_SAMPLE",
        "temperature": 22.0,
        "humidity": 60.0,
        "pressure": 101325.0,
        "vibration": 0.5,
        "voltage": 24.0,
        "status_code": 0,
        "anomaly_flag": 0,
        "anomaly_type": None,
        "firmware_version": "1.0.0",
        "model": "SampleModel",
        "manufacturer": "SampleMfg",
        "location": "Sample Location",
        "latitude": 0.0,
        "longitude": 0.0,
        "original_timezone": "+00:00",
        "synced": 0,
        "enrichment_timestamp": "2025-08-18T00:00:00.000+00:00",
        "weather_condition": "clear",
        "ambient_temperature": 20.0,
        "region": "sample-region",
    },
    "aggregated": {
        "window_start": "2025-08-18T00:00:00.000+00:00",
        "window_end": "2025-08-18T00:05:00.000+00:00",
        "sensor_id": "SENSOR_SAMPLE",
        "avg_temperature": 22.0,
        "min_temperature": 20.0,
        "max_temperature": 24.0,
        "avg_humidity": 60.0,
        "avg_pressure": 101325.0,
        "avg_vibration": 0.5,
        "avg_voltage": 24.0,
        "record_count": 300,
        "anomaly_count": 0,
        "aggregation_timestamp": "2025-08-18T00:05:00.000+00:00",
    },
    "anomalies": {
        "id": 1,
        "timestamp": "2025-08-18T00:00:00.000+00:00",
        "sensor_id": "SENSOR_SAMPLE",
        "temperature": 45.0,  # Anomalous value
        "humidity": 60.0,
        "pressure": 101325.0,
        "vibration": 2.5,  # Anomalous value
        "voltage": 24.0,
        "status_code": 1,
        "anomaly_flag": 1,
        "anomaly_type": "spike",
        "anomaly_score": 0.95,
        "firmware_version": "1.0.0",
        "model": "SampleModel",
        "manufacturer": "SampleMfg",
        "location": "Sample Location",
        "latitude": 0.0,
        "longitude": 0.0,
        "original_timezone": "+00:00",
        "synced": 0,
        "detection_timestamp": "2025-08-18T00:00:01.000+00:00",
    },
}

# Bucket mappings
BUCKET_MAPPING = {
    "ingestion": "expanso-raw-data-us-west-2",
    "validated": "expanso-validated-data-us-west-2",
    "enriched": "expanso-schematized-data-us-west-2",
    "aggregated": "expanso-aggregated-data-us-west-2",
    "anomalies": "expanso-anomalies-us-west-2",
}


def load_aws_credentials():
    """Load AWS credentials from environment or file."""
    # Try to load from credentials file first
    creds_dir = Path("credentials")
    if creds_dir.exists():
        env_file = creds_dir / "expanso-s3-env.sh"
        if env_file.exists():
            print(f"📁 Loading credentials from: {env_file}")
            with open(env_file) as f:
                for line in f:
                    if line.startswith("export AWS_ACCESS_KEY_ID="):
                        os.environ["AWS_ACCESS_KEY_ID"] = line.split("=", 1)[1].strip().strip("'\"")
                    elif line.startswith("export AWS_SECRET_ACCESS_KEY="):
                        os.environ["AWS_SECRET_ACCESS_KEY"] = (
                            line.split("=", 1)[1].strip().strip("'\"")
                        )
                    elif line.startswith("export AWS_DEFAULT_REGION="):
                        os.environ["AWS_DEFAULT_REGION"] = (
                            line.split("=", 1)[1].strip().strip("'\"")
                        )


def upload_schema_samples():
    """Upload sample files to each S3 bucket."""
    # Load credentials
    load_aws_credentials()

    # Create S3 client
    s3_client = boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    print("📤 Uploading Schema Sample Files to S3 Buckets")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for stage, bucket_name in BUCKET_MAPPING.items():
        sample = SAMPLE_DATA[stage]

        # For non-aggregated stages, wrap in array
        if stage != "aggregated":
            data = [sample]
        else:
            data = [sample]

        # Convert to JSON
        json_data = json.dumps(data, indent=2)

        # Upload to S3
        key = f"schema_sample_{timestamp}.json"

        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=json_data,
                ContentType="application/json",
                Metadata={"type": "schema_sample", "stage": stage, "timestamp": timestamp},
            )
            print(f"✅ {stage:12} → s3://{bucket_name}/{key}")
        except Exception as e:
            print(f"❌ {stage:12} → Failed: {e}")

    print()
    print("📝 Schema samples uploaded. Auto Loader will now have schemas to work with.")
    print("🔄 Re-run the Databricks notebook to process data without schema errors.")


if __name__ == "__main__":
    upload_schema_samples()
