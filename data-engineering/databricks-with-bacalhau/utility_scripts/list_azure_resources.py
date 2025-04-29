#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import os
import subprocess
import sys

import yaml


def run_azure_command(command: str) -> None:
    """Run an Azure CLI command and print the output."""
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        if result.stdout.strip():
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        if "az postgres" in command and "not found" in str(e.stderr):
            print("\nError: The 'postgres' extension is required.")
            print("Install it with: az extension add --name postgres")
            sys.exit(1)
        print(f"Error running Azure command: {e}", file=sys.stderr)
        if e.stderr:
            print(f"Azure CLI error: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def check_postgres_extension() -> None:
    """Check if the postgres extension is installed."""
    try:
        result = subprocess.run(
            "az extension show --name postgres",
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )
        return
    except subprocess.CalledProcessError:
        print("\nWarning: The 'postgres' extension is not installed.")
        print("Installing postgres extension...")
        try:
            subprocess.run(
                "az extension add --name postgres",
                shell=True,
                check=True,
                capture_output=True,
            )
            print("Successfully installed postgres extension.")
        except subprocess.CalledProcessError as e:
            print("Failed to install postgres extension automatically.")
            print(
                "Please install it manually with: az extension add --name postgres"
            )
            sys.exit(1)


def main():
    # Check for required Azure CLI extension
    check_postgres_extension()

    # Request config.yaml command line argument
    if len(sys.argv) != 2:
        print("Usage: list_azure_resources.py <config_path>")
        sys.exit(1)

    # Convert relative path to absolute path
    config_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(config_path):
        print(f"Error: config.yaml not found at {config_path}")
        sys.exit(1)

    # Read the resource group from config.yaml
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Check if azure section exists
        if "azure" not in config:
            print("Warning: 'azure' section not found in config.yaml")
            resource_group = None
        else:
            resource_group = config["azure"].get("resource_group")
    except Exception as e:
        print(f"Error reading config file: {e}")
        sys.exit(1)

    print("\nListing Azure Subscriptions:")
    print("===========================")
    run_azure_command("az account list --output table")

    print("\nCurrent Subscription:")
    print("====================")
    run_azure_command("az account show --output table")

    print("\nListing Resource Groups:")
    print("=======================")
    run_azure_command("az group list --output table")

    # If resource group is provided, list PostgreSQL instances in that group
    if resource_group:
        print(
            "\nListing PostgreSQL servers in resource group:",
            resource_group,
        )
        print("=" * (len(resource_group) + 48))
        run_azure_command(
            f"az postgres server list --resource-group {resource_group} --output table"
        )
    else:
        print("\nWarning: No resource group provided in config.yaml.")
        print("Listing all PostgreSQL servers:")
        print("=========================================")
        run_azure_command("az postgres server list --output table")

    print("\nTo switch subscriptions, use:")
    print("az account set --subscription <subscription-id-or-name>")


if __name__ == "__main__":
    main()
