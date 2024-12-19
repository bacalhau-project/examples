import argparse
import json
import os
import subprocess
import sys

import yaml


def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
            # Extract required values
            compute = config.get('Compute', {})
            if not compute:
                raise ValueError("No 'Compute' section in config")
            
            orchestrators = compute.get('Orchestrators', [])
            if not orchestrators:
                raise ValueError("No 'Orchestrators' specified in config")
            
            orchestrator = orchestrators[0]  # Use first orchestrator
            token = compute.get('Auth', {}).get('Token')
            if not token:
                raise ValueError("No 'Auth.Token' specified in config")
            
            # Extract hostname without nats:// prefix and port
            if orchestrator.startswith('nats://'):
                orchestrator = orchestrator[7:]
            orchestrator = orchestrator.split(':')[0]  # Remove port number
            
            return {
                'api_host': orchestrator,
                'token': token
            }
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

def get_nodes(api_host, token):
    """Get list of all Bacalhau nodes."""
    try:
        cmd = [
            "bacalhau",
            "node",
            "list",
            "--output", "json",
            "-c", f"API.Host={api_host}"
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

def delete_node(node_id, api_host, token):
    """Delete a specific node by ID."""
    try:
        cmd = [
            "bacalhau",
            "node",
            "delete",
            node_id,
            "-c", f"API.Host={api_host}"
        ]
        
        subprocess.run(cmd, check=True)
        print(f"Successfully deleted node: {node_id}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to delete node {node_id}. Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Delete disconnected Bacalhau nodes")
    parser.add_argument('config', help='Path to config file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    
    print(f"\nConnecting to API host: {config['api_host']}")
    
    # Get all nodes
    nodes = get_nodes(config['api_host'], config['token'])
    
    # Filter disconnected compute nodes
    disconnected_nodes = [
        node for node in nodes
        if (
            node["Connection"] == "DISCONNECTED" and
            node["Info"]["NodeType"] == "Compute"
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
    for node in disconnected_nodes:
        if delete_node(node['Info']['NodeID'], config['api_host'], config['token']):
            deleted_count += 1

    print(f"\nDeleted {deleted_count} of {len(disconnected_nodes)} disconnected nodes")

if __name__ == "__main__":
    main()