#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
# ]
# ///

import csv
import os

import boto3

# List of AWS regions for AMIs to be fetched
regions = [
    "eu-central-1",
    "us-west-2",
    "us-east-1",
    "eu-west-1",
    "eu-west-2",
    "ap-southeast-1",
    "sa-east-1",
    "eu-central-1",
    "ap-northeast-1",
    "ap-southeast-2",
    "ca-central-1",
]
UBUNTU_AMIS = {}


# Function to get the latest Ubuntu 24.04 LTS AMI ID and architecture in a region
def get_latest_ubuntu_ami(region, architecture):
    client = boto3.client("ec2", region_name=region)
    response = client.describe_images(
        Owners=["099720109477"],  # Canonical's AWS account ID
        Filters=[
            {
                "Name": "name",
                "Values": ["*ubuntu*24*04*"],
            },
            {"Name": "architecture", "Values": [architecture]},
            {"Name": "root-device-type", "Values": ["ebs"]},
            {"Name": "virtualization-type", "Values": ["hvm"]},
        ],
        MaxResults=1000,  # Ensure we get a sufficient number of results
    )
    # Sort images by creation date
    images = sorted(response["Images"], key=lambda x: x["CreationDate"], reverse=True)
    if images:
        return images[0]["ImageId"], architecture
    else:
        return None, architecture

print("Fetching Ubuntu AMIs...")
# Loop through each region and get the AMI ID for arm64 and x86_64 architectures
for region in regions:
    for architecture in ['arm64', 'x86_64']:
        UBUNTU_AMIS[(region, architecture)] = get_latest_ubuntu_ami(region, architecture)

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
csv_path = os.path.join(parent_dir, "ubuntu_amis.csv")

with open(csv_path, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Region", "Architecture", "AMI ID"])  # Write header
    for (region, architecture), (ami_id, arch) in UBUNTU_AMIS.items():
        writer.writerow([region, arch, ami_id])

print(f"Ubuntu AMIs CSV saved at: {csv_path}")
