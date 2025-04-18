#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml>=6.0",
#     "rich>=13.0.0",
#     "tabulate>=0.9.0",
# ]
# ///

"""
Query tool for Azure CosmosDB to check sensor data uploads.
More robust Python-based replacement for cosmosdb-query.sh.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import yaml
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table
from rich import box
from tabulate import tabulate


console = Console()


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file with environment variable expansion"""
    try:
        with open(config_path, "r") as f:
            config_yaml = f.read()
            
        # Simple environment variable expansion
        # Replace ${VAR} or ${VAR:-default}
        import re
        def replace_env_var(match):
            var_name = match.group(1)
            default = match.group(3) if match.group(3) else ""
            return os.environ.get(var_name, default)
            
        pattern = r'\${([a-zA-Z0-9_]+)(?::-([^}]*))?}'
        config_yaml = re.sub(pattern, replace_env_var, config_yaml)
        
        config = yaml.safe_load(config_yaml)
        return config
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {str(e)}")
        sys.exit(1)


def connect_to_cosmos(endpoint: str, key: str, database_name: str, container_name: str, verbose: bool = False) -> tuple:
    """Connect to CosmosDB and return client, database, and container objects"""
    try:
        with Progress(transient=True) as progress:
            task = progress.add_task("[cyan]Connecting to CosmosDB...", total=3)
            
            # Initialize client
            client = CosmosClient(endpoint, credential=key)
            progress.update(task, advance=1)
            
            # Get database
            database = client.get_database_client(database_name)
            progress.update(task, advance=1)
            
            # Get container
            container = database.get_container_client(container_name)
            progress.update(task, advance=1)
            
        if verbose:
            console.print(Panel.fit(
                f"[green]Connected to CosmosDB[/green]\n"
                f"[cyan]Endpoint:[/cyan] {endpoint}\n"
                f"[cyan]Database:[/cyan] {database_name}\n"
                f"[cyan]Container:[/cyan] {container_name}"
            ))
            
        return client, database, container
    except Exception as e:
        console.print(f"[bold red]Connection error:[/bold red] {str(e)}")
        sys.exit(1)


def query_cosmosdb(container, query: str, verbose: bool = False) -> List[Dict[str, Any]]:
    """Query CosmosDB and return results with error handling"""
    start_time = time.time()
    
    try:
        if verbose:
            console.print(f"[cyan]Executing query:[/cyan] {query}")
            
        with Progress(transient=True) as progress:
            task = progress.add_task("[cyan]Querying CosmosDB...", total=None)
            items = list(container.query_items(query=query, enable_cross_partition_query=True))
            progress.update(task, completed=True)
            
        elapsed = time.time() - start_time
        
        if verbose:
            console.print(f"[green]Query completed in {elapsed:.3f} seconds[/green]")
            
        return items
    except CosmosHttpResponseError as e:
        console.print(f"[bold red]CosmosDB query error:[/bold red] {str(e)}")
        if hasattr(e, 'status_code'):
            console.print(f"[red]Status code:[/red] {e.status_code}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error executing query:[/bold red] {str(e)}")
        sys.exit(1)


def format_results(items: List[Dict[str, Any]], format_type: str = "json", verbose: bool = False) -> str:
    """Format results for display"""
    if not items:
        return "No results found"
        
    if format_type == "table" and items:
        # Extract all unique keys from all items
        all_keys = set()
        for item in items:
            all_keys.update(item.keys())
            
        # Prioritize common sensor fields and remove id
        priority_keys = ["id", "sensorId", "timestamp", "temperature", "vibration", "voltage", 
                         "city", "location", "status", "anomalyFlag"]
        
        # Filter out non-priority keys if we have too many
        if len(all_keys) > 10:
            keys_to_show = [k for k in priority_keys if k in all_keys]
            if len(keys_to_show) < 5:  # If we don't have enough priority keys
                remaining_keys = list(all_keys - set(keys_to_show))
                keys_to_show.extend(remaining_keys[:10 - len(keys_to_show)])
        else:
            keys_to_show = list(all_keys)
            
        # Create table with headers
        table_data = []
        for item in items:
            row = []
            for key in keys_to_show:
                value = item.get(key, '')
                # Format datetime
                if isinstance(value, str) and len(value) > 20 and 'T' in value and 'Z' in value:
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        value = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                # Truncate long values
                if isinstance(value, str) and len(value) > 20:
                    value = value[:17] + '...'
                row.append(value)
            table_data.append(row)
            
        return tabulate(table_data, headers=keys_to_show, tablefmt='grid')
    else:
        # JSON format
        return json.dumps(items, indent=2)


def count_items(container) -> int:
    """Count items in the container"""
    try:
        with Progress(transient=True) as progress:
            task = progress.add_task("[cyan]Counting documents...", total=None)
            count_query = "SELECT VALUE COUNT(1) FROM c"
            items = list(container.query_items(
                query=count_query, 
                enable_cross_partition_query=True
            ))
            progress.update(task, completed=True)
            
        if items:
            return items[0]
        return 0
    except Exception as e:
        console.print(f"[bold red]Error counting items:[/bold red] {str(e)}")
        sys.exit(1)


def create_bulk_delete_sproc(container, verbose=False):
    """Create a stored procedure for efficient bulk deletion"""
    sproc_id = "bulkDelete"
    
    # Check if the stored procedure already exists
    try:
        container.scripts.get_stored_procedure(sproc_id)
        if verbose:
            console.print(f"[cyan]Stored procedure {sproc_id} already exists[/cyan]")
        return sproc_id
    except Exception:
        if verbose:
            console.print(f"[cyan]Creating stored procedure {sproc_id}[/cyan]")

    # JavaScript code for the stored procedure
    sproc_body = """
    function bulkDelete(query) {
        var context = getContext();
        var container = context.getCollection();
        var response = context.getResponse();
        var responseBody = { deleted: 0, continuation: true };
        
        // If no query is provided, fail
        if (!query) {
            throw new Error("Query is required");
        }
        
        // Query documents
        var accepted = container.queryDocuments(
            container.getSelfLink(),
            query,
            { pageSize: 100 },
            function(err, feed, options) {
                if (err) throw err;
                if (!feed || !feed.length) {
                    responseBody.continuation = false;
                    response.setBody(responseBody);
                    return;
                }
                
                // Process each document
                var deleted = 0;
                var maxDocumentsToDelete = Math.min(feed.length, 100);
                var pendingCallbacks = maxDocumentsToDelete;
                
                for (var i = 0; i < maxDocumentsToDelete; i++) {
                    deleteDocument(feed[i], function(err) {
                        if (err) throw err;
                        deleted++;
                        pendingCallbacks--;
                        
                        // When all are done, return response
                        if (pendingCallbacks === 0) {
                            responseBody.deleted = deleted;
                            response.setBody(responseBody);
                        }
                    });
                }
            }
        );
        
        if (!accepted) {
            throw new Error("Operation not accepted");
        }
        
        function deleteDocument(document, callback) {
            var isAccepted = container.deleteDocument(
                document._self,
                {},
                function(err) {
                    if (err) callback(err);
                    else callback();
                }
            );
            
            if (!isAccepted) {
                callback(new Error("Delete operation not accepted"));
            }
        }
    }
    """
    
    # Create the stored procedure
    try:
        sproc_definition = {
            'id': sproc_id,
            'body': sproc_body
        }
        container.scripts.create_stored_procedure(body=sproc_definition)
        if verbose:
            console.print(f"[green]Successfully created stored procedure {sproc_id}[/green]")
        return sproc_id
    except Exception as e:
        console.print(f"[red]Error creating stored procedure: {str(e)}[/red]")
        return None


def clear_data(container, filter_query=None, dry_run=True, verbose=False, use_sproc=True):
    """Clear data from the container with optional filtering"""
    try:
        # First get a count of items that will be deleted
        if filter_query:
            count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {filter_query}"
        else:
            count_query = "SELECT VALUE COUNT(1) FROM c"
            
        count_result = list(container.query_items(
            query=count_query,
            enable_cross_partition_query=True
        ))
        total_to_delete = count_result[0] if count_result else 0
        
        if total_to_delete == 0:
            console.print("[yellow]No documents found matching the criteria. Nothing to delete.[/yellow]")
            return
            
        # If it's a dry run, just show what would be deleted
        if dry_run:
            console.print(f"[yellow]DRY RUN: Would delete {total_to_delete} documents[/yellow]")
            if filter_query:
                console.print(f"[yellow]Filter query: {filter_query}[/yellow]")
            return
            
        # Confirm before deleting
        if not verbose:  # Only ask for confirmation if not in verbose mode
            console.print(f"[bold red]WARNING: You are about to delete {total_to_delete} documents![/bold red]")
            console.print("[yellow]This action cannot be undone.[/yellow]")
            
            confirm = input("Type 'DELETE' to confirm: ")
            if confirm != "DELETE":
                console.print("[green]Operation cancelled.[/green]")
                return

        # Use stored procedure for efficient deletion if enabled
        if use_sproc:
            try:
                sproc_id = create_bulk_delete_sproc(container, verbose)
                if sproc_id:
                    console.print("[cyan]Using stored procedure for bulk deletion (much faster)[/cyan]")
                    return clear_data_with_sproc(container, filter_query, total_to_delete, verbose)
            except Exception as e:
                if verbose:
                    console.print(f"[yellow]Error with stored procedure setup: {str(e)}[/yellow]")
                console.print("[yellow]Could not use stored procedure, falling back to client-side deletion[/yellow]")
                
        # Fallback to client-side deletion
        console.print("[cyan]Using client-side deletion (slower but more compatible)[/cyan]")
                    
        # Get documents to delete
        if filter_query:
            query = f"SELECT c.id, c.city FROM c WHERE {filter_query}"
        else:
            query = "SELECT c.id, c.city FROM c"
            
        # Process in batches to avoid overwhelming the database
        batch_size = 100
        deleted = 0
        
        with Progress() as progress:
            delete_task = progress.add_task("[red]Deleting documents...", total=total_to_delete)
            
            # We need to get all documents first since we can't delete while iterating
            docs_to_delete = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            # Now delete them in batches
            for i in range(0, len(docs_to_delete), batch_size):
                batch = docs_to_delete[i:i+batch_size]
                
                for doc in batch:
                    # We need both ID and partition key (city) to delete
                    doc_id = doc.get('id')
                    partition_key = doc.get('city')
                    
                    if doc_id and partition_key:
                        try:
                            container.delete_item(item=doc_id, partition_key=partition_key)
                            deleted += 1
                            progress.update(delete_task, completed=deleted)
                        except Exception as e:
                            if verbose:
                                console.print(f"[red]Error deleting document {doc_id}: {str(e)}[/red]")
                    else:
                        if verbose:
                            console.print(f"[yellow]Skipping document without ID or partition key: {doc}[/yellow]")
        
        console.print(f"[green]Successfully deleted {deleted} documents.[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error clearing data:[/bold red] {str(e)}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


def clear_data_with_sproc(container, filter_query, total_to_delete, verbose):
    """Use stored procedure to efficiently delete documents"""
    try:
        # Build the query for the stored procedure
        if filter_query:
            query = f"SELECT * FROM c WHERE {filter_query}"
        else:
            query = "SELECT * FROM c"
            
        # We need a partition key for the sproc
        # Get a list of all unique partition key values (cities)
        partition_query = "SELECT DISTINCT c.city FROM c"
        if filter_query:
            partition_query = f"SELECT DISTINCT c.city FROM c WHERE {filter_query}"
            
        partitions = list(container.query_items(
            query=partition_query,
            enable_cross_partition_query=True
        ))
        
        if not partitions:
            console.print("[yellow]No partitions found for the given filter query[/yellow]")
            return
            
        # Execute stored procedure across all partitions
        with Progress() as progress:
            delete_task = progress.add_task("[red]Deleting documents...", total=total_to_delete)
            deleted_count = 0
            
            # Process each partition
            for partition in partitions:
                city = partition.get('city')
                if not city:
                    continue
                    
                has_more = True
                partition_deleted = 0
                
                # Keep calling the sproc until all documents are deleted
                while has_more:
                    try:
                        result = container.scripts.execute_stored_procedure(
                            sproc="bulkDelete",
                            params=[query],
                            partition_key=city
                        )
                        
                        if result and isinstance(result, dict):
                            batch_deleted = result.get('deleted', 0)
                            has_more = result.get('continuation', False)
                            
                            deleted_count += batch_deleted
                            partition_deleted += batch_deleted
                            progress.update(delete_task, completed=min(deleted_count, total_to_delete))
                            
                            if verbose:
                                console.print(f"[cyan]Deleted {batch_deleted} documents from partition {city}[/cyan]")
                                
                            # If no documents were deleted, stop
                            if batch_deleted == 0:
                                has_more = False
                        else:
                            has_more = False
                    except Exception as e:
                        if verbose:
                            console.print(f"[yellow]Error in stored procedure for partition {city}: {str(e)}[/yellow]")
                        has_more = False
                
                if verbose:
                    console.print(f"[green]Completed partition {city}: {partition_deleted} documents deleted[/green]")
                    
        console.print(f"[green]Successfully deleted {deleted_count} documents.[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error using stored procedure:[/bold red] {str(e)}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


def analyze_data(container, verbose: bool = False) -> None:
    """Analyze data to provide insights about the data in the container"""
    console.print("[cyan]Analyzing database content...[/cyan]")
    
    with Progress() as progress:
        count_task = progress.add_task("[green]Counting documents...", total=None)
        sample_task = progress.add_task("[green]Getting sample data...", total=None)
        city_task = progress.add_task("[green]Analyzing cities...", total=None)
        time_task = progress.add_task("[green]Analyzing time range...", total=None)
        
        try:
            # Get total count - this works on all Cosmos accounts
            count_query = "SELECT VALUE COUNT(1) FROM c"
            count_result = list(container.query_items(query=count_query, enable_cross_partition_query=True))
            total_count = count_result[0] if count_result else 0
            progress.update(count_task, completed=True)
            
            # Get sample docs - avoid GROUP BY which isn't supported in all Cosmos accounts
            sample_query = "SELECT TOP 100 * FROM c"
            try:
                sample_docs = list(container.query_items(query=sample_query, enable_cross_partition_query=True))
                if not sample_docs and total_count > 0:
                    # If we have documents but couldn't get a sample, try a different query
                    fallback_query = "SELECT * FROM c OFFSET 0 LIMIT 100"
                    sample_docs = list(container.query_items(query=fallback_query, enable_cross_partition_query=True))
            except Exception as e:
                if verbose:
                    console.print(f"[yellow]Error getting sample data: {str(e)}[/yellow]")
                sample_docs = []
            progress.update(sample_task, completed=True)
            
            # Check if there's any data
            if not sample_docs:
                progress.update(city_task, completed=True)
                progress.update(time_task, completed=True)
                console.print("\n[yellow]No sample documents could be retrieved. The database might be empty or you may not have query permissions.[/yellow]\n")
                if total_count > 0:
                    console.print(f"[cyan]There are {total_count} documents in the database, but we couldn't retrieve sample data.[/cyan]\n")
                return
            
            # Extract unique cities and sensors from sample docs
            cities = {}
            sensors = {}
            timestamps = []
            
            for doc in sample_docs:
                # Track cities
                city = doc.get('city')
                if city:
                    cities[city] = cities.get(city, 0) + 1
                    
                # Track sensors
                sensor_id = doc.get('sensorId')
                if sensor_id:
                    sensors[sensor_id] = sensors.get(sensor_id, 0) + 1
                    
                # Track timestamps
                timestamp = doc.get('timestamp')
                if timestamp:
                    timestamps.append(timestamp)
                    
            progress.update(city_task, completed=True)
            
            # Calculate time range from sample
            time_range = {}
            if timestamps:
                timestamps.sort()
                time_range = {
                    "oldest": timestamps[0],
                    "newest": timestamps[-1]
                }
            progress.update(time_task, completed=True)
            
            # Display summary
            console.print("\n")  # Add a newline for better formatting
            table = Table(
                title=f"CosmosDB Summary (Total: {total_count} documents, Sample: {len(sample_docs)})",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED
            )
            
            # Add columns
            table.add_column("Category", style="cyan")
            table.add_column("Count", style="green")
            table.add_column("Details", style="yellow", width=70, no_wrap=False)
            
            # Add city info (from sample)
            if cities:
                city_details = ", ".join([f"{city}({count})" for city, count in 
                                        sorted(cities.items(), key=lambda x: x[1], reverse=True)[:5]])
                if len(cities) > 5:
                    city_details += f" and {len(cities) - 5} more"
                table.add_row("Cities (sample)", str(len(cities)), city_details)
            
            # Add sensor info (from sample)
            if sensors:
                sensor_details = ", ".join([f"{sensor}({count})" for sensor, count in 
                                          sorted(sensors.items(), key=lambda x: x[1], reverse=True)[:5]])
                if len(sensors) > 5:
                    sensor_details += f" and {len(sensors) - 5} more"
                table.add_row("Sensors (sample)", str(len(sensors)), sensor_details)
            
            # Add time range
            if time_range:
                oldest = time_range.get("oldest")
                newest = time_range.get("newest")
                if oldest and newest:
                    try:
                        oldest_dt = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
                        newest_dt = datetime.fromisoformat(newest.replace('Z', '+00:00'))
                        duration = newest_dt - oldest_dt
                        table.add_row(
                            "Time Range (sample)", 
                            f"{duration.days}d {duration.seconds//3600}h", 
                            f"{oldest_dt.strftime('%Y-%m-%d %H:%M')} to {newest_dt.strftime('%Y-%m-%d %H:%M')}"
                        )
                    except Exception as e:
                        if verbose:
                            console.print(f"[red]Error parsing timestamps:[/red] {str(e)}")
                        table.add_row("Time Range (sample)", "Unknown", f"{oldest} to {newest}")
                
            console.print(table)
            console.print("\n")  # Add a newline for better formatting
            
            # Data quality check (optional extra info)
            if sample_docs:
                # Check for common fields
                first_doc = sample_docs[0]
                expected_fields = ["id", "sensorId", "timestamp", "temperature", "vibration", 
                                 "voltage", "city", "location"]
                missing_fields = [field for field in expected_fields if field not in first_doc]
                
                if missing_fields:
                    console.print(f"[yellow]Warning: Sample documents are missing expected fields: "
                                f"{', '.join(missing_fields)}[/yellow]")
                
        except Exception as e:
            progress.update(count_task, completed=True)
            progress.update(sample_task, completed=True)
            progress.update(city_task, completed=True)
            progress.update(time_task, completed=True)
            console.print(f"[bold red]Error analyzing data:[/bold red] {str(e)}")
            
            if verbose:
                import traceback
                console.print("[red]Traceback:[/red]")
                console.print(traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(
        description="Query Azure CosmosDB for sensor data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--config", help="Path to the config file")
    parser.add_argument("--endpoint", help="CosmosDB endpoint URL")
    parser.add_argument("--key", help="CosmosDB access key")
    parser.add_argument("--database", help="Database name")
    parser.add_argument("--container", help="Container name")
    parser.add_argument("--query", default="SELECT * FROM c LIMIT 10", help="SQL query to execute")
    parser.add_argument("--count", action="store_true", help="Count documents instead of querying")
    parser.add_argument("--city", help="Filter by city (partition key)")
    parser.add_argument("--sensor", help="Filter by sensor ID")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results")
    parser.add_argument("--format", choices=["json", "table"], default="json", help="Output format")
    parser.add_argument("--analyze", action="store_true", help="Analyze data distribution")
    
    # Clearing data options
    parser.add_argument("--clear", action="store_true", help="Clear documents from the container")
    parser.add_argument("--filter", help="Filter condition for clearing data (e.g. 'c.city=\"London\"')")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Show what would be deleted without actually deleting")
    parser.add_argument("--force-delete", action="store_true", help="Force deletion without dry run (use with caution)")
    parser.add_argument("--no-sproc", action="store_true", help="Disable using stored procedure for deletion (slower but more compatible)")
    
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Header
    console.print(Panel.fit(
        "[bold blue]CosmosDB Query Tool[/bold blue]\n"
        "[cyan]Query Azure CosmosDB directly to check sensor data[/cyan]",
        border_style="blue"
    ))

    # Load configuration
    config = {}
    if args.config:
        config = load_config(args.config)

    # Extract Cosmos DB configuration with priority to command line args
    cosmos_config = config.get("cosmos", {})
    endpoint = args.endpoint or cosmos_config.get("endpoint")
    key = args.key or cosmos_config.get("key")
    database_name = args.database or cosmos_config.get("database_name")
    container_name = args.container or cosmos_config.get("container_name")

    # Check for environment variable overrides
    endpoint = os.environ.get("COSMOS_ENDPOINT", endpoint)
    key = os.environ.get("COSMOS_KEY", key)
    database_name = os.environ.get("COSMOS_DATABASE", database_name) or os.environ.get("COSMOS_DATABASE_NAME", database_name)
    container_name = os.environ.get("COSMOS_CONTAINER", container_name) or os.environ.get("COSMOS_CONTAINER_NAME", container_name)

    # Validate required parameters
    if not all([endpoint, key, database_name, container_name]):
        missing = []
        if not endpoint: missing.append("endpoint")
        if not key: missing.append("key")
        if not database_name: missing.append("database_name")
        if not container_name: missing.append("container_name")
        
        console.print(f"[bold red]Error:[/bold red] Missing required CosmosDB parameters: {', '.join(missing)}")
        console.print("[yellow]Provide these values via:[/yellow]")
        console.print("  1. Command line arguments (--endpoint, --key, etc.)")
        console.print("  2. Config file (--config)")
        console.print("  3. Environment variables (COSMOS_ENDPOINT, COSMOS_KEY, etc.)")
        sys.exit(1)

    # Connect to CosmosDB
    _, _, container = connect_to_cosmos(endpoint, key, database_name, container_name, args.verbose)

    # Handle count request
    if args.count:
        count = count_items(container)
        console.print(f"[bold green]Total documents:[/bold green] {count}")
        return
    
    # Handle clear request
    if args.clear:
        # Build filter query if city or sensor is specified
        filter_query = args.filter
        if not filter_query and (args.city or args.sensor):
            conditions = []
            if args.city:
                conditions.append(f"c.city = '{args.city}'")
            if args.sensor:
                conditions.append(f"c.sensorId = '{args.sensor}'")
            if conditions:
                filter_query = " AND ".join(conditions)
        
        # Determine dry run status
        # Default: dry run is true unless force-delete is specified
        dry_run = not args.force_delete
        
        # If explicit dry-run is set, it overrides force-delete
        if args.dry_run:
            dry_run = True
            
        # If deleting ALL documents (no filter) without force flag, warn and default to dry-run
        if not filter_query and not args.force_delete:
            console.print("[bold red]WARNING: You are about to delete ALL documents![/bold red]")
            console.print("[yellow]Using --dry-run by default. Use --force-delete to actually delete everything.[/yellow]")
            dry_run = True
        
        # Determine whether to use sproc
        use_sproc = not args.no_sproc
        
        clear_data(container, filter_query, dry_run, args.verbose, use_sproc)
        return

    # Handle analyze request
    if args.analyze:
        analyze_data(container, args.verbose)
        return

    # Build query if filters are specified
    query = args.query
    if args.query == "SELECT * FROM c LIMIT 10" and (args.city or args.sensor or args.limit != 10):
        # Build custom query
        query = "SELECT * FROM c WHERE 1=1"
        if args.city:
            query += f" AND c.city = '{args.city}'"
        if args.sensor:
            query += f" AND c.sensorId = '{args.sensor}'"
        query += f" LIMIT {args.limit}"

    # Execute query
    items = query_cosmosdb(container, query, args.verbose)

    # Display results
    if not items:
        console.print("[yellow]No documents found matching your query[/yellow]")
        return

    console.print(f"[green]Found {len(items)} documents[/green]")
    formatted_output = format_results(items, args.format, args.verbose)
    print(formatted_output)


if __name__ == "__main__":
    main()
