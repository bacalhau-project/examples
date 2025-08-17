#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "requests>=2.31.0",
#     "pydantic>=2.0.0",
# ]
# ///

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import boto3
import requests
from pydantic import BaseModel, Field


class SchemaMetadata(BaseModel):
    """Metadata about a cached schema."""
    
    url: str = Field(..., description="Source URL of the schema")
    version: str = Field(..., description="Schema version")
    fetched_at: datetime = Field(..., description="When schema was fetched")
    checksum: str = Field(..., description="SHA256 checksum of schema")
    ttl_hours: int = Field(default=24, description="Cache TTL in hours")
    
    def is_expired(self) -> bool:
        """Check if cached schema has expired."""
        expiry = self.fetched_at + timedelta(hours=self.ttl_hours)
        return datetime.now() > expiry


class JsonSchemaManager:
    """Manages JSON Schema fetching, caching, and versioning."""
    
    def __init__(
        self,
        cache_dir: str = "/tmp/schema_cache",
        default_ttl_hours: int = 24,
        max_retries: int = 3,
        aws_region: str = "us-west-2"
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl_hours = default_ttl_hours
        self.max_retries = max_retries
        self.aws_region = aws_region
        self._s3_client = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
    
    @property
    def s3_client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client('s3', region_name=self.aws_region)
        return self._s3_client
    
    def fetch_from_s3(self, url: str) -> Dict[str, Any]:
        parsed = urlparse(url)
        
        if parsed.scheme == 's3':
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
        elif 's3' in parsed.netloc and 'amazonaws.com' in parsed.netloc:
            parts = parsed.netloc.split('.')
            bucket = parts[0]
            key = parsed.path.lstrip('/')
        else:
            raise ValueError(f"Invalid S3 URL format: {url}")
        
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch schema from S3: {e}")
    
    def fetch_from_http(self, url: str) -> Dict[str, Any]:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch schema from HTTP: {e}")
    
    def fetch_schema(self, url: str) -> Dict[str, Any]:
        parsed = urlparse(url)
        
        for attempt in range(self.max_retries):
            try:
                if parsed.scheme in ('s3',) or 's3.amazonaws.com' in url:
                    return self.fetch_from_s3(url)
                elif parsed.scheme in ('http', 'https'):
                    return self.fetch_from_http(url)
                else:
                    raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                
                wait_time = 2 ** attempt
                print(f"Fetch attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
        
        raise RuntimeError(f"Failed to fetch schema after {self.max_retries} attempts")
    
    def get_schema(self, url: str, version: str = "latest") -> Dict[str, Any]:
        print(f"Fetching schema from {url}")
        return self.fetch_schema(url)


# Test the manager
if __name__ == "__main__":
    manager = JsonSchemaManager(
        cache_dir="/tmp/wind_turbine_schema_cache",
        default_ttl_hours=24
    )
    
    s3_url = "https://expanso-databricks-ingestion-us-west-2.s3.us-west-2.amazonaws.com/schemas/wind-turbine-schema-v1.0.json"
    
    print("Testing JSON Schema Manager")
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
