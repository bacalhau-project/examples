#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3>=1.26.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0",
# ]
# ///
"""
Check lineage and metadata for uploaded data.

This script queries S3 to find uploads by job ID, node ID, or time range,
and displays the complete lineage information.
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import boto3
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint

load_dotenv()

console = Console()


class LineageChecker:
    def __init__(self):
        """Initialize S3 client."""
        # Load credentials
        self._load_credentials()
        
        self.s3_client = boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION", "us-west-2"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        
        # Bucket mapping
        self.buckets = {
            "raw": "expanso-databricks-ingestion-us-west-2",
            "validated": "expanso-databricks-validated-us-west-2",
            "enriched": "expanso-databricks-enriched-us-west-2",
            "aggregated": "expanso-databricks-aggregated-us-west-2",
        }
    
    def _load_credentials(self):
        """Load AWS credentials from various sources."""
        cred_paths = [
            "credentials/expanso-s3-env.sh",
            "/bacalhau_data/credentials/expanso-s3-env.sh",
        ]
        
        for path in cred_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("export "):
                            line = line.replace("export ", "")
                            if "=" in line:
                                key, value = line.split("=", 1)
                                # Remove quotes and clean value
                                value = value.strip().strip('"').strip("'")
                                os.environ[key] = value
                console.print(f"[green]Loaded credentials from {path}[/green]")
                return
    
    def find_by_job_id(self, job_id: str) -> List[Dict[str, Any]]:
        """Find all uploads with a specific job ID."""
        results = []
        
        for pipeline_type, bucket in self.buckets.items():
            try:
                # List objects with the job ID in metadata
                response = self.s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=f"{pipeline_type}/"
                )
                
                if "Contents" not in response:
                    continue
                
                for obj in response["Contents"]:
                    if "metadata.json" in obj["Key"]:
                        # Get the metadata file
                        meta_response = self.s3_client.get_object(
                            Bucket=bucket,
                            Key=obj["Key"]
                        )
                        metadata = json.loads(meta_response["Body"].read())
                        
                        if metadata.get("job_id") == job_id:
                            results.append({
                                "bucket": bucket,
                                "key": obj["Key"],
                                "metadata": metadata
                            })
            except Exception as e:
                console.print(f"[yellow]Error checking {bucket}: {e}[/yellow]")
        
        return results
    
    def find_by_node_id(self, node_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find recent uploads from a specific node."""
        results = []
        
        for pipeline_type, bucket in self.buckets.items():
            try:
                # List recent objects
                response = self.s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=f"{pipeline_type}/",
                    MaxKeys=limit * 2  # Get more to filter
                )
                
                if "Contents" not in response:
                    continue
                
                for obj in response["Contents"]:
                    if "metadata.json" in obj["Key"]:
                        # Get the metadata file
                        meta_response = self.s3_client.get_object(
                            Bucket=bucket,
                            Key=obj["Key"]
                        )
                        metadata = json.loads(meta_response["Body"].read())
                        
                        if metadata.get("node_id") == node_id:
                            results.append({
                                "bucket": bucket,
                                "key": obj["Key"],
                                "metadata": metadata
                            })
                            
                            if len(results) >= limit:
                                break
            except Exception as e:
                console.print(f"[yellow]Error checking {bucket}: {e}[/yellow]")
        
        return results[:limit]
    
    def find_recent(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Find uploads from the last N hours."""
        results = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        for pipeline_type, bucket in self.buckets.items():
            try:
                # List recent objects
                response = self.s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=f"{pipeline_type}/"
                )
                
                if "Contents" not in response:
                    continue
                
                for obj in response["Contents"]:
                    if obj["LastModified"].replace(tzinfo=None) > cutoff_time:
                        if "metadata.json" in obj["Key"]:
                            # Get the metadata file
                            meta_response = self.s3_client.get_object(
                                Bucket=bucket,
                                Key=obj["Key"]
                            )
                            metadata = json.loads(meta_response["Body"].read())
                            
                            results.append({
                                "bucket": bucket,
                                "key": obj["Key"],
                                "metadata": metadata
                            })
            except Exception as e:
                console.print(f"[yellow]Error checking {bucket}: {e}[/yellow]")
        
        return results
    
    def display_lineage(self, results: List[Dict[str, Any]]):
        """Display lineage information in a formatted table."""
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        table = Table(title="Data Lineage Information")
        table.add_column("Job ID", style="cyan")
        table.add_column("Node ID", style="green")
        table.add_column("Pipeline", style="yellow")
        table.add_column("Timestamp", style="blue")
        table.add_column("Records", style="magenta")
        table.add_column("Location", style="white")
        
        for result in results:
            meta = result["metadata"]
            table.add_row(
                meta.get("job_id", "N/A"),
                meta.get("node_id", "N/A"),
                meta.get("pipeline_stage", "N/A"),
                meta.get("upload_timestamp", "N/A")[:19],
                str(meta.get("source", {}).get("record_count", 0)),
                f"s3://{result['bucket']}/{meta.get('destination', {}).get('data_path', 'N/A')}"
            )
        
        console.print(table)
        
        # Show detailed metadata for first result
        if results and len(results) == 1:
            console.print("\n[bold]Detailed Metadata:[/bold]")
            tree = Tree("📋 Upload Metadata")
            meta = results[0]["metadata"]
            
            # Job info
            job_tree = tree.add("🏷️ Job Information")
            job_tree.add(f"Job ID: {meta.get('job_id')}")
            job_tree.add(f"Node ID: {meta.get('node_id')}")
            job_tree.add(f"Pipeline: {meta.get('pipeline_stage')}")
            job_tree.add(f"Timestamp: {meta.get('upload_timestamp')}")
            
            # Source info
            source_tree = tree.add("📂 Source")
            source = meta.get("source", {})
            source_tree.add(f"Database: {source.get('database')}")
            source_tree.add(f"Table: {source.get('table')}")
            source_tree.add(f"Records: {source.get('record_count')}")
            
            time_range = source.get("time_range", {})
            if time_range:
                time_tree = source_tree.add("⏱️ Time Range")
                time_tree.add(f"Start: {time_range.get('start')}")
                time_tree.add(f"End: {time_range.get('end')}")
            
            # Environment info
            env_tree = tree.add("🔧 Environment")
            env = meta.get("environment", {})
            env_tree.add(f"Container: {meta.get('container_id')}")
            env_tree.add(f"Version: {meta.get('uploader_version')}")
            env_tree.add(f"Image: {env.get('image')}")
            
            console.print(tree)


def main():
    parser = argparse.ArgumentParser(description="Check data lineage and metadata")
    parser.add_argument("--job-id", help="Find uploads by job ID")
    parser.add_argument("--node-id", help="Find uploads by node ID")
    parser.add_argument("--recent", type=int, help="Find uploads from last N hours")
    parser.add_argument("--limit", type=int, default=10, help="Maximum results to show")
    
    args = parser.parse_args()
    
    checker = LineageChecker()
    
    if args.job_id:
        console.print(f"[bold]Searching for job ID: {args.job_id}[/bold]\n")
        results = checker.find_by_job_id(args.job_id)
    elif args.node_id:
        console.print(f"[bold]Searching for node ID: {args.node_id}[/bold]\n")
        results = checker.find_by_node_id(args.node_id, args.limit)
    elif args.recent:
        console.print(f"[bold]Searching for uploads from last {args.recent} hours[/bold]\n")
        results = checker.find_recent(args.recent)
    else:
        console.print("[bold]Recent uploads (last hour):[/bold]\n")
        results = checker.find_recent(1)
    
    checker.display_lineage(results)


if __name__ == "__main__":
    main()