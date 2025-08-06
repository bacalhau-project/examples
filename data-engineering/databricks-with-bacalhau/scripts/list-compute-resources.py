#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "databricks-sdk",
#   "python-dotenv",
#   "rich",
# ]
# ///

"""List available compute resources (clusters and SQL warehouses)."""

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
    """Create Databricks workspace client."""
    host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "")
    
    if not host or not token:
        console.print("[red]Error: DATABRICKS_HOST and DATABRICKS_TOKEN must be set[/red]")
        sys.exit(1)
    
    return WorkspaceClient(host=host, token=token)

def main():
    """List compute resources."""
    console.print("[bold blue]Available Compute Resources[/bold blue]")
    console.print("=" * 60)
    
    client = get_workspace_client()
    
    # List clusters
    console.print("\n[bold]Clusters:[/bold]")
    try:
        clusters = client.clusters.list()
        cluster_table = Table()
        cluster_table.add_column("Cluster ID", style="cyan")
        cluster_table.add_column("Name", style="green")
        cluster_table.add_column("State", style="yellow")
        cluster_table.add_column("Spark Version", style="magenta")
        
        cluster_count = 0
        for cluster in clusters:
            cluster_table.add_row(
                cluster.cluster_id,
                cluster.cluster_name or "Unnamed",
                cluster.state or "Unknown",
                cluster.spark_version or "Unknown"
            )
            cluster_count += 1
        
        if cluster_count > 0:
            console.print(cluster_table)
        else:
            console.print("[yellow]No clusters found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error listing clusters: {e}[/red]")
    
    # List SQL warehouses
    console.print("\n[bold]SQL Warehouses:[/bold]")
    try:
        warehouses = client.warehouses.list()
        warehouse_table = Table()
        warehouse_table.add_column("Warehouse ID", style="cyan")
        warehouse_table.add_column("Name", style="green")
        warehouse_table.add_column("State", style="yellow")
        warehouse_table.add_column("Size", style="magenta")
        
        warehouse_count = 0
        for warehouse in warehouses:
            warehouse_table.add_row(
                warehouse.id,
                warehouse.name,
                warehouse.state or "Unknown",
                warehouse.cluster_size or "Unknown"
            )
            warehouse_count += 1
        
        if warehouse_count > 0:
            console.print(warehouse_table)
            
            # Show HTTP path for running warehouses
            console.print("\n[bold]SQL Warehouse HTTP Paths:[/bold]")
            for warehouse in warehouses:
                if warehouse.state == "RUNNING":
                    http_path = f"/sql/1.0/warehouses/{warehouse.id}"
                    console.print(f"  {warehouse.name}: [green]{http_path}[/green]")
        else:
            console.print("[yellow]No SQL warehouses found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error listing warehouses: {e}[/red]")

if __name__ == "__main__":
    main()