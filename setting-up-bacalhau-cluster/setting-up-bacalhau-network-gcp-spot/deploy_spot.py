import argparse
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import tarfile

from dateutil import parser
from google.api_core.exceptions import NotFound
from google.api_core.operation import Operation
from google.cloud import compute_v1
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from util.config import Config
from util.scripts_provider import ScriptsProvider

console = Console(width=200)
SCRIPT_DIR = "spot_creation_scripts"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

config = Config('config.yaml')
scripts_provider = ScriptsProvider(config)

REGIONS = config.get_regions()
TOTAL_INSTANCES = config.get_total_instances()
INSTANCES_PER_REGION = TOTAL_INSTANCES // len(REGIONS) or TOTAL_INSTANCES
global_node_count = 0

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
SERVICE_ACCOUNT = os.getenv('GCP_SERVICE_ACCOUNT')

all_statuses = {}
events_to_progress = []
table_update_running = False
table_update_event = asyncio.Event()

task_name = "TASK NAME"
task_total = 10000
task_count = 0


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
    table.add_column("Zone", width=20)
    table.add_column("Status", width=35)
    table.add_column("Elapsed", width=10)
    table.add_column("Instance ID", width=35)
    table.add_column("Public IP", width=20)
    table.add_column("Private IP", width=20)

    for status in sorted(all_statuses.values(), key=lambda x: (x.region, x.zone)):
        table.add_row(
            status.id,
            status.region,
            status.zone,
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


async def get_zones(region):
    try:
        from google.cloud import compute_v1
        client = compute_v1.ZonesClient()
        zones_list = client.list(project=PROJECT_ID)
        region_zones = []
        for zone in zones_list:
            if zone.name.startswith(f"{region}-"):
                region_zones.append(zone.name)

        return region_zones

    except Exception as e:
        logging.error(f"Error retrieving GCP zones for region {region}: {str(e)}")
        return []

def calculate_elapsed_time(operation: Operation):
    try:
        insert_time = parser.isoparse(operation.insert_time)
        end_time = parser.isoparse(operation.end_time)
        return (end_time - insert_time).total_seconds()
    except Exception:
        return 0


async def create_spot_instances(config, orchestrators, token="", tls="false"):
    global task_name, task_total, global_node_count
    task_name = "Creating Spot Instances"
    task_total = TOTAL_INSTANCES

    semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent operations

    async def handle_single_instance(region, zone, index):
        status = InstanceStatus(region, zone, index)
        instance_name = f"spot-instance-{region}-{index}"
        all_statuses[status.id] = status
        events_to_progress.append(status)

        try:
            async with semaphore:
                instance_client = compute_v1.InstancesClient()

                # Define the disk configuration
                disk = compute_v1.AttachedDisk()
                disk.boot = True
                disk.auto_delete = True
                disk.initialize_params = compute_v1.AttachedDiskInitializeParams(
                    source_image=config.get_image_for_region(region))

                # Define the network interface
                network_interface = compute_v1.NetworkInterface()
                network_interface.network = "global/networks/default"
                network_interface.access_configs = [compute_v1.AccessConfig()]

                # Define scheduling (Spot instance settings)
                scheduling = compute_v1.Scheduling(
                    provisioning_model="SPOT",
                    automatic_restart=False,
                    preemptible=True
                )

                # Define metadata (Startup script)
                metadata = compute_v1.Metadata()
                metadata.items = [{"key": "user-data", "value": scripts_provider.create_cloud_init_script()}]

                # Define instance properties
                instance = compute_v1.Instance(
                    name=instance_name,
                    machine_type=f"zones/{zone}/machineTypes/{config.get_region_config(region).get('machine_type', 'n1-standard-1')}",
                    disks=[disk],
                    network_interfaces=[network_interface],
                    scheduling=scheduling,
                    metadata=metadata,
                    labels={
                        "name": instance_name,
                        "managedby": "spotinstancescript"
                    }
                )

                status.status = "Requesting"
                events_to_progress.append(status)

                # Create the instance
                operation = await asyncio.to_thread(
                    instance_client.insert,
                    project=PROJECT_ID,
                    zone=zone,
                    instance_resource=instance
                )

                status.status = "Waiting for fulfillment"
                events_to_progress.append(status)

                # Wait for this specific instance to complete
                op_status = await asyncio.to_thread(
                    operation.result
                )

                # Update status after completion
                status.elapsed_time = calculate_elapsed_time(op_status)
                status.status = "Done"
                events_to_progress.append(status)

                # Get instance details to fetch IP addresses
                instance_details = await asyncio.to_thread(
                    instance_client.get,
                    project=PROJECT_ID,
                    zone=zone,
                    instance=instance_name
                )

                if instance_details.network_interfaces:
                    if instance_details.network_interfaces[0].access_configs:
                        status.public_ip = instance_details.network_interfaces[0].access_configs[0].nat_i_p
                    status.private_ip = instance_details.network_interfaces[0].network_i_p

                return status

        except Exception as e:
            status.status = "Failed"
            status.detailed_status = str(e)
            events_to_progress.append(status)
            return status

    # Create all instance tasks
    instance_tasks = []
    for region in REGIONS:
        zones = await get_zones(region)

        available_slots = TOTAL_INSTANCES - global_node_count
        region_cfg = config.get_region_config(region)

        instances_to_create = min(INSTANCES_PER_REGION, available_slots) if region_cfg.get(
            "node_count") == "auto" else (
            min(region_cfg.get("node_count"), available_slots))

        if instances_to_create > 0:
            global_node_count += instances_to_create
            for i in range(instances_to_create):
                zone = zones[i % len(zones)]
                instance_tasks.append(handle_single_instance(region, zone, i))

    # Wait for all instances to complete
    completed_instances = await asyncio.gather(*instance_tasks)
    return completed_instances


async def list_spot_instances():
    global task_name, task_total, all_statuses
    all_statuses = {}
    task_name = "Listing Spot Instances"

    instance_client = compute_v1.InstancesClient()

    for region in REGIONS:
        zones = await get_zones(region)
        for zone in zones:
            try:
                instances = await asyncio.to_thread(
                    instance_client.list,
                    request=compute_v1.ListInstancesRequest(
                        project=PROJECT_ID,
                        zone=zone,
                        filter='labels.managedby=spotinstancescript'
                    )
                )
                for instance in instances:
                    status = InstanceStatus(region, zone, task_total, instance_id=instance.name)
                    status.status = instance.status
                    status.public_ip = instance.network_interfaces[0].access_configs[0].nat_i_p
                    status.private_ip = instance.network_interfaces[0].network_i_p

                    all_statuses[status.id] = status
                    events_to_progress.append(status.id)
                    task_total += 1

            except Exception as e:
                logging.error(f"Error listing instances in {zone}: {str(e)}")


async def destroy_instances():
    global task_name, task_total
    task_name = "Terminating spot Instances"

    instance_client = compute_v1.InstancesClient()
    semaphore = asyncio.Semaphore(10)

    async def handle_single_instance_deletion(region, zone, instance, instance_index):
        status = InstanceStatus(region, zone, instance_index, instance_id=instance.name)
        status.status = "Waiting"

        if instance.network_interfaces:
            if instance.network_interfaces[0].access_configs:
                status.public_ip = instance.network_interfaces[0].access_configs[0].nat_i_p
            status.private_ip = instance.network_interfaces[0].network_i_p

        all_statuses[status.id] = status
        events_to_progress.append(status)

        try:
            async with semaphore:
                operation = await asyncio.to_thread(
                    instance_client.delete,
                    project=PROJECT_ID,
                    zone=zone,
                    instance=instance.name
                )
                status.status = "Terminating"
                status.elapsed_time = calculate_elapsed_time(operation)
                events_to_progress.append(status)

                await asyncio.to_thread(operation.result)

                status.status = "Terminated"
                status.elapsed_time = calculate_elapsed_time(operation)
                events_to_progress.append(status)
                return status

        except Exception as e:
            status.status = "Failed"
            status.detailed_status = str(e)
            events_to_progress.append(status)
            return status

    async def get_instances_in_zone(zone):
        try:
            instances = await asyncio.to_thread(
                instance_client.list,
                request=compute_v1.ListInstancesRequest(
                    project=PROJECT_ID,
                    zone=zone,
                    filter='labels.managedby=spotinstancescript'
                )
            )
            return list(instances)
        except Exception as e:
            logging.error(f"Error listing instances in {zone}: {str(e)}")
            return []

    # Get all instances with proper indexing
    all_instances = []
    instance_index = 0
    for region in REGIONS:
        zones = await get_zones(region)
        for zone in zones:
            instances = await get_instances_in_zone(zone)
            for instance in instances:
                all_instances.append((region, zone, instance, instance_index))
                instance_index += 1

    task_total = len(all_instances)

    if task_total == 0:
        logging.info("No instances found to terminate")
        return []

    # Create deletion tasks with instance index
    deletion_tasks = [
        handle_single_instance_deletion(region, zone, instance, idx)
        for region, zone, instance, idx in all_instances
    ]

    completed_deletions = await asyncio.gather(*deletion_tasks)
    return completed_deletions


async def main():
    parser = argparse.ArgumentParser(description="Manage GCP spot instances")
    parser.add_argument("--action", choices=["create", "destroy", "list"], default="list")
    parser.add_argument("--format", choices=["default", "json"], default="default")
    args = parser.parse_args()

    orchestrators = config.get_orchestrators()

    async def perform_action():
        if args.action == "create":
            await create_spot_instances(config, orchestrators, config.get_token(), config.get_tls())
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
                "zone": status.zone,
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
                await update_task


if __name__ == "__main__":
    asyncio.run(main())
