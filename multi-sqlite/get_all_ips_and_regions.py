# Azure query to get all IPs and regions from subscription where resource group name starts with "multisqlite-bacalhau"
# Output: IPs and regions to stdout
# Usage: python get_all_ips_and_regions.py

import os
import datetime
import requests
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient


def get_all_ips_and_regions():
    """Gets all IPs and regions from subscription where resource group name starts with "multisqlite-bacalhau".

    Returns:
      A list of tuples (IP, region).
    """

    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    resource_groups = get_resource_groups(subscription_id)

    ips_and_regions = []
    for resource_group in resource_groups:
        if resource_group.name.startswith("multisqlite-bacalhau"):
            for ip_address in get_ip_addresses(resource_group):
                ips_and_regions.append((ip_address, resource_group))

    return ips_and_regions


def get_resource_groups(subscription_id):
    """Gets all resource groups in subscription.

    Args:
      subscription_id: The Azure subscription ID.

    Returns:
      A list of resource groups.
    """
    # Acquire a credential object using CLI-based authentication.
    credential = AzureCliCredential()

    # Retrieve subscription ID from environment variable.
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]

    # Obtain the management object for resources.
    resource_client = ResourceManagementClient(credential, subscription_id)

    group_list = resource_client.resource_groups.list()

    return group_list


def get_ip_addresses(resource_group):
    """Gets all IP addresses in resource group.

    Args:
      resource_group: The Azure resource group name.

    Returns:
      A list of IP addresses.
    """

    # Acquire a credential object using CLI-based authentication.
    credential = AzureCliCredential()

    # Retrieve subscription ID from environment variable.
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]

    client = NetworkManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
    )

    ip_addresses = []
    response = client.public_ip_addresses.list_all()
    for item in response:
        ip_addresses.append(item.ip_address)

    return ip_addresses


def main():
    ips_and_regions = get_all_ips_and_regions()

    for ip_address, region in ips_and_regions:
        print("{} {} {}".format(ip_address, region, datetime.datetime.now()))


if __name__ == "__main__":
    main()
