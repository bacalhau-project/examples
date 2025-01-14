#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-cloud-compute",
#     "pyyaml",
#     "google-auth",
# ]
# ///

import json
import os
import subprocess
import sys
from typing import Optional

import yaml
from google.api_core import exceptions
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import compute_v1


def ensure_gcp_auth() -> Optional[str]:
    """Ensure GCP authentication and return project ID."""
    try:
        # Try to get credentials and project ID
        credentials, project_id = default()
        return project_id
    except DefaultCredentialsError:
        print(
            "GCP credentials not found. Please authenticate using one of these methods:"
        )
        print("1. Run: gcloud auth application-default login")
        print("2. Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
        sys.exit(1)


def get_project_id() -> str:
    """Get the GCP project ID."""
    # First try environment variable
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project_id:
        return project_id

    # Then try gcloud config
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True,
        )
        project_id = result.stdout.strip()
        if project_id and project_id != "(unset)":
            return project_id
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Finally, try to get it from application default credentials
    project_id = ensure_gcp_auth()
    if project_id:
        return project_id

    print("Error: Could not determine GCP project ID. Please either:")
    print("1. Set GOOGLE_CLOUD_PROJECT environment variable")
    print("2. Run: gcloud config set project YOUR_PROJECT_ID")
    print("3. Use application default credentials with a project")
    sys.exit(1)


def check_zone_access(
    client: compute_v1.ZonesClient, project_id: str, zone_name: str
) -> bool:
    """Check if we have access to a specific zone."""
    try:
        request = compute_v1.GetZoneRequest(project=project_id, zone=zone_name)
        zone = client.get(request=request)
        # Check if the zone is actually available for use
        return zone.status == "UP" and "DEPRECATED" not in zone.deprecated
    except exceptions.PermissionDenied:
        print(f"⚠️  No permission to access zone {zone_name}")
        return False
    except exceptions.Forbidden:
        print(f"⚠️  Access forbidden to zone {zone_name}")
        return False
    except Exception as e:
        print(f"⚠️  Error checking zone {zone_name}: {str(e)}")
        return False


def get_all_zones(project_id: str):
    """Query GCP to get all available zones."""
    client = compute_v1.ZonesClient()

    try:
        zones = []
        request = compute_v1.ListZonesRequest(project=project_id)

        print("Fetching available zones...")
        for zone in client.list(request=request):
            # Only include UP zones that aren't deprecated
            if zone.status == "UP" and not zone.deprecated:
                region = zone.name.rsplit("-", 1)[0]
                zones.append(
                    {
                        "region": region,
                        "zone": zone.name,
                    }
                )
                print(f"✓ Found zone: {zone.name}")

        if not zones:
            print("\nNo available zones found. This could mean:")
            print("1. You don't have the required permissions")
            print("2. The Compute Engine API isn't enabled")
            print("3. Your project isn't properly set up for Compute Engine")
            print("\nTry running: gcloud services enable compute.googleapis.com")
            sys.exit(1)

        return zones
    except Exception as e:
        print(f"Error fetching zones: {str(e)}")
        print(
            "Please ensure you have the necessary permissions and the Compute Engine API is enabled."
        )
        print(
            "You can enable it by running: gcloud services enable compute.googleapis.com"
        )
        sys.exit(1)


def generate_locations_config(zones):
    """Generate the locations configuration."""
    locations = {}

    for zone_info in zones:
        zone = zone_info["zone"]

        # Use zone as the key instead of region
        zone_key = zone.replace(
            "-", "_"
        )  # Replace hyphens with underscores for valid keys
        locations[zone_key] = {
            "zone": zone,
            "machine_type": "e2-standard-4",
            "node_count": 1,
        }

    return locations


def main():
    # Ensure authentication and get project ID
    project_id = get_project_id()
    print(f"Using GCP project: {project_id}")

    # Get all zones
    print("Fetching zones from GCP...")
    zones = get_all_zones(project_id)

    if not zones:
        print(
            "No zones found. Please check your permissions and project configuration."
        )
        sys.exit(1)

    # Generate the locations configuration
    locations = generate_locations_config(zones)

    # Save as YAML
    with open("all_locations.yaml", "w") as yaml_file:
        yaml.dump({"locations": locations}, yaml_file, default_flow_style=False)

    # Save as JSON (for env.json format)
    with open("all_locations.json", "w") as json_file:
        json.dump({"locations": locations}, json_file, indent=2)

    print(f"\nGenerated configurations with {len(locations)} zones:")
    for zone_key in sorted(locations.keys()):
        print(f"  - {locations[zone_key]['zone']}")


if __name__ == "__main__":
    main()
