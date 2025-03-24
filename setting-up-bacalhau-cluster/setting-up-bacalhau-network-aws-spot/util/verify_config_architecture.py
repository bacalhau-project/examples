#!/usr/bin/env uv run -s
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
#     "rich",
#     "boto3",
# ]
# ///

"""
Verify the architecture compatibility of AMIs and instance types in a config file.
This script checks if the AMI architecture matches the expected instance type architecture.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List

import boto3
import yaml
from rich.console import Console
from rich.table import Table

# Initialize rich console
console = Console()


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            if not config:
                console.print(
                    f"[bold red]Error:[/bold red] Configuration file {config_path} is empty."
                )
                sys.exit(1)
            return config
    except FileNotFoundError:
        console.print(
            f"[bold red]Error:[/bold red] Configuration file {config_path} not found."
        )
        sys.exit(1)
    except yaml.YAMLError as e:
        console.print(
            f"[bold red]Error:[/bold red] Failed to parse {config_path}: {str(e)}"
        )
        sys.exit(1)
    except Exception as e:
        console.print(
            f"[bold red]Error:[/bold red] Failed to load {config_path}: {str(e)}"
        )
        sys.exit(1)


def load_ami_data(ami_path: str) -> Dict[str, Dict[str, Any]]:
    """Load AMI information from JSON file."""
    try:
        with open(ami_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] AMI information file {ami_path} not found."
        )
        return {}
    except json.JSONDecodeError as e:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Failed to parse {ami_path}: {str(e)}"
        )
        return {}
    except Exception as e:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Failed to load {ami_path}: {str(e)}"
        )
        return {}


def check_instance_availability(region: str, instance_type: str) -> dict:
    """
    Check if an instance type is available in a region and get its spot price.

    Args:
        region: The AWS region to check
        instance_type: The instance type to check

    Returns:
        Dictionary with availability status and price information
    """
    try:
        # Create EC2 client for the region
        ec2_client = boto3.client("ec2", region_name=region)

        # Check spot price history
        spot_response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )

        # If we got a price, the instance type is available for spot
        if spot_response.get("SpotPriceHistory"):
            spot_price = float(spot_response["SpotPriceHistory"][0]["SpotPrice"])
            return {"available": True, "spot_price": spot_price, "error": None}
        return {
            "available": False,
            "spot_price": None,
            "error": "No spot price history found",
        }
    except Exception as e:
        error_message = str(e)
        if "The request must contain the parameter InstanceType" in error_message:
            return {
                "available": False,
                "spot_price": None,
                "error": f"Instance type {instance_type} does not exist",
            }
        elif (
            "InvalidParameterValue" in error_message and "instanceType" in error_message
        ):
            return {
                "available": False,
                "spot_price": None,
                "error": f"Instance type {instance_type} not supported in {region}",
            }
        else:
            return {"available": False, "spot_price": None, "error": error_message}


def verify_architectures(
    config: Dict[str, Any],
    ami_data: Dict[str, Dict[str, Any]],
    skip_live_check: bool = False,
) -> List[Dict[str, Any]]:
    """Verify architecture compatibility for all regions in the config."""
    issues = []
    price_info = {}

    # Get regions section from config, handling both old and new formats
    if isinstance(config.get("regions"), list):
        # Old format with list of dicts
        region_configs = {}
        for region_entry in config["regions"]:
            if isinstance(region_entry, dict):
                region_configs.update(region_entry)
    else:
        # New format with direct dict
        region_configs = config.get("regions", {})

    for region_name, region_config in region_configs.items():
        # Skip if not a dict
        if not isinstance(region_config, dict):
            continue

        # Get instance type
        instance_type = region_config.get("machine_type", "")
        if not instance_type:
            issues.append(
                {
                    "region": region_name,
                    "issue_type": "missing_instance_type",
                    "details": "No machine_type specified",
                    "severity": "error",
                }
            )
            continue

        # Get AMI architecture from config
        config_architecture = region_config.get("architecture", "x86_64")

        # Get AMI ID
        ami_id = region_config.get("ami_id", region_config.get("image", "auto"))

        # Determine expected architecture based on instance type
        expected_arch = (
            "arm64"
            if any(
                family in instance_type for family in ["a1", "t4g", "c6g", "m6g", "r6g"]
            )
            else "x86_64"
        )

        # Check for architecture mismatch in config
        if config_architecture != expected_arch:
            issues.append(
                {
                    "region": region_name,
                    "issue_type": "architecture_mismatch",
                    "details": f"Instance type {instance_type} expects {expected_arch} architecture, but config specifies {config_architecture}",
                    "severity": "error",
                    "instance_type": instance_type,
                    "expected_arch": expected_arch,
                    "config_arch": config_architecture,
                }
            )

        # If we have AMI data, verify the AMI architecture
        if ami_data and region_name in ami_data:
            if expected_arch in ami_data[region_name]:
                ami_info = ami_data[region_name][expected_arch]

                # If the AMI ID is specified in config, check if it matches
                if ami_id != "auto" and ami_id != ami_info["image_id"]:
                    issues.append(
                        {
                            "region": region_name,
                            "issue_type": "ami_mismatch",
                            "details": f"Config specifies AMI {ami_id}, but the recommended AMI for {expected_arch} is {ami_info['image_id']}",
                            "severity": "warning",
                            "config_ami": ami_id,
                            "recommended_ami": ami_info["image_id"],
                        }
                    )
            else:
                issues.append(
                    {
                        "region": region_name,
                        "issue_type": "missing_ami",
                        "details": f"No {expected_arch} AMI found for region {region_name}",
                        "severity": "error" if ami_id == "auto" else "warning",
                        "expected_arch": expected_arch,
                    }
                )

    return issues


def print_issues_table(issues: List[Dict[str, Any]]) -> None:
    """Print a table of architecture compatibility issues."""
    if not issues:
        console.print(
            "[bold green]✓[/bold green] No architecture compatibility issues found!"
        )
        return

    # Filter issues - separate errors and warnings
    errors = [issue for issue in issues if issue["severity"] == "error"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]

    # Group issues by region
    issues_by_region = {}

    # Show errors first, then warnings if we have any errors
    display_issues = errors if errors else issues

    for issue in display_issues:
        region = issue["region"]
        if region not in issues_by_region:
            issues_by_region[region] = []
        issues_by_region[region].append(issue)

    # Create a table
    table = Table(title="Architecture Compatibility Issues")
    table.add_column("Region", style="cyan")
    table.add_column("Issue Type", style="yellow")
    table.add_column("Details", style="white")
    table.add_column("Spot Price", style="green")
    table.add_column("Severity", style="red")

    for region, region_issues in sorted(issues_by_region.items()):
        for i, issue in enumerate(sorted(region_issues, key=lambda x: x["severity"])):
            # Show region only on first issue for this region
            region_display = region if i == 0 else ""

            # Colorize severity
            severity = issue["severity"]
            if severity == "error":
                severity_display = "[bold red]ERROR[/bold red]"
            else:
                severity_display = "[yellow]WARNING[/yellow]"

            # Get price information if available
            price_info = issue.get("price_info", {})
            if price_info and price_info.get("spot_price"):
                price_display = f"${price_info['spot_price']:.4f}/hr"
            else:
                price_display = "N/A"

            table.add_row(
                region_display,
                issue["issue_type"].replace("_", " ").title(),
                issue["details"],
                price_display,
                severity_display,
            )

    console.print(table)

    # Print summary by severity
    error_count = len(errors)
    warning_count = len(warnings)

    console.print(
        f"\nFound [bold red]{error_count} errors[/bold red] and [yellow]{warning_count} warnings[/yellow]"
    )

    # Print recommendations
    if error_count > 0:
        console.print("\n[bold]Recommendations for Errors:[/bold]")
        console.print(
            "[yellow]1. Run 'util/get_ubuntu_amis.py' to fetch AMIs for both x86_64 and arm64 architectures[/yellow]"
        )
        console.print(
            "[yellow]2. Run 'util/update_config_with_regions.py' to update your config with appropriate AMIs[/yellow]"
        )
        console.print(
            "[yellow]3. Edit config.yaml to ensure instance types match their AMI architectures:[/yellow]"
        )
        console.print(
            "   - ARM instance types (a1, t4g, c6g, m6g, r6g) need arm64 AMIs"
        )
        console.print("   - x86 instance types (t2, t3, m5, c5, etc.) need x86_64 AMIs")

    # If only warnings about instance types, provide specific fix
    elif warning_count > 0 and all(
        issue["issue_type"] == "invalid_instance_type" for issue in warnings
    ):
        console.print("\n[bold]Recommendations for Instance Type Warnings:[/bold]")
        console.print(
            "[yellow]To fix all instance type compatibility warnings, run:[/yellow]"
        )
        console.print(
            "sed -i '' 's/machine_type: t3a.small/machine_type: t3.small/g' config.yaml"
        )
        console.print("\n[yellow]Or for even wider compatibility:[/yellow]")
        console.print(
            "sed -i '' 's/machine_type: t3a.small/machine_type: t2.small/g' config.yaml"
        )
        console.print(
            "\n[yellow]After making changes, run the update and verify scripts again:[/yellow]"
        )
        console.print("uv run -s util/update_config_with_regions.py")
        console.print("uv run -s util/verify_config_architecture.py")


def main():
    parser = argparse.ArgumentParser(
        description="Verify architecture compatibility in config"
    )
    parser.add_argument(
        "--config", "-c", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--ami-data", "-a", default="ubuntu_amis.json", help="Path to AMI data file"
    )
    parser.add_argument(
        "--fix", "-f", action="store_true", help="Automatically fix common issues"
    )
    parser.add_argument(
        "--skip-live-check",
        "-s",
        action="store_true",
        help="Skip live AWS spot price and availability check",
    )
    args = parser.parse_args()

    # Check if config exists
    if not os.path.exists(args.config):
        console.print(
            f"[bold red]Error:[/bold red] Config file {args.config} not found!"
        )
        sys.exit(1)

    # Load config
    console.print(f"Loading configuration from {args.config}...")
    config = load_config(args.config)

    # Load AMI data if available
    ami_data = {}
    if os.path.exists(args.ami_data):
        console.print(f"Loading AMI data from {args.ami_data}...")
        ami_data = load_ami_data(args.ami_data)
    else:
        console.print(
            f"[yellow]AMI data file {args.ami_data} not found. Run util/get_ubuntu_amis.py to fetch AMIs.[/yellow]"
        )

    # Verify architectures
    console.print("Verifying architecture compatibility...")
    issues = verify_architectures(config, ami_data, args.skip_live_check)

    # Auto-fix if requested
    if args.fix and issues:
        warnings_only = all(issue["severity"] == "warning" for issue in issues)
        instance_type_issues = all(
            issue["issue_type"] == "invalid_instance_type" for issue in issues
        )

        if warnings_only and instance_type_issues:
            console.print(
                "\n[bold green]Attempting to auto-fix instance type compatibility issues...[/bold green]"
            )

            # Create backup
            backup_path = f"{args.config}.bak"
            try:
                with open(args.config, "r") as f:
                    config_content = f.read()

                with open(backup_path, "w") as f:
                    f.write(config_content)

                console.print(f"Created backup at {backup_path}")

                # Replace problematic instance types with region-specific valid ones
                new_content = config_content

                # Load the configuration as YAML to access the structure
                config_yaml = yaml.safe_load(config_content)
                if "regions" in config_yaml:
                    regions_section = config_yaml["regions"]

                    # Handle the regions section
                    if isinstance(regions_section, list):
                        # Old format with list of dicts
                        for i, region_entry in enumerate(regions_section):
                            if isinstance(region_entry, dict):
                                for region_name, region_config in region_entry.items():
                                    if (
                                        isinstance(region_config, dict)
                                        and "machine_type" in region_config
                                    ):
                                        current_type = region_config["machine_type"]
                                        # Replace t3a.small with t3.small for better compatibility
                                        if current_type == "t3a.small":
                                            pattern = f"machine_type: {current_type}"
                                            replacement_text = "machine_type: t3.small"
                                            new_content = new_content.replace(
                                                pattern, replacement_text
                                            )
                                            console.print(
                                                f"  - Region {region_name}: Replacing {current_type} with t3.small"
                                            )
                    else:
                        # New format with direct dict
                        for region_name, region_config in regions_section.items():
                            if (
                                isinstance(region_config, dict)
                                and "machine_type" in region_config
                            ):
                                current_type = region_config["machine_type"]
                                # Replace t3a.small with t3.small for better compatibility
                                if current_type == "t3a.small":
                                    pattern = f"machine_type: {current_type}"
                                    replacement_text = "machine_type: t3.small"
                                    new_content = new_content.replace(
                                        pattern, replacement_text
                                    )
                                    console.print(
                                        f"  - Region {region_name}: Replacing {current_type} with t3.small"
                                    )

                with open(args.config, "w") as f:
                    f.write(new_content)

                console.print(
                    "[bold green]Fixed instance type issues by replacing t3a.small with t3.small for better compatibility[/bold green]"
                )

                # Re-verify after fix
                console.print("\nRe-verifying configuration after fixes...")
                config = load_config(args.config)
                issues = verify_architectures(config, ami_data, args.skip_live_check)

            except Exception as e:
                console.print(f"[bold red]Error during auto-fix:[/bold red] {str(e)}")
        else:
            console.print(
                "[yellow]Cannot auto-fix errors or complex issues. Please follow the recommendations below.[/yellow]"
            )

    # Print issues table
    print_issues_table(issues)

    # Exit with error code if there are critical issues
    if any(issue["severity"] == "error" for issue in issues):
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
