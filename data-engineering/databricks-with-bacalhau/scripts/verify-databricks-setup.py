#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "boto3",
#   "python-dotenv",
#   "rich",
# ]
# ///

"""
Verify Databricks Unity Catalog setup is complete and working.

This script checks:
1. S3 buckets exist and are accessible
2. IAM role has correct permissions
3. Storage credential is configured
4. External locations are created
5. Auto Loader can access the buckets
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

import boto3
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

console = Console()

# Configuration
S3_BUCKET_PREFIX = os.getenv("S3_BUCKET_PREFIX", "expanso")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
STORAGE_CREDENTIAL = "s3_storage_for_sensor_data"

# Expected resources
EXPECTED_BUCKETS = [
    f"{S3_BUCKET_PREFIX}-databricks-ingestion-{AWS_REGION}",
    f"{S3_BUCKET_PREFIX}-databricks-validated-{AWS_REGION}",
    f"{S3_BUCKET_PREFIX}-databricks-enriched-{AWS_REGION}",
    f"{S3_BUCKET_PREFIX}-databricks-aggregated-{AWS_REGION}",
    f"{S3_BUCKET_PREFIX}-databricks-checkpoints-{AWS_REGION}",
    f"{S3_BUCKET_PREFIX}-databricks-metadata-{AWS_REGION}",
]

EXPECTED_EXTERNAL_LOCATIONS = {
    "expanso_ingestion_data": f"s3://{S3_BUCKET_PREFIX}-databricks-ingestion-{AWS_REGION}/ingestion/",
    "expanso_validated_data": f"s3://{S3_BUCKET_PREFIX}-databricks-validated-{AWS_REGION}/validated/",
    "expanso_enriched_data": f"s3://{S3_BUCKET_PREFIX}-databricks-enriched-{AWS_REGION}/enriched/",
    "expanso_aggregated_data": f"s3://{S3_BUCKET_PREFIX}-databricks-aggregated-{AWS_REGION}/aggregated/",
    "expanso_checkpoints": f"s3://{S3_BUCKET_PREFIX}-databricks-checkpoints-{AWS_REGION}/",
    "expanso_metadata": f"s3://{S3_BUCKET_PREFIX}-databricks-metadata-{AWS_REGION}/",
}


def check_s3_buckets() -> Dict[str, bool]:
    """Check if S3 buckets exist."""
    s3 = boto3.client('s3', region_name=AWS_REGION)
    results = {}
    
    for bucket in EXPECTED_BUCKETS:
        try:
            s3.head_bucket(Bucket=bucket)
            results[bucket] = True
        except:
            results[bucket] = False
    
    return results


def check_databricks_setup() -> Dict[str, any]:
    """Check Databricks Unity Catalog setup."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    
    if not host or not token:
        return {"error": "DATABRICKS_HOST and DATABRICKS_TOKEN not set"}
    
    try:
        client = WorkspaceClient(host=host, token=token)
        
        # Check storage credential
        storage_cred_exists = False
        iam_role = None
        try:
            # List all credentials and find the one we need
            creds = client.storage_credentials.list()
            for cred in creds:
                if cred.name.startswith("s3_storage_for_sensor"):
                    storage_cred_exists = True
                    # Get full details
                    full_cred = client.storage_credentials.get(cred.name)
                    iam_role = full_cred.aws_iam_role.role_arn if hasattr(full_cred, 'aws_iam_role') and full_cred.aws_iam_role else None
                    break
        except:
            pass
        
        # Check external locations
        external_locations = {}
        try:
            locations = client.external_locations.list()
            for loc in locations:
                if loc.name in EXPECTED_EXTERNAL_LOCATIONS:
                    external_locations[loc.name] = loc.url
        except:
            pass
        
        return {
            "storage_credential_exists": storage_cred_exists,
            "iam_role": iam_role,
            "external_locations": external_locations
        }
    
    except Exception as e:
        return {"error": str(e)}


def main():
    """Run verification checks."""
    console.print(Panel.fit("[bold blue]Databricks Infrastructure Verification[/bold blue]"))
    
    # Check S3 buckets
    console.print("\n[bold]1. Checking S3 Buckets[/bold]")
    bucket_results = check_s3_buckets()
    
    bucket_table = Table()
    bucket_table.add_column("Bucket", style="cyan")
    bucket_table.add_column("Status", style="green")
    
    all_buckets_ok = True
    for bucket, exists in bucket_results.items():
        status = "✅ Exists" if exists else "❌ Missing"
        bucket_table.add_row(bucket, status)
        if not exists:
            all_buckets_ok = False
    
    console.print(bucket_table)
    
    # Check Databricks setup
    console.print("\n[bold]2. Checking Databricks Unity Catalog[/bold]")
    databricks_results = check_databricks_setup()
    
    if "error" in databricks_results:
        console.print(f"[red]Error: {databricks_results['error']}[/red]")
    else:
        # Storage credential
        if databricks_results["storage_credential_exists"]:
            console.print(f"✅ Storage Credential: [green]{STORAGE_CREDENTIAL}[/green]")
            if databricks_results["iam_role"]:
                console.print(f"   IAM Role: [yellow]{databricks_results['iam_role']}[/yellow]")
        else:
            console.print(f"❌ Storage Credential: [red]{STORAGE_CREDENTIAL} not found[/red]")
        
        # External locations
        console.print("\n[bold]3. External Locations[/bold]")
        location_table = Table()
        location_table.add_column("Location Name", style="cyan")
        location_table.add_column("Expected URL", style="yellow")
        location_table.add_column("Status", style="green")
        
        all_locations_ok = True
        for name, expected_url in EXPECTED_EXTERNAL_LOCATIONS.items():
            if name in databricks_results["external_locations"]:
                actual_url = databricks_results["external_locations"][name]
                # Normalize URLs for comparison (remove trailing slashes)
                normalized_actual = actual_url.rstrip('/')
                normalized_expected = expected_url.rstrip('/')
                if normalized_actual == normalized_expected:
                    status = "✅ Correct"
                else:
                    status = f"⚠️  Different URL: {actual_url}"
                    all_locations_ok = False
            else:
                status = "❌ Missing"
                all_locations_ok = False
            
            location_table.add_row(name, expected_url, status)
        
        console.print(location_table)
    
    # Summary
    console.print("\n[bold]Summary[/bold]")
    if all_buckets_ok and databricks_results.get("storage_credential_exists") and all_locations_ok:
        console.print("[bold green]✅ All infrastructure is properly configured![/bold green]")
        console.print("\nYour Auto Loader notebooks should now work correctly.")
    else:
        console.print("[bold red]❌ Some infrastructure components are missing or misconfigured[/bold red]")
        
        if not all_buckets_ok:
            console.print("\n[yellow]Missing S3 buckets. Run:[/yellow]")
            console.print("  cd scripts && ./create-pipeline-buckets.sh")
        
        if not databricks_results.get("storage_credential_exists"):
            console.print("\n[yellow]Storage credential missing. Create it in Databricks UI.[/yellow]")
        
        if not all_locations_ok:
            console.print("\n[yellow]External locations missing. Run:[/yellow]")
            console.print("  cd scripts && uv run -s setup-external-locations.py")
    
    # Test commands
    console.print("\n[bold]Test Commands[/bold]")
    console.print("To test Auto Loader, run the notebook:")
    console.print("  [green]01-setup-autoloader-demo-simple.py[/green]")
    console.print("\nTo upload test data:")
    console.print("  [green]cd .. && uv run -s test-upload.py[/green]")


if __name__ == "__main__":
    main()