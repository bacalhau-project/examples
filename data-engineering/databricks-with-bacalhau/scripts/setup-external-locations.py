#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "python-dotenv",
#   "rich",
#   "click",
# ]
# ///

"""
Create Unity Catalog external locations using Databricks SDK.

This script creates all necessary external locations programmatically
without needing to use the Databricks UI.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict

import click
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

console = Console()

# Configuration
S3_BUCKET_PREFIX = os.getenv("S3_BUCKET_PREFIX", "expanso")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
STORAGE_CREDENTIAL = "expanso-databricks-s3-credential-us-west-2"

# External locations to create
EXTERNAL_LOCATIONS = {
    "expanso_ingestion_data": f"s3://expanso-databricks-ingestion-{AWS_REGION}/ingestion/",
    "expanso_validated_data": f"s3://expanso-databricks-validated-{AWS_REGION}/validated/",
    "expanso_enriched_data": f"s3://expanso-databricks-enriched-{AWS_REGION}/enriched/",
    "expanso_aggregated_data": f"s3://expanso-databricks-aggregated-{AWS_REGION}/aggregated/",
    "expanso_checkpoints": f"s3://expanso-databricks-checkpoints-{AWS_REGION}/",
    "expanso_metadata": f"s3://expanso-databricks-metadata-{AWS_REGION}/"
}


def get_workspace_client() -> WorkspaceClient:
    """Create Databricks workspace client from environment variables."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    
    if not host or not token:
        console.print("[red]Error: DATABRICKS_HOST and DATABRICKS_TOKEN must be set in .env[/red]")
        sys.exit(1)
    
    return WorkspaceClient(host=host, token=token)


def list_existing_locations(client: WorkspaceClient) -> Dict[str, str]:
    """List all existing external locations."""
    existing = {}
    try:
        locations = client.external_locations.list()
        for location in locations:
            existing[location.name] = location.url
    except Exception as e:
        console.print(f"[yellow]Warning: Could not list existing locations: {e}[/yellow]")
    return existing


def create_external_location(client: WorkspaceClient, name: str, url: str, credential: str) -> bool:
    """Create a single external location."""
    try:
        client.external_locations.create(
            name=name,
            url=url,
            credential_name=credential,
            comment=f"External location for {name.replace('_', ' ')}"
        )
        return True
    except Exception as e:
        if "already exists" in str(e):
            console.print(f"  [yellow]Location already exists: {name}[/yellow]")
        else:
            console.print(f"  [red]Error creating {name}: {e}[/red]")
        return False


def grant_permissions(client: WorkspaceClient, location_name: str) -> bool:
    """Grant permissions on external location to account users."""
    permissions = [
        "CREATE_MANAGED_STORAGE",
        "CREATE_EXTERNAL_TABLE", 
        "READ_FILES",
        "WRITE_FILES"
    ]
    
    try:
        # Get current grants
        current_grants = client.grants.get(securable_type="external_location", full_name=location_name)
        
        # Check if account users already have permissions
        existing_privileges = set()
        if current_grants.privilege_assignments:
            for assignment in current_grants.privilege_assignments:
                if assignment.principal == "account users":
                    existing_privileges.update(assignment.privileges or [])
        
        # Add missing permissions
        missing_privileges = [p for p in permissions if p not in existing_privileges]
        
        if missing_privileges:
            from databricks.sdk.service.catalog import PrivilegeAssignment, SecurableType
            
            client.grants.update(
                securable_type=SecurableType.EXTERNAL_LOCATION,
                full_name=location_name,
                changes=[
                    PrivilegeAssignment(
                        principal="account users",
                        privileges=missing_privileges
                    )
                ]
            )
            return True
        else:
            console.print(f"  [dim]Permissions already granted for {location_name}[/dim]")
            return True
            
    except Exception as e:
        console.print(f"  [red]Error granting permissions for {location_name}: {e}[/red]")
        return False


@click.command()
@click.option('--dry-run', is_flag=True, help='Show what would be created without actually creating')
@click.option('--skip-permissions', is_flag=True, help='Skip granting permissions to account users')
def main(dry_run: bool, skip_permissions: bool):
    """Create Unity Catalog external locations programmatically."""
    
    console.print("[bold blue]Unity Catalog External Locations Setup[/bold blue]")
    console.print("=" * 60)
    
    # Initialize client
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Connecting to Databricks...", total=None)
        client = get_workspace_client()
        progress.update(task, completed=True)
    
    # List existing locations
    console.print("\n[bold]Checking existing external locations...[/bold]")
    existing = list_existing_locations(client)
    
    # Show what will be created
    console.print("\n[bold]External Locations to Create:[/bold]")
    table = Table()
    table.add_column("Location Name", style="cyan")
    table.add_column("S3 URL", style="yellow")
    table.add_column("Status", style="green")
    
    to_create = []
    for name, url in EXTERNAL_LOCATIONS.items():
        if name in existing:
            status = "✓ Exists"
        else:
            status = "To create"
            to_create.append((name, url))
        table.add_row(name, url, status)
    
    console.print(table)
    
    if dry_run:
        console.print("\n[yellow]Dry run mode - no changes will be made[/yellow]")
        return
    
    if not to_create:
        console.print("\n[green]All external locations already exist![/green]")
    else:
        # Create external locations
        console.print(f"\n[bold]Creating {len(to_create)} external locations...[/bold]")
        
        created = 0
        for name, url in to_create:
            console.print(f"\nCreating: {name}")
            if create_external_location(client, name, url, STORAGE_CREDENTIAL):
                created += 1
                
                if not skip_permissions:
                    console.print(f"  Granting permissions...")
                    grant_permissions(client, name)
        
        console.print(f"\n[green]✓ Created {created} external locations[/green]")
    
    # Grant permissions for existing locations if needed
    if not skip_permissions and existing:
        console.print("\n[bold]Updating permissions for existing locations...[/bold]")
        for name in existing:
            if name in EXTERNAL_LOCATIONS:
                grant_permissions(client, name)
    
    # Verify final state
    console.print("\n[bold]Final State:[/bold]")
    final_locations = list_existing_locations(client)
    
    verify_table = Table()
    verify_table.add_column("Location Name", style="cyan")
    verify_table.add_column("Status", style="green")
    
    for name in EXTERNAL_LOCATIONS:
        if name in final_locations:
            verify_table.add_row(name, "✓ Active")
        else:
            verify_table.add_row(name, "✗ Missing")
    
    console.print(verify_table)
    
    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("\nYou can now use these external locations in your notebooks and Auto Loader.")


if __name__ == "__main__":
    main()