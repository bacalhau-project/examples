#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "python-dotenv",
#   "rich",
# ]
# ///

"""Get details about the storage credential including IAM role ARN."""

import os
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

console = Console()

def get_workspace_client() -> WorkspaceClient:
    """Create Databricks workspace client from environment variables."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    
    if not host or not token:
        console.print("[red]Error: DATABRICKS_HOST and DATABRICKS_TOKEN must be set in .env[/red]")
        sys.exit(1)
    
    return WorkspaceClient(host=host, token=token)

def main():
    """Get storage credential details."""
    console.print(Panel.fit("[bold blue]Storage Credential Details[/bold blue]"))
    
    client = get_workspace_client()
    
    try:
        # Get the specific storage credential
        cred_name = "s3_storage_for_sensor_data"
        cred = client.storage_credentials.get(cred_name)
        
        console.print(f"\n[bold]Storage Credential:[/bold] {cred.name}")
        console.print(f"[bold]Comment:[/bold] {cred.comment or 'No comment'}")
        console.print(f"[bold]Created by:[/bold] {cred.created_by}")
        
        if hasattr(cred, 'aws_iam_role') and cred.aws_iam_role:
            console.print(f"\n[bold green]AWS IAM Role Details:[/bold green]")
            console.print(f"  Role ARN: [yellow]{cred.aws_iam_role.role_arn}[/yellow]")
            
            # Extract role name from ARN
            role_name = cred.aws_iam_role.role_arn.split('/')[-1]
            console.print(f"  Role Name: [yellow]{role_name}[/yellow]")
            
            console.print(f"\n[bold]To update IAM permissions:[/bold]")
            console.print(f"1. Run: [green]./update-iam-role-for-new-buckets.sh[/green]")
            console.print(f"2. When prompted, enter role name: [yellow]{role_name}[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    main()