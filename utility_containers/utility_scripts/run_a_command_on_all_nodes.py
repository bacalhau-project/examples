#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import argparse
import json
import subprocess
import sys
from typing import List, Optional, Tuple


def run_bacalhau_command(command: str) -> Optional[str]:
    """Run a bacalhau command and return the output."""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {command}")
        print(f"Error output: {e.stderr}")
        return None


def get_nodes() -> List[Tuple[str, str]]:
    """Get list of node public IPs and their cloud providers from bacalhau node list."""
    output = run_bacalhau_command("bacalhau node list --output json")
    if not output:
        print("❌ Failed to get node list")
        sys.exit(1)

    try:
        nodes = json.loads(output)
        # Extract nodes with PUBLIC_IP label
        node_info = []
        skipped = 0
        for node in nodes:
            labels = node.get("Info", {}).get("Labels", {})
            public_ip = labels.get("PUBLIC_IP")
            cloud_provider = labels.get("CLOUD_PROVIDER", "Unknown")

            if public_ip:
                node_info.append((public_ip, cloud_provider))
            else:
                skipped += 1

        if skipped > 0:
            print(f"ℹ️  Skipped {skipped} nodes without PUBLIC_IP label")

        if not node_info:
            print("❌ No nodes found with PUBLIC_IP label")
            sys.exit(1)

        return node_info

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse node list JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error processing node list: {e}")
        sys.exit(1)


def run_command_on_node(
    username: str, node_ip: str, command: str, provider: str
) -> bool:
    """Run command on a single node via SSH."""
    ssh_command = f"ssh -o StrictHostKeyChecking=no {username}@{node_ip} '{command}'"
    try:
        print(f"\n🔄 Running on {node_ip} ({provider})...")
        result = subprocess.run(
            ssh_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )

        if result.returncode == 0:
            print(f"✅ Success on {node_ip}")
            if result.stdout.strip():
                print("Output:")
                print(result.stdout)
            return True
        else:
            print(f"❌ Failed on {node_ip}")
            print(f"Error output: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error executing command on {node_ip}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run a command on all Bacalhau nodes")
    parser.add_argument(
        "username",
        help="Username to use for SSH connection",
    )
    parser.add_argument(
        "command",
        help="Command to run on each node",
        nargs="+",  # Allow multiple words in command
    )

    args = parser.parse_args()
    command = " ".join(args.command)  # Join command parts back together

    print("🔍 Getting node list...")
    nodes = get_nodes()
    print(f"Found {len(nodes)} nodes with PUBLIC_IP label")

    success_count = 0
    for node_ip, provider in nodes:
        if run_command_on_node(args.username, node_ip, command, provider):
            success_count += 1

    print(f"\n📊 Summary: Successfully ran on {success_count}/{len(nodes)} nodes")
    if success_count < len(nodes):
        sys.exit(1)


if __name__ == "__main__":
    main()
