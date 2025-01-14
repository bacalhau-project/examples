#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
#     "rich",
# ]
# ///

import argparse
import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

import yaml
from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, TimeRemainingColumn
from rich.table import Table

# Set up argument parser before logging configuration
parser = argparse.ArgumentParser(description="Deploy or destroy infrastructure")
parser.add_argument("command", choices=["create", "destroy"], help="Action to perform")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")

args = parser.parse_args()

# Set up logging with more detail
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log"),
            mode="w",  # Overwrite the file each run
        ),
    ],
)

# Log the start of the script with a clear separator
logging.info("=" * 80)
logging.info("Starting new deployment operation")
if args.debug:
    logging.info("Debug logging enabled")
logging.info("=" * 80)

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
        logging.debug(f"Executing command: {' '.join(cmd)}")
        if cwd:
            logging.debug(f"Working directory: {cwd}")

        # Get current environment
        env = os.environ.copy()

        logging.debug("Starting command execution")
        result = subprocess.run(
            cmd,
            check=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env,
        )
        logging.debug("Command completed successfully")
        if result.stdout:
            logging.debug(f"Command stdout:\n{result.stdout}")
        if result.stderr:
            logging.debug(f"Command stderr:\n{result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {' '.join(cmd)}\n"
        error_msg += f"Exit code: {e.returncode}\n"
        if e.stdout:
            error_msg += f"stdout:\n{e.stdout}\n"
        if e.stderr:
            error_msg += f"stderr:\n{e.stderr}\n"
        logging.error(error_msg)

        # Print a user-friendly error message
        console.print(
            f"\n[red]Error: Command failed with exit code {e.returncode}[/red]"
        )
        console.print(f"[red]Command: {' '.join(cmd)}[/red]")
        if e.stderr:
            console.print(f"[yellow]Error details:[/yellow]\n{e.stderr}")

        # Exit immediately on command failure
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error running command: {' '.join(cmd)}\n{str(e)}"
        logging.error(error_msg)

        # Print a user-friendly error message
        console.print("\n[red]Unexpected error:[/red]")
        console.print(f"[red]Command: {' '.join(cmd)}[/red]")
        console.print(f"[yellow]Error details:[/yellow]\n{str(e)}")

        # Exit immediately on any error
        sys.exit(1)


def load_config() -> Dict[str, Any]:
    """Load configuration from locations.yaml"""
    try:
        with open("locations.yaml", "r") as f:
            yaml_data = yaml.safe_load(f)
            if not isinstance(yaml_data, list):
                raise ValueError("Expected a list of zone configurations")

            # Convert list of zone configurations into a dictionary
            config = {}
            for zone_dict in yaml_data:
                if not isinstance(zone_dict, dict):
                    raise ValueError("Each zone configuration must be a dictionary")
                if len(zone_dict) != 1:
                    raise ValueError(
                        "Each zone configuration must have exactly one key"
                    )

                zone_name = list(zone_dict.keys())[0]
                zone_config = zone_dict[zone_name]

                # Create a unique key for this zone
                zone_key = zone_name

                # Validate and set required fields
                config[zone_key] = {
                    "instance_type": zone_config.get("instance_type"),
                    "instance_ami": zone_config.get("instance_ami"),
                    "node_count": zone_config.get("node_count", 1),
                    "region": zone_config.get("region"),
                    "zone": zone_config.get("zone", zone_name),
                }

            # Validate the configuration
            validate_config(config)
            return config

    except FileNotFoundError:
        print("Error: locations.yaml file not found")
        print("Please create a locations.yaml file with your zone configurations")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing locations.yaml: {e}")
        print("Please ensure your YAML file is properly formatted")
        sys.exit(1)
    except ValueError as e:
        print(f"Invalid configuration: {e}")
        sys.exit(1)


def update_machines_file(region: str, zone: str, outputs: Dict[str, Any]) -> None:
    """Update MACHINES.json with outputs from a region/zone"""
    machines_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "MACHINES.json"
    )

    try:
        if os.path.exists(machines_file):
            with open(machines_file, "r") as f:
                machines_data = json.load(f)
        else:
            machines_data = {}

        # Extract values from outputs, ensuring we get the raw values
        public_ips = outputs.get("public_ips", {}).get("value", [])
        private_ips = outputs.get("private_ips", {}).get("value", [])
        instance_ids = outputs.get("instance_ids", {}).get("value", [])

        # Log the raw values for debugging
        logging.debug(f"Raw outputs for {region}/{zone}:")
        logging.debug(f"Public IPs: {public_ips}")
        logging.debug(f"Private IPs: {private_ips}")
        logging.debug(f"Instance IDs: {instance_ids}")

        # Handle nested lists (sometimes AWS returns nested arrays)
        if (
            isinstance(public_ips, list)
            and public_ips
            and isinstance(public_ips[0], list)
        ):
            public_ips = public_ips[0]
        if (
            isinstance(private_ips, list)
            and private_ips
            and isinstance(private_ips[0], list)
        ):
            private_ips = private_ips[0]
        if (
            isinstance(instance_ids, list)
            and instance_ids
            and isinstance(instance_ids[0], list)
        ):
            instance_ids = instance_ids[0]

        # Ensure all lists are actually lists
        public_ips = (
            public_ips
            if isinstance(public_ips, list)
            else [public_ips]
            if public_ips
            else []
        )
        private_ips = (
            private_ips
            if isinstance(private_ips, list)
            else [private_ips]
            if private_ips
            else []
        )
        instance_ids = (
            instance_ids
            if isinstance(instance_ids, list)
            else [instance_ids]
            if instance_ids
            else []
        )

        # Create instances list for this zone
        instances = []
        max_length = max(len(instance_ids), len(public_ips), len(private_ips))

        for i in range(max_length):
            if i < len(instance_ids):  # Only create instance if we have an ID
                instance = {
                    "instance_id": instance_ids[i],
                    "public_ip": public_ips[i] if i < len(public_ips) else None,
                    "private_ip": private_ips[i] if i < len(private_ips) else None,
                    "zone": zone,
                }
                instances.append(instance)

        # Initialize region if it doesn't exist
        if region not in machines_data:
            machines_data[region] = {"name": region, "zones": {}}

        # Update the zone's data
        machines_data[region]["zones"][zone] = {"name": zone, "instances": instances}

        # Write updated data back to file
        with open(machines_file, "w") as f:
            json.dump(machines_data, f, indent=2)

        logging.info(
            f"Updated MACHINES.json with {len(instances)} instances for {region}/{zone}"
        )
    except Exception as e:
        logging.error(f"Error updating MACHINES.json: {str(e)}")
        raise


def check_machines_file() -> bool:
    """Check if MACHINES.json exists and return True if it does"""
    machines_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "MACHINES.json"
    )
    return os.path.exists(machines_file)


def delete_machines_file() -> None:
    """Delete MACHINES.json if it exists"""
    machines_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "MACHINES.json"
    )
    try:
        if os.path.exists(machines_file):
            os.remove(machines_file)
            logging.info("Deleted MACHINES.json")
    except Exception as e:
        logging.error(f"Error deleting MACHINES.json: {str(e)}")
        raise


def deploy(command, zone, zone_config):
    """Deploys or destroys resources in a single zone."""
    terraform_command = "apply" if command == "create" else "destroy"
    logging.info(f"Starting {command} operation for zone {zone}")

    # Get absolute path to env.tfvars.json
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    env_vars_file = os.path.join(workspace_dir, "env.tfvars.json")
    logging.info(f"Using env vars file: {env_vars_file}")

    # Check if env.tfvars.json exists
    if not os.path.exists(env_vars_file):
        logging.error(f"Required file not found: {env_vars_file}")
        raise FileNotFoundError(f"Required file not found: {env_vars_file}")

    logging.info(f"Zone config: {json.dumps(zone_config, indent=2)}")

    # For destroy command, get the current state before destroying
    destroyed_resources = {}
    if command == "destroy":
        try:
            run_command(["terraform", "workspace", "select", "-or-create", zone])
            result = run_command(["terraform", "output", "-json"])
            try:
                destroyed_resources = (
                    json.loads(result.stdout) if result.stdout.strip() else {}
                )
            except json.JSONDecodeError:
                logging.warning(f"Could not parse terraform output for zone {zone}")
                destroyed_resources = {}
        except Exception as e:
            logging.warning(f"Could not get current state for zone {zone}: {e}")
            # Even if we can't get the current state, we should still show what was in MACHINES.json
            destroyed_resources = {}

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]{zone}[/cyan] - {command.capitalize()}", total=3
        )

        # Select workspace for this zone
        logging.info(f"Selecting/creating workspace for zone {zone}")
        run_command(["terraform", "workspace", "select", "-or-create", zone])

        progress.update(
            task, advance=1, description=f"[cyan]{zone}[/cyan] - Initializing"
        )
        logging.info(f"Running terraform init for zone {zone}")
        run_command(["terraform", "init", "-upgrade"])

        progress.update(
            task,
            advance=1,
            description=f"[cyan]{zone}[/cyan] - {command.capitalize()}",
        )
        logging.info(f"Running terraform {terraform_command} for zone {zone}")
        logging.info(
            f"Command variables: region={zone_config['region']}, zone={zone_config['zone']}, "
            f"instance_ami={zone_config['instance_ami']}, "
            f"node_count={zone_config['node_count']}, "
            f"instance_type={zone_config['instance_type']}"
        )
        try:
            logging.debug(f"Starting terraform {terraform_command}")
            result = run_command(
                [
                    "terraform",
                    terraform_command,
                    "-auto-approve",
                    f"-var=region={zone_config['region']}",
                    f"-var=zone={zone_config['zone']}",
                    f"-var=instance_ami={zone_config['instance_ami']}",
                    f"-var=node_count={zone_config['node_count']}",
                    f"-var=instance_type={zone_config['instance_type']}",
                    f"-var-file={env_vars_file}",
                ]
            )
            logging.info(f"Terraform {terraform_command} completed successfully")

            # After successful creation, update MACHINES.json
            if command == "create":
                outputs_result = run_command(["terraform", "output", "-json"])
                outputs = json.loads(outputs_result.stdout)
                update_machines_file(zone_config["region"], zone, outputs)

            logging.debug(f"Terraform {terraform_command} output:\n{result.stdout}")
            if result.stderr:
                logging.debug(f"Terraform {terraform_command} stderr:\n{result.stderr}")
        except Exception as e:
            logging.error(f"Error during {terraform_command} for zone {zone}: {str(e)}")
            raise

        progress.update(
            task, advance=1, description=f"[cyan]{zone}[/cyan] - ✓ Complete"
        )
        logging.info(f"Completed {command} operation for zone {zone}")

    return destroyed_resources if command == "destroy" else None


def validate_aws_credentials() -> Tuple[bool, str]:
    """Validate AWS credentials are properly configured"""
    logging.info("Validating AWS credentials...")

    try:
        # Simply try to make an AWS API call
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            check=True,
        )
        identity = json.loads(result.stdout)
        user_arn = identity.get("Arn", "Unknown")
        account_id = identity.get("Account", "Unknown")
        logging.info(f"AWS credentials valid - User: {user_arn}, Account: {account_id}")
        return True, f"AWS credentials valid - Account: {account_id}"
    except subprocess.CalledProcessError as e:
        error_msg = "AWS credentials not found or invalid"
        if e.stderr:
            error_msg = f"AWS credential error: {e.stderr.strip()}"
        logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error validating AWS credentials: {str(e)}"
        logging.error(error_msg)
        return False, error_msg


def read_machines_file() -> Dict[str, Any]:
    """Read and return the contents of MACHINES.json"""
    machines_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "MACHINES.json"
    )
    try:
        if os.path.exists(machines_file):
            with open(machines_file, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"Error reading MACHINES.json: {str(e)}")
        raise


def main():
    try:
        command = args.command

        # Check MACHINES.json status
        if command == "create" and check_machines_file():
            console.print("\n[red]Error: MACHINES.json already exists[/red]")
            console.print("This indicates that there might be existing infrastructure.")
            console.print(
                "Please run 'destroy' first or manually delete MACHINES.json if you're sure it's safe."
            )
            sys.exit(1)

        # For destroy command, read the existing state before deleting
        machines_data = {}
        destroyed_resources = {}
        if command == "destroy":
            machines_data = read_machines_file()
            delete_machines_file()

        # Validate AWS credentials before proceeding
        credentials_valid, message = validate_aws_credentials()
        if not credentials_valid:
            console.print("\n[red]Error: AWS credentials are not valid[/red]")
            console.print(
                "Please configure your AWS credentials using one of these methods:"
            )
            console.print("1. Set environment variables:")
            console.print("   export AWS_ACCESS_KEY_ID='your-access-key'")
            console.print("   export AWS_SECRET_ACCESS_KEY='your-secret-key'")
            console.print("\n2. Or configure AWS CLI:")
            console.print("   aws configure")
            console.print("\nThen verify your credentials with:")
            console.print("   aws sts get-caller-identity")
            sys.exit(1)
        else:
            console.print(f"\n[green]{message}[/green]")

        # Get absolute path to env.tfvars.json
        workspace_dir = os.path.dirname(os.path.abspath(__file__))
        env_vars_file = os.path.join(workspace_dir, "env.tfvars.json")

        # Check if env.tfvars.json exists before starting
        if not os.path.exists(env_vars_file):
            console.print(
                f"\n[red]Error: Required file not found: {env_vars_file}[/red]"
            )
            console.print(
                "Please ensure env.tfvars.json exists in the same directory as deploy.py"
            )
            sys.exit(1)

        # Load and validate configuration
        config = load_config()

        console.print(f"\n[bold blue]Starting {command} operation...[/bold blue]\n")

        # Deploy/destroy resources in each zone sequentially
        for zone, zone_config in config.items():
            result = deploy(command, zone, zone_config)
            if command == "destroy" and result:
                destroyed_resources[zone] = result

        # Display final summary
        console.clear()
        console.print("\n")

        if command == "destroy":
            # Show summary of destroyed resources using both the saved machines_data
            # and the actual destroyed resources
            console.print("[bold red]Resources Destroyed:[/bold red]\n")

            for zone in config.keys():
                region = config[zone]["region"]
                console.print(f"[bold cyan]Zone: {zone} (Region: {region})[/bold cyan]")

                # Get data from both sources
                saved_data = (
                    machines_data.get(region, {}).get("zones", {}).get(zone, {})
                )
                destroyed_data = destroyed_resources.get(zone, {})

                # Display destroyed instances from MACHINES.json
                instances = saved_data.get("instances", [])
                if instances:
                    console.print("  [yellow]Instances:[/yellow]")
                    for instance in instances:
                        console.print(f"    [red]✗[/red] {instance['instance_id']}:")
                        console.print(
                            f"      [dim]Public IP: {instance['public_ip']}[/dim]"
                        )
                        console.print(
                            f"      [dim]Private IP: {instance['private_ip']}[/dim]"
                        )

                # Show VPCs and other AWS resources that were destroyed
                if destroyed_data:
                    vpc_resources = [
                        key for key in destroyed_data.keys() if "vpc" in key.lower()
                    ]
                    if vpc_resources:
                        console.print("  [yellow]VPC Resources:[/yellow]")
                        for resource in vpc_resources:
                            value = destroyed_data[resource].get("value")
                            if isinstance(value, list):
                                for v in value:
                                    console.print(f"    [red]✗[/red] {v}")
                            else:
                                console.print(f"    [red]✗[/red] {value}")

                    other_resources = [
                        key
                        for key in destroyed_data.keys()
                        if key not in vpc_resources
                        and key
                        not in [
                            "public_ips",
                            "private_ips",
                            "instance_ids",
                        ]
                    ]
                    if other_resources:
                        console.print("  [yellow]Other Resources:[/yellow]")
                        for resource in other_resources:
                            value = destroyed_data[resource].get("value")
                            if isinstance(value, list):
                                for v in value:
                                    console.print(f"    [red]✗[/red] {v}")
                            else:
                                console.print(f"    [red]✗[/red] {value}")

                # Only show "No resources" message if both sources are empty
                if not instances and not destroyed_data:
                    console.print("  [dim]No resources were active in this zone[/dim]")

                console.print()

        else:
            # Show active resources table using MACHINES.json
            machines_data = read_machines_file()

            table = Table(
                title="Active Deployments",
                show_header=True,
                header_style="bold",
                padding=(0, 2),
                box=box.DOUBLE,
            )

            # Columns for create operation
            table.add_column(
                "Region", style="cyan", width=15, justify="left", no_wrap=True
            )
            table.add_column(
                "Zone", style="green", width=15, justify="left", no_wrap=True
            )
            table.add_column(
                "Instance ID", style="yellow", width=25, justify="left", no_wrap=True
            )
            table.add_column(
                "Public IP", style="blue", width=20, justify="left", no_wrap=True
            )
            table.add_column(
                "Private IP", style="magenta", width=20, justify="left", no_wrap=True
            )

            # Add rows for each active instance from MACHINES.json
            for region_name, region_data in machines_data.items():
                for zone_name, zone_data in region_data.get("zones", {}).items():
                    for instance in zone_data.get("instances", []):
                        table.add_row(
                            region_name,
                            zone_name,
                            instance["instance_id"],
                            instance["public_ip"] or "",
                            instance["private_ip"] or "",
                        )

            console.print(table)

            # Print summary counts
            total_instances = sum(
                len(zone_data.get("instances", []))
                for region_data in machines_data.values()
                for zone_data in region_data.get("zones", {}).values()
            )
            total_regions = len(machines_data)
            total_zones = sum(
                len(region_data.get("zones", {}))
                for region_data in machines_data.values()
            )

            console.print("\n[bold cyan]Summary:[/bold cyan]")
            console.print(f"Total Regions: {total_regions}")
            console.print(f"Total Zones: {total_zones}")
            console.print(f"Total Instances: {total_instances}")

        console.print("\n[bold green]Operation complete![/bold green]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
