import argparse
import json
import os
import subprocess
import sys
import concurrent.futures
import threading

import yaml


def get_nodes(api_host):
    """Get list of all Bacalhau nodes."""
    try:
        cmd = [
            "bacalhau",
            "node",
            "list",
            "--output",
            "json",
            "-c",
            f"API.Host={api_host}",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running bacalhau node list: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}")
        sys.exit(1)


def delete_node(node_id, api_host, print_lock):
    """Delete a specific node by ID."""
    try:
        cmd = [
            "bacalhau",
            "node",
            "delete",
            node_id,
            "-c",
            f"API.Host={api_host}",
        ]

        result = subprocess.run(cmd, capture_output=True, check=True, text=True)
        with print_lock:
            print(f"Successfully deleted node: {node_id}")
        return True
    except subprocess.CalledProcessError as e:
        with print_lock:
            print(f"Failed to delete node {node_id}. Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Delete disconnected Bacalhau nodes")
    parser.add_argument("--api-host", help="API host to connect to")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    if not args.api_host:
        print("API host is required")
        sys.exit(1)

    print(f"\nConnecting to API host: {args.api_host}")

    # Get all nodes
    nodes = get_nodes(args.api_host)

    # Filter disconnected compute nodes
    disconnected_nodes = [
        node
        for node in nodes
        if (
            node["Connection"] == "DISCONNECTED"
            and node["Info"]["NodeType"] == "Compute"
        )
    ]

    if not disconnected_nodes:
        print("No disconnected nodes found.")
        return

    print(f"\nFound {len(disconnected_nodes)} disconnected node(s):")
    for node in disconnected_nodes:
        print(f"  - {node['Info']['NodeID']}")

    if args.dry_run:
        print("\nDry run - no nodes were deleted")
        return

    print("\nDeleting nodes...")
    deleted_count = 0
    print_lock = threading.Lock()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Create a list to store the futures
        future_to_node = {
            executor.submit(delete_node, node["Info"]["NodeID"], args.api_host, print_lock): node 
            for node in disconnected_nodes
        }
        
        # As each future completes, count the successful deletions
        for future in concurrent.futures.as_completed(future_to_node):
            if future.result():
                deleted_count += 1

    print(f"\nDeleted {deleted_count} of {len(disconnected_nodes)} disconnected nodes")


if __name__ == "__main__":
    main()
