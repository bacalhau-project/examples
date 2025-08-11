#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sdk",
#     "rich",
# ]
# ///

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import compute
from rich.console import Console
import time

console = Console()

# Initialize client
client = WorkspaceClient()

console.print("[bold blue]Starting Databricks Cluster[/bold blue]")
console.print("=" * 60)

# Try to get the cluster
cluster_id = "6a80650f34fb7115"

try:
    # Try to get cluster info
    cluster = client.clusters.get(cluster_id=cluster_id)
    console.print(f"[yellow]Found cluster: {cluster.cluster_name}[/yellow]")
    console.print(f"[yellow]State: {cluster.state}[/yellow]")
    
    # Start if not running
    if cluster.state != "RUNNING":
        console.print("[yellow]Starting cluster...[/yellow]")
        client.clusters.start(cluster_id=cluster_id)
        
        # Wait for cluster to start
        while True:
            cluster = client.clusters.get(cluster_id=cluster_id)
            if cluster.state == "RUNNING":
                console.print("[green]✅ Cluster is running![/green]")
                break
            elif cluster.state in ["TERMINATED", "ERROR", "UNKNOWN"]:
                console.print(f"[red]❌ Cluster failed to start: {cluster.state}[/red]")
                break
            else:
                console.print(f"[yellow]State: {cluster.state}...[/yellow]")
                time.sleep(10)
    else:
        console.print("[green]✅ Cluster is already running![/green]")
        
except Exception as e:
    console.print(f"[red]Cluster {cluster_id} not found: {e}[/red]")
    
    # Create a new cluster
    console.print("\n[yellow]Creating new cluster...[/yellow]")
    try:
        cluster = client.clusters.create(
            cluster_name="AutoLoader-Cluster",
            spark_version="13.3.x-scala2.12",
            node_type_id="i3.xlarge",
            num_workers=0,  # Single node
            autotermination_minutes=60,
            spark_conf={
                "spark.databricks.cluster.profile": "singleNode",
                "spark.master": "local[*]"
            }
        )
        console.print(f"[green]✅ Created cluster: {cluster.cluster_id}[/green]")
        console.print(f"[cyan]Cluster ID: {cluster.cluster_id}[/cyan]")
        
        # Wait for it to start
        console.print("[yellow]Waiting for cluster to start...[/yellow]")
        while True:
            cluster_info = client.clusters.get(cluster_id=cluster.cluster_id)
            if cluster_info.state == "RUNNING":
                console.print("[green]✅ Cluster is running![/green]")
                break
            elif cluster_info.state in ["TERMINATED", "ERROR", "UNKNOWN"]:
                console.print(f"[red]❌ Cluster failed to start: {cluster_info.state}[/red]")
                break
            else:
                console.print(f"[yellow]State: {cluster_info.state}...[/yellow]")
                time.sleep(10)
                
    except Exception as e2:
        console.print(f"[red]❌ Failed to create cluster: {e2}[/red]")
