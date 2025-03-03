import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.compute.aio import ComputeManagementClient
from azure.mgmt.network.aio import NetworkManagementClient
from azure.mgmt.resource.resources.aio import ResourceManagementClient
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from azure.network_security_group_rules import network_security_group_rules
from util.config import Config
from util.scripts_provider import ScriptsProvider

console = Console(width=200)
SCRIPT_DIR = "spot_creation_scripts"

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

config = Config('config.yaml')
scripts_provider = ScriptsProvider(config)

REGIONS = config.get_regions()
TOTAL_INSTANCES = config.get_total_instances()
global_node_count = 0

INSTANCES_PER_REGION = (TOTAL_INSTANCES // len(REGIONS)) or TOTAL_INSTANCES

current_dir = os.path.dirname(__file__)

all_statuses = {}
events_to_progress = []
table_update_running = False
table_update_event = asyncio.Event()

task_name = "TASK NAME"
task_total = 10000
task_count = 0

credential = None
compute_client = None
network_client = None
subscription_id = None
subscription_client = None
resource_client = None

# Tag to filter instances by
FILTER_TAG_NAME = "managedby"
FILTER_TAG_VALUE = "spotinstancescript"


async def initialize_clients():
    global credential, compute_client, network_client, subscription_id, subscription_client, resource_client

    credential = DefaultAzureCredential()
    subscription_client = SubscriptionClient(credential)

    async def get_subscription_id():
        subscriptions = []
        async for subscription in subscription_client.subscriptions.list():
            subscriptions.append(subscription)
            return subscriptions[0].subscription_id if subscriptions else None

    subscription_id = await get_subscription_id()
    resource_client = ResourceManagementClient(credential, subscription_id)
    compute_client = ComputeManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)

    logging.info(f"Initialized clients for subscription: {subscription_id}")
    return compute_client, network_client


async def close_clients():
    global credential, compute_client, network_client, subscription_client, resource_client
    await compute_client.close()
    await network_client.close()
    await credential.close()
    await subscription_client.close()
    await resource_client.close()


class InstanceStatus:
    def __init__(self, region, zone, index=0, instance_id=None):
        input_string = f"{region}-{zone}-{index}"
        hashed_string = hashlib.sha256(input_string.encode()).hexdigest()

        self.id = hashed_string[:6]
        self.region = region
        self.zone = zone
        self.status = "Initializing"
        self.detailed_status = ""
        self.elapsed_time = 0
        self.instance_id = instance_id or self.id
        self.public_ip = None
        self.private_ip = None

    def combined_status(self):
        return f"{self.status} ({self.detailed_status})" if self.detailed_status != "" else self.status


def make_progress_table():
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", width=10)
    table.add_column("Region", width=20)
    table.add_column("Status", width=35)
    table.add_column("Elapsed", width=10)
    table.add_column("Instance ID", width=35)
    table.add_column("Public IP", width=20)
    table.add_column("Private IP", width=20)

    for status in sorted(all_statuses.values(), key=lambda x: (x.region, x.zone)):
        table.add_row(
            status.id,
            status.region,
            status.combined_status(),
            f"{status.elapsed_time:.1f}s",
            status.instance_id,
            status.public_ip,
            status.private_ip
        )
    return table


async def update_table(live):
    global table_update_running, task_total, events_to_progress

    if table_update_running:
        return

    try:
        table_update_running = True
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            expand=True
        )
        task = progress.add_task(task_name, total=task_total)

        while not table_update_event.is_set():
            while events_to_progress:
                event = events_to_progress.pop(0)
                if isinstance(event, str):
                    all_statuses[event].status = "Listed"
                else:
                    all_statuses[event.id] = event

            completed = len(
                [s for s in all_statuses.values() if s.status in {"Done", "Terminated", "Listed"}]
            )
            progress.update(task, completed=completed)

            table = make_progress_table()
            layout = Layout()
            layout.split(
                Layout(Panel(progress, title="Progress"), size=5),
                Layout(table)
            )
            live.update(layout)
            await asyncio.sleep(0.1)

    finally:
        table_update_running = False


async def get_azure_availability_zones(region: str):
    global compute_client

    async for sku in compute_client.resource_skus.list(filter=f"location eq '{region}'"):
        if sku.locations and sku.locations[0].lower() == region.lower():
            if hasattr(sku, "location_info") and sku.location_info:
                for info in sku.location_info:
                    if hasattr(info, "zones") and info.zones:
                        return sorted(info.zones)
    return []


# fetching this from API is very slow
def get_regions():
    supported_regions = [
        "eastus", "eastus2", "westus", "centralus", "northcentralus", "southcentralus",
        "northeurope", "westeurope", "eastasia", "southeastasia", "japaneast", "japanwest",
        "australiaeast", "australiasoutheast", "australiacentral", "brazilsouth",
        "southindia", "centralindia", "westindia", "canadacentral", "canadaeast",
        "westus2", "westcentralus", "uksouth", "ukwest", "koreacentral", "koreasouth",
        "francecentral", "southafricanorth", "uaenorth", "switzerlandnorth",
        "germanywestcentral", "norwayeast", "jioindiawest", "westus3", "swedencentral",
        "qatarcentral", "polandcentral", "italynorth", "israelcentral", "spaincentral",
        "mexicocentral", "newzealandnorth"
    ]
    return supported_regions


async def create_resource_group_if_not_exists(resource_group_name: str, region: str):
    global resource_client, credential
    try:
        await resource_client.resource_groups.get(resource_group_name)
        logging.info(f"Resource group {resource_group_name} already exists.")
    except ResourceNotFoundError:
        await resource_client.resource_groups.create_or_update(
            resource_group_name, {"location": region}
        )
        logging.info(f"Resource group {resource_group_name} created.")
    return resource_group_name


async def create_vnet_if_not_exists(vnet_name: str, resource_group_name: str, region: str):
    global network_client
    try:
        await network_client.virtual_networks.get(resource_group_name, vnet_name)
        logging.info(f"VNet {vnet_name} already exists.")
    except ResourceNotFoundError:
        logging.info(f"Creating VNet {vnet_name}...")
        vnet_params = {
            'location': region,
            'address_space': {
                'address_prefixes': ['10.0.0.0/16']
            }
        }
        vnet = await network_client.virtual_networks.begin_create_or_update(
            resource_group_name, vnet_name, vnet_params)
        await vnet.result()


async def create_subnet_if_not_exists(resource_group_name: str, vnet_name: str):
    global network_client
    cidr_base_prefix = "10.0."
    cidr_base_suffix = ".0/24"
    for i in range(0, 256):
        subnet_name = f"default-{i}"
        try:
            subnet = await network_client.subnets.get(resource_group_name, vnet_name, subnet_name)
            logging.info(f"Subnet {subnet_name} in VNet {vnet_name} already exists...")
            return subnet
        except ResourceNotFoundError:
            try:
                cidr_block = cidr_base_prefix + str(i) + cidr_base_suffix
                logging.info(f"Creating subnet {subnet_name} in VNet {vnet_name}...")
                subnet_params = {
                    'address_prefix': cidr_block
                }
                subnet = await network_client.subnets.begin_create_or_update(
                    resource_group_name, vnet_name, subnet_name, subnet_params)
                return await subnet.result()
            except Exception:
                continue
    # If we've tried all possible CIDRs and none worked, raise an error
    raise Exception(f"Unable to create subnet in {resource_group_name}/{vnet_name}. All CIDR blocks are in use.")


async def create_network_security_group_if_not_exist(resource_group_name: str, nsg_name: str, region: str):
    try:
        nsg = await network_client.network_security_groups.get(resource_group_name, nsg_name)
        logging.info(f"Retrieved existing NSG: {nsg.name}")
        return nsg
    except ResourceNotFoundError as e:
        logging.info(f"Creating NSG {nsg_name} in {resource_group_name}...")
        nsg_params = {
            'location': region,
            'security_rules': network_security_group_rules
        }

    nsg = await network_client.network_security_groups.begin_create_or_update(
        resource_group_name,
        nsg_name,
        nsg_params
    )
    return await nsg.result()


async def create_spot_instances_in_region(config, instances_to_create, region):
    global task_name, task_total, subscription_id, credential, all_statuses

    # Limit concurrent operations to avoid API throttling
    semaphore = asyncio.Semaphore(10)
    events_to_progress = []
    total_completed_instances = []

    # Create resource group if it doesn't exist
    resource_group_name = f"spot-instances-{region}"
    await create_resource_group_if_not_exists(resource_group_name, region)

    # Create VNet if it doesn't exist
    vnet_name = f"vnet-{region}"
    await create_vnet_if_not_exists(vnet_name, resource_group_name, region)

    # Create subnet if it doesn't exist
    subnet = await create_subnet_if_not_exists(resource_group_name, vnet_name)
    subnet_name = subnet.name

    # create network security group if it doesn't exist
    nsg_name = f"nsg-{region}"
    nsg = await create_network_security_group_if_not_exist(resource_group_name, nsg_name, region)

    async def handle_single_instance(region, zone, index):
        status = InstanceStatus(region, zone, index)
        hash = hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:6]
        instance_name = f"spot-vm-{region}-{hash}-{index}"
        all_statuses[status.id] = status
        events_to_progress.append(status)

        try:
            async with semaphore:
                nic_name = f"nic-{instance_name}"

                # Create a public IP address
                public_ip_name = f"pip-{instance_name}"
                public_ip_parameters = {
                    "location": region,
                    "sku": {"name": "Standard"},
                    "public_ip_allocation_method": "Static",
                    "public_ip_address_version": "IPV4"
                }

                public_ip_result = await network_client.public_ip_addresses.begin_create_or_update(
                    resource_group_name,
                    public_ip_name,
                    public_ip_parameters
                )
                public_ip = await public_ip_result.result()

                # Create a network interface
                nic_parameters = {
                    "location": region,
                    "ip_configurations": [{
                        "name": "ipconfig1",
                        "subnet": {
                            "id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/{subnet_name}"
                        },
                        "public_ip_address": {
                            "id": public_ip.id
                        }
                    }],
                    "network_security_group": {"id": nsg.id}
                }

                nic_result = await network_client.network_interfaces.begin_create_or_update(
                    resource_group_name,
                    nic_name,
                    nic_parameters
                )
                nic = await nic_result.result()

                status.status = "Requesting VM"
                all_statuses[status.id] = status
                events_to_progress.append(status)

                # Get VM size based on region configuration
                vm_size = config.get_region_config(region).get('machine_type', 'Standard_B2s')

                # Get the image URN alias from config for this region
                image_urn_parts = config.get_region_config(region).get('image_urn',
                                                                       'Canonical:ubuntu-24_04-lts:server:latest').split(
                    ":")
                # Prepare VM parameters with spot instance settings
                vm_parameters = {
                    "location": region,
                    "hardware_profile": {
                        "vm_size": vm_size
                    },
                    "storage_profile": {
                        "image_reference": {
                            "publisher": image_urn_parts[0],
                            "offer": image_urn_parts[1],
                            "sku": image_urn_parts[2],
                            "version": image_urn_parts[3]
                        },
                        "os_disk": {
                            "name": f"osdisk-{instance_name}",
                            "caching": "ReadWrite",
                            "create_option": "FromImage",
                            "managed_disk": {
                                "storage_account_type": "Standard_LRS"
                            },
                            "delete_option": "Delete"
                        }
                    },
                    "os_profile": {
                        "computer_name": instance_name,
                        "admin_username": config.get_username(),
                        "linux_configuration": {
                            "disable_password_authentication": True,
                            "ssh": {
                                "public_keys": [{
                                    "path": f"/home/{config.get_username()}/.ssh/authorized_keys",
                                    "key_data": scripts_provider.get_ssh_public_key(config.get_public_ssh_key_path())
                                }]
                            }
                        },
                        "custom_data": base64.b64encode(scripts_provider.create_cloud_init_script().encode()).decode()
                    },
                    "network_profile": {
                        "network_interfaces": [{
                            "id": nic.id
                        }]
                    },
                    "priority": "Spot",
                    "eviction_policy": "Deallocate",
                    "billing_profile": {
                        "max_price": -1  # -1 means the VM won't be evicted because of price
                    },
                    "tags": {
                        "name": instance_name,
                        "managedby": "spotinstancescript"
                    }
                }

                # Add zone if specified
                if zone:
                    vm_parameters["zones"] = [zone]

                status.status = "Waiting for fulfillment"
                all_statuses[status.id] = status
                events_to_progress.append(status)

                # Create the VM
                vm_result = await compute_client.virtual_machines.begin_create_or_update(
                    resource_group_name,
                    instance_name,
                    vm_parameters
                )
                vm = await vm_result.result()

                # Get VM details to fetch IP addresses
                vm_details = await compute_client.virtual_machines.get(
                    resource_group_name,
                    instance_name,
                    expand="instanceView"
                )

                nic_details = await network_client.network_interfaces.get(
                    resource_group_name,
                    nic_name
                )

                if nic_details.ip_configurations:
                    status.private_ip = nic_details.ip_configurations[0].private_ip_address

                    # Get public IP if available
                    if nic_details.ip_configurations[0].public_ip_address:
                        public_ip_id = nic_details.ip_configurations[0].public_ip_address.id
                        public_ip_name = public_ip_id.split('/')[-1]
                        public_ip_details = await network_client.public_ip_addresses.get(
                            resource_group_name,
                            public_ip_name
                        )
                        status.public_ip = public_ip_details.ip_address

                # Update status after completion
                try:
                    status.elapsed_time = (datetime.now(timezone.utc) - vm.time_created).total_seconds()
                except:
                    status.elapsed_time = 0

                status.status = "Done"
                all_statuses[status.id] = status
                events_to_progress.append(status)

                return status

        except Exception as e:
            status.status = "Failed"
            status.detailed_status = str(e)[:120]
            all_statuses[status.id] = status
            events_to_progress.append(status)

            return status

    batch_tasks = []

    for i in range(instances_to_create):

        # Get availability zones for the current region
        availability_zones = await get_azure_availability_zones(region)

        # Select zone if available
        zone = None
        if availability_zones:
            zone_index = i % len(availability_zones)
            zone = availability_zones[zone_index]

        batch_tasks.append(handle_single_instance(region, zone, i))

    # Process this batch
    batch_results = await asyncio.gather(*batch_tasks)
    total_completed_instances.extend(batch_results)

    return total_completed_instances


async def create_spot_instances(config):
    global global_node_count

    global task_name
    task_name = "Creating Spot Instances"
    global task_total
    task_total = TOTAL_INSTANCES

    async def create_in_region(region):
        global global_node_count
        available_slots = TOTAL_INSTANCES - global_node_count
        region_cfg = config.get_region_config(region)
        if available_slots <= 0:
            logging.warning(f"Reached maximum nodes. Skipping region: {region}")
            return [], {}

        instances_to_create = min(INSTANCES_PER_REGION, available_slots) if region_cfg.get(
            "node_count") == "auto" else (
            min(region_cfg.get("node_count"), available_slots))

        if instances_to_create == 0:
            return [], {}

        logging.debug(
            f"Creating {instances_to_create} spot instances in region: {region}"
        )
        global_node_count += instances_to_create
        instance_ids = await create_spot_instances_in_region(
            config,
            instances_to_create,
            region
        )
        return instance_ids

    tasks = [create_in_region(region) for region in REGIONS]
    await asyncio.gather(*tasks)

    logging.debug("Finished creating spot instances")
    return


async def list_spot_instances():
    global all_statuses, subscription_id, compute_client, network_client

    logging.info(f"Starting to list Azure Spot instances with tag {FILTER_TAG_NAME}={FILTER_TAG_VALUE}")
    all_statuses = {}
    task_total = 0
    events_to_progress = []

    try:
        # List all VMs in the subscription
        vms = []
        async for vm in compute_client.virtual_machines.list_all():
            vms.append(vm)

        # Filter for Spot instances with the specified tag
        spot_vms = [
            vm for vm in vms
            if vm.priority == "Spot"
               and vm.tags
               and FILTER_TAG_NAME in vm.tags
               and vm.tags[FILTER_TAG_NAME] == FILTER_TAG_VALUE
        ]

        logging.info(f"Found {len(spot_vms)} tagged Spot VMs")

        for vm in spot_vms:
            vm_id = vm.id
            vm_name = vm.name
            vm_location = vm.location
            resource_group = vm_id.split('/')[4]  # Extract resource group from ID

            # Get VM instance view for status
            vm_status = await compute_client.virtual_machines.instance_view(
                resource_group,
                vm_name
            )

            # Get status and IP addresses
            state = next((s.display_status for s in vm_status.statuses if s.code.startswith("PowerState/")),
                         "Unknown")

            # Get network interfaces to find IP addresses
            nic_refs = vm.network_profile.network_interfaces
            public_ip = "Not available"
            private_ip = "Not available"

            if nic_refs:
                primary_nic_id = nic_refs[0].id
                nic_name = primary_nic_id.split('/')[-1]
                nic_group = primary_nic_id.split('/')[4]

                # Get the network interface details
                nic = await network_client.network_interfaces.get(
                    nic_group,
                    nic_name
                )

                # Get private IP
                if nic.ip_configurations and len(nic.ip_configurations) > 0:
                    private_ip = nic.ip_configurations[0].private_ip_address

                    # Get public IP if associated
                    if nic.ip_configurations[0].public_ip_address:
                        public_ip_id = nic.ip_configurations[0].public_ip_address.id
                        public_ip_name = public_ip_id.split('/')[-1]
                        public_ip_group = public_ip_id.split('/')[4]

                        public_ip_info = await network_client.public_ip_addresses.get(
                            public_ip_group,
                            public_ip_name
                        )
                        public_ip = public_ip_info.ip_address

            status = InstanceStatus(vm_location, None, task_total, instance_id=vm_name)
            status.status = state
            status.public_ip = public_ip
            status.private_ip = private_ip

            all_statuses[status.id] = status
            events_to_progress.append(status)
            task_total += 1

    except Exception as e:
        logging.error(f"Error listing VMs: {str(e)}")

    logging.info(f"Found a total of {task_total} Spot instances with tag {FILTER_TAG_NAME}={FILTER_TAG_VALUE}")
    return all_statuses


async def destroy_instances():
    global task_name, task_total, all_statuses, events_to_progress
    task_name = "Terminating Azure Spot Instances"
    task_total = 0

    semaphore = asyncio.Semaphore(10)

    async def handle_single_instance_deletion(resource_group, vm_name, location, instance_index):
        status = InstanceStatus(location, None, instance_index, instance_id=vm_name)
        status.status = "Waiting"
        all_statuses[status.id] = status
        events_to_progress.append(status)

        try:
            async with semaphore:
                # Get the network interface details first before deleting the VM
                vm = await compute_client.virtual_machines.get(
                    resource_group,
                    vm_name
                )

                nic_ids = []
                public_ip_ids = []

                if vm.network_profile and vm.network_profile.network_interfaces:
                    for nic_ref in vm.network_profile.network_interfaces:
                        nic_ids.append(nic_ref.id)
                        nic_name = nic_ref.id.split('/')[-1]
                        nic_group = nic_ref.id.split('/')[4]

                        # Get NIC details to find associated public IPs
                        try:
                            nic = await network_client.network_interfaces.get(
                                nic_group,
                                nic_name
                            )

                            # Find associated public IP addresses
                            if nic.ip_configurations:
                                for ip_config in nic.ip_configurations:
                                    if ip_config.public_ip_address:
                                        public_ip_ids.append(ip_config.public_ip_address.id)

                                        # Get public IP for status display
                                        public_ip_name = ip_config.public_ip_address.id.split('/')[-1]
                                        public_ip_group = ip_config.public_ip_address.id.split('/')[4]
                                        public_ip_info = await network_client.public_ip_addresses.get(
                                            public_ip_group,
                                            public_ip_name
                                        )
                                        status.public_ip = public_ip_info.ip_address

                                    # Get private IP for status display
                                    if ip_config.private_ip_address:
                                        status.private_ip = ip_config.private_ip_address
                        except Exception as e:
                            logging.warning(f"Error getting NIC details: {str(e)}")

                start_time = datetime.now(timezone.utc)
                status.status = "Deleting VM"
                events_to_progress.append(status)

                # Delete the VM
                vm_delete_operation = await compute_client.virtual_machines.begin_delete(
                    resource_group,
                    vm_name
                )
                await vm_delete_operation.wait()

                status.status = "Deleting NICs"
                status.elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                events_to_progress.append(status)

                for nic_id in nic_ids:
                    nic_name = nic_id.split('/')[-1]
                    nic_group = nic_id.split('/')[4]

                    nic_delete_operation = await network_client.network_interfaces.begin_delete(
                        nic_group,
                        nic_name
                    )
                    await nic_delete_operation.wait()

                status.status = "Deleting Public IPs"
                status.elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                events_to_progress.append(status)

                # Delete the public IP addresses
                for public_ip_id in public_ip_ids:
                    public_ip_name = public_ip_id.split('/')[-1]
                    public_ip_group = public_ip_id.split('/')[4]

                    pip_delete_operation = await network_client.public_ip_addresses.begin_delete(
                        public_ip_group,
                        public_ip_name
                    )
                    await pip_delete_operation.wait()

                status.status = "Terminated"
                status.elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                events_to_progress.append(status)

                return status

        except Exception as e:
            status.status = "Failed"
            status.detailed_status = str(e)[:120]
            events_to_progress.append(status)
            return status

    try:
        vms = []
        async for vm in compute_client.virtual_machines.list_all():
            vms.append(vm)

        spot_vms = [
            (vm.id.split('/')[4], vm.name, vm.location, vm.id, i)
            for i, vm in enumerate(vms)
            if vm.priority == "Spot"
               and vm.tags
               and FILTER_TAG_NAME in vm.tags
               and vm.tags[FILTER_TAG_NAME] == FILTER_TAG_VALUE
        ]

        task_total = len(spot_vms)

        if task_total == 0:
            logging.info(f"No spot instances found with tag {FILTER_TAG_NAME}={FILTER_TAG_VALUE}")
            return []

        logging.info(f"Found {task_total} spot instances to terminate")

        deletion_tasks = [
            handle_single_instance_deletion(resource_group, vm_name, location, idx)
            for resource_group, vm_name, location, vm_id, idx in spot_vms
        ]

        completed_deletions = await asyncio.gather(*deletion_tasks)
        return completed_deletions

    except Exception as e:
        logging.error(f"Error in destroy_instances: {str(e)}")
        return []


async def main():
    parser = argparse.ArgumentParser(description="Manage Azure spot instances")
    parser.add_argument("--action", choices=["create", "destroy", "list"], default="list")
    parser.add_argument("--format", choices=["default", "json"], default="default")
    args = parser.parse_args()

    await initialize_clients()

    async def perform_action():
        if args.action == "create":
            await create_spot_instances(config)
        elif args.action == "list":
            await list_spot_instances()
        elif args.action == "destroy":
            await destroy_instances()

    if args.format == "json":
        await perform_action()
        print(json.dumps({
            status.id: {
                "id": status.id,
                "region": status.region,
                "status": status.status,
                "instance_id": status.instance_id,
                "public_ip": status.public_ip,
                "private_ip": status.private_ip
            } for status in all_statuses.values()
        }, indent=2))
    else:
        with Live(console=console, refresh_per_second=20) as live:
            update_task = asyncio.create_task(update_table(live))
            try:
                await perform_action()
                await asyncio.sleep(1)
            finally:
                table_update_event.set()
                await close_clients()
            await update_task


if __name__ == "__main__":
    asyncio.run(main())
