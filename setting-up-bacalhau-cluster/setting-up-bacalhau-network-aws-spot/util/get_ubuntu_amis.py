#!/usr/bin/env python3
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


def get_latest_ubuntu_ami(region):
    """
    Get the latest Ubuntu 22.04 LTS AMI ID in a region
    """
    try:
        client = boto3.client("ec2", region_name=region)
        response = client.describe_images(
            Owners=["099720109477"],  # Canonical's AWS account ID
            Filters=[
                {
                    "Name": "name",
                    "Values": [
                        "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
                    ],
                },
                {"Name": "architecture", "Values": ["x86_64"]},
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
            print(f"Warning: No Ubuntu 22.04 LTS AMIs found in region {region}")
            return None
        return images[0]["ImageId"]
    except Exception as e:
        print(f"Error getting AMI for region {region}: {str(e)}")
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

    # Loop through each region and get the AMI ID
    print(f"Getting Ubuntu AMIs for {len(regions)} regions...")
    for region in regions:
        ami_id = get_latest_ubuntu_ami(region)
        if ami_id:
            UBUNTU_AMIS[region] = ami_id
            print(f"Found AMI {ami_id} for region {region}")

    # Create the CSV file
    csv_path = os.path.join(parent_dir, "ubuntu_amis.csv")
    with open(csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)

        # Write header with additional information if available
        if region_details:
            writer.writerow(
                [
                    "Region",
                    "AMI ID",
                    "Instance Type",
                    "vCPUs",
                    "Memory (GiB)",
                    "Spot Price ($/hr)",
                ]
            )

            # Write data with instance details
            for region, ami_id in UBUNTU_AMIS.items():
                details = region_details.get(region, {})
                instance = (
                    details.get("cheapest_instance", {})
                    if details.get("available", False)
                    else {}
                )

                if instance:
                    writer.writerow(
                        [
                            region,
                            ami_id,
                            instance.get("instance_type", ""),
                            instance.get("vcpus", ""),
                            instance.get("memory_gib", ""),
                            f"${instance.get('spot_price', 0):.4f}",
                        ]
                    )
                else:
                    writer.writerow([region, ami_id, "", "", "", ""])
        else:
            # Simple format if no instance details are available
            writer.writerow(["Region", "AMI ID"])
            for region, ami_id in UBUNTU_AMIS.items():
                writer.writerow([region, ami_id])

    print(f"Ubuntu AMIs CSV saved at: {csv_path}")
    print(f"Found AMIs for {len(UBUNTU_AMIS)} out of {len(regions)} regions")


if __name__ == "__main__":
    main()
