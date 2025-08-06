#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
#     "jsonschema>=4.0",
#     "python-dateutil>=2.8",
# ]
# ///

"""
SQLite to JSON Transformer for Sensor Data

This script transforms flat SQLite sensor data into structured JSON format
with transformation metadata for tracking in the data pipeline.
"""

import json
import sqlite3
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
import jsonschema
from dateutil import parser
import argparse
import logging

# Transformation version
TRANSFORMATION_VERSION = "1.0.0"

class SensorDataTransformer:
    """Transforms SQLite sensor data to structured JSON with metadata."""
    
    def __init__(self, schema_path: str = "sensor_data_schema.json"):
        """Initialize transformer with JSON schema."""
        self.logger = logging.getLogger(__name__)
        
        # Load JSON schema
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
        
        # Load node identity for hashing
        self.node_identity_hash = self._generate_node_identity_hash()
        
    def _generate_node_identity_hash(self) -> str:
        """Generate a hash of the node identity file."""
        identity_files = [
            "node_identity.json",
            "config/node_identity.json",
            "../node_identity.json"
        ]
        
        for identity_file in identity_files:
            if os.path.exists(identity_file):
                with open(identity_file, 'rb') as f:
                    content = f.read()
                    return hashlib.sha256(content).hexdigest()[:16]
        
        # Fallback to hostname if no identity file
        import socket
        hostname = socket.gethostname()
        return hashlib.sha256(hostname.encode()).hexdigest()[:16]
    
    def transform_record(self, row: Dict[str, Any], bacalhau_job_id: str) -> Dict[str, Any]:
        """Transform a single SQLite row to structured JSON format."""
        # Parse timestamp
        timestamp = row.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = parser.parse(timestamp).isoformat()
        
        # Build structured JSON
        structured_data = {
            "timestamp": timestamp,
            "sensor_id": row.get('sensor_id'),
            "readings": {
                "temperature": float(row.get('temperature', 0)),
                "humidity": float(row.get('humidity', 0)),
                "pressure": float(row.get('pressure', 0)),
                "vibration": float(row.get('vibration', 0)),
                "voltage": float(row.get('voltage', 0))
            },
            "status": {
                "status_code": int(row.get('status_code', 0)),
                "anomaly_flag": bool(row.get('anomaly_flag', False)),
                "anomaly_type": row.get('anomaly_type'),
                "synced": bool(row.get('synced', False))
            },
            "device_info": {
                "manufacturer": row.get('manufacturer'),
                "model": row.get('model'),
                "firmware_version": row.get('firmware_version'),
                "serial_number": row.get('serial_number'),
                "manufacture_date": row.get('manufacture_date')
            },
            "location_info": {
                "location": row.get('location'),
                "latitude": float(row.get('latitude', 0)),
                "longitude": float(row.get('longitude', 0)),
                "original_timezone": row.get('original_timezone')
            },
            "deployment_info": {
                "deployment_type": row.get('deployment_type'),
                "installation_date": row.get('installation_date'),
                "height_meters": float(row.get('height_meters')) if row.get('height_meters') else None,
                "orientation_degrees": float(row.get('orientation_degrees')) if row.get('orientation_degrees') else None
            },
            "metadata": {
                "instance_id": row.get('instance_id'),
                "sensor_type": row.get('sensor_type')
            },
            "transformation_metadata": {
                "bacalhau_job_id": bacalhau_job_id,
                "transformation_timestamp": datetime.now(timezone.utc).isoformat(),
                "node_identity_hash": self.node_identity_hash,
                "transformation_version": TRANSFORMATION_VERSION,
                "original_record_id": row.get('id')
            }
        }
        
        return structured_data
    
    def validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate a record against the JSON schema."""
        try:
            jsonschema.validate(instance=record, schema=self.schema)
            return True
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"Validation error for record {record.get('sensor_id')}: {e}")
            return False
    
    def transform_sqlite_to_json(self, 
                                db_path: str, 
                                output_path: str,
                                bacalhau_job_id: str,
                                table_name: str = "sensor_readings",
                                limit: Optional[int] = None,
                                where_clause: Optional[str] = None) -> Dict[str, Any]:
        """Transform SQLite data to JSON format."""
        stats = {
            "total_records": 0,
            "transformed": 0,
            "validation_errors": 0,
            "transformation_errors": 0
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
                "stats": stats
            },
            "records": output_records
        }
        
        with open(output_path, 'w') as f:
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Transform data
    transformer = SensorDataTransformer(schema_path=args.schema)
    stats = transformer.transform_sqlite_to_json(
        db_path=args.db_path,
        output_path=args.output,
        bacalhau_job_id=args.job_id,
        table_name=args.table,
        limit=args.limit,
        where_clause=args.where
    )
    
    print(f"Transformation complete: {stats}")


if __name__ == "__main__":
    main()