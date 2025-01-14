#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
# ]
# ///

import json
import subprocess

# Define the VM series to check
VM_SERIES = ["B", "A", "D", "F"]


def get_vm_skus(region):
    # Run the Azure CLI command to get VM SKUs
    result = subprocess.run(
        [
            "az",
            "vm",
            "list-skus",
            "--location",
            region,
            "--resource-type",
            "virtualMachines",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Error fetching VM SKUs:", result.stderr)
        return []
    return json.loads(result.stdout)


def filter_vm_skus(skus, series):
    # Filter for VM sizes in the specified series
    filtered_skus = []
    for sku in skus:
        if any(sku["name"].startswith(f"Standard_{s}") for s in series):
            filtered_skus.append(sku)
    return filtered_skus


def main():
    # Define the region to check
    region = "eastus"

    # Get VM SKUs for the region
    skus = get_vm_skus(region)
    if not skus:
        print("No VM SKUs found.")
        return

    # Filter for VM sizes in the specified series
    filtered_skus = filter_vm_skus(skus, VM_SERIES)
    if not filtered_skus:
        print(f"No VM sizes in series {VM_SERIES} found in {region}.")
        return

    # Print the filtered VM sizes
    print(f"Available VM sizes in {region}:")
    for sku in filtered_skus:
        print(
            f"Name: {sku['name']}, Family: {sku['family']}, Locations: {sku['locationInfo'][0]['location']}"
        )


if __name__ == "__main__":
    main()
