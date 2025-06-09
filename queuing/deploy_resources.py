import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from subprocess import CalledProcessError, run

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from dotenv import load_dotenv, set_key

NUMBER_OF_CONCURRENT_JOBS = 10

PREFIX = "bac-queue-"

support_locations = [
    "westus",
    "centralus",
    "eastus2",
    "southcentralus",
    "westeurope",
    "northeurope",
    "uksouth",
    "eastasia",
    "southeastasia",
]


def run_command(command):
    try:
        result = run(command, check=True, capture_output=True, text=True)
        return result.stdout
    except CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)


def authenticate(subscription_id):
    try:
        credential = DefaultAzureCredential()
        client = ResourceManagementClient(credential, subscription_id)
        return client
    except Exception as e:
        print(f"Error during authentication: {e}")
        sys.exit(1)


def deploy_bicep_template(resource_group_name, template_file, parameters):
    try:
        command = [
            "az",
            "deployment",
            "group",
            "create",
            "--resource-group",
            resource_group_name,
            "--template-file",
            template_file,
            "--parameters",
        ] + [f"{k}={v['value']}" for k, v in parameters.items()]

        print(f"Running command: {' '.join(command)}")
        run(command, check=True)
        print("Deployment completed successfully")
    except CalledProcessError as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)


async def deploy_support_node(
    semaphore, resource_group_name, unique_id, loc, admin_username, ssh_key
):
    async with semaphore:
        deploy_bicep_template(
            resource_group_name,
            "support_nodes.bicep",
            {
                "uniqueId": {"value": unique_id},
                "location": {"value": loc},
                "adminUsername": {"value": admin_username},
                "sshKey": {"value": ssh_key},
            },
        )


async def deploy_support_nodes(resource_group_name, unique_id, admin_username, ssh_key):
    semaphore = asyncio.Semaphore(NUMBER_OF_CONCURRENT_JOBS)
    tasks = [
        deploy_support_node(
            semaphore, resource_group_name, unique_id, loc, admin_username, ssh_key
        )
        for loc in support_locations
    ]
    await asyncio.gather(*tasks)


def destroy_bicep_template(client, resource_group_name, wait=False):
    print(f"Deleting resource group: {resource_group_name}")
    delete_async_operation = client.resource_groups.begin_delete(resource_group_name)
    if wait:
        delete_async_operation.result()
        print("Resource group deletion completed successfully")
    else:
        print("Resource group deletion initiated successfully")


def list_resources_with_tag(client, unique_id):
    print(f"Listing resources with tag 'uniqueId={unique_id}'")
    resources = client.resources.list(
        filter=f"tagName eq 'uniqueId' and tagValue eq '{unique_id}'"
    )
    resource_ips = []
    for resource in resources:
        if resource.type == "Microsoft.Compute/virtualMachines" and resource.properties:
            print(
                f"Resource: {resource.name}, Type: {resource.type}, ID: {resource.id}"
            )
            network_profile = resource.properties.get("networkProfile")
            if network_profile:
                for nic in network_profile.get("networkInterfaces", []):
                    nic_id = nic.get("id")
                    if nic_id:
                        nic_details = client.resources.get_by_id(nic_id, "2021-02-01")
                        ip_configurations = nic_details.properties.get(
                            "ipConfigurations", []
                        )
                        for ip_configuration in ip_configurations:
                            ip_address = ip_configuration["properties"].get(
                                "privateIPAddress", None
                            )
                            if ip_address:
                                resource_ips.append(ip_address)
                                print(f"  IP Address: {ip_address}")
    return resource_ips


def get_subscription_id():
    load_dotenv()
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")

    if not subscription_id:
        print("Subscription ID not found in .env file.")
        print("Querying available subscriptions...")

        subscriptions_output = run_command(
            ["az", "account", "list", "--output", "json"]
        )
        subscriptions = json.loads(subscriptions_output)

        if not subscriptions:
            print("No subscriptions found. Please check your Azure CLI login.")
            sys.exit(1)

        print("Available subscriptions:")
        for idx, sub in enumerate(subscriptions):
            print(f"{idx + 1}: {sub['name']} (ID: {sub['id']})")

        selected_index = int(input("Select the subscription to use (number): ")) - 1
        subscription_id = subscriptions[selected_index]["id"]

        set_key(".env", "AZURE_SUBSCRIPTION_ID", subscription_id)

    return subscription_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy, list, or destroy Azure resources using Bicep templates."
    )
    parser.add_argument("--create", action="store_true", help="Create resources")
    parser.add_argument("--destroy", action="store_true", help="Destroy resources")
    parser.add_argument(
        "--list", action="store_true", help="List all resources with the unique tag"
    )
    args = parser.parse_args()

    if not (args.create or args.destroy or args.list):
        parser.print_help()
        exit(1)

    subscription_id = get_subscription_id()
    client = authenticate(subscription_id)

    unique_id = None
    if os.path.exists("UNIQUEID"):
        with open("UNIQUEID", "r") as f:
            unique_id = f.read().strip()

    if args.create and unique_id:
        print(
            "Warning: UNIQUEID file exists. Resources might already be created with this ID."
        )
        exit(1)

    if not unique_id:
        # Generate a timestamp-based unique ID with millisecond precision
        unique_id = datetime.now().strftime("%y%m%d%H%M%S%f")[:10]

    resource_group_name = f"{PREFIX}rg-{unique_id}"
    location = "eastus"

    ssh_key_path = os.path.expanduser("~/.ssh/id_ed25519.pub")
    with open(ssh_key_path, "r") as file:
        ssh_key = file.read().strip()

    admin_username = "azureuser"

    if args.create:
        # Create resource group
        print(f"Creating resource group: {resource_group_name} in location: {location}")
        client.resource_groups.create_or_update(
            resource_group_name, {"location": location, "tags": {"uniqueId": unique_id}}
        )
        print("Resource group created successfully")

        # Deploy control plane
        deploy_bicep_template(
            resource_group_name,
            "control_plane.bicep",
            {
                "uniqueId": {"value": unique_id},
                "location": {"value": location},
                "adminUsername": {"value": admin_username},
                "sshKey": {"value": ssh_key},
            },
        )

        # Deploy support nodes to different locations
        asyncio.run(
            deploy_support_nodes(
                resource_group_name, unique_id, admin_username, ssh_key
            )
        )

        # Write the unique ID to the UNIQUEID file
        with open("UNIQUEID", "w") as f:
            f.write(unique_id)

    if args.list:
        if unique_id:
            resource_ips = list_resources_with_tag(client, unique_id)
            for ip in resource_ips:
                print(f"Resource IP: {ip}")
        else:
            print(
                "Error: UNIQUEID file not found. Cannot list resources without a unique ID."
            )
        exit(0)

    if args.destroy:
        if unique_id:
            destroy_bicep_template(client, resource_group_name)
        else:
            print(
                "Error: UNIQUEID file not found. Cannot destroy resources without a unique ID."
            )
            exit(1)
        exit(0)
