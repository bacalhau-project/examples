#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import json
import subprocess
import sys
from typing import Dict, List


def get_node_ips() -> List[str]:
    """Get list of public IPs from Bacalhau nodes."""
    try:
        # Run bacalhau node list command
        result = subprocess.run(
            ["bacalhau", "node", "list", "--output", "json"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output
        nodes = json.loads(result.stdout)

        # Extract public IPs
        ips = []
        for node in nodes:
            labels = node.get("Info", {}).get("Labels", {})
            if public_ip := labels.get("PUBLIC_IP"):
                ips.append(public_ip)

        return ips

    except subprocess.CalledProcessError as e:
        print(f"Error running bacalhau command: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}", file=sys.stderr)
        sys.exit(1)


def clean_logs(ip: str) -> None:
    """Remove log files from a remote node."""
    try:
        print(f"Cleaning logs on {ip}...")

        # Run remote command to remove log files
        subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",  # Don't prompt for key verification
                f"bacalhau-runner@{ip}",
                "sudo rm -f /bacalhau_data/*.log*",  # Remove all .log files
            ],
            check=True,
        )
        print(f"Successfully cleaned logs on {ip}")

    except subprocess.CalledProcessError as e:
        print(f"Error cleaning logs on {ip}: {e}", file=sys.stderr)


def main():
    """Main function to clean logs on all nodes."""
    # Get list of node IPs
    print("Getting node IPs...")
    ips = get_node_ips()

    if not ips:
        print("No nodes found with public IPs")
        return

    print(f"Found {len(ips)} nodes")

    # Clean logs on each node
    for ip in ips:
        clean_logs(ip)


if __name__ == "__main__":
    main()
