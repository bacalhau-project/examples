#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
#     "rich",
# ]
# ///

import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, Optional

import yaml
from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, TimeRemainingColumn
from rich.table import Table

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Default configuration values
DEFAULTS = {
    "instance_type": "t2.medium",
    "node_count": 1,
}

REQUIRED_FIELDS = {
    "zone": str,
    "instance_ami": str,
}

console = Console()


def validate_config(config: Dict[str, Any]) -> None:
    """Validate the configuration format and required fields"""
    if not config:
        raise ValueError("Empty configuration")

    for region, region_config in config.items():
        if not isinstance(region_config, dict):
            raise ValueError(f"Invalid configuration for region {region}")

        # Check required fields
        for field, field_type in REQUIRED_FIELDS.items():
            if field not in region_config:
                raise ValueError(
                    f"Missing required field '{field}' for region {region}"
                )
            if not isinstance(region_config[field], field_type):
                raise ValueError(
                    f"Invalid type for field '{field}' in region {region}. "
                    f"Expected {field_type.__name__}"
                )

        # Apply defaults for optional fields
        for field, default_value in DEFAULTS.items():
            if field not in region_config:
                region_config[field] = default_value


def run_command(
    cmd: list[str], cwd: Optional[str] = None
) -> subprocess.CompletedProcess:
    """Run a command with proper error handling"""
    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {' '.join(cmd)}\n"
        error_msg += f"Exit code: {e.returncode}\n"
        if e.stdout:
            error_msg += f"stdout:\n{e.stdout}\n"
        if e.stderr:
            error_msg += f"stderr:\n{e.stderr}\n"
        raise RuntimeError(error_msg) from e


def load_config() -> Dict[str, Any]:
    """Load configuration from locations.yaml"""
    try:
        with open("locations.yaml", "r") as f:
            yaml_data = yaml.safe_load(f)
            if not isinstance(yaml_data, list):
                raise ValueError("Expected a list of region configurations")

            # Convert list of single-key dictionaries into a single dictionary
            config = {}
            for region_dict in yaml_data:
                if not isinstance(region_dict, dict):
                    raise ValueError("Each region configuration must be a dictionary")
                if len(region_dict) != 1:
                    raise ValueError(
                        "Each region configuration must have exactly one key"
                    )

                region = list(region_dict.keys())[0]
                config[region] = region_dict[region]

            # Validate the configuration
            validate_config(config)
            return config

    except FileNotFoundError:
        print("Error: locations.yaml file not found")
        print("Please create a locations.yaml file with your region configurations")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing locations.yaml: {e}")
        print("Please ensure your YAML file is properly formatted")
        sys.exit(1)
    except ValueError as e:
        print(f"Invalid configuration: {e}")
        sys.exit(1)


def deploy(command, region, region_config):
    """Deploys or destroys resources in a single region."""
    terraform_command = "apply" if command == "create" else "destroy"

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]{region}[/cyan] - {command.capitalize()}", total=3
        )

        # Select workspace for this region
        run_command(["terraform", "workspace", "select", "-or-create", region])

        progress.update(
            task, advance=1, description=f"[cyan]{region}[/cyan] - Initializing"
        )
        run_command(["terraform", "init", "-upgrade"])

        progress.update(
            task, advance=1, description=f"[cyan]{region}[/cyan] - Applying"
        )
        run_command(
            [
                "terraform",
                terraform_command,
                "-auto-approve",
                f"-var=region={region}",
                f"-var=zone={region_config['zone']}",
                f"-var=instance_ami={region_config['instance_ami']}",
                f"-var=node_count={region_config['node_count']}",
                f"-var=instance_type={region_config['instance_type']}",
                "-var-file=env.tfvars.json",
            ]
        )

        progress.update(
            task, advance=1, description=f"[cyan]{region}[/cyan] - ✓ Complete"
        )


def main():
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ["create", "destroy"]:
            console.print(
                "[yellow]Please specify 'create' or 'destroy' as argument[/yellow]"
            )
            sys.exit(1)

        command = sys.argv[1]

        # Load and validate configuration
        config = load_config()

        console.print(f"\n[bold blue]Starting {command} operation...[/bold blue]\n")

        # Deploy/destroy resources in each region sequentially
        for region, region_config in config.items():
            deploy(command, region, region_config)

        # Display final summary with fixed-width columns
        table = Table(
            title="Deployment Summary",
            show_header=True,
            header_style="bold",
            padding=(0, 2),  # Add padding for readability
            box=box.DOUBLE,  # Use double-line box style for better visibility
        )

        # Fixed column widths with better alignment
        table.add_column("Region", style="cyan", width=15, justify="left", no_wrap=True)
        table.add_column(
            "Status", style="magenta", width=10, justify="center", no_wrap=True
        )
        table.add_column(
            "Instance", style="green", width=30, justify="left", no_wrap=True
        )
        table.add_column("IP", style="blue", width=20, justify="left", no_wrap=True)

        # Create a live display
        with console.status(
            "[bold blue]Gathering deployment information...[/bold blue]"
        ) as status:
            for region, region_config in config.items():
                try:
                    # Select the workspace for this region
                    run_command(
                        ["terraform", "workspace", "select", "-or-create", region]
                    )

                    # Refresh the state
                    run_command(
                        [
                            "terraform",
                            "refresh",
                            f"-var=region={region}",
                            f"-var=zone={region_config['zone']}",
                            f"-var=instance_ami={region_config['instance_ami']}",
                            f"-var=node_count={region_config['node_count']}",
                            f"-var=instance_type={region_config['instance_type']}",
                            "-var-file=env.tfvars.json",
                        ]
                    )

                    # Get all outputs
                    result = run_command(["terraform", "output", "-json"])
                    outputs = json.loads(result.stdout)

                    if not outputs:
                        table.add_row(region, "No resources deployed", "", "")
                        continue

                    # Get instance details
                    public_ips = outputs.get("public_ip", {}).get("value", [])
                    instance_names = outputs.get("instance_name", {}).get("value", [])

                    if not public_ips or not instance_names:
                        table.add_row(region, "No instances found", "")
                        continue

                    # Add a row for each instance
                    for i, (name, ip) in enumerate(zip(instance_names, public_ips)):
                        # Truncate long values to fit columns
                        truncated_name = (name[:27] + "...") if len(name) > 27 else name
                        truncated_ip = (ip[:17] + "...") if len(ip) > 17 else ip

                        status_icon = "✓" if command == "create" else "✗"
                        status_style = "green" if command == "create" else "red"

                        if i == 0:
                            table.add_row(
                                region,
                                f"[{status_style}]{status_icon}[/{status_style}]",
                                f"{truncated_name}",
                                truncated_ip,
                            )
                        else:
                            table.add_row(
                                "",
                                "",
                                f"└─ {truncated_name}",
                                truncated_ip,
                            )

                except subprocess.CalledProcessError as e:
                    if (
                        "InvalidClientTokenId" in e.stderr
                        or "security token included in the request is invalid"
                        in e.stderr
                    ):
                        table.add_row(region, "⚠ Region Disabled", "", style="yellow")
                    elif "Empty or non-existent state" in e.stderr:
                        table.add_row(region, "No resources deployed", "")
                    else:
                        raise

                except Exception as e:
                    logging.error(f"Failed to get output for region {region}: {str(e)}")
                    table.add_row(region, "✗ Failed", "", style="red")

        # Clear any previous output and show the final table
        console.clear()
        console.print("\n")
        console.print(table)
        console.print("\n[bold green]Operation complete![/bold green]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
