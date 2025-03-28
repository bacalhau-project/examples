#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml"
# ]
# ///
import json
import os
import sys

import yaml


def main():
    # Get the parent directory
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    json_path = os.path.join(parent_dir, "available_regions.json")
    config_path = os.path.join(parent_dir, "config.yaml")

    # Check if the JSON file exists
    if not os.path.exists(json_path):
        print(
            f"Error: {json_path} not found. Please run get_available_regions.py first."
        )
        sys.exit(1)

    # Check if the config file exists
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        sys.exit(1)

    # Load the JSON file
    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        # Get the list of available regions
        regions = data.get("available_regions", [])

        if not regions:
            print("No available regions found in the JSON file.")
            sys.exit(1)

        print(f"Found {len(regions)} available regions in {json_path}")

        # Get region details for additional information
        region_details = data.get("region_details", {})

    except Exception as e:
        print(f"Error reading {json_path}: {str(e)}")
        sys.exit(1)

    # Load the config file
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if config is None:
            config = {}

        print(f"Loaded configuration from {config_path}")

    except Exception as e:
        print(f"Error reading {config_path}: {str(e)}")
        sys.exit(1)

    # Check if regions key exists
    if "regions" not in config:
        config["regions"] = []

    # Get existing regions to avoid duplicates
    existing_regions = set()
    for region_entry in config["regions"]:
        if isinstance(region_entry, dict):
            existing_regions.update(region_entry.keys())

    # Count how many regions we'll add
    new_regions = [r for r in regions if r not in existing_regions]
    print(f"Adding {len(new_regions)} new regions to config.yaml")

    # Get the default machine type from existing regions or use t3.small
    default_machine_type = "t3.small"  # Default

    # Try to find a better default from existing config
    if config["regions"]:
        for region_entry in config["regions"]:
            if isinstance(region_entry, dict):
                for region_name, region_config in region_entry.items():
                    if "machine_type" in region_config:
                        default_machine_type = region_config["machine_type"]
                        break

    # Add new regions to the config
    for region in new_regions:
        # Get the recommended instance type from region_details if available
        recommended_instance = None
        if region in region_details and region_details[region].get("available", False):
            recommended_instance = (
                region_details[region].get("cheapest_instance", {}).get("instance_type")
            )

        machine_type = (
            recommended_instance if recommended_instance else default_machine_type
        )

        config["regions"].append(
            {
                region: {
                    "image": "auto",
                    "machine_type": machine_type,
                    "node_count": "auto",
                }
            }
        )

    # Save the updated config
    try:
        # Create a backup of the original config
        backup_path = f"{config_path}.bak"
        with open(backup_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"Created backup of original config at {backup_path}")

        # Write the updated config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"Updated {config_path} with {len(new_regions)} new regions")
        print(f"Total regions in config: {len(config['regions'])}")

    except Exception as e:
        print(f"Error writing to {config_path}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
