#!/usr/bin/env uv run -s
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "botocore",
# ]
# ///

import csv
import json
import os
import sys

import boto3

# Dictionary to store AMI IDs by region
UBUNTU_AMIS = {}


def get_latest_ubuntu_ami(region, architecture="x86_64"):
    """
    Get the latest Ubuntu 22.04 LTS AMI ID in a region for a specific architecture

    Args:
        region: AWS region
        architecture: CPU architecture ("x86_64" or "arm64")

    Returns:
        Dictionary with AMI ID and architecture, or None if not found
    """
    try:
        # Set the correct image name pattern based on architecture
        if architecture == "arm64":
            name_pattern = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-arm64-server-*"
        else:
            name_pattern = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"

        client = boto3.client("ec2", region_name=region)
        response = client.describe_images(
            Owners=["099720109477"],  # Canonical's AWS account ID
            Filters=[
                {
                    "Name": "name",
                    "Values": [name_pattern],
                },
                {"Name": "architecture", "Values": [architecture]},
                {"Name": "root-device-type", "Values": ["ebs"]},
                {"Name": "virtualization-type", "Values": ["hvm"]},
            ],
            MaxResults=1000,  # Ensure we get a sufficient number of results
        )
        # Sort images by creation date
        images = sorted(
            response["Images"], key=lambda x: x["CreationDate"], reverse=True
        )
        if not images:
            print(
                f"Warning: No Ubuntu 22.04 LTS AMIs found in region {region} for architecture {architecture}"
            )
            return None

        return {
            "image_id": images[0]["ImageId"],
            "architecture": architecture,
            "name": images[0]["Name"],
            "creation_date": images[0]["CreationDate"],
        }
    except Exception as e:
        print(
            f"Error getting AMI for region {region}, architecture {architecture}: {str(e)}"
        )
        return None


def main():
    # Get the parent directory
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    json_path = os.path.join(parent_dir, "available_regions.json")

    # Check if the JSON file exists
    if not os.path.exists(json_path):
        print(
            f"Error: {json_path} not found. Please run get_available_regions.py first."
        )
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
        print("Falling back to default regions...")
        regions = [
            "us-west-2",
            "us-east-1",
            "eu-central-1",
            "eu-west-1",
            "eu-west-2",
            "ap-southeast-1",
            "sa-east-1",
            "ap-northeast-1",
            "ap-southeast-2",
            "ca-central-1",
        ]

    # Dictionary to store AMI information by region and architecture
    ami_info = {}

    # Architectures to fetch
    architectures = ["x86_64", "arm64"]

    # Loop through each region and get AMIs for both architectures
    print(
        f"Getting Ubuntu AMIs for {len(regions)} regions across {len(architectures)} architectures..."
    )

    for region in regions:
        ami_info[region] = {}

        for arch in architectures:
            ami_data = get_latest_ubuntu_ami(region, arch)
            if ami_data:
                ami_info[region][arch] = ami_data
                print(f"Found AMI {ami_data['image_id']} ({arch}) for region {region}")

    # Create the CSV file with architecture information
    csv_path = os.path.join(parent_dir, "ubuntu_amis.csv")
    with open(csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)

        # Write header with architecture information
        if region_details:
            writer.writerow(
                [
                    "Region",
                    "Architecture",
                    "AMI ID",
                    "Instance Type",
                    "Instance Architecture",
                    "vCPUs",
                    "Memory (GiB)",
                    "Spot Price ($/hr)",
                ]
            )

            # Write data with instance details for each architecture
            for region in regions:
                for arch in architectures:
                    if region in ami_info and arch in ami_info[region]:
                        ami_data = ami_info[region][arch]
                        details = region_details.get(region, {})
                        instance = (
                            details.get("cheapest_instance", {})
                            if details.get("available", False)
                            else {}
                        )

                        # Determine if instance is likely ARM compatible
                        instance_type = instance.get("instance_type", "")
                        instance_arch = (
                            "arm64"
                            if any(
                                family in instance_type
                                for family in ["a1", "t4g", "c6g", "m6g", "r6g"]
                            )
                            else "x86_64"
                        )

                        # Only include this row if there's instance info
                        if instance:
                            writer.writerow(
                                [
                                    region,
                                    arch,
                                    ami_data["image_id"],
                                    instance_type,
                                    instance_arch,
                                    instance.get("vcpus", ""),
                                    instance.get("memory_gib", ""),
                                    f"${instance.get('spot_price', 0):.4f}",
                                ]
                            )
                        else:
                            writer.writerow(
                                [region, arch, ami_data["image_id"], "", "", "", "", ""]
                            )
        else:
            # Simple format if no instance details are available
            writer.writerow(["Region", "Architecture", "AMI ID"])
            for region in regions:
                for arch in architectures:
                    if region in ami_info and arch in ami_info[region]:
                        ami_data = ami_info[region][arch]
                        writer.writerow([region, arch, ami_data["image_id"]])

    # Also create a separate mapping file in JSON format for easier programmatic access
    json_ami_path = os.path.join(parent_dir, "ubuntu_amis.json")
    with open(json_ami_path, "w") as f:
        json.dump(ami_info, f, indent=2, default=str)

    # Count how many regions have AMIs for each architecture
    x86_regions = sum(1 for region in ami_info if "x86_64" in ami_info[region])
    arm_regions = sum(1 for region in ami_info if "arm64" in ami_info[region])

    print(f"Ubuntu AMIs CSV saved at: {csv_path}")
    print(f"Ubuntu AMIs JSON mapping saved at: {json_ami_path}")
    print(f"Found AMIs for {len(ami_info)} out of {len(regions)} regions")
    print(f"- x86_64 architecture: {x86_regions} regions")
    print(f"- arm64 architecture: {arm_regions} regions")


if __name__ == "__main__":
    main()
