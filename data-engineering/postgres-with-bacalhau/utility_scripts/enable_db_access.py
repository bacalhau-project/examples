#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "psycopg2-binary",
#     "pyyaml",
# ]
# ///

import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

import requests
import yaml


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


def read_config() -> Dict[str, Any]:
    """Read the config file to get Azure resource details."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Error: config file not found at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing config file: {e}")
        sys.exit(1)


def get_current_ip() -> str:
    """Get the current public IP address."""
    try:
        response = requests.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return response.json()["ip"]
    except Exception as e:
        print(f"Error getting current IP address: {e}")
        sys.exit(1)


def run_azure_command(command: str) -> Optional[Dict[str, Any]]:
    """Run an Azure CLI command and return the JSON output."""
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        if result.stdout.strip():
            # Only try to parse JSON if the command doesn't end with '-o tsv'
            if not command.strip().endswith("-o tsv"):
                return json.loads(result.stdout)
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        if "az postgres" in command and "not found" in str(e.stderr):
            print("\nError: The 'postgres' extension is required.")
            print("Install it with: az extension add --name postgres")
            sys.exit(1)
        print(f"Error running Azure command: {e}")
        if e.stderr:
            print(f"Azure CLI error: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing Azure CLI output: {e}")
        print(f"Command output: {result.stdout}")
        sys.exit(1)


def main():
    # Check for required Azure CLI extension
    check_postgres_extension()

    # Read config
    config = read_config()

    # Extract Azure resource details
    try:
        # Require all necessary configuration
        if "postgresql" not in config:
            print("Error: Missing 'postgresql' section in config.yaml")
            sys.exit(1)

        if "azure" not in config:
            print("Error: Missing 'azure' section in config.yaml")
            sys.exit(1)

        required_pg_fields = ["host", "database", "user", "password", "port"]
        missing_pg = [f for f in required_pg_fields if f not in config["postgresql"]]
        if missing_pg:
            print(
                f"Error: Missing required PostgreSQL fields in config.yaml: {', '.join(missing_pg)}"
            )
            sys.exit(1)

        required_azure_fields = ["resource_group", "server_name"]
        missing_azure = [f for f in required_azure_fields if f not in config["azure"]]
        if missing_azure:
            print(
                f"Error: Missing required Azure fields in config.yaml: {', '.join(missing_azure)}"
            )
            print("\nPlease add to config.yaml:")
            print("azure:")
            print("  resource_group: your-resource-group")
            print("  server_name: your-server-name")
            sys.exit(1)

        resource_group = config["azure"]["resource_group"]
        server_name = config["azure"]["server_name"]

    except KeyError as e:
        print(f"Error: Missing required config: {e}")
        sys.exit(1)

    # Get current IP
    current_ip = get_current_ip()
    print(f"Current IP address: {current_ip}")

    # Add IP to firewall rules
    rule_name = f"Allow_{current_ip.replace('.', '_')}"
    print(f"Adding IP {current_ip} to firewall rules...")

    run_azure_command(
        f"az postgres server update "
        f"--name {server_name} "
        f"--resource-group {resource_group} "
        f"--public-network-access Enabled "  # Enable public access
        f"--add-ip {current_ip}"  # Add IP to allowed ranges
    )

    print(f"\nSuccessfully added IP {current_ip} to firewall rules")
    print("\nYou should now be able to connect to the database")


if __name__ == "__main__":
    main()
