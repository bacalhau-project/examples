#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
# "duckdb",
# "requests",
# "natsort",
# "google-cloud-storage",
# "google-cloud-bigquery",
# "google-cloud-resource-manager",
# "google-cloud-iam",
# "google-cloud-service-usage",
# "google-auth",
# "pyyaml",
# "google-api-core",
# ]
# ///

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

import yaml
from google.api_core import exceptions
from google.cloud import bigquery, resourcemanager, service_usage_v1
from google.oauth2 import service_account

DEFAULT_CONFIG = {
    "project": {
        "id": "your-project-id",
        "region": "US",
        "create_if_missing": True,
    },
    "credentials": {
        "path": "credentials.json",
    },
    "bigquery": {
        "dataset_name": "log_analytics",
        "table_name": "log_results",
        "location": "US",
    },
}

REQUIRED_APIS = [
    "bigquery.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
]


def prompt_yes_no(question, default="yes"):
    """Ask a yes/no question and return the answer."""
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError(f"Invalid default answer: '{default}'")

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")


def generate_project_id(base_id: str) -> str:
    """Generate a unique project ID with timestamp suffix."""
    timestamp = datetime.now().strftime("%y%m%d%H%M")
    # Remove any existing timestamp suffix if present
    base_id = base_id.split("-20")[0]  # Remove any existing timestamp

    # Ensure the total length stays under 30 characters
    # Format: base-id + "-" + timestamp = max 30 chars
    max_base_length = 19  # 30 - 10 (timestamp) - 1 (hyphen)
    if len(base_id) > max_base_length:
        base_id = base_id[:max_base_length]

    return f"{base_id}-{timestamp}"


def create_project(project_id):
    """Create a new GCP project."""
    try:
        # Create project without credentials
        client = resourcemanager.ProjectsClient()

        # Add timestamp to project ID only if it doesn't already have one
        if not any(c.isdigit() for c in project_id):
            project_id = generate_project_id(project_id)

        # Create project
        project = resourcemanager.Project()
        project.project_id = project_id
        project.display_name = "Bacalhau BigQuery"

        print(f"\nCreating project {project_id}...")
        operation = client.create_project(request={"project": project})
        result = operation.result()  # Wait for operation to complete

        # Wait for project to be fully created and ready
        print("Waiting for project to be ready...")
        time.sleep(30)  # Give time for project to propagate

        print(f"Project {project_id} created successfully!")
        return project_id
    except Exception as e:
        print(f"Failed to create project: {e}")
        return None


def check_api_enabled(project_id, api_name):
    """Check if a specific API is enabled for the project."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "gcloud",
                "services",
                "list",
                "--project",
                project_id,
                "--filter",
                f"config.name={api_name}",
                "--format",
                "value(state)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return "ENABLED" in result.stdout.upper()
    except subprocess.CalledProcessError:
        return False


def enable_api_with_gcloud(project_id, api_name):
    """Enable an API using gcloud command."""
    try:
        print(f"Enabling {api_name}...")
        subprocess.run(
            ["gcloud", "services", "enable", api_name, f"--project={project_id}"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to enable {api_name}: {e.stderr}")
        return False


def enable_project_apis(project_id, credentials):
    """Enable required APIs for the project using gcloud."""
    try:
        # Check and enable Service Usage API first
        if not check_api_enabled(project_id, "serviceusage.googleapis.com"):
            if not enable_api_with_gcloud(project_id, "serviceusage.googleapis.com"):
                print(
                    "\nFailed to enable Service Usage API. Please ensure you have the right permissions."
                )
                print("Try running: gcloud auth login")
                sys.exit(1)

        # Enable other required APIs using gcloud
        for api in REQUIRED_APIS:
            if not check_api_enabled(project_id, api):
                if not enable_api_with_gcloud(project_id, api):
                    return False
            else:
                print(f"API {api} is already enabled.")

        print("All required APIs are enabled")
        return True
    except Exception as e:
        print(f"Failed to enable APIs: {e}")
        return False


def print_credentials_instructions(project_id: str):
    """Print instructions for creating service account and credentials using gcloud CLI."""
    print("\nTo create service account and credentials, run these commands:")
    print("\n1. Create service account:")
    print("gcloud iam service-accounts create bacalhau-bigquery \\")
    print("    --display-name='Bacalhau BigQuery Service Account' \\")
    print(f"    --project={project_id}")

    print("\n2. Grant necessary roles:")
    print(f"gcloud projects add-iam-policy-binding {project_id} \\")
    print(
        f"    --member='serviceAccount:bacalhau-bigquery@{project_id}.iam.gserviceaccount.com' \\"
    )
    print("    --role='roles/bigquery.dataEditor'")
    print(f"gcloud projects add-iam-policy-binding {project_id} \\")
    print(
        f"    --member='serviceAccount:bacalhau-bigquery@{project_id}.iam.gserviceaccount.com' \\"
    )
    print("    --role='roles/bigquery.jobUser'")

    print("\n3. Download service account key:")
    print("gcloud iam service-accounts keys create credentials.json \\")
    print(
        f"    --iam-account=bacalhau-bigquery@{project_id}.iam.gserviceaccount.com \\"
    )
    print(f"    --project={project_id}")

    print("\nAfter running these commands, run this script again to continue setup.")


def interactive_setup():
    """Guide the user through the setup process."""
    print("\n=== Bacalhau BigQuery Setup ===\n")

    # Check if config exists
    if os.path.exists("config.yaml"):
        if not prompt_yes_no("config.yaml already exists. Do you want to reconfigure?"):
            return load_or_create_config("config.yaml")

    config = DEFAULT_CONFIG.copy()

    # Project configuration
    print("\n1. Project Configuration")
    print("-----------------------")
    project_id = input(
        "Enter your Google Cloud project ID (or press Enter to create new): "
    ).strip()

    if not project_id:
        # Generate a project ID with timestamp
        base_id = "bq"  # Shorter base name to allow for timestamp
        default_id = generate_project_id(base_id)
        project_id = input(f"Enter new project ID (default: {default_id}): ").strip()
        project_id = project_id if project_id else default_id

        # Create the project
        new_project_id = create_project(project_id)
        if not new_project_id:
            print("\nPlease create the project manually using:")
            print(f"gcloud projects create {project_id}")
            sys.exit(1)

        config["project"]["id"] = new_project_id
        config["project"]["create_if_missing"] = False  # Project is already created

        # Save configuration immediately after project creation
        with open("config.yaml", "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        print("\nConfiguration saved to config.yaml with project ID:", new_project_id)

        # Print instructions for creating service account
        print_credentials_instructions(new_project_id)
        sys.exit(0)
    else:
        config["project"]["id"] = project_id
        config["project"]["create_if_missing"] = prompt_yes_no(
            "Create project if it doesn't exist?"
        )

    # Credentials setup
    print("\n2. Credentials Setup")
    print("------------------")
    while True:
        creds_path = input(
            "\nEnter the path to your credentials file (default: credentials.json): "
        ).strip()
        if not creds_path:
            creds_path = "credentials.json"

        if os.path.exists(creds_path):
            config["credentials"]["path"] = creds_path
            break
        else:
            print(f"Error: File not found at {creds_path}")
            print_credentials_instructions(project_id)
            sys.exit(1)

    # BigQuery configuration
    print("\n3. BigQuery Configuration")
    print("----------------------")
    dataset = input("Enter dataset name (default: log_analytics): ").strip()
    if dataset:
        config["bigquery"]["dataset_name"] = dataset

    table = input("Enter table name (default: log_results): ").strip()
    if table:
        config["bigquery"]["table_name"] = table

    # Save final configuration
    with open("config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print("\nConfiguration saved to config.yaml")
    return config


def load_or_create_config(config_path):
    """Load configuration from YAML file or create if doesn't exist."""
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    # If no config exists, run interactive setup
    return interactive_setup()


def validate_config(config):
    """Validate the configuration has all required fields."""
    required_fields = [
        ("project.id", lambda c: c.get("project", {}).get("id")),
        ("credentials.path", lambda c: c.get("credentials", {}).get("path")),
    ]

    for field, getter in required_fields:
        if not getter(config) or getter(config) == DEFAULT_CONFIG["project"]["id"]:
            print(f"Missing or invalid required field: {field}")
            if prompt_yes_no("Would you like to run the interactive setup?"):
                return interactive_setup()
            sys.exit(1)


def setup_bigquery(config, credentials):
    """Setup BigQuery resources."""
    client = bigquery.Client(credentials=credentials, project=config["project"]["id"])

    # Create dataset if it doesn't exist
    dataset_id = f"{config['project']['id']}.{config['bigquery']['dataset_name']}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = config["bigquery"]["location"]

    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"Dataset {dataset_id} created or already exists.")
    except Exception as e:
        print(f"Error creating dataset: {e}")
        return False

    # Create table if it doesn't exist
    schema = [
        bigquery.SchemaField("projectID", "STRING"),
        bigquery.SchemaField("region", "STRING"),
        bigquery.SchemaField("nodeName", "STRING"),
        bigquery.SchemaField("syncTime", "STRING"),
        bigquery.SchemaField("remote_log_id", "STRING"),
        bigquery.SchemaField("timestamp", "STRING"),
        bigquery.SchemaField("version", "STRING"),
        bigquery.SchemaField("message", "STRING"),
    ]

    table_id = f"{dataset_id}.{config['bigquery']['table_name']}"
    table = bigquery.Table(table_id, schema=schema)
    try:
        table = client.create_table(table, exists_ok=True)
        print(f"Table {table_id} created or already exists.")
    except Exception as e:
        print(f"Error creating table: {e}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Setup BigQuery resources")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to configuration file"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run interactive setup"
    )
    args = parser.parse_args()

    print("\nSetting up BigQuery integration...")

    # Try to load existing config first
    config = None
    if os.path.exists(args.config):
        try:
            with open(args.config, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading config file: {e}")

    # If no config or interactive mode, run setup
    if config is None or args.interactive:
        config = interactive_setup()

    # Validate configuration
    validate_config(config)

    project_id = config["project"]["id"]

    # First, ensure project exists
    try:
        # Try to create client without credentials first
        client = resourcemanager.ProjectsClient()
        project = client.get_project(name=f"projects/{project_id}")
        print(f"Project {project_id} exists.")
    except exceptions.NotFound:
        print(f"\nProject {project_id} does not exist.")
        if config["project"].get("create_if_missing", False):
            new_project_id = create_project(project_id)
            if not new_project_id:
                sys.exit(1)
            # Update config with new project ID
            config["project"]["id"] = new_project_id
            project_id = new_project_id
            # Save updated config
            with open(args.config, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            print(f"Updated config.yaml with new project ID: {new_project_id}")
        else:
            if prompt_yes_no("Would you like to create the project now?"):
                new_project_id = create_project(project_id)
                if not new_project_id:
                    sys.exit(1)
                # Update config with new project ID
                config["project"]["id"] = new_project_id
                project_id = new_project_id
                # Save updated config
                with open(args.config, "w") as f:
                    yaml.dump(config, f, default_flow_style=False)
                print(f"Updated config.yaml with new project ID: {new_project_id}")
            else:
                sys.exit(1)
    except exceptions.PermissionDenied:
        print(f"\nUnable to verify project {project_id} - insufficient permissions.")
        print("Please run: gcloud auth login")
        print("Then try again.")
        sys.exit(1)

    # Now check for credentials
    creds_path = os.path.expanduser(config["credentials"]["path"])
    if not os.path.exists(creds_path):
        print(f"\nCredentials file not found at {creds_path}")
        # Ensure config is saved before showing instructions
        if not os.path.exists(args.config):
            with open(args.config, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            print(f"Created config.yaml with project ID: {project_id}")
        print_credentials_instructions(project_id)
        sys.exit(1)

    # Enable required APIs using gcloud credentials (not service account)
    print("\nEnabling required APIs using your gcloud credentials...")
    if not enable_project_apis(project_id, None):
        print(
            "\nFailed to enable APIs. Please ensure you have the right permissions and try again."
        )
        print("You may need to run: gcloud auth login")
        sys.exit(1)

    # Setup credentials for BigQuery operations
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    # Setup BigQuery resources
    if setup_bigquery(config, credentials):
        print("\nBigQuery setup completed successfully!")
        print(
            f"\nYou can now use the following project ID in your queries: {project_id}"
        )
    else:
        print("\nBigQuery setup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
