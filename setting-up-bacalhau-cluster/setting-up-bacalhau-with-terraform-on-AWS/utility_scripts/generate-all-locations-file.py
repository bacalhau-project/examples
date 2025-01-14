#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
#     "boto3",
# ]
# ///

import json
from pathlib import Path

import boto3
import yaml


def get_all_regions():
    """Get all AWS regions."""
    ec2 = boto3.client("ec2")
    regions = [region["RegionName"] for region in ec2.describe_regions()["Regions"]]
    return sorted(regions)


def get_region_zones(region):
    """Get all availability zones for a given region."""
    ec2 = boto3.client("ec2", region_name=region)
    zones = [
        zone["ZoneName"]
        for zone in ec2.describe_availability_zones(
            Filters=[{"Name": "state", "Values": ["available"]}]
        )["AvailabilityZones"]
    ]
    return sorted(zones)


def get_latest_ubuntu_ami(region):
    """Get the latest Ubuntu 22.04 LTS AMI ID for a region."""
    ec2 = boto3.client("ec2", region_name=region)

    try:
        response = ec2.describe_images(
            Filters=[
                {
                    "Name": "name",
                    "Values": [
                        "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
                    ],
                },
                {"Name": "state", "Values": ["available"]},
                {"Name": "architecture", "Values": ["x86_64"]},
            ],
            Owners=["099720109477"],  # Canonical's AWS account ID
        )

        # Sort images by creation date
        images = sorted(
            response["Images"], key=lambda x: x["CreationDate"], reverse=True
        )
        if images:
            return images[0]["ImageId"]
    except Exception as e:
        print(f"Warning: Could not get AMI for region {region}: {str(e)}")

    return None


def generate_locations_file():
    """Generate a YAML file with all AWS zones as top-level entries."""
    locations = []

    for region in get_all_regions():
        try:
            zones = get_region_zones(region)
            ami_id = get_latest_ubuntu_ami(region)

            if ami_id:
                # Create a zone-based configuration for each zone
                for zone in zones:
                    zone_config = {
                        zone: {
                            "region": region,
                            "instance_type": "t3.medium",
                            "instance_ami": ami_id,
                            "node_count": 1,
                            "zone": zone,
                        }
                    }
                    locations.append(zone_config)
        except Exception as e:
            print(f"Warning: Could not process region {region}: {str(e)}")

    # Create the locations directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "locations"
    output_dir.mkdir(exist_ok=True)

    # Write YAML file
    yaml_path = output_dir / "all_locations.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(locations, f, default_flow_style=False)

    # Write JSON file (as an alternative format)
    json_path = output_dir / "all_locations.json"
    with open(json_path, "w") as f:
        json.dump(locations, f, indent=2)

    print("Generated files:")
    print(f"YAML: {yaml_path}")
    print(f"JSON: {json_path}")

    # Calculate total nodes
    total_nodes = sum(
        config[zone]["node_count"] for config in locations for zone in config
    )
    print(f"\nTotal zones: {len(locations)}")
    print(f"Total nodes: {total_nodes}")


if __name__ == "__main__":
    generate_locations_file()
