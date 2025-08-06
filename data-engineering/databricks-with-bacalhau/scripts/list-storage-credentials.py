#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "python-dotenv",
#   "rich",
# ]
# ///

"""List all storage credentials in Unity Catalog."""

import os
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

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
    """List storage credentials."""
    console.print("[bold blue]Unity Catalog Storage Credentials[/bold blue]")
    console.print("=" * 60)
    
    client = get_workspace_client()
    
    try:
        credentials = client.storage_credentials.list()
        
        if not credentials:
            console.print("[yellow]No storage credentials found[/yellow]")
            return
        
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Comment", style="yellow")
        table.add_column("Created By", style="magenta")
        
        for cred in credentials:
            cred_type = "Unknown"
            if hasattr(cred, 'aws_iam_role') and cred.aws_iam_role:
                cred_type = "AWS IAM Role"
            elif hasattr(cred, 'azure_service_principal') and cred.azure_service_principal:
                cred_type = "Azure Service Principal"
            elif hasattr(cred, 'gcp_service_account_key') and cred.gcp_service_account_key:
                cred_type = "GCP Service Account"
                
            table.add_row(
                cred.name,
                cred_type,
                cred.comment or "",
                cred.created_by or ""
            )
        
        console.print(table)
        
        # Also list external locations
        console.print("\n[bold blue]Existing External Locations[/bold blue]")
        console.print("=" * 60)
        
        locations = client.external_locations.list()
        
        if not locations:
            console.print("[yellow]No external locations found[/yellow]")
        else:
            loc_table = Table()
            loc_table.add_column("Name", style="cyan")
            loc_table.add_column("URL", style="yellow")
            loc_table.add_column("Storage Credential", style="green")
            
            for loc in locations:
                loc_table.add_row(
                    loc.name,
                    loc.url,
                    loc.credential_name
                )
            
            console.print(loc_table)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[yellow]Note: You may need account-level permissions to list storage credentials[/yellow]")

if __name__ == "__main__":
    main()