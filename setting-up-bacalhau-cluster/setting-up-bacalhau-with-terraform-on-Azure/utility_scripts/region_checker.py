#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "rich"
# ]
# ///
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()


def create_status_table(regions, results=None):
    """Create a table showing status for each region."""
    table = Table(title="Region VM Size Availability Check")
    table.add_column("Region")
    table.add_column("Display Name")
    table.add_column("Status")

    results = results or {}
    for region in sorted(regions, key=lambda x: x["name"]):
        name = region["name"]
        status = results.get(name, "⏳ Checking...")
        table.add_row(name, region["displayName"], status)
    return table


def check_region(region, vm_size):
    """Check VM size availability for a single region."""
    query = f"[?name=='{vm_size}'].name"
    cmd = [
        "az",
        "vm",
        "list-sizes",
        "--location",
        region["name"],
        "--query",
        query,
        "-o",
        "json",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        sizes = json.loads(result.stdout)
        if sizes:  # If the VM size is available in this region
            return region["name"], "✅ Available"
    return region["name"], "❌ Not Available"


def get_vm_availability(vm_size, debug=False):
    """Get VM size availability for all regions in parallel."""
    try:
        # First get all regions
        query = "[].{name:name, displayName:displayName}"
        cmd = [
            "az",
            "account",
            "list-locations",
            "--query",
            query,
            "-o",
            "json",
        ]
        if debug:
            console.print("[yellow]Fetching regions...[/yellow]")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Error: {result.stderr}[/red]")
            return None

        regions = json.loads(result.stdout)
        available_regions = []
        results = {}

        # Create and display the live table
        with Live(create_status_table(regions, results), refresh_per_second=4) as live:
            # Check regions in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_region = {
                    executor.submit(check_region, region, vm_size): region
                    for region in regions
                }

                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        region_name, status = future.result()
                        results[region_name] = status
                        if status == "✅ Available":
                            available_regions.append(region)
                        live.update(create_status_table(regions, results))
                    except Exception as e:
                        results[region["name"]] = f"❌ Error: {str(e)}"
                        live.update(create_status_table(regions, results))

        return available_regions
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        return []


def generate_locations_section(regions, vm_size):
    """Generate locations section for available regions."""
    return {
        region["name"]: {"machine_type": vm_size, "node_count": 1} for region in regions
    }


def main(vm_size, debug=False):
    console.print(f"[cyan]Checking availability for VM size: {vm_size}[/cyan]")

    # Get VM availability data
    available_regions = get_vm_availability(vm_size, debug)

    if not available_regions:
        console.print(f"\n[red]VM size {vm_size} not found in any region[/red]")
        return

    # Generate the locations section
    locations_section = generate_locations_section(available_regions, vm_size)

    # Print to console
    console.print("\n[green]Available Regions Summary:[/green]")
    for region in sorted(available_regions, key=lambda x: x["name"]):
        console.print(f"✅ {region['name']} ({region['displayName']})")

    # Save to file
    output_file = (
        f"vm_availability_{vm_size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_file, "w") as f:
        json.dump({"locations": locations_section}, f, indent=4)

    console.print(
        f"\n[blue]Generated Locations Configuration saved to: {output_file}[/blue]"
    )
    console.print(f"\n[cyan]Summary:[/cyan]")
    console.print(f"Available regions: {len(available_regions)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vm-size",
        type=str,
        default="Standard_B2ms",
        help="VM size to check (default: Standard_B2ms)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print Azure CLI commands being executed",
    )
    args = parser.parse_args()

    main(args.vm_size, args.debug)
