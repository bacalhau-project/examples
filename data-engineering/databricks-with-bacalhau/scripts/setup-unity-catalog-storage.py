#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "boto3",
#   "click",
#   "rich",
#   "python-dotenv",
# ]
# ///

"""
Setup Unity Catalog storage credentials and external locations for Databricks.

This script:
1. Creates an IAM role for Unity Catalog with proper S3 access
2. Creates storage credential in Unity Catalog
3. Creates external locations for each S3 bucket

Environment variables (from .env):
- DATABRICKS_HOST: Databricks workspace URL
- DATABRICKS_ACCOUNT_ID: Databricks account ID
- DATABRICKS_EXTERNAL_ID: External ID for storage credential
- AWS_REGION: AWS region (default: us-west-2)
- S3_BUCKET_PREFIX: Prefix for S3 bucket names (default: expanso)
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import boto3
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()

# Load environment variables
load_dotenv()

# Configuration from environment
S3_BUCKET_PREFIX = os.getenv("S3_BUCKET_PREFIX", "expanso")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# Bucket configuration
BUCKET_TYPES = ["ingestion", "validated", "enriched", "aggregated", "checkpoints", "metadata"]

def get_bucket_name(bucket_type: str) -> str:
    """Get bucket name with prefix and region."""
    return f"{S3_BUCKET_PREFIX}-databricks-{bucket_type}-{AWS_REGION}"

def get_external_location_name(bucket_type: str) -> str:
    """Get external location name."""
    return f"{S3_BUCKET_PREFIX}_{bucket_type}_data" if bucket_type in ["ingestion", "validated", "enriched", "aggregated"] else f"{S3_BUCKET_PREFIX}_{bucket_type}"


def extract_workspace_id(workspace_url: str) -> Optional[str]:
    """Extract workspace ID from Databricks URL."""
    # Format: https://dbc-XXXXXXXX-XXXX.cloud.databricks.com
    match = re.search(r'dbc-([a-f0-9-]+)\.', workspace_url)
    if match:
        return match.group(1)
    
    # Also try e2-dogfood format
    match = re.search(r'e2-dogfood-([a-f0-9-]+)\.', workspace_url)
    if match:
        return match.group(1)
    
    return None


def get_databricks_config() -> tuple[str, str, str]:
    """Get Databricks configuration from environment or user input."""
    # Try to get from environment first
    workspace_url = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    account_id = os.getenv("DATABRICKS_ACCOUNT_ID", "")
    external_id = os.getenv("DATABRICKS_EXTERNAL_ID", "")
    
    # Prompt for missing values
    if not workspace_url:
        workspace_url = click.prompt(
            "Enter your Databricks workspace URL (e.g., https://dbc-12345678-90ab.cloud.databricks.com)",
            type=str
        )
    
    workspace_id = extract_workspace_id(workspace_url)
    if not workspace_id:
        console.print(f"[red]Could not extract workspace ID from URL: {workspace_url}[/red]")
        workspace_id = click.prompt("Enter workspace ID manually", type=str)
    
    if not account_id:
        account_id = click.prompt(
            "Enter your Databricks account ID (found in account console)",
            type=str
        )
    
    if not external_id:
        external_id = click.prompt(
            "Enter the External ID from your Databricks storage credential setup",
            type=str
        )
    
    return workspace_id, account_id, external_id


def create_iam_role(role_name: str, workspace_id: str, account_id: str, external_id: str) -> Dict:
    """Create IAM role for Unity Catalog."""
    iam = boto3.client('iam')
    sts = boto3.client('sts')
    
    # Get current AWS account ID
    aws_account_id = sts.get_caller_identity()['Account']
    
    # Trust policy for Unity Catalog
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "sts:ExternalId": external_id
                    }
                }
            }
        ]
    }
    
    # S3 access policy - use bucket names from configuration
    bucket_resources = []
    for bucket_type in BUCKET_TYPES:
        bucket_name = get_bucket_name(bucket_type)
        bucket_resources.extend([
            f"arn:aws:s3:::{bucket_name}/*",
            f"arn:aws:s3:::{bucket_name}"
        ])
    
    s3_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:ListBucketMultipartUploads",
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts"
                ],
                "Resource": bucket_resources
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sts:AssumeRole"
                ],
                "Resource": [
                    f"arn:aws:iam::{aws_account_id}:role/{role_name}"
                ]
            }
        ]
    }
    
    try:
        # Create the role
        console.print(f"Creating IAM role: {role_name}")
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Unity Catalog storage access role for Databricks',
            MaxSessionDuration=43200  # 12 hours
        )
        
        # Create and attach the policy
        policy_name = f"{role_name}-Policy"
        console.print(f"Creating IAM policy: {policy_name}")
        
        policy_response = iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(s3_policy),
            Description='S3 access policy for Unity Catalog'
        )
        
        # Attach the policy to the role
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_response['Policy']['Arn']
        )
        
        console.print(f"[green]✓ Created IAM role: {role_response['Role']['Arn']}[/green]")
        return role_response['Role']
        
    except iam.exceptions.EntityAlreadyExistsException:
        console.print(f"[yellow]IAM role {role_name} already exists[/yellow]")
        
        # Update the trust policy
        try:
            console.print("Updating trust policy...")
            iam.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust_policy)
            )
            console.print("[green]✓ Updated trust policy[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not update trust policy: {e}[/yellow]")
        
        return iam.get_role(RoleName=role_name)['Role']


def generate_databricks_sql(role_arn: str, external_id: str) -> str:
    """Generate SQL commands for Databricks."""
    sql_commands = []
    
    # Storage credential name
    storage_credential_name = f"{S3_BUCKET_PREFIX}_s3_credential"
    
    # Create storage credential
    sql_commands.append(f"""
-- Create storage credential
CREATE STORAGE CREDENTIAL IF NOT EXISTS {storage_credential_name}
WITH (
  AWS_IAM_ROLE = '{role_arn}'
);

-- Grant usage on storage credential
GRANT USAGE ON STORAGE CREDENTIAL {storage_credential_name} TO `account users`;
""")
    
    # Create external locations
    for bucket_type in BUCKET_TYPES:
        bucket_name = get_bucket_name(bucket_type)
        location_name = get_external_location_name(bucket_type)
        
        # Different paths for different bucket types
        if bucket_type in ["ingestion", "validated", "enriched", "aggregated"]:
            s3_path = f"s3://{bucket_name}/{bucket_type}/"
        else:
            s3_path = f"s3://{bucket_name}/"
        
        sql_commands.append(f"""
-- Create external location for {bucket_type}
CREATE EXTERNAL LOCATION IF NOT EXISTS {location_name}
WITH (
  STORAGE_CREDENTIAL = {storage_credential_name},
  URL = '{s3_path}'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION {location_name} TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION {location_name} TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION {location_name} TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION {location_name} TO `account users`;
""")
    
    # Add verification commands
    sql_commands.append("""
-- Verify the setup
SHOW STORAGE CREDENTIALS;
SHOW EXTERNAL LOCATIONS;
""")
    
    return "\n".join(sql_commands)


@click.command()
@click.option('--workspace-id', help='Databricks workspace ID (or set DATABRICKS_HOST in .env)')
@click.option('--account-id', help='Databricks account ID (or set DATABRICKS_ACCOUNT_ID in .env)')
@click.option('--external-id', help='External ID for storage credential (or set DATABRICKS_EXTERNAL_ID in .env)')
@click.option('--role-name', help='IAM role name', default=None)
@click.option('--region', help='AWS region (or set AWS_REGION in .env)', default=None)
@click.option('--prefix', help='S3 bucket prefix (or set S3_BUCKET_PREFIX in .env)', default=None)
def main(workspace_id: Optional[str], account_id: Optional[str], external_id: Optional[str], 
         role_name: Optional[str], region: Optional[str], prefix: Optional[str]):
    """Setup Unity Catalog storage credentials and external locations."""
    
    console.print("[bold blue]Unity Catalog Storage Setup[/bold blue]")
    console.print("=" * 50)
    
    # Override environment variables if provided
    if region:
        global AWS_REGION
        AWS_REGION = region
    if prefix:
        global S3_BUCKET_PREFIX
        S3_BUCKET_PREFIX = prefix
    
    # Set default role name based on prefix
    if not role_name:
        role_name = f"databricks-unity-catalog-{S3_BUCKET_PREFIX}-role"
    
    # Display configuration
    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  S3 Bucket Prefix: {S3_BUCKET_PREFIX}")
    console.print(f"  AWS Region: {AWS_REGION}")
    console.print(f"  IAM Role Name: {role_name}")
    
    # Get Databricks configuration
    if not all([workspace_id, account_id, external_id]):
        workspace_id, account_id, external_id = get_databricks_config()
    
    # Set AWS region
    boto3.setup_default_session(region_name=AWS_REGION)
    
    # Create IAM role
    console.print("\n[bold]Step 1: Creating IAM Role[/bold]")
    role = create_iam_role(role_name, workspace_id, account_id, external_id)
    role_arn = role['Arn']
    
    # Generate SQL commands
    console.print("\n[bold]Step 2: Generating Databricks SQL Commands[/bold]")
    sql_commands = generate_databricks_sql(role_arn, external_id)
    
    # Save SQL to file
    sql_file = Path("setup-unity-catalog-storage.sql")
    sql_file.write_text(sql_commands)
    console.print(f"[green]✓ SQL commands saved to: {sql_file}[/green]")
    
    # Display summary
    console.print("\n[bold]Summary[/bold]")
    table = Table(title="Created Resources")
    table.add_column("Resource", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("IAM Role ARN", role_arn)
    table.add_row("External ID", external_id)
    table.add_row("Storage Credential", f"{S3_BUCKET_PREFIX}_s3_credential")
    table.add_row("SQL File", str(sql_file))
    
    console.print(table)
    
    # Display bucket mapping
    console.print("\n[bold]S3 Buckets and External Locations:[/bold]")
    bucket_table = Table()
    bucket_table.add_column("Bucket Type", style="cyan")
    bucket_table.add_column("S3 Bucket", style="yellow")
    bucket_table.add_column("External Location", style="green")
    
    for bucket_type in BUCKET_TYPES:
        bucket_table.add_row(
            bucket_type,
            get_bucket_name(bucket_type),
            get_external_location_name(bucket_type)
        )
    
    console.print(bucket_table)
    
    # Next steps
    console.print("\n[bold yellow]Next Steps:[/bold yellow]")
    console.print("1. Go to your Databricks workspace")
    console.print("2. Open a SQL editor (Catalog Explorer → SQL Editor)")
    console.print(f"3. Run the SQL commands from: {sql_file}")
    console.print("4. Verify the storage credential and external locations were created")
    console.print("\n[bold]To verify in Databricks SQL:[/bold]")
    console.print("SHOW STORAGE CREDENTIALS;")
    console.print("SHOW EXTERNAL LOCATIONS;")


if __name__ == "__main__":
    main()