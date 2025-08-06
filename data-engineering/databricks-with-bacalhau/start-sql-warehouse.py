#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "python-dotenv",
#   "rich",
# ]
# ///

"""Start SQL warehouse if it's stopped."""

import os
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Load environment variables
load_dotenv()

console = Console()

def main():
    """Start SQL warehouse."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "")
    
    if not all([host, token, http_path]):
        console.print("[red]Error: Missing required environment variables[/red]")
        sys.exit(1)
    
    # Extract warehouse ID from HTTP path
    warehouse_id = http_path.split("/")[-1]
    console.print(f"[bold]SQL Warehouse ID:[/bold] {warehouse_id}")
    
    # Create client
    client = WorkspaceClient(host=host, token=token)
    
    try:
        # Get warehouse status
        warehouse = client.warehouses.get(id=warehouse_id)
        console.print(f"[bold]Current State:[/bold] {warehouse.state}")
        
        if warehouse.state == "RUNNING":
            console.print("[green]✓ SQL warehouse is already running[/green]")
            return
        
        # Start warehouse
        console.print("\n[yellow]Starting SQL warehouse...[/yellow]")
        client.warehouses.start(id=warehouse_id)
        
        # Wait for it to start
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Waiting for warehouse to start...", total=None)
            
            while True:
                warehouse = client.warehouses.get(id=warehouse_id)
                if warehouse.state == "RUNNING":
                    break
                elif warehouse.state in ["STOPPED", "DELETED"]:
                    console.print(f"[red]Warehouse failed to start: {warehouse.state}[/red]")
                    sys.exit(1)
                time.sleep(5)
        
        console.print("[green]✓ SQL warehouse started successfully![/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[yellow]Note: The SQL warehouse might not exist or you might not have permissions.[/yellow]")
        console.print("Please check your Databricks workspace and ensure the warehouse exists.")


if __name__ == "__main__":
    main()