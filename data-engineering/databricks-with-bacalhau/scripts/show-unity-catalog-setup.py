#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv",
#   "rich",
# ]
# ///

"""Show Unity Catalog setup information based on .env configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

console = Console()

# Get configuration
S3_BUCKET_PREFIX = os.getenv("S3_BUCKET_PREFIX", "expanso")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_ACCOUNT_ID = os.getenv("DATABRICKS_ACCOUNT_ID", "")

console.print("[bold blue]Unity Catalog Setup Information[/bold blue]")
console.print("=" * 60)

console.print("\n[bold]Current Configuration (from .env):[/bold]")
config_table = Table()
config_table.add_column("Variable", style="cyan")
config_table.add_column("Value", style="green")

config_table.add_row("S3_BUCKET_PREFIX", S3_BUCKET_PREFIX)
config_table.add_row("AWS_REGION", AWS_REGION)
config_table.add_row("DATABRICKS_HOST", DATABRICKS_HOST)
config_table.add_row("DATABRICKS_ACCOUNT_ID", DATABRICKS_ACCOUNT_ID)
config_table.add_row("DATABRICKS_EXTERNAL_ID", "[red]Not set - you need to get this from Databricks[/red]")

console.print(config_table)

console.print("\n[bold]Your S3 Buckets:[/bold]")
bucket_table = Table()
bucket_table.add_column("Purpose", style="cyan")
bucket_table.add_column("Bucket Name", style="yellow")

buckets = [
    ("Ingestion", f"{S3_BUCKET_PREFIX}-databricks-ingestion-{AWS_REGION}"),
    ("Validated", f"{S3_BUCKET_PREFIX}-databricks-validated-{AWS_REGION}"),
    ("Enriched", f"{S3_BUCKET_PREFIX}-databricks-enriched-{AWS_REGION}"),
    ("Aggregated", f"{S3_BUCKET_PREFIX}-databricks-aggregated-{AWS_REGION}"),
    ("Checkpoints", f"{S3_BUCKET_PREFIX}-databricks-checkpoints-{AWS_REGION}"),
    ("Metadata", f"{S3_BUCKET_PREFIX}-databricks-metadata-{AWS_REGION}"),
]

for purpose, bucket in buckets:
    bucket_table.add_row(purpose, bucket)

console.print(bucket_table)

console.print("\n[bold yellow]To get your DATABRICKS_EXTERNAL_ID:[/bold yellow]")
console.print("1. Go to your Databricks workspace")
console.print("2. Navigate to: Catalog → External Locations → Create External Location")
console.print("3. Click on 'Create a new storage credential'")
console.print("4. Select 'AWS IAM Role'")
console.print("5. Copy the External ID shown there")
console.print("6. Add it to your .env file as: DATABRICKS_EXTERNAL_ID=<your-external-id>")

console.print("\n[bold]Once you have the External ID, run:[/bold]")
console.print("cd scripts")
console.print("uv run -s setup-unity-catalog-storage.py")

console.print("\n[bold]The script will create:[/bold]")
console.print(f"- IAM Role: databricks-unity-catalog-{S3_BUCKET_PREFIX}-role")
console.print(f"- Storage Credential: {S3_BUCKET_PREFIX}_s3_credential")
console.print("- 6 External Locations (one for each bucket)")