#!/usr/bin/env uv run -s
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

    # Load AMI information if available
    ami_json_path = os.path.join(parent_dir, "ubuntu_amis.json")
    ami_data = {}

    if os.path.exists(ami_json_path):
        try:
            with open(ami_json_path, "r") as f:
                ami_data = json.load(f)
            print(f"Loaded AMI information from {ami_json_path}")
        except Exception as e:
            print(f"Error reading {ami_json_path}: {str(e)}")
            print("Proceeding without AMI architecture information")
    else:
        print(
            f"AMI information file {ami_json_path} not found. Please run get_ubuntu_amis.py first."
        )
        print("Proceeding without AMI architecture information")

    # Add new regions to the config
    for region in new_regions:
        # Get the recommended instance type from region_details if available
        recommended_instance = None
        if region in region_details and region_details[region].get("available", False):
            recommended_instance = (
                region_details[region].get("cheapest_instance", {}).get("instance_type")
            )

        # Set of widely compatible instance types by region for 2 vCPU/4GB minimum
        # These are the most reliable medium instances (2vCPU, 4GB RAM) across AWS regions
        region_instance_map = {
            # North America
            "us-east-1": ["t3.medium", "t2.medium"],
            "us-east-2": ["t3.medium", "t2.medium"],
            "us-west-1": ["t3.medium", "t2.medium"],
            "us-west-2": ["t3.medium", "t2.medium"],
            "ca-central-1": ["t3.medium", "t2.medium"],
            "ca-west-1": ["t3.medium"],
            
            # Europe
            "eu-west-1": ["t3.medium", "t2.medium"],
            "eu-west-2": ["t3.medium", "t2.medium"],
            "eu-west-3": ["t3.medium", "t2.medium"],
            "eu-central-1": ["t3.medium", "t2.medium"],
            "eu-central-2": ["t3.medium"],
            "eu-north-1": ["t3.medium"],
            "eu-south-1": ["t3.medium"],
            "eu-south-2": ["t3.medium"],
            
            # Asia Pacific
            "ap-northeast-1": ["t3.medium", "t2.medium"],
            "ap-northeast-2": ["t3.medium", "t2.medium"],
            "ap-northeast-3": ["t3.medium", "t2.medium"],
            "ap-southeast-1": ["t3.medium", "t2.medium"],
            "ap-southeast-2": ["t3.medium", "t2.medium"],
            "ap-southeast-3": ["t3.medium"],
            "ap-southeast-4": ["t3.medium"],
            "ap-southeast-5": ["t3.medium"],
            "ap-south-1": ["t3.medium", "t2.medium"],
            "ap-south-2": ["t3.medium"],
            "ap-east-1": ["t3.medium"],
            
            # Middle East and Africa
            "me-central-1": ["t3.medium"],
            "me-south-1": ["t3.medium"],
            "af-south-1": ["t3.medium"],
            
            # South America
            "sa-east-1": ["t3.medium", "t2.medium"],
        }
        
        # Default to t2.medium which is widely available with 2vCPU/4GB RAM
        machine_type = "t2.medium"
        
        # First preference: Check if we have a region-specific override
        if region in region_instance_map:
            machine_type = region_instance_map[region][0]
            
        # Second preference: Check if recommended instance meets our specs (2vCPU, 4GB+)
        # This helps find the most cost-effective option from available_regions.json
        if (recommended_instance and 
            region_details.get(region, {}).get("available", False)):
            
            instance_info = region_details[region].get("cheapest_instance", {})
            
            # Verify instance has 2+ vCPU and 4+ GB RAM
            if (instance_info.get("vcpus", 0) >= 2 and 
                instance_info.get("memory_gib", 0) >= 4):
                
                machine_type = recommended_instance
                print(f"Using recommended instance {machine_type} for {region} (confirmed: {instance_info.get('vcpus')} vCPU, {instance_info.get('memory_gib')} GB RAM)")
            else:
                print(f"Recommended instance {recommended_instance} rejected (insufficient resources). Using {machine_type} for {region}")
        else:
            print(f"Using default instance {machine_type} for {region}")

        # Determine instance architecture
        is_arm_instance = any(
            family in machine_type for family in ["a1", "t4g", "c6g", "m6g", "r6g"]
        )
        instance_arch = "arm64" if is_arm_instance else "x86_64"

        # Get the appropriate AMI ID for the architecture if available
        ami_id = "auto"
        if region in ami_data and instance_arch in ami_data[region]:
            ami_id = ami_data[region][instance_arch]["image_id"]
            print(
                f"Using {instance_arch} AMI {ami_id} for {region} with {machine_type} instance"
            )

        config["regions"].append(
            {
                region: {
                    "ami_id": ami_id,
                    "architecture": instance_arch,
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
