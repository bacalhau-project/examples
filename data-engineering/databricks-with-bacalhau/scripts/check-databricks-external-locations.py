#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sdk>=0.12.0",
#     "rich>=13.0.0",
#     "click>=8.0.0",
# ]
# ///
"""
Check Databricks external locations for references to old buckets.

This script will:
1. List all external locations in Unity Catalog
2. Identify any that reference emergency or regional buckets
3. Provide commands to update or remove them
"""

import click
from databricks.sdk import WorkspaceClient
from rich.console import Console
from rich.table import Table
from typing import List, Dict, Any
import os
import sys

console = Console()


def check_external_locations(w: WorkspaceClient) -> List[Dict[str, Any]]:
    """Check external locations for old bucket references."""
    problematic_locations = []

    try:
        # List all external locations
        locations = w.external_locations.list()

        for location in locations:
            # Check if URL contains emergency or regional
            if location.url and any(x in location.url for x in ["emergency", "regional"]):
                problematic_locations.append(
                    {
                        "name": location.name,
                        "url": location.url,
                        "owner": location.owner,
                        "comment": location.comment or "",
                        "type": "emergency" if "emergency" in location.url else "regional",
                    }
                )

    except Exception as e:
        console.print(f"[red]Error listing external locations: {e}[/red]")
        console.print("[yellow]Make sure you have Databricks credentials configured[/yellow]")
        sys.exit(1)

    return problematic_locations


def check_tables_using_location(w: WorkspaceClient, location_name: str) -> List[str]:
    """Check if any tables are using this external location."""
    tables_using_location = []

    try:
        # This would require querying the catalog, which is complex
        # For now, we'll just note that manual checking is needed
        pass
    except:
        pass

    return tables_using_location


@click.command()
@click.option("--profile", help="Databricks CLI profile to use")
@click.option("--fix", is_flag=True, help="Show commands to fix issues")
def main(profile: str, fix: bool):
    """Check Databricks external locations for old bucket references."""

    console.print("\n[bold blue]🔍 Databricks External Location Checker[/bold blue]")
    console.print("Checking for emergency and regional bucket references...\n")

    # Initialize Databricks client
    try:
        if profile:
            w = WorkspaceClient(profile=profile)
        else:
            # Try to use environment variables or default profile
            w = WorkspaceClient()
    except Exception as e:
        console.print(f"[red]Error connecting to Databricks: {e}[/red]")
        console.print(
            "[yellow]Set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables[/yellow]"
        )
        console.print("[yellow]Or use --profile to specify a CLI profile[/yellow]")
        sys.exit(1)

    # Check external locations
    problematic_locations = check_external_locations(w)

    if not problematic_locations:
        console.print(
            "[green]✓ No external locations found referencing emergency or regional buckets![/green]"
        )

        # Show current external locations
        console.print("\n[bold]Current external locations:[/bold]")
        try:
            locations = w.external_locations.list()
            table = Table(title="External Locations")
            table.add_column("Name", style="cyan")
            table.add_column("URL", style="yellow")
            table.add_column("Owner", style="magenta")

            for location in locations:
                if "expanso" in location.url.lower():
                    table.add_row(location.name, location.url, location.owner)

            console.print(table)
        except:
            pass

        return

    # Display problematic locations
    table = Table(title="External Locations to Update/Remove")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("URL", style="yellow")
    table.add_column("Owner", style="green")

    for location in problematic_locations:
        table.add_row(
            location["name"], location["type"].capitalize(), location["url"], location["owner"]
        )

    console.print(table)

    if fix:
        console.print("\n[bold]Fix Commands:[/bold]")
        console.print("\nTo remove these external locations, run these SQL commands in Databricks:")
        console.print("```sql")

        for location in problematic_locations:
            console.print(f"-- Check if any tables use this location")
            console.print(f"SHOW TABLES IN expanso_catalog;")
            console.print(f"-- If no tables use it, drop the location")
            console.print(f"DROP EXTERNAL LOCATION IF EXISTS `{location['name']}`;")
            console.print()

        console.print("```")

        console.print(
            "\n[yellow]⚠️  Make sure no tables are using these locations before dropping them![/yellow]"
        )
        console.print("[yellow]Run SHOW TABLES and check each table's location first.[/yellow]")

    # Provide next steps
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("1. Check if any tables are using these external locations")
    console.print("2. Update tables to use the new bucket structure if needed")
    console.print("3. Drop the old external locations")
    console.print("4. Update any Auto Loader jobs that reference these locations")


if __name__ == "__main__":
    main()
