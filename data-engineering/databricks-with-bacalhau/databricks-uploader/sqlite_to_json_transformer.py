#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
#     "jsonschema>=4.0",
#     "python-dateutil>=2.8",
#     "boto3>=1.26.0",
#     "pydantic>=2.0.0",
#     "requests>=2.31.0",
# ]
# ///

"""
SQLite to JSON Transformer with Schema Validation

Transforms SQLite sensor data to JSON format and validates against
a dynamically loaded schema. Records that fail validation are routed
to an anomaly stream for separate processing.
"""

import json
import sqlite3
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import yaml
import jsonschema
from dateutil import parser
import argparse
import logging
import boto3
import requests
from pydantic import ValidationError

# Import our custom modules
import sys

sys.path.append(str(Path(__file__).parent))
from sensor_data_models import WindTurbineSensorData, validate_sensor_data

# Transformation version
TRANSFORMATION_VERSION = "2.0.0"


class SensorDataTransformer:
    """Transforms SQLite sensor data with validation against dynamic schemas."""

    def __init__(
        self,
        schema_path: Optional[str] = None,
        schema_url: Optional[str] = None,
        validate_data: bool = True,
        route_anomalies: bool = True,
    ):
        """
        Initialize transformer with schema validation.

        Args:
            schema_path: Local path to JSON schema file
            schema_url: URL to fetch JSON schema from
            validate_data: Whether to validate data against schema
            route_anomalies: Whether to route invalid data to anomaly stream
        """
        self.logger = logging.getLogger(__name__)
        self.validate_data = validate_data
        self.route_anomalies = route_anomalies

        # Statistics tracking
        self.stats = {
            "total_processed": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "validation_errors": {},
        }

        # Load schema if validation is enabled
        self.schema = None
        if self.validate_data:
            if schema_url:
                self.schema = self._fetch_schema_from_url(schema_url)
            elif schema_path and os.path.exists(schema_path):
                with open(schema_path, "r") as f:
                    self.schema = json.load(f)
            else:
                self.logger.warning("No schema provided, using Pydantic model validation only")

        # Load node identity for hashing
        self.node_identity_hash = self._generate_node_identity_hash()

    def _fetch_schema_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON schema from URL (S3 or HTTP)."""
        try:
            if url.startswith("s3://"):
                # Parse S3 URL
                parts = url.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""

                s3 = boto3.client("s3")
                response = s3.get_object(Bucket=bucket, Key=key)
                return json.loads(response["Body"].read().decode("utf-8"))
            else:
                # HTTP/HTTPS URL
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch schema from {url}: {e}")
            return None

    def _generate_node_identity_hash(self) -> str:
        """Generate a hash of the node identity file."""
        identity_files = [
            "node_identity.json",
            "config/node_identity.json",
            "../node_identity.json",
        ]

        for identity_file in identity_files:
            if os.path.exists(identity_file):
                with open(identity_file, "rb") as f:
                    content = f.read()
                    return hashlib.sha256(content).hexdigest()[:16]

        # Fallback to hostname if no identity file
        import socket

        hostname = socket.gethostname()
        return hashlib.sha256(hostname.encode()).hexdigest()[:16]

    def transform_record(self, row: Dict[str, Any], bacalhau_job_id: str) -> Dict[str, Any]:
        """Transform a single SQLite row to structured JSON format."""
        # Parse timestamp
        timestamp = row.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = parser.parse(timestamp).isoformat()

        # Build structured JSON
        structured_data = {
            "timestamp": timestamp,
            "sensor_id": row.get("sensor_id"),
            "readings": {
                "temperature": float(row.get("temperature", 0)),
                "humidity": float(row.get("humidity", 0)),
                "pressure": float(row.get("pressure", 0)),
                "vibration": float(row.get("vibration", 0)),
                "voltage": float(row.get("voltage", 0)),
            },
            "status": {
                "status_code": int(row.get("status_code", 0)),
                "anomaly_flag": bool(row.get("anomaly_flag", False)),
                "anomaly_type": row.get("anomaly_type"),
                "synced": bool(row.get("synced", False)),
            },
            "device_info": {
                "manufacturer": row.get("manufacturer"),
                "model": row.get("model"),
                "firmware_version": row.get("firmware_version"),
                "serial_number": row.get("serial_number"),
                "manufacture_date": row.get("manufacture_date"),
            },
            "location_info": {
                "location": row.get("location"),
                "latitude": float(row.get("latitude", 0)),
                "longitude": float(row.get("longitude", 0)),
                "original_timezone": row.get("original_timezone"),
            },
            "deployment_info": {
                "deployment_type": row.get("deployment_type"),
                "installation_date": row.get("installation_date"),
                "height_meters": float(row.get("height_meters"))
                if row.get("height_meters")
                else None,
                "orientation_degrees": float(row.get("orientation_degrees"))
                if row.get("orientation_degrees")
                else None,
            },
            "metadata": {
                "instance_id": row.get("instance_id"),
                "sensor_type": row.get("sensor_type"),
            },
            "transformation_metadata": {
                "bacalhau_job_id": bacalhau_job_id,
                "transformation_timestamp": datetime.now(timezone.utc).isoformat(),
                "node_identity_hash": self.node_identity_hash,
                "transformation_version": TRANSFORMATION_VERSION,
                "original_record_id": row.get("id"),
            },
        }

        return structured_data

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a record against the schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # First try Pydantic validation if we're using wind turbine data
        if "turbine_id" in record:
            try:
                WindTurbineSensorData(**record)
                return True, None
            except ValidationError as e:
                error_msg = str(e)
                self.logger.debug(f"Pydantic validation error: {error_msg}")
                return False, error_msg

        # Fall back to JSON schema validation if provided
        if self.schema:
            try:
                jsonschema.validate(instance=record, schema=self.schema)
                return True, None
            except jsonschema.exceptions.ValidationError as e:
                error_msg = str(e)
                self.logger.debug(f"JSON schema validation error: {error_msg}")
                return False, error_msg

        # If no validation configured, consider valid
        return True, None

    def transform_and_validate_record(
        self, row: Dict[str, Any], bacalhau_job_id: str
    ) -> Tuple[Optional[Dict[str, Any]], bool, Optional[str]]:
        """
        Transform and validate a single record.

        Returns:
            Tuple of (transformed_record, is_valid, error_message)
        """
        try:
            # Transform the record
            structured_record = self.transform_record(row, bacalhau_job_id)

            # Validate if enabled
            if self.validate_data:
                is_valid, error_msg = self.validate_record(structured_record)
                return structured_record, is_valid, error_msg

            return structured_record, True, None

        except Exception as e:
            self.logger.error(f"Error transforming record: {e}")
            return None, False, str(e)

    def transform_sqlite_with_validation(
        self,
        db_path: str,
        valid_output_path: str,
        anomaly_output_path: Optional[str],
        bacalhau_job_id: str,
        table_name: str = "sensor_readings",
        limit: Optional[int] = None,
        where_clause: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transform SQLite data with validation routing.

        Valid records go to valid_output_path, invalid to anomaly_output_path.
        """
        stats = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "transformation_errors": 0,
            "validation_errors": {},
        }

        valid_records = []
        anomaly_records = []

        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = f"SELECT * FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        if limit:
            query += f" LIMIT {limit}"

        self.logger.info(f"Executing query: {query}")

        # Process records
        for row in cursor.execute(query):
            stats["total_records"] += 1
            row_dict = dict(row)

            # Transform and validate
            record, is_valid, error_msg = self.transform_and_validate_record(
                row_dict, bacalhau_job_id
            )

            if record is None:
                stats["transformation_errors"] += 1
                continue

            if is_valid:
                valid_records.append(record)
                stats["valid_records"] += 1
            else:
                # Add validation error to record
                record["validation_error"] = error_msg
                anomaly_records.append(record)
                stats["invalid_records"] += 1

                # Track error types
                error_type = error_msg.split(":")[0] if error_msg else "unknown"
                stats["validation_errors"][error_type] = (
                    stats["validation_errors"].get(error_type, 0) + 1
                )

        conn.close()

        # Write valid records
        if valid_records:
            valid_output = {
                "metadata": {
                    "transformation_version": TRANSFORMATION_VERSION,
                    "transformation_timestamp": datetime.now(timezone.utc).isoformat(),
                    "bacalhau_job_id": bacalhau_job_id,
                    "record_count": len(valid_records),
                    "record_type": "valid",
                },
                "records": valid_records,
            }

            with open(valid_output_path, "w") as f:
                json.dump(valid_output, f, indent=2, default=str)

            self.logger.info(f"Wrote {len(valid_records)} valid records to {valid_output_path}")

        # Write anomaly records if configured
        if self.route_anomalies and anomaly_records and anomaly_output_path:
            anomaly_output = {
                "metadata": {
                    "transformation_version": TRANSFORMATION_VERSION,
                    "transformation_timestamp": datetime.now(timezone.utc).isoformat(),
                    "bacalhau_job_id": bacalhau_job_id,
                    "record_count": len(anomaly_records),
                    "record_type": "anomaly",
                },
                "records": anomaly_records,
            }

            with open(anomaly_output_path, "w") as f:
                json.dump(anomaly_output, f, indent=2, default=str)

            self.logger.info(
                f"Wrote {len(anomaly_records)} anomaly records to {anomaly_output_path}"
            )

        # Update transformer stats
        self.stats["total_processed"] += stats["total_records"]
        self.stats["valid_records"] += stats["valid_records"]
        self.stats["invalid_records"] += stats["invalid_records"]

        for error_type, count in stats["validation_errors"].items():
            self.stats["validation_errors"][error_type] = (
                self.stats["validation_errors"].get(error_type, 0) + count
            )

        return stats

    def transform_sqlite_to_json(
        self,
        db_path: str,
        output_path: str,
        bacalhau_job_id: str,
        table_name: str = "sensor_readings",
        limit: Optional[int] = None,
        where_clause: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transform SQLite data to JSON format."""
        stats = {
            "total_records": 0,
            "transformed": 0,
            "validation_errors": 0,
            "transformation_errors": 0,
        }

        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = f"SELECT * FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        if limit:
            query += f" LIMIT {limit}"

        self.logger.info(f"Executing query: {query}")

        # Process records
        output_records = []
        for row in cursor.execute(query):
            stats["total_records"] += 1

            try:
                # Convert row to dict
                row_dict = dict(row)

                # Transform to structured format
                structured_record = self.transform_record(row_dict, bacalhau_job_id)

                # Validate against schema
                if self.validate_record(structured_record):
                    output_records.append(structured_record)
                    stats["transformed"] += 1
                else:
                    stats["validation_errors"] += 1

            except Exception as e:
                self.logger.error(f"Error transforming record {row_dict.get('id')}: {e}")
                stats["transformation_errors"] += 1

        conn.close()

        # Write output
        output_data = {
            "metadata": {
                "transformation_version": TRANSFORMATION_VERSION,
                "transformation_timestamp": datetime.now(timezone.utc).isoformat(),
                "bacalhau_job_id": bacalhau_job_id,
                "source_database": db_path,
                "stats": stats,
            },
            "records": output_records,
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        self.logger.info(f"Transformation complete. Stats: {stats}")
        return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Transform SQLite sensor data to JSON")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--job-id", required=True, help="Bacalhau job ID")
    parser.add_argument("--table", default="sensor_readings", help="Table name")
    parser.add_argument("--schema", default="sensor_data_schema.json", help="JSON schema path")
    parser.add_argument("--limit", type=int, help="Limit number of records")
    parser.add_argument("--where", help="WHERE clause for filtering")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Transform data
    transformer = SensorDataTransformer(schema_path=args.schema)
    stats = transformer.transform_sqlite_to_json(
        db_path=args.db_path,
        output_path=args.output,
        bacalhau_job_id=args.job_id,
        table_name=args.table,
        limit=args.limit,
        where_clause=args.where,
    )

    print(f"Transformation complete: {stats}")


if __name__ == "__main__":
    main()
