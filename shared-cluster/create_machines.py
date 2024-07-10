import argparse
import asyncio
import datetime
import json
import logging
import os
import random
import socket
import subprocess
import sys
import tempfile
import traceback
from collections import namedtuple
from subprocess import CalledProcessError, run

import asyncssh
from asyncssh import Error as AsyncSSHError
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.core.pipeline.policies import HttpLoggingPolicy

# Get the subscription ID from Azure CLI
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import VirtualMachine
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkSecurityGroup
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

messages = []

console = Console()
table_update_running = False
table_update_event = asyncio.Event()
resources_progress = {}

global \
    resource_group_name, \
    storage_account_name, \
    share_name, \
    vnet_name, \
    subnet_name, \
    nic_name, \
    requester_vm_name, \
    compute_vm_name, \
    vnet, \
    subnet


def generate_unique_id():
    timestamp = datetime.datetime.now().strftime("%y%m%d%H%M")
    random_digits = f"{random.randint(0, 99):02d}"
    return f"{timestamp}{random_digits}"


VM_IPS = namedtuple("VM_IPS", ["public_ip", "private_ip"])


class ResourceStatus:
    def __init__(self, resource_type, name):
        self.name = name
        self.resource_type = resource_type
        self.action = "Creating"
        self.status = "Initializing"
        self.public_ip = None
        self.private_ip = None
        self.finished_time = None

        self.start_time = datetime.datetime.now()

    def get_elapsed_time(self):
        if not self.finished_time:
            if self.status == "Completed":
                self.finished_time = datetime.datetime.now()
            else:
                return datetime.datetime.now() - self.start_time
        return self.finished_time - self.start_time


def format_elapsed_time(elapsed):
    if isinstance(elapsed, datetime.timedelta):
        seconds = elapsed.total_seconds()
    else:
        seconds = elapsed

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def make_progress_table():
    table = Table(show_header=True, header_style="bold magenta", show_lines=False)
    table.overflow = "ellipsis"
    table.add_column("Name", width=25, style="cyan", no_wrap=True)
    table.add_column("Type", width=15, style="cyan", no_wrap=True)
    table.add_column("Action", width=10, style="cyan", no_wrap=True)
    table.add_column("Status", width=10, style="yellow", no_wrap=True)
    table.add_column(
        "Elapsed", width=10, justify="right", style="magenta", no_wrap=True
    )
    table.add_column("Public IP", width=18, style="blue", no_wrap=True)
    table.add_column("Private IP", width=18, style="blue", no_wrap=True)
    table.add_column("Error", width=30, style="red", no_wrap=True)

    sorted_statuses = sorted(
        resources_progress.values(), key=lambda x: (x.resource_type, x.name)
    )
    for status in sorted_statuses:
        table.add_row(
            status.name,
            status.resource_type,
            status.action,
            status.status,
            format_elapsed_time(status.get_elapsed_time()),
            status.public_ip or "",
            status.private_ip or "",
            status.error_message or "",
        )
    return table


def create_layout(table, messages):
    layout = Layout()
    layout.split(
        Layout(table, name="table"),
        Layout(
            Panel(messages, title="Messages", border_style="green"),
            name="messages",
            size=10,
            ratio=1,
        ),
    )
    return layout


async def update_table(live):
    while True:
        table = make_progress_table()
        layout = create_layout(table, "\n".join(messages))
        live.update(layout)

        if table_update_event.is_set():
            break

        await asyncio.sleep(0.5)


def resources_progress_to_dict():
    return {
        status.name: {
            "resource_type": status.resource_type,
            "status": status.status,
            "elapsed_time": status.get_elapsed_time(),
            "action": status.action,
            "public_ip": status.public_ip,
            "private_ip": status.private_ip,
            "error_message": status.error_message,
        }
        for status in resources_progress.values()
    }


def update_progress(
    resource_name: str,
    resource_type: str,
    action: str,
    status: str,
    public_ip: str = "",
    private_ip: str = "",
    exception: str = "",
):
    global resources_progress

    rs = resources_progress.get(resource_name)
    if not rs:
        rs = ResourceStatus(resource_type, resource_name)

    rs.action = action
    rs.status = status
    rs.public_ip = public_ip
    rs.private_ip = private_ip
    rs.error_message = exception

    resources_progress[resource_name] = rs


# Global variables for Azure clients and subscription ID
global credential, resource_client, compute_client, network_client, storage_client

# List of required environment variables
required_vars = [
    "AZURE_SUBSCRIPTION_ID",
    # "AZURE_CLIENT_ID",
    # "AZURE_CLIENT_SECRET",
    # "AZURE_TENANT_ID",
]

# Set up logging
logging.basicConfig(
    filename="deploy.log",
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Configure Azure SDK logging
azure_logger = logging.getLogger("azure")
azure_logger.setLevel(logging.INFO)
azure_logger.propagate = False  # Prevent Azure logs from propagating to the root logger

# Delete existing log file if it exists
log_file_path = "deploy-azure.log"
if os.path.exists(log_file_path):
    os.remove(log_file_path)

azure_handler = logging.FileHandler(log_file_path)
azure_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
azure_logger.addHandler(azure_handler)

# Clear any existing handlers from the logger
for handler in azure_logger.handlers[:]:
    azure_logger.removeHandler(handler)

# Add the new handler
azure_logger.addHandler(azure_handler)

# Create a custom HttpLoggingPolicy
custom_logging_policy = HttpLoggingPolicy(base_url=None, logger=azure_logger)


def log_message(message, level="INFO"):
    logging.log(getattr(logging, level), message)
    messages.append(f"{level}: {message}")
    if len(messages) > 10:
        messages.pop(0)

    if level in ["WARNING", "ERROR"]:
        console.print(f"[bold {level.lower()}]{message}[/bold {level.lower()}]")
    # else:
    #     print(message)  # Add this line to print all messages


# Compute Variables
RESOURCE_GROUP_PREFIX = "bac-sci"
LOCATION = "swedencentral"
REQUESTER_NODE_NAME = "vm-requester"
COMPUTE_NODE_NAME = "vm-compute"
REQUESTER_NODE_SIZE = "Standard_D2s_v3"
COMPUTE_NODE_SIZE = "Standard_D8s_v3"
ADMIN_USERNAME = "azureuser"
IMAGE = "UbuntuLTS"

# Network Variables
VNET_NAME = "bac-sci-vnet"
SUBNET_NAME = "bac-sci-subnet"
NSG_NAME = "bac-sci-nsg"
PIP_NAME = "bac-sci-pip"
NIC_NAME = "bac-sci-nic"

# Storage Variables
STORAGE_ACCOUNT_NAME_PREFIX = "bacstg"
STORAGE_SHARE_NAME = "sharedfiles"
STORAGE_SKU = "Premium_LRS"

SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa.pub")


def run_command(command):
    try:
        result = run(command, check=True, capture_output=True, text=True)
        return result.stdout
    except CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)


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


def authenticate(subscription_id):
    try:
        credential = DefaultAzureCredential()
        client = ResourceManagementClient(credential, subscription_id)
        return client
    except Exception as e:
        print(f"Error during authentication: {e}")
        sys.exit(1)


def initialize_azure_clients():
    global resource_client, compute_client, network_client, storage_client, credential

    # Use AzureCliCredential to get credentials from Azure CLI
    credential = AzureCliCredential()
    client_kwargs = {
        "credential": credential,
        "subscription_id": get_subscription_id(),
        "logging_enable": True,
        "logging_policy": custom_logging_policy,
    }

    resource_client = ResourceManagementClient(**client_kwargs)
    compute_client = ComputeManagementClient(**client_kwargs)
    network_client = NetworkManagementClient(**client_kwargs)
    storage_client = StorageManagementClient(**client_kwargs)


def read_ssh_key():
    if not os.path.exists(SSH_KEY_PATH):
        log_message(f"SSH key file not found at {SSH_KEY_PATH}", "ERROR")
        sys.exit(1)

    with open(SSH_KEY_PATH, "r") as file:
        return file.read().strip()


def resource_group_exists(resource_group_name):
    try:
        return resource_client.resource_groups.check_existence(resource_group_name)
    except Exception as e:
        log_message(f"Error checking resource group existence: {str(e)}", "ERROR")
        return False


def create_resource_group(resource_group_name, location):
    resource_client.resource_groups.create_or_update(
        resource_group_name, {"location": location}
    )


async def get_or_create_storage_account(
    storage_account_name, resource_group_name, location, vnet_name, subnet_name
):
    try:
        log_message(f"Checking if storage account {storage_account_name} exists...")
        account = storage_client.storage_accounts.get_properties(
            resource_group_name, storage_account_name
        )
        log_message(f"Storage account {storage_account_name} found.")
    except ResourceNotFoundError:
        log_message(f"Storage account {storage_account_name} not found. Creating it...")
        poller = storage_client.storage_accounts.begin_create(
            resource_group_name,
            storage_account_name,
            {
                "location": location,
                "kind": "FileStorage",
                "sku": {"name": "Premium_LRS"},
                "enable_https_traffic_only": False,
                "access_tier": "Hot",
                "minimum_tls_version": "TLS1_2",
                "allow_blob_public_access": False,
                "network_rule_set": {
                    "default_action": "Allow",
                    "ip_rules": [],
                },
            },
        )
        account = poller.result()
        log_message(f"Storage account {storage_account_name} created successfully.")

        return account


def create_file_share(resource_group_name, storage_account_name, share_name):
    try:
        file_service = storage_client.file_shares
        file_service.create(
            resource_group_name,
            storage_account_name,
            share_name,
            {
                "share_quota": 102400,
            },
        )
        log_message(f"SMB file share {share_name} created successfully.")

        # Set share-level permissions
        storage_client.file_services.set_service_properties(
            resource_group_name,
            storage_account_name,
            {
                "protocol_settings": {
                    "smb": {
                        "versions": "SMB3.0,SMB3.1.1",
                    }
                }
            },
        )
    except ResourceExistsError:
        log_message(f"File share {share_name} already exists.")
    except Exception as e:
        log_message(f"Error creating file share: {str(e)}", "ERROR")
        raise


def create_virtual_network(resource_group_name, vnet_name, location):
    log_message(f"Creating virtual network {vnet_name}")
    poller = network_client.virtual_networks.begin_create_or_update(
        resource_group_name,
        vnet_name,
        {
            "location": location,
            "address_space": {"address_prefixes": ["10.0.0.0/16"]},
        },
    )
    return poller.result()


def create_subnet(resource_group_name, vnet_name, subnet_name):
    poller = network_client.subnets.begin_create_or_update(
        resource_group_name, vnet_name, subnet_name, {"address_prefix": "10.0.0.0/24"}
    )
    return poller.result()


def create_public_ip_address(resource_group_name, ip_name, location):
    poller = network_client.public_ip_addresses.begin_create_or_update(
        resource_group_name,
        ip_name,
        {
            "location": location,
            "sku": {"name": "Standard"},
            "public_ip_allocation_method": "Static",
            "public_ip_address_version": "IPV4",
        },
    )
    return poller.result()


def create_network_interface(
    resource_group_name,
    nic_name,
    location,
    subnet_id,
    ip_config_name,
    public_ip_address_id,
    nsg_id,
):
    poller = network_client.network_interfaces.begin_create_or_update(
        resource_group_name,
        nic_name,
        {
            "location": location,
            "ip_configurations": [
                {
                    "name": ip_config_name,
                    "subnet": {"id": subnet_id},
                    "public_ip_address": {"id": public_ip_address_id},
                }
            ],
            "network_security_group": {"id": nsg_id},  # Add this line
        },
    )
    return poller.result()


def create_nsg(resource_group_name, nsg_name, location) -> NetworkSecurityGroup:
    log_message(f"Creating Network Security Group {nsg_name}")
    poller = network_client.network_security_groups.begin_create_or_update(
        resource_group_name,
        nsg_name,
        {
            "location": location,
        },
    )
    return poller.result()


def create_nsg_rule(resource_group_name, nsg_name, rule_name, rule_params):
    update_progress(
        resource_name=nsg_name,
        resource_type="Network Security Rule - " + rule_name,
        action="Creating",
        status="Provisioning",
    )
    poller = network_client.security_rules.begin_create_or_update(
        resource_group_name, nsg_name, rule_name, rule_params
    )
    update_progress(
        resource_name=nsg_name,
        resource_type="Network Security Rule - " + rule_name,
        action="Creating",
        status="Completed",
    )
    return poller.result()


def create_vm(
    resource_group_name, vm_name, location, nic_id, vm_size
) -> VirtualMachine:
    ssh_key = read_ssh_key()

    image_references = [
        {
            "publisher": "Canonical",
            "offer": "0001-com-ubuntu-server-jammy",
            "sku": "22_04-lts-gen2",
            "version": "latest",
        },
        {
            "publisher": "Canonical",
            "offer": "UbuntuServer",
            "sku": "18.04-LTS",
            "version": "latest",
        },
    ]

    for image_ref in image_references:
        try:
            poller = compute_client.virtual_machines.begin_create_or_update(
                resource_group_name,
                vm_name,
                {
                    "location": location,
                    "storage_profile": {"image_reference": image_ref},
                    "hardware_profile": {"vm_size": vm_size},
                    "os_profile": {
                        "computer_name": vm_name,
                        "admin_username": ADMIN_USERNAME,
                        "linux_configuration": {
                            "disable_password_authentication": True,
                            "ssh": {
                                "public_keys": [
                                    {
                                        "path": f"/home/{ADMIN_USERNAME}/.ssh/authorized_keys",
                                        "key_data": ssh_key,
                                    }
                                ]
                            },
                        },
                    },
                    "network_profile": {"network_interfaces": [{"id": nic_id}]},
                },
            )
            return poller.result()
        except ResourceNotFoundError:
            log_message(f"Image {image_ref} not found, trying next option...")


async def setup_vm(vm_ip, storage_account_name, share_name, storage_account_key):
    setup_script = f"""#!/bin/bash
set -e
echo "Updating package lists..."
sudo apt update

echo "Installing CIFS utilities..."
sudo apt install -y cifs-utils

echo "Creating mount point..."
sudo mkdir -p /mnt/azureshare

echo "Creating credentials file..."
sudo bash -c 'echo "username={storage_account_name}" > /etc/smbcredentials/{storage_account_name}.cred'
sudo bash -c 'echo "password={storage_account_key}" >> /etc/smbcredentials/{storage_account_name}.cred'
sudo chmod 600 /etc/smbcredentials/{storage_account_name}.cred

echo "Mounting SMB share..."
sudo mount -t cifs //{storage_account_name}.file.core.windows.net/{share_name} /mnt/azureshare -o credentials=/etc/smbcredentials/{storage_account_name}.cred,dir_mode=0777,file_mode=0777,serverino,nosharesock,actimeo=30

echo "Setting permissions..."
sudo chmod 777 /mnt/azureshare

echo "Adding mount to fstab..."
echo "//{storage_account_name}.file.core.windows.net/{share_name} /mnt/azureshare cifs credentials=/etc/smbcredentials/{storage_account_name}.cred,dir_mode=0777,file_mode=0777,serverino,nosharesock,actimeo=30,_netdev 0 0" | sudo tee -a /etc/fstab

echo "Testing write access..."
echo "Test write access" | sudo tee /mnt/azureshare/test_write.txt

echo "Setup complete!"
"""

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
        temp_file.write(setup_script)
        temp_file_path = temp_file.name

    try:
        log_message(f"Copying setup script to VM {vm_ip}...")
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "scp",
                "-o",
                "StrictHostKeyChecking=no",
                temp_file_path,
                f"{ADMIN_USERNAME}@{vm_ip}:~/setup_script.sh",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        log_message(f"Setup script copied to VM {vm_ip}")

        log_message(f"Executing setup script on VM {vm_ip}...")
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                f"{ADMIN_USERNAME}@{vm_ip}",
                "sudo bash ~/setup_script.sh",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            log_message(f"VM {vm_ip}: {line}")

    except subprocess.CalledProcessError as e:
        log_message(f"Error during VM setup for {vm_ip}: {e}", "ERROR")
        log_message(f"Error output: {e.stderr}", "ERROR")
    finally:
        os.unlink(temp_file_path)

    log_message(f"VM setup completed for {vm_ip}")


async def destroy_cluster():
    log_message("Starting cluster destruction process")

    # Check if UNIQUEID file exists
    if not os.path.exists("UNIQUEID"):
        log_message("No UNIQUEID file found. Nothing to destroy.", "WARNING")
        update_progress(
            resource_name="Cluster",
            resource_type="Destruction",
            action="No cluster found",
            status="Completed",
        )
        return

    # Read UNIQUEID
    with open("UNIQUEID", "r") as f:
        unique_id = f.read().strip()

    if not unique_id:
        log_message("UNIQUEID file is empty. Nothing to destroy.", "WARNING")
        update_progress(
            resource_name="Cluster",
            resource_type="Destruction",
            action="Empty UNIQUEID",
            status="Completed",
        )
        return

    resource_group_name = f"{RESOURCE_GROUP_PREFIX}-{unique_id}"

    table = make_progress_table()

    try:
        with Live(table, refresh_per_second=4):
            update_progress(
                resource_name=resource_group_name,
                resource_type="Resource Group",
                action="Deleting",
                status="In Progress",
            )
            try:
                poller = resource_client.resource_groups.begin_delete(
                    resource_group_name
                )
                # Check if the deletion has started successfully
                if poller.done():
                    update_progress(
                        resource_name=resource_group_name,
                        resource_type="Resource Group",
                        action="Deleting",
                        status="In Progress",
                    )
                else:
                    update_progress(
                        resource_name=resource_group_name,
                        resource_type="Resource Group",
                        action="Deleting",
                        status="Failed",
                    )
            except Exception as e:
                error_message = f"Error deleting resource group: {str(e)}"
                log_message(error_message, "ERROR")
                update_progress(
                    resource_name=resource_group_name,
                    resource_type="Resource Group",
                    action="Deleting",
                    status="Failed",
                    exception=error_message,
                )

            # Add a small delay to ensure the table is updated before the Live context exits
            await asyncio.sleep(1)
    except Exception as e:
        log_message(f"Unexpected error during cluster destruction: {str(e)}", "ERROR")
    finally:
        log_message("Cluster destruction process completed")

    # Check if the resource group still exists
    if resource_group_exists(resource_group_name):
        log_message(
            f"Resource group '{resource_group_name}' still exists. Manual cleanup may be required.",
            "WARNING",
        )
    else:
        log_message(
            f"Resource group '{resource_group_name}' has been successfully deleted."
        )
        # Remove the UNIQUEID file
        os.remove("UNIQUEID")


def get_public_ip(vm_info):
    for ip in vm_info["ip_addresses"]:
        if "public" in ip:
            return ip["public"]
    return None


async def create_cluster(num_vms=2):
    global \
        resources_progress, \
        task_total, \
        task_name, \
        resource_group_name, \
        storage_account, \
        file_share, \
        vnet, \
        subnet, \
        nic, \
        requester_vm, \
        compute_vm

    log_message("Starting cluster creation process")

    unique_id = generate_unique_id()
    resource_group_name = f"{RESOURCE_GROUP_PREFIX}-{unique_id}"
    storage_account_name = f"{STORAGE_ACCOUNT_NAME_PREFIX}{unique_id.lower()}"
    nsg_name = f"{RESOURCE_GROUP_PREFIX}-nsg-{unique_id}"

    with open("UNIQUEID", "w") as f:
        f.write(unique_id)

    task_total = 4 + num_vms
    task_name = "Creating Cluster"

    try:
        # Resource Group
        log_message("Creating Resource Group")
        update_progress(
            resource_name=resource_group_name,
            resource_type="Resource Group",
            action="Creating",
            status="In Progress",
        )
        await asyncio.to_thread(create_resource_group, resource_group_name, LOCATION)
        update_progress(
            resource_name=resource_group_name,
            resource_type="Resource Group",
            action="Creating",
            status="Completed",
        )
        log_message("Resource Group created successfully")

        pre_vm_tasks = []

        async def create_storage_account_local():
            try:
                log_message("Creating Storage Account")
                update_progress(
                    resource_name=storage_account_name,
                    resource_type="Storage Account",
                    action="Creating",
                    status="In Progress",
                )
                storage_account = await get_or_create_storage_account(
                    storage_account_name,
                    resource_group_name,
                    LOCATION,
                    VNET_NAME,
                    SUBNET_NAME,
                )

                storage_client.storage_accounts.update(
                    resource_group_name,
                    storage_account_name,
                    {
                        "large_file_shares_state": "Enabled",
                        "enable_https_traffic_only": True,
                        "minimum_tls_version": "TLS1_2",
                        "allow_blob_public_access": False,
                        "network_rule_set": {
                            "default_action": "Allow",
                            "bypass": "AzureServices",
                        },
                    },
                )
                update_progress(
                    resource_name=storage_account_name,
                    resource_type="Storage Account",
                    action="Creating",
                    status="Completed",
                )
                log_message(
                    f"Storage Account created/found successfully in resource group {resource_group_name}"
                )
                return storage_account
            except Exception as e:
                log_message(f"Error creating Storage Account: {str(e)}", "ERROR")
                log_message(traceback.format_exc())
                update_progress(
                    resource_name=storage_account_name,
                    resource_type="Storage Account",
                    action="Creating",
                    status="Failed",
                    exception=str(e),
                )
                raise

        async def create_file_share_local():
            try:
                log_message("Creating File Share")
                update_progress(
                    resource_name=STORAGE_SHARE_NAME,
                    resource_type="File Share",
                    action="Creating",
                    status="In Progress",
                )

                max_retries = 10
                retry_delay = 10  # seconds
                for attempt in range(max_retries):
                    try:
                        await asyncio.to_thread(
                            create_file_share,
                            resource_group_name,
                            storage_account_name,
                            STORAGE_SHARE_NAME,
                        )
                        break
                    except ResourceNotFoundError:
                        log_message(
                            f"Storage account not ready, retrying... (Attempt {attempt + 1}/{max_retries})"
                        )
                        if attempt == max_retries - 1:
                            raise Exception("Storage account creation timed out")
                        await asyncio.sleep(retry_delay)

                update_progress(
                    resource_name=STORAGE_SHARE_NAME,
                    resource_type="File Share",
                    action="Creating",
                    status="Completed",
                )
                log_message("File Share created successfully")
            except Exception as e:
                log_message(f"Error creating File Share: {str(e)}", "ERROR")
                log_message(traceback.format_exc())
                update_progress(
                    resource_name=STORAGE_SHARE_NAME,
                    resource_type="File Share",
                    action="Creating",
                    status="Failed",
                    exception=str(e),
                )
                raise

        async def create_vnet_local():
            global vnet
            try:
                log_message("Creating Virtual Network")
                update_progress(
                    resource_name=VNET_NAME,
                    resource_type="Virtual Network",
                    action="Creating",
                    status="In Progress",
                )
                max_retries = 10
                retry_delay = 10  # seconds
                for attempt in range(max_retries):
                    try:
                        vnet = await asyncio.to_thread(
                            create_virtual_network,
                            resource_group_name,
                            VNET_NAME,
                            LOCATION,
                        )
                        if vnet.provisioning_state == "Succeeded":
                            break
                    except Exception as e:
                        log_message(
                            f"Error creating Virtual Network, retrying... (Attempt {attempt + 1}/{max_retries})"
                        )
                        if attempt == max_retries - 1:
                            raise Exception(
                                "Virtual Network creation failed after multiple attempts"
                            ) from e
                        await asyncio.sleep(retry_delay)

                update_progress(
                    resource_name=VNET_NAME,
                    resource_type="Virtual Network",
                    action="Creating",
                    status="Completed",
                )
                log_message("Virtual Network created successfully")
            except Exception as e:
                log_message(f"Error creating Virtual Network: {str(e)}", "ERROR")
                log_message(traceback.format_exc())
                update_progress(
                    resource_name=VNET_NAME,
                    resource_type="Virtual Network",
                    action="Creating",
                    status="Failed",
                    exception=str(e),
                )
                raise

        async def create_subnet_local():
            global subnet
            try:
                log_message("Creating Subnet")
                update_progress(
                    resource_name=VNET_NAME,
                    resource_type="Subnet",
                    action="Creating",
                    status="In Progress",
                )
                max_retries = 10
                retry_delay = 10  # seconds
                for attempt in range(max_retries):
                    try:
                        subnet = await asyncio.to_thread(
                            create_subnet, resource_group_name, VNET_NAME, SUBNET_NAME
                        )
                        if subnet.provisioning_state == "Succeeded":
                            break
                    except ResourceNotFoundError:
                        log_message(
                            f"Virtual Network not found, retrying... (Attempt {attempt + 1}/{max_retries})"
                        )
                        if attempt == max_retries - 1:
                            raise Exception(
                                "Subnet creation failed: Virtual Network not found after multiple attempts"
                            )
                        await asyncio.sleep(retry_delay)
                    except Exception as e:
                        log_message(
                            f"Error creating Subnet, retrying... (Attempt {attempt + 1}/{max_retries})"
                        )
                        if attempt == max_retries - 1:
                            raise Exception(
                                "Subnet creation failed after multiple attempts"
                            ) from e
                        await asyncio.sleep(retry_delay)

                update_progress(
                    resource_name=VNET_NAME,
                    resource_type="Subnet",
                    action="Creating",
                    status="Completed",
                )
                log_message(f"Subnet {subnet.name} created successfully")
            except Exception as e:
                log_message(f"Error creating Subnet: {str(e)}", "ERROR")
                log_message(traceback.format_exc())
                update_progress(
                    resource_name=VNET_NAME,
                    resource_type="Subnet",
                    action="Creating",
                    status="Failed",
                    exception=str(e),
                )
                raise

        async def create_nsg_local():
            try:
                log_message("Creating Network Security Group")
                update_progress(
                    resource_name=nsg_name,
                    resource_type="Network Security Group",
                    action="Creating",
                    status="In Progress",
                )
                nsg = await asyncio.to_thread(
                    create_nsg, resource_group_name, nsg_name, LOCATION
                )
                update_progress(
                    resource_name=nsg_name,
                    resource_type="Network Security Group",
                    action="Creating",
                    status="Completed",
                )
                log_message("Network Security Group created successfully")

                log_message("Creating NSG Rules")
                update_progress(
                    resource_name=nsg_name,
                    resource_type="NSG Rules",
                    action="Creating",
                    status="In Progress",
                )

                rule_configs = [
                    {
                        "name": "AllowSSH",
                        "params": {
                            "protocol": "Tcp",
                            "source_port_range": "*",
                            "destination_port_range": "22",
                            "source_address_prefix": "*",
                            "destination_address_prefix": "*",
                            "access": "Allow",
                            "priority": 1000,
                            "direction": "Inbound",
                        },
                    },
                    {
                        "name": "AllowBacalhau1234",
                        "params": {
                            "protocol": "Tcp",
                            "source_port_range": "*",
                            "destination_port_range": "1234",
                            "source_address_prefix": "*",
                            "destination_address_prefix": "*",
                            "access": "Allow",
                            "priority": 1001,
                            "direction": "Inbound",
                        },
                    },
                    {
                        "name": "AllowBacalhau1235",
                        "params": {
                            "protocol": "Tcp",
                            "source_port_range": "*",
                            "destination_port_range": "1235",
                            "source_address_prefix": "*",
                            "destination_address_prefix": "*",
                            "access": "Allow",
                            "priority": 1002,
                            "direction": "Inbound",
                        },
                    },
                    {
                        "name": "AllowSMB",
                        "params": {
                            "protocol": "Tcp",
                            "source_port_range": "*",
                            "destination_port_range": "445",
                            "source_address_prefix": "*",
                            "destination_address_prefix": "*",
                            "access": "Allow",
                            "priority": 1003,
                            "direction": "Inbound",
                        },
                    },
                ]

                rule_tasks = [
                    asyncio.create_task(
                        asyncio.to_thread(
                            create_nsg_rule,
                            resource_group_name,
                            nsg_name,
                            rule["name"],
                            rule["params"],
                        )
                    )
                    for rule in rule_configs
                ]

                await asyncio.gather(*rule_tasks)

                update_progress(
                    resource_name=nsg_name,
                    resource_type="NSG Rules",
                    action="Creating",
                    status="Completed",
                )
                log_message("NSG Rules created successfully")
                return nsg
            except Exception as e:
                log_message(f"Error creating NSG or NSG Rules: {str(e)}", "ERROR")
                log_message(traceback.format_exc())
                update_progress(
                    resource_name=nsg_name,
                    resource_type="Network Security Group",
                    action="Creating",
                    status="Failed",
                    exception=str(e),
                )
                raise

        pre_vm_tasks = [
            asyncio.create_task(create_vnet_local()),
            asyncio.create_task(create_subnet_local()),
            asyncio.create_task(create_nsg_local()),
        ]

        try:
            pre_vm_results = await asyncio.gather(*pre_vm_tasks)
            log_message("All pre-VM tasks completed successfully")
            nsg = next(
                result
                for result in pre_vm_results
                if isinstance(result, NetworkSecurityGroup)
            )
        except Exception as e:
            log_message(f"Error in pre-VM tasks: {str(e)}", "ERROR")
            log_message(traceback.format_exc())
            raise

        # Run create storage account separately, so we can use the vnet and subnet
        await create_storage_account_local()

        vm_infos = []
        vm_tasks = []
        for i in range(num_vms):
            vm_name = (
                f"{REQUESTER_NODE_NAME if i == 0 else COMPUTE_NODE_NAME}-{i+1:03d}"
            )
            is_orchestrator = i == 0
            vm_size = REQUESTER_NODE_SIZE if i == 0 else COMPUTE_NODE_SIZE
            vm_tasks.append(
                asyncio.create_task(
                    create_vm_with_dependencies(
                        resource_group_name,
                        vm_name,
                        LOCATION,
                        subnet.id,
                        vm_size,
                        nsg.id,
                        is_orchestrator,
                    )
                )
            )

        log_message(f"Creating {num_vms} VMs")
        log_message(f"All tasks: {task_total}")

        vm_tasks.append(asyncio.create_task(create_file_share_local()))

        try:
            vm_results = await asyncio.gather(*vm_tasks)
            log_message("VM creation tasks completed")

            # Filter out None results and the file share result
            vm_infos = [
                result
                for result in vm_results
                if result is not None and isinstance(result, dict)
            ]

            if not vm_infos:
                log_message("No VMs were created successfully", "WARNING")
            else:
                log_message(f"{len(vm_infos)} VM(s) created successfully")

                # Write VM information to MACHINES.json
                with open("MACHINES.json", "w") as f:
                    json.dump(vm_infos, f, indent=4)

                console.print("Cluster creation completed successfully!")
                console.print("Machine information written to MACHINES.json")

        except Exception as e:
            log_message(f"Error during VM creation: {str(e)}", "ERROR")
            log_message(traceback.format_exc())
            raise

        log_message("Finished all VM creation tasks.")
        log_message(f"Beginning provisioning tasks on {len(vm_infos)} VMs...")

        vm_ips = []
        for vm_info in vm_infos:
            public_ip = get_public_ip(vm_info)
            if public_ip:
                vm_ips.append(public_ip)
            else:
                log_message(f"No public IP found for {vm_info['name']}", "WARNING")

        if vm_ips:
            log_message("Starting VM setup process...")

            # Retrieve the storage account key
            storage_keys = storage_client.storage_accounts.list_keys(
                resource_group_name, storage_account_name
            )
            storage_account_key = storage_keys.keys[0].value

            setup_tasks = [
                asyncio.create_task(
                    setup_vm(
                        vm_ip,
                        storage_account_name,
                        STORAGE_SHARE_NAME,
                        storage_account_key,
                    )
                )
                for vm_ip in vm_ips
                if vm_ip is not None
            ]
            try:
                await asyncio.gather(*setup_tasks)
                log_message("All VM setups completed successfully")
            except Exception as e:
                log_message(f"Error during VM setup: {str(e)}", "ERROR")
                log_message(traceback.format_exc())
                raise

            with open("MACHINES.json", "w") as f:
                json.dump(vm_infos, f, indent=4)

            console.print("Cluster creation completed successfully!")
            console.print("Machine information written to MACHINES.json")
        else:
            log_message("No VMs were created successfully", "WARNING")

    except Exception as e:
        log_message(f"Error during cluster creation: {str(e)}", "ERROR")
        log_message(traceback.format_exc())
        for status in resources_progress.values():
            if status.status == "Creating":
                status.status = "Failed"
                status.detailed_status = str(e)
    finally:
        table_update_event.set()
        await asyncio.sleep(1)  # Give time for the final table update


async def wait_for_nic_provisioning(resource_group_name, nic_name):
    max_retries = 30
    retry_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            nic = network_client.network_interfaces.get(resource_group_name, nic_name)
            if nic.provisioning_state == "Succeeded":
                log_message(f"NIC {nic_name} provisioning completed successfully")
                return True
            else:
                log_message(
                    f"NIC {nic_name} provisioning state: {nic.provisioning_state}"
                )
        except Exception as e:
            log_message(f"Error checking NIC {nic_name} provisioning state: {str(e)}")

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    log_message(
        f"NIC {nic_name} provisioning did not complete in the expected time", "WARNING"
    )
    return False


async def wait_for_vm_provisioning(resource_group_name, vm_name):
    max_retries = 60
    retry_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            vm = compute_client.virtual_machines.get(resource_group_name, vm_name)
            if vm.provisioning_state == "Succeeded":
                log_message(f"VM {vm_name} provisioning completed successfully")
                return True
            else:
                log_message(f"VM {vm_name} provisioning state: {vm.provisioning_state}")
        except Exception as e:
            log_message(f"Error checking VM {vm_name} provisioning state: {str(e)}")

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    log_message(
        f"VM {vm_name} provisioning did not complete in the expected time", "WARNING"
    )
    return False


async def create_vm_with_dependencies(
    resource_group_name, vm_name, location, subnet_id, vm_size, nsg_id, is_orchestrator
) -> dict:
    try:
        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="In Progress",
        )
        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="Creating Public IP",
        )
        public_ip = await asyncio.to_thread(
            create_public_ip_address, resource_group_name, f"{vm_name}-ip", location
        )

        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="Creating Network Interface",
        )
        nic = await asyncio.to_thread(
            create_network_interface,
            resource_group_name,
            f"{vm_name}-nic",
            location,
            subnet_id,
            "ipconfig1",
            public_ip.id,
            nsg_id,
        )

        nic_provisioning_success = await wait_for_nic_provisioning(
            resource_group_name, f"{vm_name}-nic"
        )
        if not nic_provisioning_success:
            raise Exception(
                f"NIC for VM {vm_name} did not complete provisioning in the expected time"
            )
        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="Creating VM",
        )
        await asyncio.to_thread(
            create_vm, resource_group_name, vm_name, location, nic.id, vm_size
        )

        # Fetch the public IP address
        public_ip_address = await asyncio.to_thread(
            network_client.public_ip_addresses.get, resource_group_name, f"{vm_name}-ip"
        )

        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="Waiting for VM provisioning",
        )

        provisioning_success = await wait_for_vm_provisioning(
            resource_group_name, vm_name
        )

        if not provisioning_success:
            raise Exception(
                f"VM {vm_name} provisioning did not complete in the expected time"
            )

        # Add a delay after VM provisioning
        await asyncio.sleep(5)

        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="Waiting for SSH",
        )

        # Wait for SSH to become available
        max_retries = 60  # Increase from 30 to 60
        base_delay = 5  # seconds
        max_delay = 60  # seconds

        for attempt in range(max_retries):
            try:
                async with asyncio.timeout(30):
                    async with asyncssh.connect(
                        public_ip_address.ip_address,
                        username=ADMIN_USERNAME,
                        known_hosts=None,
                    ) as conn:
                        await conn.run('echo "SSH connection successful"')
                log_message(f"SSH connection to {vm_name} established successfully")
                break
            except (AsyncSSHError, asyncio.TimeoutError, OSError, socket.error) as e:
                if attempt == max_retries - 1:
                    raise Exception(
                        f"SSH connection to {vm_name} failed after multiple attempts: {str(e)}"
                    )

                delay = min(max_delay, base_delay * (2**attempt) + random.uniform(0, 1))
                log_message(
                    f"Waiting for SSH on {vm_name} to become available (Attempt {attempt + 1}/{max_retries}). Retrying in {delay:.2f} seconds. Error: {str(e)}"
                )

                update_progress(
                    resource_name=vm_name,
                    resource_type="Virtual Machine",
                    action="Creating",
                    status=f"Waiting for SSH ({attempt + 1}/{max_retries})",
                )

                await asyncio.sleep(delay)

        # After successfully creating the VM and establishing SSH connection
        log_message(f"Preparing VM info for {vm_name}")

        private_ip = (
            nic.ip_configurations[0].private_ip_address
            if nic and nic.ip_configurations
            else None
        )
        public_ip = public_ip_address.ip_address if public_ip_address else None

        log_message(f"VM {vm_name} - Private IP: {private_ip}, Public IP: {public_ip}")

        vm_info = {
            "name": vm_name,
            "location": location,
            "ssh_username": ADMIN_USERNAME,
            "ssh_key_path": os.path.expanduser("~/.ssh/id_ed25519"),
            "ip_addresses": [
                {"private": private_ip} if private_ip else {},
                {"public": public_ip} if public_ip else {},
            ],
            "is_orchestrator_node": is_orchestrator,
        }

        log_message(f"VM info for {vm_name}: {json.dumps(vm_info, indent=2)}")

        return vm_info
    except Exception as e:
        log_message(f"Error creating VM {vm_name}: {str(e)}", "ERROR")
        log_message(f"Traceback for {vm_name}: {traceback.format_exc()}", "ERROR")
        update_progress(
            resource_name=vm_name,
            resource_type="Virtual Machine",
            action="Creating",
            status="Failed",
            exception=str(e),
        )
        return None


async def main():
    initialize_azure_clients()

    global table_update_running
    table_update_running = False

    parser = argparse.ArgumentParser(
        description="Manage Azure resources for Bacalhau Science cluster."
    )
    parser.add_argument(
        "action",
        choices=["create", "destroy", "list"],
        help="Action to perform",
    )
    parser.add_argument(
        "--num-vms",
        type=int,
        default=3,
        help="Number of VMs to create (default: 2)",
    )
    parser.add_argument(
        "--format", choices=["default", "json"], default="default", help="Output format"
    )
    args = parser.parse_args()

    async def perform_action():
        if args.action == "create":
            await create_cluster(args.num_vms)
        elif args.action == "destroy":
            await destroy_cluster()

    if args.format == "json":
        await perform_action()
        print(json.dumps(resources_progress_to_dict(), indent=2))
    else:
        with Live(console=console, refresh_per_second=4) as live:
            update_task = asyncio.create_task(update_table(live))
            try:
                await perform_action()
            except Exception as e:
                logging.error(f"Error in main: {str(e)}")
            finally:
                table_update_event.set()
                await update_task


if __name__ == "__main__":
    asyncio.run(main())
