#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "botocore",
#     "pyyaml",
#     "rich",
# ]
# ///


import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

import boto3
import botocore
import rich
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Row, Table

from util.config import Config
from util.scripts_provider import ScriptsProvider

# Tag to filter instances by
FILTER_TAG_NAME = "ManagedBy"
FILTER_TAG_VALUE = "SpotInstanceScript"

# Initialize console with explicit width
console = Console(width=200)

# Configure a logger separate from the root logger to avoid conflicts
logger = logging.getLogger("bacalhau_spot")
logger.setLevel(logging.INFO)  # Default level, will be updated with -v flag

config = Config("config.yaml")
scripts_provider = ScriptsProvider(config)

AWS_REGIONS = config.get_regions()
TOTAL_INSTANCES = config.get_total_instances()
global_node_count = 0
INSTANCES_PER_REGION = (
    TOTAL_INSTANCES // len(AWS_REGIONS)
) or TOTAL_INSTANCES  # Evenly distribute instances if set to 'auto' in config

MAX_NODES = (
    config.get_total_instances()
)  # Global limit for total nodes across all regions
current_dir = os.path.dirname(__file__)

SCRIPT_DIR = "instance/scripts"

all_statuses = {}  # Moved to global scope
global_node_count = 0

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
    def __init__(self, region, zone, index=0, instance_id=None):
        input_string = f"{region}-{zone}-{index}"
        hashed_string = hashlib.sha256(input_string.encode()).hexdigest()

        self.id = hashed_string[:6]
        self.region = region
        self.zone = zone
        self.status = "Initializing"
        self.detailed_status = "Initializing"
        self.elapsed_time = 0
        self.instance_id = instance_id

        if self.instance_id is not None:
            self.id = self.instance_id

        self.public_ip = None
        self.private_ip = None
        self.vpc_id = None

    def combined_status(self):
        return f"{self.status} ({self.detailed_status})"


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
    table = Table(
        show_header=True,
        header_style="bold magenta",
        show_lines=False,
        box=rich.box.ROUNDED,
        title="Instance Status",
    )
    table.overflow = "ellipsis"
    table.add_column("ID", width=5, style="cyan", no_wrap=True)
    table.add_column("Region", width=15, style="green", no_wrap=True)
    table.add_column("Zone", width=15, style="green", no_wrap=True)
    table.add_column("Status", width=15, style="yellow", no_wrap=True)
    table.add_column(
        "Elapsed", width=10, justify="right", style="magenta", no_wrap=True
    )
    table.add_column("Instance ID", width=15, style="blue", no_wrap=True)
    table.add_column("Public IP", width=15, style="blue", no_wrap=True)
    table.add_column("Private IP", width=15, style="blue", no_wrap=True)

    # Sort instances for consistent display
    sorted_statuses = sorted(
        all_statuses.values(),
        key=lambda x: (x.region, x.zone, getattr(x, "instance_id", "")),
    )

    for status in sorted_statuses:
        table.add_row(
            status.id,
            status.region,
            status.zone,
            status.combined_status(),
            format_elapsed_time(status.elapsed_time),
            status.instance_id or "",
            status.public_ip or "",
            status.private_ip or "",
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

    logger.debug(f"update_table called with live object: {type(live)}")
    logger.debug(f"Current task_name: {task_name}, task_total: {task_total}")
    logger.debug(f"Events in queue: {len(events_to_progress)}")
    logger.debug(f"Number of status items: {len(all_statuses)}")

    if table_update_running:
        logger.debug("Table update already running. Exiting.")
        return

    logger.debug("Starting table update.")

    try:
        table_update_running = True
        update_count = 0

        # Start the update loop
        while not table_update_event.is_set():
            update_count += 1
            logger.debug(f"Update iteration {update_count}")

            # Process events
            events_processed = 0
            while events_to_progress:
                event = events_to_progress.pop(0)
                events_processed += 1

                logger.debug(f"Processing event {events_processed}: {type(event)}")

                if isinstance(event, str):
                    # For list operation, event is instance_id
                    logger.debug(f"Setting status 'Listed' for instance_id: {event}")
                    all_statuses[event].status = "Listed"
                else:
                    # For create and destroy operations, event is InstanceStatus object
                    logger.debug(
                        f"Updating status object for id: {event.id}, status: {event.status}"
                    )
                    all_statuses[event.id] = event

            if events_processed > 0:
                logger.debug(f"Processed {events_processed} events")

            # Calculate completed count based on task type
            if task_name == "Creating Instances":
                completed = len(
                    [s for s in all_statuses.values() if s.status != "Initializing"]
                )
                logger.debug(
                    f"Creating Instances: {completed} of {task_total} completed"
                )
            elif task_name == "Terminating Spot Instances":
                completed = len(
                    [s for s in all_statuses.values() if s.status == "Terminated"]
                )
                logger.debug(
                    f"Terminating Instances: {completed} of {task_total} completed"
                )
            elif task_name == "Listing Spot Instances":
                completed = len(
                    [s for s in all_statuses.values() if s.status == "Listed"]
                )
                logger.debug(
                    f"Listing Instances: {completed} of {task_total} completed"
                )
            else:
                completed = 0
                logger.debug(f"Unknown task '{task_name}', defaulting to 0 completed")

            # Create a completely new layout from scratch
            try:
                # Create a new progress component
                progress = Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=None),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("[progress.completed]{task.completed} of {task.total}"),
                    TextColumn("[progress.elapsed]{task.elapsed:>3.0f}s"),
                    expand=True,
                )

                # Add task with current totals
                task = progress.add_task(task_name, total=task_total)
                progress.update(task, completed=completed)

                # Create a fresh table
                table = make_progress_table()

                # Create a completely new layout
                new_layout = create_layout(progress, table)

                # Update the live display with the new layout
                live.update(new_layout)

            except Exception as inner_e:
                logger.error(f"Error during layout update: {str(inner_e)}")
                logger.error(traceback.format_exc())

            # Sleep between updates - increased refresh rate
            await asyncio.sleep(0.05)

    except Exception as e:
        logger.error(f"Error in update_table: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        table_update_running = False
        logger.debug("Table update finished.")


def get_ec2_client(region):
    return boto3.client("ec2", region_name=region)


async def get_availability_zones(ec2):
    response = await asyncio.to_thread(
        ec2.describe_availability_zones,
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}],
    )
    return [zone["ZoneName"] for zone in response["AvailabilityZones"]][
        :1
    ]  # Get 1 AZ per region


async def create_spot_instances_in_region(config: Config, instances_to_create, region):
    global all_statuses, events_to_progress

    ec2 = get_ec2_client(region)
    region_cfg = config.get_region_config(region)

    try:
        user_data = scripts_provider.create_cloud_init_script()
        if not user_data:
            logging.error("User data is empty. Stopping creation.")
            return [], {}

        encoded_user_data = base64.b64encode(user_data.encode()).decode()

        vpc_id = await create_vpc_if_not_exists(ec2)
        igw_id = await create_internet_gateway(ec2, vpc_id)
        route_table_id = await create_route_table(ec2, vpc_id, igw_id)
        security_group_id = await create_security_group_if_not_exists(ec2, vpc_id)

        instance_ids = []
        zones = await get_availability_zones(ec2)
        for i in range(instances_to_create):
            zone = zones[i % len(zones)]  # Distribute instances across available zones

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

            thisInstanceStatusObject = InstanceStatus(region, zone, i)
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
            events_to_progress.append(thisInstanceStatusObject)

            start_time = time.time()
            launch_specification = {
                "ImageId": config.get_image_for_region(region),
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
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
            events_to_progress.append(thisInstanceStatusObject)

            logging.debug(f"Requesting spot instance in {region}-{zone}")
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

            thisInstanceStatusObject.status = "Waiting for fulfillment"
            thisInstanceStatusObject.detailed_status = "Spot request submitted"
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
            events_to_progress.append(thisInstanceStatusObject)

            # Wait for spot instances to be fulfilled
            waiter = ec2.get_waiter("spot_instance_request_fulfilled")
            max_wait_time = 180  # Reduced to 3 minutes to avoid long waits
            start_wait_time = time.time()
            max_check_attempts = 12  # Allow 12 checks before giving up
            check_attempt = 0

            while check_attempt < max_check_attempts:
                check_attempt += 1
                try:
                    thisInstanceStatusObject.detailed_status = f"Waiting for fulfillment (attempt {check_attempt}/{max_check_attempts})"
                    all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                    events_to_progress.append(thisInstanceStatusObject)

                    logging.debug(
                        f"Waiting for spot instance fulfillment in {region}-{zone} (attempt {check_attempt})"
                    )
                    await asyncio.to_thread(
                        waiter.wait,
                        SpotInstanceRequestIds=spot_request_ids,
                        WaiterConfig={"MaxAttempts": 1, "Delay": 5},
                    )
                    logging.debug(f"Spot instance request fulfilled in {region}-{zone}")
                    break
                except botocore.exceptions.WaiterError:
                    thisInstanceStatusObject.elapsed_time = time.time() - start_time
                    if time.time() - start_wait_time > max_wait_time:
                        machine_type = region_cfg.get("machine_type", "t2.medium")
                        logging.error(
                            f"Timeout waiting for spot instance fulfillment in {region}-{zone}"
                        )
                        # Mark this region as having no capacity after timeout
                        regions_with_no_capacity[region] = machine_type

                        # Update the status for UI
                        thisInstanceStatusObject.status = "Timeout"
                        thisInstanceStatusObject.detailed_status = (
                            f"Request timed out for {machine_type}"
                        )
                        all_statuses[thisInstanceStatusObject.id] = (
                            thisInstanceStatusObject
                        )
                        events_to_progress.append(thisInstanceStatusObject)

                        console.print(
                            f"[yellow]Warning:[/yellow] Spot request timed out in {region}-{zone} for instance type {machine_type}"
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
                        machine_type = region_cfg.get("machine_type", "t2.medium")
                        logging.error(
                            f"Spot request failed in {region}-{zone}: {status_code} - {status_message}"
                        )

                        # Update UI based on error type
                        if status_code == "capacity-not-available":
                            # Track regions with no capacity to avoid retrying
                            regions_with_no_capacity[region] = machine_type

                            # Update the status object to reflect no capacity
                            thisInstanceStatusObject.status = "No Capacity"
                            thisInstanceStatusObject.detailed_status = (
                                f"No capacity for {machine_type}"
                            )
                            console.print(
                                f"[yellow]No capacity:[/yellow] Region {region}-{zone} has no capacity for {machine_type}"
                            )
                        elif status_code == "price-too-low":
                            thisInstanceStatusObject.status = "Price Too Low"
                            thisInstanceStatusObject.detailed_status = (
                                f"Spot price too low for {machine_type}"
                            )
                            console.print(
                                f"[yellow]Price too low:[/yellow] Region {region}-{zone} requires higher bid for {machine_type}"
                            )

                        all_statuses[thisInstanceStatusObject.id] = (
                            thisInstanceStatusObject
                        )
                        events_to_progress.append(thisInstanceStatusObject)
                        break

            # Get instance IDs
            zone_instance_ids = [
                request["InstanceId"]
                for request in describe_response["SpotInstanceRequests"]
                if "InstanceId" in request
            ]
            instance_ids.extend(zone_instance_ids)

            if zone_instance_ids:
                thisInstanceStatusObject.instance_id = zone_instance_ids[0]
                thisInstanceStatusObject.status = "Tagging"

                # Tag instances
                await asyncio.to_thread(
                    ec2.create_tags,
                    Resources=zone_instance_ids,
                    Tags=[
                        {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                        {"Key": "Name", "Value": f"SpotInstance-{region}-{zone}"},
                        {"Key": "AZ", "Value": zone},
                    ],
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
                thisInstanceStatusObject.status = "Failed to request spot instance"
                update_all_statuses(thisInstanceStatusObject)

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # Handle different AWS error codes
        if error_code == "InvalidParameterValue" and "InstanceType" in error_message:
            machine_type = region_cfg.get("machine_type", "t2.medium")
            logging.error(f"Invalid instance type in {region}: {error_message}")
            console.print(
                f"[bold red]Error:[/bold red] Instance type '{machine_type}' is not valid in region {region}"
            )

            # Create a status object for UI display
            for zone in ["unavailable"]:
                thisInstanceStatusObject = InstanceStatus(region, zone)
                thisInstanceStatusObject.status = "Error"
                thisInstanceStatusObject.detailed_status = (
                    f"Invalid type: {machine_type}"
                )
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)
        elif error_code == "UnauthorizedOperation":
            logging.error(f"Unauthorized operation in {region}: {error_message}")
            console.print(
                f"[bold red]Error:[/bold red] Unauthorized to create spot instances in region {region}"
            )
        else:
            logging.error(
                f"AWS error in {region}: {error_code} - {error_message}", exc_info=True
            )
            console.print(f"[bold red]Error in {region}:[/bold red] {error_message}")

        return [], {}
    except Exception as e:
        logging.error(f"An error occurred in {region}: {str(e)}", exc_info=True)
        console.print(f"[bold red]Error in {region}:[/bold red] {str(e)}")
        return [], {}

    return instance_ids


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
            cidrBlock = (
                cidr_block
                if cidr_block
                else cidr_base_prefix + str(i) + cidr_base_suffix
            )
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
            ],
        )
        return security_group_id


async def verify_instance_type_for_region(region, instance_type):
    """Verify that the specified instance type is valid in the given region."""
    try:
        ec2 = get_ec2_client(region)
        # Check if the instance type is valid in this region
        response = await asyncio.to_thread(
            ec2.describe_instance_type_offerings,
            LocationType="region",
            Filters=[
                {"Name": "instance-type", "Values": [instance_type]},
                {"Name": "location", "Values": [region]},
            ],
        )
        return len(response.get("InstanceTypeOfferings", [])) > 0
    except Exception as e:
        logging.error(f"Error checking instance type in {region}: {str(e)}")
        return False


# Dictionary to track regions with no spot capacity
regions_with_no_capacity = {}


async def check_common_spot_instance_types(region):
    """Check which common instance types are available in the region."""
    # List of common instance types in order of preference (most reliable first)
    common_types = [
        "t3a.medium",
        "t3.medium",
        "t2.medium",
        "m5a.large",
        "m5.large",
        "c5a.large",
        "c5.large",
    ]

    try:
        ec2 = get_ec2_client(region)
        available_types = []

        # Check each instance type
        for instance_type in common_types:
            try:
                response = await asyncio.to_thread(
                    ec2.describe_instance_type_offerings,
                    LocationType="region",
                    Filters=[
                        {"Name": "instance-type", "Values": [instance_type]},
                        {"Name": "location", "Values": [region]},
                    ],
                )
                if len(response.get("InstanceTypeOfferings", [])) > 0:
                    available_types.append(instance_type)
            except Exception:
                pass

        return available_types
    except Exception as e:
        logging.error(f"Error checking instance types in {region}: {str(e)}")
        return []


async def create_spot_instances():
    global task_name, task_total, regions_with_no_capacity, table_update_event

    # Clear any existing data
    all_statuses.clear()
    events_to_progress.clear()
    regions_with_no_capacity.clear()

    # Set up the live display first before any other operations
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        expand=True,
    )
    task_id = progress.add_task("[cyan]Preparing spot instances...", total=100)

    # Initial table
    status_table = Table(
        title="Spot Instance Status", show_header=True, box=rich.box.ROUNDED
    )
    status_table.add_column("Region", style="cyan", no_wrap=True)
    status_table.add_column("Type", style="green", no_wrap=True)
    status_table.add_column("Status", style="yellow")

    # Create layout
    layout = Layout()
    layout.split(
        Layout(Panel(progress, title="Progress", border_style="green"), size=3),
        Layout(Panel(status_table, title="Region Status", border_style="blue")),
    )

    # Start the live display
    with Live(layout, refresh_per_second=4, console=console) as live:
        # First phase: Check all regions for valid instance types
        progress.update(
            task_id,
            description="[cyan]Checking available instance types in regions...",
            completed=10,
        )

        region_instance_types = {}
        for i, region in enumerate(AWS_REGIONS):
            progress_pct = 10 + (i / len(AWS_REGIONS) * 20)  # Progress from 10% to 30%
            progress.update(task_id, completed=int(progress_pct))

            # Add row to table showing checking status
            status_table.add_row(region, "...", "Checking available types")
            live.update(layout)

            # Check what instance types are available
            available_types = await check_common_spot_instance_types(region)

            if available_types:
                # Use the first available type (most reliable from the list)
                region_instance_types[region] = available_types[0]
                status_table.rows[-1] = Row(
                    region, available_types[0], "Type available"
                )
            else:
                status_table.rows[-1] = Row(
                    region, "None", "[red]No suitable types[/red]"
                )

            live.update(layout)

        # Update progress for next phase
        progress.update(
            task_id, description="[cyan]Setting up instance creation...", completed=30
        )
        live.update(layout)

        # Set task details for the instance creation process
        task_name = "Creating Spot Instances"
        task_total = 0  # Will be updated as we determine actual instances to create

        # Collect regions with valid instance types
        valid_regions = [r for r in AWS_REGIONS if r in region_instance_types]
        if not valid_regions:
            progress.update(
                task_id,
                description="[red]No valid regions found with suitable instance types",
                completed=100,
            )
            status_table.add_row("N/A", "N/A", "[red]No valid regions available[/red]")
            live.update(layout)
            await asyncio.sleep(2)  # Give user time to see the message
            return

        # Figure out instances per region
        instances_per_valid_region = MAX_NODES // len(valid_regions) or 1
        task_total = instances_per_valid_region * len(valid_regions)

        # Update progress
        progress.update(
            task_id,
            description=f"[cyan]Creating {task_total} spot instances across {len(valid_regions)} regions...",
            completed=40,
        )
        live.update(layout)

        # Start a task to update the table periodically
        table_update_event.clear()
        update_task = asyncio.create_task(update_table(live))

        try:
            # Create instances in parallel in valid regions
            async def create_in_region(region):
                global global_node_count

                # Calculate instances to create
                available_slots = MAX_NODES - global_node_count
                if available_slots <= 0:
                    logging.warning(f"Reached maximum nodes. Skipping region: {region}")
                    return [], {}

                instances_to_create = min(instances_per_valid_region, available_slots)

                # Update config with best instance type for the region
                region_cfg = config.get_region_config(region)
                region_cfg["machine_type"] = region_instance_types[region]

                # Create status row in table
                status_table.add_row(
                    region,
                    region_instance_types[region],
                    f"Creating {instances_to_create} instances",
                )
                live.update(layout)

                # Create the instances
                logging.debug(
                    f"Creating {instances_to_create} spot instances in region: {region}"
                )
                global_node_count += instances_to_create
                instance_ids = await create_spot_instances_in_region(
                    config, instances_to_create, region
                )

                # Update status
                for i, r in enumerate(status_table.rows):
                    if r[0] == region:
                        status = "Success" if instance_ids else "[red]Failed[/red]"
                        status_table.rows[i] = Row(
                            region, region_instance_types[region], status
                        )
                        break

                live.update(layout)
                return instance_ids

            # Launch creation tasks
            tasks = [create_in_region(region) for region in valid_regions]
            results = await asyncio.gather(*tasks)

            # Update progress
            progress.update(
                task_id, description="[green]Finalizing spot instances...", completed=90
            )
            live.update(layout)

            # Wait for public IPs
            logging.debug("Waiting for public IP addresses...")
            await wait_for_public_ips()

            # Complete progress
            progress.update(
                task_id,
                description="[green]Spot instance creation complete",
                completed=100,
            )

            # Final status update
            successful_count = sum(1 for ids in results if ids)
            total_instances = sum(len(ids) for ids in results if ids)

            status_table.add_row(
                "SUMMARY",
                f"{total_instances} instances",
                f"[green]{successful_count}/{len(valid_regions)} regions successful[/green]",
            )
            live.update(layout)

            # Give user time to see final status
            await asyncio.sleep(2)

        finally:
            # Stop the table update task
            table_update_event.set()
            try:
                await update_task
            except asyncio.CancelledError:
                pass

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
                    ec2.describe_instances,
                    InstanceIds=instance_ids,
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
    events_to_progress = []  # Clear the events list

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
                        {
                            "Name": f"tag:{FILTER_TAG_NAME}",
                            "Values": [FILTER_TAG_VALUE],
                        },
                    ],
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        thisInstanceStatusObject = InstanceStatus(
                            region, az, 0, instance_id
                        )
                        thisInstanceStatusObject.status = instance["State"][
                            "Name"
                        ].capitalize()
                        thisInstanceStatusObject.elapsed_time = (
                            datetime.now(timezone.utc) - instance["LaunchTime"]
                        ).total_seconds()
                        thisInstanceStatusObject.public_ip = instance.get(
                            "PublicIpAddress", ""
                        )
                        thisInstanceStatusObject.private_ip = instance.get(
                            "PrivateIpAddress", ""
                        )

                        events_to_progress.append(instance_id)
                        all_statuses[instance_id] = thisInstanceStatusObject
                        task_total += 1  # Increment task_total for each instance found

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

    # Use console.status for the search phase
    with console.status(
        "[bold blue]Identifying instances to terminate...", spinner="dots"
    ):
        logger.debug(f"Looking in {len(AWS_REGIONS)} regions: {AWS_REGIONS}")
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
                        {
                            "Name": f"tag:{FILTER_TAG_NAME}",
                            "Values": [FILTER_TAG_VALUE],
                        },
                    ],
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        az = instance["Placement"]["AvailabilityZone"]
                        vpc_id = instance.get("VpcId")
                        thisInstanceStatusObject = InstanceStatus(region, az)
                        thisInstanceStatusObject.instance_id = instance_id
                        thisInstanceStatusObject.status = "Terminating"
                        thisInstanceStatusObject.detailed_status = (
                            "Identifying instances"
                        )
                        thisInstanceStatusObject.vpc_id = vpc_id
                        all_statuses[instance_id] = thisInstanceStatusObject
                        instance_region_map[instance_id] = {
                            "region": region,
                            "vpc_id": vpc_id,
                        }
                        # Add to events to trigger UI update
                        events_to_progress.append(thisInstanceStatusObject)

            except Exception as e:
                logger.error(
                    f"An error occurred while listing instances in {region}: {str(e)}"
                )

    if not all_statuses:
        console.print("[yellow]No instances found to terminate.[/yellow]")
        return

    task_total = len(all_statuses)
    console.print(f"[bold blue]Found {task_total} instances to terminate.[/bold blue]")

    # Create a progress bar for the termination process
    progress_bar = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        expand=True,
    )

    # Create a table for instance status
    status_table = Table(
        title="Instance Status",
        show_header=True,
        header_style="bold magenta",
        box=rich.box.ROUNDED,
    )
    status_table.add_column("Instance ID", style="cyan", no_wrap=True)
    status_table.add_column("Region", style="green", no_wrap=True)
    status_table.add_column("Status", style="yellow")
    status_table.add_column("Elapsed", style="magenta", justify="right")
    status_table.add_column("Details", style="blue")

    # Combine them in a single layout
    layout = Layout()
    layout.split(
        Layout(Panel(progress_bar, title="Progress", border_style="green"), size=5),
        Layout(Panel(status_table, title="Instances", border_style="blue")),
    )

    # Function to update the table inside the Live context
    def update_table():
        nonlocal status_table
        # Clear the table and rebuild it entirely
        status_table.rows.clear()

        # Sort instances for consistent display
        sorted_instances = sorted(
            all_statuses.values(),
            key=lambda x: (
                x.status != "Terminated",
                x.region,
                getattr(x, "instance_id", ""),
            ),
        )

        # Add rows to the table
        for status in sorted_instances:
            if hasattr(status, "instance_id") and status.instance_id:
                status_table.add_row(
                    status.instance_id,
                    status.region,
                    status.status,
                    format_elapsed_time(status.elapsed_time),
                    getattr(status, "detailed_status", ""),
                )

    # Create the task for tracking overall progress
    async def terminate_instances_in_region(region, region_instances):
        ec2 = get_ec2_client(region)
        try:
            # Request termination
            logger.debug(
                f"Requesting termination for {len(region_instances)} instances in {region}"
            )
            await asyncio.to_thread(
                ec2.terminate_instances, InstanceIds=region_instances
            )

            # Update status immediately after request
            for instance_id in region_instances:
                if instance_id in all_statuses:
                    thisInstanceStatusObject = all_statuses[instance_id]
                    thisInstanceStatusObject.elapsed_time = 0
                    thisInstanceStatusObject.status = "Terminating"
                    thisInstanceStatusObject.detailed_status = "Termination requested"
                    all_statuses[instance_id] = thisInstanceStatusObject

            # Wait for termination to complete
            waiter = ec2.get_waiter("instance_terminated")
            start_time = time.time()

            # Check status more frequently
            last_check_time = 0
            update_interval = (
                2  # Seconds between instance status updates (reduced from 5)
            )

            while True:
                try:
                    await asyncio.to_thread(
                        waiter.wait,
                        InstanceIds=region_instances,
                        WaiterConfig={"MaxAttempts": 1},
                    )
                    logger.debug(f"All instances in {region} terminated")
                    break
                except botocore.exceptions.WaiterError:
                    current_time = time.time()
                    elapsed_time = current_time - start_time

                    # Check status more often than the waiter can
                    if current_time - last_check_time >= update_interval:
                        last_check_time = current_time
                        # Get current status of all instances
                        try:
                            logger.debug(f"Checking status of instances in {region}")
                            response = await asyncio.to_thread(
                                ec2.describe_instances, InstanceIds=region_instances
                            )

                            # Update status for each instance based on current state
                            for reservation in response.get("Reservations", []):
                                for instance in reservation.get("Instances", []):
                                    instance_id = instance["InstanceId"]
                                    if instance_id in all_statuses:
                                        state = instance.get("State", {}).get(
                                            "Name", "unknown"
                                        )
                                        thisInstanceStatusObject = all_statuses[
                                            instance_id
                                        ]
                                        thisInstanceStatusObject.elapsed_time = (
                                            elapsed_time
                                        )

                                        if state == "shutting-down":
                                            thisInstanceStatusObject.status = (
                                                "ShuttingDown"
                                            )
                                            thisInstanceStatusObject.detailed_status = (
                                                "In progress"
                                            )
                                        elif state == "terminated":
                                            thisInstanceStatusObject.status = (
                                                "Terminated"
                                            )
                                            thisInstanceStatusObject.detailed_status = (
                                                "Instance terminated"
                                            )
                                            # Update completed count
                                            completed_count = sum(
                                                1
                                                for s in all_statuses.values()
                                                if s.status == "Terminated"
                                            )
                                            # Update the progress - task_id is defined in the outer scope
                                            try:
                                                progress_bar.update(
                                                    main_task_id,
                                                    completed=completed_count,
                                                )
                                            except Exception as e:
                                                logger.debug(
                                                    f"Error updating progress: {e}"
                                                )
                                        else:
                                            thisInstanceStatusObject.status = (
                                                state.capitalize()
                                            )
                                            thisInstanceStatusObject.detailed_status = (
                                                f"State: {state}"
                                            )

                                        all_statuses[instance_id] = (
                                            thisInstanceStatusObject
                                        )
                                        logger.debug(
                                            f"Updated instance {instance_id} status to {state}"
                                        )
                        except Exception as status_e:
                            logger.error(f"Error checking instance status: {status_e}")

                    # Update elapsed time even if we didn't check full status
                    for instance_id in region_instances:
                        if instance_id in all_statuses:
                            all_statuses[instance_id].elapsed_time = elapsed_time

                    # Wait before next check
                    await asyncio.sleep(1)  # Reduced from 2

            # Update status for terminated instances
            for instance_id in region_instances:
                thisInstanceStatusObject = all_statuses[instance_id]
                thisInstanceStatusObject.status = "Terminated"
                thisInstanceStatusObject.detailed_status = "Instance terminated"
                all_statuses[instance_id] = thisInstanceStatusObject

            # Update the progress once for all the terminated instances
            completed_count = sum(
                1 for s in all_statuses.values() if s.status == "Terminated"
            )
            # Update the progress - task_id is defined in the outer scope
            try:
                progress_bar.update(main_task_id, completed=completed_count)
            except Exception as e:
                logger.debug(f"Error updating progress: {e}")

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
                            all_statuses[instance_id] = status

                    await clean_up_vpc_resources(ec2, vpc_id)

                except Exception as e:
                    logger.error(
                        f"An error occurred while cleaning up VPC {vpc_id} in {region}: {str(e)}"
                    )

        except Exception as e:
            logger.error(
                f"An error occurred while cleaning up resources in {region}: {str(e)}"
            )

    # Group instances by region
    region_instances = {}
    for instance_id, info in instance_region_map.items():
        region = info["region"]
        if region not in region_instances:
            region_instances[region] = []
        region_instances[region].append(instance_id)

    # Create a Live display for the termination process
    with Live(layout, refresh_per_second=10, console=console):  # Increased from 4
        # Create a main task to track overall progress
        main_task_id = progress_bar.add_task(
            f"[cyan]Terminating {task_total} instances...", total=task_total
        )

        # Start an async task to update the table periodically
        async def refresh_display():
            while True:
                update_table()  # Update the table with fresh data
                await asyncio.sleep(
                    0.25
                )  # Update 4 times per second (reduced from 0.5)

        # Start the refresh task
        refresh_task = asyncio.create_task(refresh_display())

        try:
            # Terminate instances in parallel
            await asyncio.gather(
                *[
                    terminate_instances_in_region(region, instances)
                    for region, instances in region_instances.items()
                ]
            )
        finally:
            # Clean up the refresh task
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass

    # Print a summary after the live display is done
    console.print(
        "\n[bold green]All instances have been terminated successfully![/bold green]"
    )

    # Print a summary table
    summary_table = Table(
        show_header=True, title="Termination Summary", box=rich.box.ROUNDED
    )
    summary_table.add_column("Status", style="cyan")
    summary_table.add_column("Count", style="magenta", justify="right")

    status_counts = {}
    for status in all_statuses.values():
        if status.status not in status_counts:
            status_counts[status.status] = 0
        status_counts[status.status] += 1

    for status, count in status_counts.items():
        summary_table.add_row(status, str(count))

    summary_table.add_row("Total", str(len(all_statuses)), style="bold")

    console.print(summary_table)


async def clean_up_vpc_resources(ec2, vpc_id):
    # Helper function to update status of all instances with this VPC ID
    def update_vpc_instance_status(message):
        for instance_id, status in all_statuses.items():
            if hasattr(status, "vpc_id") and status.vpc_id == vpc_id:
                status.detailed_status = message
                all_statuses[instance_id] = status

    try:
        # Clean up network interfaces first
        update_vpc_instance_status("Deleting Network Interfaces")
        network_interfaces = await asyncio.to_thread(
            ec2.describe_network_interfaces,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        for eni in network_interfaces.get("NetworkInterfaces", []):
            try:
                eni_id = eni["NetworkInterfaceId"]
                # Detach if attached
                if eni.get("Attachment"):
                    attachment_id = eni["Attachment"].get("AttachmentId")
                    if attachment_id:
                        logging.debug(f"Detaching network interface {eni_id}")
                        await asyncio.to_thread(
                            ec2.detach_network_interface,
                            AttachmentId=attachment_id,
                            Force=True,
                        )
                        # Give AWS time to detach
                        await asyncio.sleep(3)

                # Delete the interface
                logging.debug(f"Deleting network interface {eni_id}")
                await asyncio.to_thread(
                    ec2.delete_network_interface, NetworkInterfaceId=eni_id
                )
            except Exception as e:
                logging.error(f"Error deleting network interface: {str(e)}")

        # Clean up security group rules first to avoid dependency issues
        update_vpc_instance_status("Cleaning Security Group Rules")
        sgs = await asyncio.to_thread(
            ec2.describe_security_groups,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )

        for sg in sgs["SecurityGroups"]:
            sg_id = sg["GroupId"]

            # Skip default security group for now
            if sg["GroupName"] == "default":
                continue

            # Remove all ingress rules
            if sg.get("IpPermissions"):
                try:
                    await asyncio.to_thread(
                        ec2.revoke_security_group_ingress,
                        GroupId=sg_id,
                        IpPermissions=sg["IpPermissions"],
                    )
                except Exception as e:
                    logging.error(
                        f"Error removing ingress rules from {sg_id}: {str(e)}"
                    )

            # Remove all egress rules
            if sg.get("IpPermissionsEgress"):
                try:
                    await asyncio.to_thread(
                        ec2.revoke_security_group_egress,
                        GroupId=sg_id,
                        IpPermissions=sg["IpPermissionsEgress"],
                    )
                except Exception as e:
                    logging.error(f"Error removing egress rules from {sg_id}: {str(e)}")

        # Now delete the security groups
        update_vpc_instance_status("Deleting Security Groups")
        for sg in sgs["SecurityGroups"]:
            if sg["GroupName"] != "default":
                try:
                    await asyncio.to_thread(
                        ec2.delete_security_group, GroupId=sg["GroupId"]
                    )
                except Exception as e:
                    logging.error(
                        f"Error deleting security group {sg['GroupId']}: {str(e)}"
                    )

        # Delete subnets
        update_vpc_instance_status("Deleting Subnets")
        subnets = await asyncio.to_thread(
            ec2.describe_subnets,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        for subnet in subnets["Subnets"]:
            try:
                await asyncio.to_thread(ec2.delete_subnet, SubnetId=subnet["SubnetId"])
            except Exception as e:
                logging.error(f"Error deleting subnet {subnet['SubnetId']}: {str(e)}")

        # Handle route tables
        update_vpc_instance_status("Deleting Route Tables")
        rts = await asyncio.to_thread(
            ec2.describe_route_tables,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )

        for rt in rts["RouteTables"]:
            # First, delete all non-local routes
            for route in rt.get("Routes", []):
                # Skip the local route (can't be deleted)
                if route.get("GatewayId") == "local":
                    continue

                try:
                    if "DestinationCidrBlock" in route:
                        await asyncio.to_thread(
                            ec2.delete_route,
                            RouteTableId=rt["RouteTableId"],
                            DestinationCidrBlock=route["DestinationCidrBlock"],
                        )
                except Exception as e:
                    logging.error(f"Error deleting route: {str(e)}")

            # Disassociate from any subnets (except main associations)
            for assoc in rt.get("Associations", []):
                if assoc.get("Main", False):
                    continue

                if "RouteTableAssociationId" in assoc:
                    try:
                        await asyncio.to_thread(
                            ec2.disassociate_route_table,
                            AssociationId=assoc["RouteTableAssociationId"],
                        )
                    except Exception as e:
                        logging.error(f"Error disassociating route table: {str(e)}")

            # Only delete non-main route tables
            if not any(
                assoc.get("Main", False) for assoc in rt.get("Associations", [])
            ):
                try:
                    await asyncio.to_thread(
                        ec2.delete_route_table,
                        RouteTableId=rt["RouteTableId"],
                    )
                except Exception as e:
                    logging.error(
                        f"Error deleting route table {rt['RouteTableId']}: {str(e)}"
                    )

        # Handle internet gateways
        update_vpc_instance_status("Detaching and Deleting Internet Gateways")
        igws = await asyncio.to_thread(
            ec2.describe_internet_gateways,
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
        )
        for igw in igws["InternetGateways"]:
            try:
                await asyncio.to_thread(
                    ec2.detach_internet_gateway,
                    InternetGatewayId=igw["InternetGatewayId"],
                    VpcId=vpc_id,
                )
                await asyncio.to_thread(
                    ec2.delete_internet_gateway,
                    InternetGatewayId=igw["InternetGatewayId"],
                )
            except Exception as e:
                logging.error(
                    f"Error handling internet gateway {igw['InternetGatewayId']}: {str(e)}"
                )

        # Finally delete the VPC
        update_vpc_instance_status("Deleting VPC")
        try:
            await asyncio.to_thread(ec2.delete_vpc, VpcId=vpc_id)
            logging.info(f"Successfully deleted VPC {vpc_id}")
        except Exception as e:
            logging.error(f"Error deleting VPC {vpc_id}: {str(e)}")
            update_vpc_instance_status(f"Error cleaning up resources: {str(e)}")

    except Exception as e:
        logging.error(f"Error in clean_up_vpc_resources: {str(e)}")
        update_vpc_instance_status(f"Error cleaning up resources: {str(e)}")


async def delete_disconnected_aws_nodes():
    global task_name, task_total, events_to_progress
    task_name = "Deleting Disconnected AWS Nodes"
    events_to_progress = []

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
            logging.info("No disconnected AWS nodes found.")
            return

        logging.info(f"Found {len(disconnected_aws_nodes)} disconnected AWS node(s).")
        task_total = len(disconnected_aws_nodes)

        # Create status objects for the nodes
        for i, node_id in enumerate(disconnected_aws_nodes):
            # Use a placeholder region/zone since we don't know the actual ones
            thisNodeStatusObject = InstanceStatus("unknown", "unknown", i)
            thisNodeStatusObject.id = node_id[:6]  # Use first 6 chars as ID
            thisNodeStatusObject.instance_id = node_id
            thisNodeStatusObject.status = "Identified"
            thisNodeStatusObject.detailed_status = "Preparing to delete"
            all_statuses[thisNodeStatusObject.id] = thisNodeStatusObject
            events_to_progress.append(thisNodeStatusObject)

        for i, node_id in enumerate(disconnected_aws_nodes):
            node_short_id = node_id[:6]
            logging.info(f"Deleting node: {node_id}")

            # Update status
            if node_short_id in all_statuses:
                all_statuses[node_short_id].status = "Deleting"
                all_statuses[node_short_id].detailed_status = "Executing delete command"
                events_to_progress.append(all_statuses[node_short_id])

            try:
                # Run bacalhau admin node delete command
                subprocess.run(["bacalhau", "node", "delete", node_id], check=True)

                # Update status
                if node_short_id in all_statuses:
                    all_statuses[node_short_id].status = "Deleted"
                    all_statuses[
                        node_short_id
                    ].detailed_status = "Node successfully deleted"
                    events_to_progress.append(all_statuses[node_short_id])

                logging.info(f"Successfully deleted node: {node_id}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to delete node {node_id}. Error: {e}")

                # Update status
                if node_short_id in all_statuses:
                    all_statuses[node_short_id].status = "Failed"
                    all_statuses[node_short_id].detailed_status = f"Error: {str(e)}"
                    events_to_progress.append(all_statuses[node_short_id])

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running bacalhau node list: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON output: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


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


def setup_logging(verbose=False):
    """Configure logging with verbose option and debug file."""
    global logger

    # Remove any existing handlers to start fresh
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set log level based on verbose flag
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Always add a console handler for normal output
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)  # Console only shows INFO and above
    console_formatter = logging.Formatter("%(message)s")  # Simple format for console
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Add file handler for debug logs
    if verbose:
        # Truncate the debug log file when verbose mode is enabled
        file_handler = logging.FileHandler("debug.log", mode="w")  # 'w' mode truncates
    else:
        file_handler = logging.FileHandler("debug.log", mode="a")  # 'a' mode appends

    file_handler.setLevel(logging.DEBUG)  # File gets all logs
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Log initial startup message with version info
    logger.debug("=" * 50)
    logger.debug(f"Script started at {datetime.now().isoformat()}")
    logger.debug(f"Python version: {sys.version}")

    # Get Rich version safely
    try:
        import importlib.metadata

        rich_version = importlib.metadata.version("rich")
    except Exception:
        try:
            rich_version = getattr(rich, "__version__", "unknown")
        except Exception:
            rich_version = "unknown"
    logger.debug(f"Rich version: {rich_version}")

    # Get Boto3 version safely
    try:
        boto3_version = getattr(boto3, "__version__", "unknown")
    except Exception:
        boto3_version = "unknown"
    logger.debug(f"Boto3 version: {boto3_version}")

    logger.debug("=" * 50)

    # Disable loggers from other libraries to avoid spam
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


async def verify_aws_credentials():
    """Verify AWS credentials and SSO token are valid before proceeding."""
    try:
        # Use a simple region that's likely to be available
        test_region = "us-east-1"
        ec2 = get_ec2_client(test_region)

        # Try a simple API call that requires valid credentials
        await asyncio.to_thread(ec2.describe_regions, RegionNames=[test_region])

        # If the call succeeds, credentials are valid
        logger.debug("AWS credentials verification successful")
        return True
    except botocore.exceptions.ClientError as e:
        error_msg = str(e)

        # Check specifically for token errors
        if "Token" in error_msg and ("expired" in error_msg or "invalid" in error_msg):
            console.print(f"[bold red]AWS Token Error: {error_msg}[/bold red]")
            console.print(
                "[yellow]Your AWS token has expired or is invalid. Please refresh your AWS credentials.[/yellow]"
            )
            console.print(
                "[yellow]Try running: 'aws sso login' or refresh your credentials in your AWS config.[/yellow]"
            )
            return False
        elif "AccessDenied" in error_msg or "NotAuthorized" in error_msg:
            console.print(f"[bold red]AWS Access Error: {error_msg}[/bold red]")
            console.print(
                "[yellow]You don't have sufficient permissions to access AWS resources.[/yellow]"
            )
            return False
        else:
            console.print(f"[bold red]AWS Credentials Error: {error_msg}[/bold red]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error verifying AWS credentials: {str(e)}[/bold red]")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Manage spot instances across multiple AWS regions."
    )
    parser.add_argument(
        "--action",
        choices=["create", "destroy", "list", "delete_disconnected_aws_nodes"],
        help="Action to perform",
        default="list",
    )
    parser.add_argument(
        "--format", choices=["default", "json"], default="default", help="Output format"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging to debug.log",
    )
    parser.add_argument(
        "--skip-aws-check",
        action="store_true",
        help="Skip AWS credentials verification",
    )
    args = parser.parse_args()

    # Set up logging with verbose flag
    setup_logging(args.verbose)

    logger.debug(f"Main function started with args: {args}")
    logger.debug(f"action={args.action}, format={args.format}, verbose={args.verbose}")

    # Verify AWS credentials before proceeding
    if not args.skip_aws_check:
        logger.debug("Verifying AWS credentials")
        credentials_valid = await verify_aws_credentials()
        if not credentials_valid:
            logger.error("AWS credentials verification failed. Exiting.")
            return

    # Perform the selected action directly
    if args.action == "create":
        logger.debug("Starting create_spot_instances")
        await create_spot_instances()
    elif args.action == "list":
        logger.debug("Starting list_spot_instances")
        await list_spot_instances()

        # Display the results
        if args.format == "json":
            result = json.dumps(all_statuses_to_dict(), indent=2)
            sys.stdout.write(f"{result}\n")
            sys.stdout.flush()
        else:
            # Display a nice table of instances
            table = Table(show_header=True, title="Spot Instances")
            table.add_column("Instance ID", style="cyan", no_wrap=True)
            table.add_column("Region", style="green", no_wrap=True)
            table.add_column("AZ", style="green", no_wrap=True)
            table.add_column("Status", style="yellow")
            table.add_column("IP Address", style="blue")
            table.add_column("Uptime", style="magenta", justify="right")

            # Sort instances
            sorted_instances = sorted(
                all_statuses.values(),
                key=lambda x: (x.region, x.zone, getattr(x, "instance_id", "")),
            )

            for status in sorted_instances:
                if hasattr(status, "instance_id") and status.instance_id:
                    table.add_row(
                        status.instance_id,
                        status.region,
                        status.zone,
                        status.status,
                        status.public_ip or "",
                        format_elapsed_time(status.elapsed_time),
                    )

            # Print the table
            console.print(table)

    elif args.action == "destroy":
        logger.debug("Starting destroy_instances")
        await destroy_instances()
    elif args.action == "delete_disconnected_aws_nodes":
        logger.debug("Starting delete_disconnected_aws_nodes")
        await delete_disconnected_aws_nodes()

    logger.debug(f"Action {args.action} completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # For fatal errors at the program level, it's safe to use print directly
        # because the Live display would already be torn down due to the exception
        sys.stderr.write(f"Fatal error: {e}\n")
        sys.stderr.write("Check debug.log for more details\n")
        sys.stderr.flush()

        # Try to log the error even if logging isn't set up yet
        try:
            logging.basicConfig(
                filename="debug.log",
                level=logging.DEBUG,
                format="%(asctime)s - %(levelname)s - %(message)s",
            )
            logging.error(f"Fatal error: {e}")
            logging.error(traceback.format_exc())
        except Exception as e:
            # Last resort: write directly to debug.log
            with open("debug.log", "a") as f:
                f.write(f"\n\nFatal error: {e}\n")
                f.write(traceback.format_exc())
