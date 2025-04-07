#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "botocore",
# ]
# ///

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

# Minimum requirements for running Docker and one small Python container
# These are minimal requirements - Docker needs about 2GB and a small Python container ~512MB
MIN_VCPU = 2
MIN_MEMORY_GIB = 2

# Instance families that are good candidates for small workloads
PREFERRED_INSTANCE_FAMILIES = [
    "t3",
    "t3a",
    "t4g",  # Burstable instances - good for intermittent workloads
    "t2",  # Older burstable instances
    "a1",  # ARM-based instances - can be cheaper
    "m6g",
    "m5",
    "m5a",  # General purpose instances
]


def check_region_spot_availability(region):
    """
    Check if a region has spot instances available that meet our requirements
    """
    try:
        # Create EC2 client for the region
        ec2_client = boto3.client("ec2", region_name=region)

        # Get available instance types in the region
        response = ec2_client.describe_instance_types()
        instance_types = response["InstanceTypes"]

        # Filter for instance types that meet our minimum requirements
        suitable_instances = []
        for instance in instance_types:
            instance_type = instance.get("InstanceType", "")

            # Check if instance meets minimum requirements
            if (
                instance.get("VCpuInfo", {}).get("DefaultVCpus", 0) >= MIN_VCPU
                and instance.get("MemoryInfo", {}).get("SizeInMiB", 0) / 1024
                >= MIN_MEMORY_GIB
            ):
                # Calculate a "size score" - lower is better (smaller instance)
                vcpus = instance.get("VCpuInfo", {}).get("DefaultVCpus", 0)
                memory_gib = instance.get("MemoryInfo", {}).get("SizeInMiB", 0) / 1024
                size_score = vcpus * 10 + memory_gib

                # Check if it's in our preferred families
                is_preferred = any(
                    instance_type.startswith(family)
                    for family in PREFERRED_INSTANCE_FAMILIES
                )

                suitable_instances.append(
                    {
                        "instance_type": instance_type,
                        "vcpus": vcpus,
                        "memory_gib": memory_gib,
                        "size_score": size_score,
                        "is_preferred": is_preferred,
                    }
                )

        if not suitable_instances:
            return {"region": region, "available": False}

        # Sort by preference first, then by size score (smallest first)
        suitable_instances.sort(
            key=lambda x: (0 if x["is_preferred"] else 1, x["size_score"])
        )

        # Check spot pricing and availability for suitable instances
        available_instances = []
        for instance_info in suitable_instances[
            :10
        ]:  # Check first 10 suitable instances
            instance_type = instance_info["instance_type"]
            try:
                # Check spot price history
                spot_response = ec2_client.describe_spot_price_history(
                    InstanceTypes=[instance_type],
                    ProductDescriptions=["Linux/UNIX"],
                    MaxResults=1,
                )

                # If we got a price, the instance type is available for spot
                if spot_response.get("SpotPriceHistory"):
                    spot_price = float(
                        spot_response["SpotPriceHistory"][0]["SpotPrice"]
                    )
                    print(
                        f"Region {region} has spot availability for {instance_type} - "
                        f"{instance_info['vcpus']} vCPUs, {instance_info['memory_gib']:.1f} GiB RAM, "
                        f"${spot_price:.4f}/hr"
                    )

                    available_instances.append(
                        {
                            "instance_type": instance_type,
                            "vcpus": instance_info["vcpus"],
                            "memory_gib": round(instance_info["memory_gib"], 1),
                            "spot_price": spot_price,
                        }
                    )
            except Exception as e:
                continue

        if available_instances:
            # Sort available instances by price
            available_instances.sort(key=lambda x: x["spot_price"])
            return {
                "region": region,
                "available": True,
                "instances": available_instances,
                "cheapest_instance": available_instances[0],
            }
        else:
            return {"region": region, "available": False}
    except Exception as e:
        print(f"Error checking region {region}: {str(e)}")
        return {"region": region, "available": False, "error": str(e)}


def get_all_aws_regions():
    """
    Get a list of all AWS regions
    """
    ec2 = boto3.client("ec2", region_name="us-east-1")
    regions = [region["RegionName"] for region in ec2.describe_regions()["Regions"]]
    return regions


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Find AWS regions with suitable spot instances for Docker and containers"
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all available regions, not just the top 5",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Maximum number of parallel workers (default: 10)",
    )
    args = parser.parse_args()

    # Get all AWS regions
    all_regions = get_all_aws_regions()
    print(f"Checking {len(all_regions)} AWS regions for spot availability...")
    print(
        f"Looking for instances with at least {MIN_VCPU} vCPUs and {MIN_MEMORY_GIB} GiB RAM"
    )

    # Results will store detailed information about each region
    results = []

    # Check each region in parallel
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_region = {
            executor.submit(check_region_spot_availability, region): region
            for region in all_regions
        }

        for future in as_completed(future_to_region):
            region_result = future.result()
            results.append(region_result)

    # Filter for available regions
    available_regions = [r for r in results if r.get("available", False)]

    # Sort available regions by cheapest instance price
    available_regions.sort(key=lambda x: x["cheapest_instance"]["spot_price"])

    # Create a list of just the region names for backward compatibility
    region_names = [r["region"] for r in available_regions]

    # Save the results to JSON
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    json_path = os.path.join(parent_dir, "available_regions.json")

    output_data = {
        "available_regions": region_names,
        "region_details": {r["region"]: r for r in available_regions},
        "all_regions_checked": len(all_regions),
        "available_regions_count": len(available_regions),
        "min_requirements": {"vcpu": MIN_VCPU, "memory_gib": MIN_MEMORY_GIB},
        "timestamp": import_time.strftime(
            "%Y-%m-%d %H:%M:%S UTC", import_time.gmtime()
        ),
    }

    with open(json_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(
        f"\nFound {len(available_regions)} regions with suitable spot instances out of {len(all_regions)} total regions"
    )
    print(f"Available regions saved to: {json_path}")

    # For backward compatibility, also create the Python module
    output_path = os.path.join(parent_dir, "available_regions.py")
    with open(output_path, "w") as f:
        f.write(
            "# AWS regions with spot instances suitable for Docker and containers\n"
        )
        f.write("# This file is auto-generated by get_available_regions.py\n\n")
        f.write("AVAILABLE_REGIONS = [\n")
        for region in sorted(region_names):
            f.write(f'    "{region}",\n')
        f.write("]\n\n")

        # Add detailed information about each region
        f.write(
            "# Detailed information about each region's smallest suitable instance\n"
        )
        f.write("REGION_DETAILS = {\n")
        for region_data in available_regions:
            region = region_data["region"]
            instance = region_data["cheapest_instance"]
            f.write(f'    "{region}": {{\n')
            f.write(f'        "instance_type": "{instance["instance_type"]}",\n')
            f.write(f'        "vcpus": {instance["vcpus"]},\n')
            f.write(f'        "memory_gib": {instance["memory_gib"]},\n')
            f.write(f'        "spot_price": {instance["spot_price"]:.6f},\n')
            f.write(f"    }},\n")
        f.write("}\n")

    print(f"Python module also saved to: {output_path}")

    # Print a summary of the available regions
    if args.show_all:
        print(
            f"\nAll {len(available_regions)} available regions for running Docker with a small Python container:"
        )
        for i, region_data in enumerate(available_regions, 1):
            region = region_data["region"]
            instance = region_data["cheapest_instance"]
            print(
                f"{i}. {region} - {instance['instance_type']} - "
                f"{instance['vcpus']} vCPUs, {instance['memory_gib']} GiB RAM, "
                f"${instance['spot_price']:.4f}/hr"
            )
    else:
        # Just show the top 5 by default
        display_count = min(5, len(available_regions))
        print(
            f"\nTop {display_count} cheapest regions for running Docker with a small Python container:"
        )
        print(f"(Use --show-all to see all {len(available_regions)} available regions)")
        for i, region_data in enumerate(available_regions[:display_count], 1):
            region = region_data["region"]
            instance = region_data["cheapest_instance"]
            print(
                f"{i}. {region} - {instance['instance_type']} - "
                f"{instance['vcpus']} vCPUs, {instance['memory_gib']} GiB RAM, "
                f"${instance['spot_price']:.4f}/hr"
            )


if __name__ == "__main__":
    import time as import_time

    main()
