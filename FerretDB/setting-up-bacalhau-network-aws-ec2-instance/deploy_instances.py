#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "click",
#     "aiohttp",
#     "botocore",
#     "python-dotenv",
#     "pyyaml",
#     "rich",
# ]
# ///

import argparse
import asyncio
import base64
import json
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone

import boto3
import botocore
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from util.config import Config

# Tag to filter instances by
FILTER_TAG_NAME = "ManagedBy"
FILTER_TAG_VALUE = "SpotInstanceScript"

console = Console()

# Set up logging to file only (no console output)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Disable noisy boto3/botocore logging
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Clear existing handlers to prevent any console output
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler
try:
    # Truncate the file by opening in 'w' mode
    open("debug_deploy_instances.log", "w").close()
    file_handler = logging.FileHandler("debug_deploy_instances.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
    )
    logger.addHandler(file_handler)
    logger.debug("Logging initialized")
except Exception as e:
    # Don't print to console, just write to the log file if possible
    with open("debug_deploy_spot.log", "a") as f:
        f.write(f"Failed to set up file logging: {e}\n")

subnet_creation_lock = asyncio.Lock()
scripts_provider_lock = asyncio.Lock()

config = Config('config.yaml')

AWS_REGIONS = config.get_regions()
TOTAL_INSTANCES = config.get_total_instances()
global_node_count = 0
nodes_in_region = {}
INSTANCES_PER_REGION = (TOTAL_INSTANCES // len(
    AWS_REGIONS)) or TOTAL_INSTANCES  # Evenly distribute instances if set to 'auto' in config

MAX_NODES = config.get_total_instances()  # Global limit for total nodes across all regions
current_dir = os.path.dirname(__file__)

SCRIPT_DIR = "instance/scripts"

all_statuses = {}

table_update_running = False
table_update_event = asyncio.Event()

task_name = "TASK NAME"
task_total = 10000
task_count = 0
events_to_progress = []


def update_all_statuses(status):
    async def update_all_statuses_async(status):
        all_statuses_lock = asyncio.Lock()

        async with all_statuses_lock:
            all_statuses[status.id] = status

    update_all_statuses_async(status)


class InstanceStatus:

    def __init__(self, region, zone, instance_id=None):

        self.region = region
        self.zone = zone
        self.status = "Initializing"
        self.detailed_status = "Initializing"
        self.elapsed_time = 0
        self.instance_id = instance_id

        if self.instance_id is not None:
            self.id = self.instance_id
        else:
            self.id = str(uuid.uuid4())

        self.public_ip = None
        self.private_ip = None
        self.vpc_id = None

    def combined_status(self):
        return f"{self.status} ({self.detailed_status})" if self.detailed_status else self.status


def format_elapsed_time(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def make_progress_table():
    global all_statuses
    table = Table(show_header=True, header_style="bold magenta", show_lines=False)
    table.overflow = "ellipsis"
    table.add_column("ID", style="cyan")
    table.add_column("Region", style="cyan")
    table.add_column("Zone", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Elapsed", justify="right", style="magenta")
    table.add_column("Instance ID", style="blue")
    table.add_column("Public IP", style="blue")
    table.add_column("Private IP", style="blue")

    sorted_statuses = sorted(all_statuses.values(), key=lambda x: (x.region, x.zone))
    for status in sorted_statuses:
        table.add_row(
            status.id,
            status.region,
            status.zone,
            status.combined_status(),
            f"{status.elapsed_time:.1f}s",
            status.instance_id,
            status.public_ip,
            status.private_ip,
        )
    return table


def create_layout(progress, table):
    layout = Layout()
    progress_panel = Panel(
        progress,
        title="Progress",
        border_style="green",
        padding=(1, 1),
    )
    layout.split(
        Layout(progress_panel, size=5),
        Layout(table),
    )
    return layout


async def update_table(live):
    global \
        table_update_running, \
        task_total, \
        events_to_progress, \
        all_statuses, \
        console, \
        task_name
    if table_update_running:
        logging.debug("Table update already running. Exiting.")
        return

    logging.debug("Starting table update.")

    try:
        table_update_running = True
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed} of {task.total}"),
            TextColumn("[progress.elapsed]{task.elapsed:>3.0f}s"),
            expand=True,
        )
        task = progress.add_task(task_name, total=task_total)

        while not table_update_event.is_set():
            while events_to_progress:
                event = events_to_progress.pop(0)
                if isinstance(event, str):
                    # For list operation, event is instance_id
                    all_statuses[event].status = "Listed"
                    # all_statuses[event].detailed_status = ""
                else:
                    # For create and destroy operations, event is InstanceStatus object
                    all_statuses[event.id] = event

            if task_name == "Creating Instances":
                completed = len(
                    [s for s in all_statuses.values() if s.status != "Initializing"]
                )
            elif task_name == "Terminating Spot Instances":
                completed = len(
                    [s for s in all_statuses.values() if s.status == "Terminated"]
                )
            elif task_name == "Listing Spot Instances":
                completed = len(
                    [s for s in all_statuses.values() if s.status == "Listed"]
                )
            else:
                completed = 0

            # Update task_total if it has changed
            if task_total != progress.tasks[0].total:
                progress.update(task, total=task_total)

            progress.update(task, completed=completed)

            table = make_progress_table()
            layout = create_layout(progress, table)
            live.update(layout)

            await asyncio.sleep(0.05)  # Reduce sleep time for more frequent updates

    except Exception as e:
        logging.error(f"Error in update_table: {str(e)}")
    finally:
        table_update_running = False
        logging.debug("Table update finished.")


def get_ec2_client(region):
    return boto3.client("ec2", region_name=region)


async def get_availability_zones(ec2):
    response = await asyncio.to_thread(
        ec2.describe_availability_zones,
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}],
    )
    return [zone["ZoneName"] for zone in response["AvailabilityZones"]][:1]  # Get 1 AZ per region


async def get_scripts_provider_locked(config, region, region_cfg):
    async with scripts_provider_lock:
        current_count = nodes_in_region.get(region, 0)
        scripts_provider = config.get_scripts_provider(region, region_cfg, current_count)
        nodes_in_region[region] = current_count + 1
    return scripts_provider


async def create_instances_in_region(config: Config, instances_to_create, region, region_cfg):
    global all_statuses, events_to_progress, nodes_in_region

    ec2 = get_ec2_client(region)

    try:
        vpc_id = await create_vpc_if_not_exists(ec2)
        igw_id = await create_internet_gateway(ec2, vpc_id)
        route_table_id = await create_route_table(ec2, vpc_id, igw_id)
        security_group_id = await create_security_group_if_not_exists(ec2, vpc_id)

        instance_ids = []
        zones = await get_availability_zones(ec2)
        for i in range(instances_to_create):
            zone = zones[i % len(zones)]  # Distribute instances across available zones

            scripts_provider = await get_scripts_provider_locked(config, region, region_cfg)
            user_data = scripts_provider.create_cloud_init_script(region_cfg)
            if not user_data:
                logging.error("User data is empty. Stopping creation.")
                return [], {}

            encoded_user_data = base64.b64encode(user_data.encode()).decode()

            subnet_id = await create_subnet(ec2, vpc_id, zone, f"10.0.{i}.0/24")
            try:
                await associate_route_table(ec2, route_table_id, subnet_id)
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
                    logging.info(
                        f"Route table already associated in {region}-{zone}: {str(e)}"
                    )
                else:
                    logging.warning(
                        f"Error associating route table in {region}-{zone}: {str(e)}"
                    )

            thisInstanceStatusObject = InstanceStatus(region, zone)
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject

            start_time = time.time()
            launch_specification = {
                "ImageId": config.get_image_for_region(region, region_cfg),
                "InstanceType": region_cfg.get("machine_type", "t2.medium"),
                "UserData": encoded_user_data,
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {"DeleteOnTermination": True},
                    }
                ],
                "NetworkInterfaces": [
                    {
                        "DeviceIndex": 0,
                        "AssociatePublicIpAddress": True,
                        "DeleteOnTermination": True,
                        "SubnetId": subnet_id,
                        "Groups": [security_group_id],
                    }
                ],
            }

            thisInstanceStatusObject.status = "Requesting"

            logging.debug(f"Requesting instance in {region}-{zone}")

            if region_cfg.get("spot", True):
                name_prefix = "Spot"
                spot_request_ids = await request_spot_instance(ec2, launch_specification, region, zone)
                thisInstanceStatusObject.status = "Waiting for fulfillment"
                zone_instance_ids = await wait_for_spot_request_fulfillment(ec2, region, spot_request_ids, start_time,
                                                                            thisInstanceStatusObject, zone)
            else:
                name_prefix = ""
                on_demand_request_ids = await request_on_demand_instance(ec2, launch_specification, region, zone)
                thisInstanceStatusObject.status = "Waiting for fulfillment"
                zone_instance_ids = await wait_for_on_demand_request_fulfillment(ec2, region, on_demand_request_ids,
                                                                                 start_time,
                                                                                 thisInstanceStatusObject, zone)

            instance_ids.extend(zone_instance_ids)

            if zone_instance_ids:
                thisInstanceStatusObject.instance_id = zone_instance_ids[0]
                thisInstanceStatusObject.status = "Tagging"

                tags = [
                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                    {"Key": "Name", "Value": f"{name_prefix}Instance-{region}-{zone}"},
                    {"Key": "AZ", "Value": zone}
                ]
                custom_tags = region_cfg.get("tags")
                if custom_tags:
                    tags.append({"Key": "Custom", "Value": custom_tags})

                # Tag instances
                await asyncio.to_thread(
                    ec2.create_tags,
                    Resources=zone_instance_ids,
                    Tags=tags,
                )

                # Fetch instance details to get IP addresses
                instance_details = await asyncio.to_thread(
                    ec2.describe_instances,
                    InstanceIds=[thisInstanceStatusObject.instance_id],
                )
                if instance_details["Reservations"]:
                    instance = instance_details["Reservations"][0]["Instances"][0]
                    thisInstanceStatusObject.public_ip = instance.get(
                        "PublicIpAddress", ""
                    )
                    thisInstanceStatusObject.private_ip = instance.get(
                        "PrivateIpAddress", ""
                    )

                thisInstanceStatusObject.status = "Done"
                events_to_progress.append(thisInstanceStatusObject)
            else:
                thisInstanceStatusObject.status = "Failed to request instance"
                update_all_statuses(thisInstanceStatusObject)

    except Exception as e:
        logging.error(f"An error occurred in {region}: {str(e)}", exc_info=True)
        return [], {}

    return instance_ids


async def wait_for_on_demand_request_fulfillment(ec2, region, instance_ids, start_time, thisInstanceStatusObject, zone):
    # Wait for on-demand instance to be running
    waiter = ec2.get_waiter("instance_running")
    max_wait_time = 600  # Increase to 10 minutes
    start_wait_time = time.time()

    while True:
        try:
            logging.debug(f"Waiting for on-demand instance in {region}-{zone}")
            await asyncio.to_thread(
                waiter.wait,
                InstanceIds=instance_ids,
                WaiterConfig={"MaxAttempts": 1},
            )
            logging.debug(f"On-demand instance running in {region}-{zone}")
            break
        except botocore.exceptions.WaiterError:
            thisInstanceStatusObject.elapsed_time = time.time() - start_time
            if time.time() - start_wait_time > max_wait_time:
                logging.error(
                    f"Timeout waiting for on-demand instance in {region}-{zone}"
                )
                break
            await asyncio.sleep(3)  # Increase sleep time to reduce API calls

        # Check instance status
        describe_response = await asyncio.to_thread(
            ec2.describe_instances,
            InstanceIds=instance_ids,
        )

        for reservation in describe_response["Reservations"]:
            for instance in reservation["Instances"]:
                state_name = instance.get("State", {}).get("Name")
                logging.debug(f"On-demand instance status in {region}-{zone}: {state_name}")

                if state_name != "running":
                    logging.error(
                        f"On-demand instance failed to start in {region}-{zone} with state: {state_name}"
                    )
                    break
    return instance_ids


async def wait_for_spot_request_fulfillment(ec2, region, spot_request_ids, start_time, thisInstanceStatusObject, zone):
    # Wait for spot instances to be fulfilled
    waiter = ec2.get_waiter("spot_instance_request_fulfilled")
    max_wait_time = 600  # Increase to 10 minutes
    start_wait_time = time.time()
    while True:
        try:
            logging.debug(
                f"Waiting for spot instance fulfillment in {region}-{zone}"
            )
            await asyncio.to_thread(
                waiter.wait,
                SpotInstanceRequestIds=spot_request_ids,
                WaiterConfig={"MaxAttempts": 1},
            )
            logging.debug(f"Spot instance request fulfilled in {region}-{zone}")
            break
        except botocore.exceptions.WaiterError:
            thisInstanceStatusObject.elapsed_time = time.time() - start_time
            if time.time() - start_wait_time > max_wait_time:
                logging.error(
                    f"Timeout waiting for spot instance fulfillment in {region}-{zone}"
                )
                break
            await asyncio.sleep(3)  # Increase sleep time to reduce API calls

        # Check spot request status
        describe_response = await asyncio.to_thread(
            ec2.describe_spot_instance_requests,
            SpotInstanceRequestIds=spot_request_ids,
        )
        for request in describe_response["SpotInstanceRequests"]:
            status_code = request["Status"]["Code"]
            status_message = request["Status"].get("Message", "No message")
            logging.debug(
                f"Spot request status in {region}-{zone}: {status_code} - {status_message}"
            )
            if status_code in ["price-too-low", "capacity-not-available"]:
                logging.error(
                    f"Spot request failed in {region}-{zone}: {status_code} - {status_message}"
                )
                break
    # Get instance IDs
    zone_instance_ids = [
        request["InstanceId"]
        for request in describe_response["SpotInstanceRequests"]
        if "InstanceId" in request
    ]
    return zone_instance_ids


async def request_spot_instance(ec2, launch_specification, region, zone):
    response = await asyncio.to_thread(
        ec2.request_spot_instances,
        InstanceCount=1,  # Create a single instance per request
        Type="one-time",
        InstanceInterruptionBehavior="terminate",
        LaunchSpecification=launch_specification,
        TagSpecifications=[
            {
                "ResourceType": "spot-instances-request",
                "Tags": [
                    {"Key": "Name", "Value": f"SpotInstance-{region}-{zone}"},
                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                ],
            },
        ],
    )
    spot_request_ids = [
        request["SpotInstanceRequestId"]
        for request in response["SpotInstanceRequests"]
    ]
    logging.debug(f"Spot request IDs: {spot_request_ids}")
    return spot_request_ids


async def request_on_demand_instance(ec2, launch_specification, region, zone):
    response = await asyncio.to_thread(
        ec2.run_instances,  # Method changed from request_spot_instances to run_instances
        ImageId=launch_specification["ImageId"],
        InstanceType=launch_specification["InstanceType"],
        MinCount=1,
        MaxCount=1,
        UserData=launch_specification["UserData"],
        BlockDeviceMappings=launch_specification["BlockDeviceMappings"],
        NetworkInterfaces=launch_specification["NetworkInterfaces"],
        TagSpecifications=[
            {
                "ResourceType": "instance",  # Resource type changed for on-demand instances
                "Tags": [
                    {"Key": "Name", "Value": f"OnDemandInstance-{region}-{zone}"},
                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                ],
            },
        ],
    )
    on_demand_request_ids = [
        instance["InstanceId"]
        for instance in response["Instances"]
    ]
    logging.debug(f"Spot request IDs: {on_demand_request_ids}")
    return on_demand_request_ids


async def create_vpc_if_not_exists(ec2):
    vpcs = await asyncio.to_thread(
        ec2.describe_vpcs, Filters=[{"Name": "tag:Name", "Values": ["SpotInstanceVPC"]}]
    )
    if vpcs["Vpcs"]:
        return vpcs["Vpcs"][0]["VpcId"]
    else:
        vpc = await asyncio.to_thread(ec2.create_vpc, CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        await asyncio.to_thread(
            ec2.create_tags,
            Resources=[vpc_id],
            Tags=[{"Key": "Name", "Value": "SpotInstanceVPC"}],
        )
        await asyncio.to_thread(
            ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsHostnames={"Value": True}
        )
        await asyncio.to_thread(
            ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsSupport={"Value": True}
        )
        return vpc_id


async def create_subnet(ec2, vpc_id, zone, cidr_block=None):
    async with subnet_creation_lock:
        # First, check if a subnet already exists in this zone
        existing_subnets = await asyncio.to_thread(
            ec2.describe_subnets,
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "availability-zone", "Values": [zone]},
            ],
        )

        if existing_subnets["Subnets"]:
            # If a subnet exists, return its ID
            return existing_subnets["Subnets"][0]["SubnetId"]

        # If no subnet exists, try to create one
        cidr_base_prefix = "10.0."
        cidr_base_suffix = ".0/24"
        for i in range(256):
            try:
                cidrBlock = cidr_block if cidr_block else cidr_base_prefix + str(i) + cidr_base_suffix
                logging.debug(f"Creating subnet in {zone} with CIDR block {cidrBlock}")
                subnet = await asyncio.to_thread(
                    ec2.create_subnet,
                    VpcId=vpc_id,
                    CidrBlock=cidrBlock,
                    AvailabilityZone=zone,
                )
                return subnet["Subnet"]["SubnetId"]
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "InvalidSubnet.Conflict":
                    # If this CIDR is in use, try the next one
                    continue
                else:
                    # If it's a different error, raise it
                    raise

        # If we've tried all possible CIDRs and none worked, raise an error
        raise Exception(f"Unable to create subnet in {zone}. All CIDR blocks are in use.")


async def create_internet_gateway(ec2, vpc_id):
    # First, check if the VPC already has an Internet Gateway attached
    igws = await asyncio.to_thread(
        ec2.describe_internet_gateways,
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
    )

    if igws["InternetGateways"]:
        # If an Internet Gateway is already attached, return its ID
        return igws["InternetGateways"][0]["InternetGatewayId"]

    # If no Internet Gateway is attached, create and attach a new one
    igw = await asyncio.to_thread(ec2.create_internet_gateway)
    igw_id = igw["InternetGateway"]["InternetGatewayId"]

    try:
        await asyncio.to_thread(
            ec2.attach_internet_gateway, InternetGatewayId=igw_id, VpcId=vpc_id
        )
    except botocore.exceptions.ClientError:
        # If an error occurs during attachment, delete the created IGW
        await asyncio.to_thread(ec2.delete_internet_gateway, InternetGatewayId=igw_id)
        # Re-check for existing IGW in case one was attached concurrently
        igws = await asyncio.to_thread(
            ec2.describe_internet_gateways,
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
        )
        if igws["InternetGateways"]:
            return igws["InternetGateways"][0]["InternetGatewayId"]
        else:
            # If still no IGW found, re-raise the original error
            raise

    return igw_id


async def create_route_table(ec2, vpc_id, igw_id):
    # Check if a route table already exists for the VPC
    route_tables = await asyncio.to_thread(
        ec2.describe_route_tables,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )
    for rt in route_tables["RouteTables"]:
        for association in rt.get("Associations", []):
            if association.get("Main", False):
                # Found the main route table, add a route to the IGW if it doesn't exist
                route_table_id = rt["RouteTableId"]
                routes = rt.get("Routes", [])
                if not any(route.get("GatewayId") == igw_id for route in routes):
                    await asyncio.to_thread(
                        ec2.create_route,
                        RouteTableId=route_table_id,
                        DestinationCidrBlock="0.0.0.0/0",
                        GatewayId=igw_id,
                    )
                return route_table_id

    # If no route table exists, create a new one
    route_table = await asyncio.to_thread(ec2.create_route_table, VpcId=vpc_id)
    route_table_id = route_table["RouteTable"]["RouteTableId"]

    # Create a route to the Internet Gateway
    await asyncio.to_thread(
        ec2.create_route,
        RouteTableId=route_table_id,
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=igw_id,
    )

    # Associate the route table with the VPC (make it the main route table)
    await asyncio.to_thread(
        ec2.associate_route_table,
        RouteTableId=route_table_id,
        VpcId=vpc_id,
    )

    return route_table_id


async def associate_route_table(ec2, route_table_id, subnet_id):
    try:
        await asyncio.to_thread(
            ec2.associate_route_table, RouteTableId=route_table_id, SubnetId=subnet_id
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
            logging.debug(
                f"Route table already associated in {route_table_id}-{subnet_id}: {str(e)}"
            )
        else:
            raise


async def create_security_group_if_not_exists(ec2, vpc_id):
    security_groups = await asyncio.to_thread(
        ec2.describe_security_groups,
        Filters=[
            {"Name": "group-name", "Values": ["SpotInstanceSG"]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ],
    )
    if security_groups["SecurityGroups"]:
        return security_groups["SecurityGroups"][0]["GroupId"]
    else:
        security_group = await asyncio.to_thread(
            ec2.create_security_group,
            GroupName="SpotInstanceSG",
            Description="Security group for Spot Instances",
            VpcId=vpc_id,
        )
        security_group_id = security_group["GroupId"]
        await asyncio.to_thread(
            ec2.authorize_security_group_ingress,
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1234,
                    "ToPort": 1234,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1235,
                    "ToPort": 1235,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 4222,
                    "ToPort": 4222,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 27017,
                    "ToPort": 27017,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
            ],
        )
        return security_group_id


async def create_spot_instances():
    global task_name, task_total
    task_name = "Creating Spot Instances"
    task_total = MAX_NODES

    async def create_in_region(region, region_cfg):
        global global_node_count
        available_slots = MAX_NODES - global_node_count
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
        instance_ids = await create_instances_in_region(
            config,
            instances_to_create,
            region,
            region_cfg
        )
        return instance_ids

    tasks = [
        create_in_region(region, cfg[region])
        for region in AWS_REGIONS
        for cfg in config.get_region_config(region)
    ]
    await asyncio.gather(*tasks)

    logging.debug("Waiting for public IP addresses...")
    await wait_for_public_ips()

    logging.debug("Finished creating spot instances")
    return


async def wait_for_public_ips():
    global all_statuses
    timeout = 300  # 5 minutes timeout
    start_time = time.time()

    while True:
        all_have_ips = all(status.public_ip for status in all_statuses.values())
        if all_have_ips or time.time() - start_time > timeout:
            break

        for region in AWS_REGIONS:
            ec2 = get_ec2_client(region)
            instance_ids = [
                status.instance_id
                for status in all_statuses.values()
                if status.region == region and not status.public_ip
            ]
            if instance_ids:
                response = await asyncio.to_thread(
                    ec2.describe_instances, InstanceIds=instance_ids
                )
                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        public_ip = instance.get("PublicIpAddress", "")
                        if public_ip:
                            for status in all_statuses.values():
                                if status.instance_id == instance_id:
                                    status.public_ip = public_ip
                                    events_to_progress.append(status)

        await asyncio.sleep(5)  # Wait 5 seconds before checking again


async def list_spot_instances():
    global all_statuses, events_to_progress, task_total
    all_statuses = {}  # Reset the global statuses

    global task_name
    task_name = "Listing Spot Instances"
    task_total = 0  # We'll update this as we go

    logging.debug("Starting to list spot instances")

    for region in AWS_REGIONS:
        ec2 = get_ec2_client(region)
        try:
            az_response = await asyncio.to_thread(ec2.describe_availability_zones)
            availability_zones = [
                az["ZoneName"] for az in az_response["AvailabilityZones"]
            ]

            for az in availability_zones:
                response = await asyncio.to_thread(
                    ec2.describe_instances,
                    Filters=[
                        {
                            "Name": "instance-state-name",
                            "Values": ["pending", "running", "stopped"],
                        },
                        {"Name": "availability-zone", "Values": [az]},
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
                    ],
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        thisInstanceStatusObject = InstanceStatus(region, az, instance_id)
                        thisInstanceStatusObject.detailed_status = next(
                            (tag['Value'] for tag in instance["Tags"] if tag['Key'] == 'Custom'), None)
                        thisInstanceStatusObject.status = instance["State"]["Name"].capitalize()
                        thisInstanceStatusObject.elapsed_time = ((datetime.now(timezone.utc) - instance["LaunchTime"]).
                                                                 total_seconds())
                        thisInstanceStatusObject.public_ip = instance.get("PublicIpAddress", "")
                        thisInstanceStatusObject.private_ip = instance.get("PrivateIpAddress", "")

                        all_statuses[instance_id] = thisInstanceStatusObject
                        events_to_progress.append(instance_id)
                        task_total = len(all_statuses)  # Increment task_total for each instance found

            logging.debug(f"Found {len(all_statuses)} instances in region {region}")

        except Exception as e:
            logging.error(
                f"An error occurred while listing instances in {region}: {str(e)}"
            )

    logging.debug("Finished listing spot instances")

    return all_statuses


async def destroy_instances():
    instance_region_map = {}

    global task_name, task_total, events_to_progress
    task_name = "Terminating Spot Instances"
    events_to_progress = []

    print("Identifying instances to terminate...")
    for region in AWS_REGIONS:
        ec2 = get_ec2_client(region)
        try:
            response = await asyncio.to_thread(
                ec2.describe_instances,
                Filters=[
                    {
                        "Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping", "stopped"],
                    },
                    {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
                ],
            )

            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    az = instance["Placement"]["AvailabilityZone"]
                    vpc_id = instance.get("VpcId")
                    thisInstanceStatusObject = InstanceStatus(region, az, instance_id)
                    thisInstanceStatusObject.status = "Terminating"
                    thisInstanceStatusObject.detailed_status = (
                        "Initializing termination"
                    )
                    thisInstanceStatusObject.vpc_id = vpc_id
                    all_statuses[instance_id] = thisInstanceStatusObject
                    instance_region_map[instance_id] = {
                        "region": region,
                        "vpc_id": vpc_id,
                    }

        except Exception as e:
            print(f"An error occurred while listing instances in {region}: {str(e)}")

    if not all_statuses:
        print("No instances found to terminate.")
        return

    task_total = len(all_statuses)
    print(f"\nFound {task_total} instances to terminate.")

    async def terminate_instances_in_region(region, region_instances):
        ec2 = get_ec2_client(region)
        try:
            await asyncio.to_thread(
                ec2.terminate_instances, InstanceIds=region_instances
            )
            waiter = ec2.get_waiter("instance_terminated")
            start_time = time.time()
            while True:
                try:
                    await asyncio.to_thread(
                        waiter.wait,
                        InstanceIds=region_instances,
                        WaiterConfig={"MaxAttempts": 1},
                    )
                    break
                except botocore.exceptions.WaiterError:
                    elapsed_time = time.time() - start_time
                    for instance_id in region_instances:
                        thisInstanceStatusObject = all_statuses[instance_id]
                        thisInstanceStatusObject.elapsed_time = elapsed_time
                        thisInstanceStatusObject.detailed_status = (
                            f"Terminating ({elapsed_time:.0f}s)"
                        )
                        events_to_progress.append(thisInstanceStatusObject)
                        all_statuses[instance_id] = thisInstanceStatusObject
                    await asyncio.sleep(10)

            # Update status for terminated instances
            for instance_id in region_instances:
                thisInstanceStatusObject = all_statuses[instance_id]
                thisInstanceStatusObject.status = "Terminated"
                thisInstanceStatusObject.detailed_status = "Instance terminated"
                events_to_progress.append(thisInstanceStatusObject)
                all_statuses[instance_id] = thisInstanceStatusObject

            # Clean up resources for each VPC
            vpcs_to_delete = set(
                info["vpc_id"]
                for info in instance_region_map.values()
                if info["region"] == region and info["vpc_id"]
            )
            for vpc_id in vpcs_to_delete:
                try:
                    for instance_id, status in all_statuses.items():
                        if status.vpc_id == vpc_id:
                            status.detailed_status = "Cleaning up VPC resources"
                            events_to_progress.append(status)

                    await clean_up_vpc_resources(ec2, vpc_id)

                except Exception as e:
                    print(
                        f"An error occurred while cleaning up VPC {vpc_id} in {region}: {str(e)}"
                    )

        except Exception as e:
            print(
                f"An error occurred while cleaning up resources in {region}: {str(e)}"
            )

    # Group instances by region
    region_instances = {}
    for instance_id, info in instance_region_map.items():
        region = info["region"]
        if region not in region_instances:
            region_instances[region] = []
        region_instances[region].append(instance_id)

    # Terminate instances in parallel
    await asyncio.gather(
        *[
            terminate_instances_in_region(region, instances)
            for region, instances in region_instances.items()
        ]
    )

    print("All instances have been terminated.")


async def clean_up_vpc_resources(ec2, vpc_id):
    async def update_status(message):
        for status in all_statuses.values():
            if status.vpc_id == vpc_id:
                status.detailed_status = message

    await update_status("Deleting Security Groups")
    sgs = await asyncio.to_thread(
        ec2.describe_security_groups,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )
    for sg in sgs["SecurityGroups"]:
        if sg["GroupName"] != "default":
            await asyncio.to_thread(ec2.delete_security_group, GroupId=sg["GroupId"])

    await update_status("Deleting Subnets")
    subnets = await asyncio.to_thread(
        ec2.describe_subnets,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )
    for subnet in subnets["Subnets"]:
        await asyncio.to_thread(ec2.delete_subnet, SubnetId=subnet["SubnetId"])

    await update_status("Deleting Route Tables")
    rts = await asyncio.to_thread(
        ec2.describe_route_tables,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )
    for rt in rts["RouteTables"]:
        if not any(
                association.get("Main", False) for association in rt.get("Associations", [])
        ):
            await asyncio.to_thread(
                ec2.delete_route_table,
                RouteTableId=rt["RouteTableId"],
            )

    await update_status("Detaching and Deleting Internet Gateways")
    igws = await asyncio.to_thread(
        ec2.describe_internet_gateways,
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
    )
    for igw in igws["InternetGateways"]:
        await asyncio.to_thread(
            ec2.detach_internet_gateway,
            InternetGatewayId=igw["InternetGatewayId"],
            VpcId=vpc_id,
        )
        await asyncio.to_thread(
            ec2.delete_internet_gateway,
            InternetGatewayId=igw["InternetGatewayId"],
        )

    await update_status("Deleting VPC")
    await asyncio.to_thread(ec2.delete_vpc, VpcId=vpc_id)


async def delete_disconnected_aws_nodes():
    try:
        # Run bacalhau node list command and capture output
        result = subprocess.run(
            ["bacalhau", "node", "list", "--output", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        nodes = json.loads(result.stdout)

        disconnected_aws_nodes = []

        for node in nodes:
            if (
                    node["Connection"] == "DISCONNECTED"
                    and node["Info"]["NodeType"] == "Compute"
                    and "EC2_INSTANCE_FAMILY" in node["Info"]["Labels"]
            ):
                disconnected_aws_nodes.append(node["Info"]["NodeID"])

        if not disconnected_aws_nodes:
            print("No disconnected AWS nodes found.")
            return

        print(f"Found {len(disconnected_aws_nodes)} disconnected AWS node(s).")

        for node_id in disconnected_aws_nodes:
            print(f"Deleting node: {node_id}")
            try:
                # Run bacalhau admin node delete command
                subprocess.run(["bacalhau", "node", "delete", node_id], check=True)
                print(f"Successfully deleted node: {node_id}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to delete node {node_id}. Error: {e}")

    except subprocess.CalledProcessError as e:
        print(f"Error running bacalhau node list: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def all_statuses_to_dict():
    return {
        status.id: {
            "id": status.id,
            "region": status.region,
            "zone": status.zone,
            "status": status.status,
            "detailed_status": status.detailed_status,
            "elapsed_time": status.elapsed_time,
            "instance_id": status.instance_id,
            "public_ip": status.public_ip,
            "private_ip": status.private_ip,
            "vpc_id": status.vpc_id,
        }
        for status in all_statuses.values()
    }


async def main():
    global table_update_running
    table_update_running = False

    parser = argparse.ArgumentParser(
        description="Manage spot instances across multiple AWS regions."
    )
    parser.add_argument(
        "--action",
        choices=["create", "destroy", "list", "delete_disconnected_aws_nodes"],
        help="Action to perform",
        default="list"
    )
    parser.add_argument(
        "--format", choices=["default", "json"], default="default", help="Output format"
    )
    args = parser.parse_args()

    async def perform_action():
        if args.action == "create":
            await create_spot_instances()
        elif args.action == "list":
            await list_spot_instances()
        elif args.action == "destroy":
            await destroy_instances()
        elif args.action == "delete_disconnected_aws_nodes":
            await delete_disconnected_aws_nodes()

    if args.format == "json":
        await perform_action()
        print(json.dumps(all_statuses_to_dict(), indent=2))
    else:
        with Live(console=console, refresh_per_second=20) as live:
            update_task = asyncio.create_task(update_table(live))
            try:
                await perform_action()
                await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Error in main: {str(e)}")
            finally:
                table_update_event.set()
                await update_task


if __name__ == "__main__":
    asyncio.run(main())
