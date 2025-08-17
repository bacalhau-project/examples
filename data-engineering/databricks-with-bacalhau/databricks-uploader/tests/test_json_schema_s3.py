#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "pydantic>=2.0.0",
# ]
# ///

import json
from spec_version_manager import JsonSchemaManager

# Test using S3 protocol
manager = JsonSchemaManager()

# Use S3 protocol URL instead
s3_url = "s3://expanso-databricks-ingestion-us-west-2/schemas/wind-turbine-schema-v1.0.json"

print("Testing JSON Schema Manager with S3 protocol")
print("="*50)

print("\n1. Fetching schema from S3...")
try:
    schema = manager.get_schema(s3_url, version="1.0")
    print(f"✓ Successfully fetched schema with {len(schema.get('properties', {}))} properties")
    print(f"  Title: {schema.get('title', 'N/A')}")
    print(f"  Description: {schema.get('description', 'N/A')}")
    print(f"  Required fields: {', '.join(schema.get('required', [])[:5])}...")
except Exception as e:
    print(f"✗ Failed to fetch schema: {e}")
