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
from concurrent.futures import TimeoutError
from datetime import datetime, timezone

import boto3
import botocore
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from util.config import Config
from util.scripts_provider import ScriptsProvider

# Formatter for logs
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# We'll configure the logger later after parsing command-line arguments
# to respect the verbose flag
file_handler = None
logging.basicConfig(level=logging.INFO)  # Default to INFO level

logger = logging.getLogger(__name__)

# Tag to filter instances by
FILTER_TAG_NAME = "ManagedBy"
FILTER_TAG_VALUE = "SpotInstanceScript"

# Initialize console with auto-detection of width
console = Console()

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

# Status tracking
all_statuses = {}  # Dictionary to track all instance statuses
status_lock = asyncio.Lock()  # Lock for thread-safe updates to all_statuses

# Event for signaling the table update task to stop
table_update_event = asyncio.Event()

# Task tracking
task_name = "TASK NAME"
task_total = 10000
events_to_progress = []

# AWS API timeouts
AWS_API_TIMEOUT = 30  # seconds


async def update_status(status):
    """Thread-safe update of instance status"""
    async with status_lock:
        all_statuses[status.id] = status
        # Add to events queue for progress tracking
        events_to_progress.append(status)


class InstanceStatus:
    def __init__(self, region, zone, index=0, instance_id=None):
        input_string = f"{region}-{zone}-{index}"
        hashed_string = hashlib.sha256(input_string.encode()).hexdigest()

        self.id = hashed_string[:6]
        self.region = region
        self.zone = zone
        self.status = "Initializing"
        self.detailed_status = "Initializing"
        self.start_time = time.time()
        self.elapsed_time = 0
        self.instance_id = instance_id
        self.public_ip = None
        self.private_ip = None
        self.vpc_id = None

        if self.instance_id is not None:
            self.id = self.instance_id

    def update_elapsed_time(self):
        self.elapsed_time = time.time() - self.start_time
        return self.elapsed_time

    def combined_status(self):
        if self.detailed_status and self.detailed_status != self.status:
            combined = f"{self.detailed_status}"
            if len(combined) > 30:
                return combined[:27] + "..."
            return combined
        return self.status


def format_elapsed_time(seconds):
    """Format elapsed time in a human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def make_progress_table():
    """Create a table showing instance status with adaptive column widths"""
    # Get terminal width
    width = console.width

    # Calculate column widths based on available space
    id_width = 6
    region_width = min(15, max(10, int(width * 0.10)))
    zone_width = min(15, max(10, int(width * 0.10)))
    status_width = min(30, max(20, int(width * 0.20)))  # Wider status column
    elapsed_width = 8
    instance_id_width = min(20, max(10, int(width * 0.12)))
    ip_width = min(15, max(10, int(width * 0.08)))

    # Create table with adaptive column widths
    table = Table(show_header=True, header_style="bold magenta", expand=False)

    # Add columns with appropriate widths
    table.add_column("ID", width=id_width, style="cyan", no_wrap=True)
    table.add_column("Region", width=region_width, style="cyan", no_wrap=True)
    table.add_column("Zone", width=zone_width, style="cyan", no_wrap=True)
    table.add_column("Status", width=status_width, style="yellow", no_wrap=True)
    table.add_column(
        "Time", width=elapsed_width, justify="right", style="magenta", no_wrap=True
    )
    table.add_column("Instance ID", width=instance_id_width, style="blue", no_wrap=True)
    table.add_column("Public IP", width=ip_width, style="green", no_wrap=True)
    table.add_column("Private IP", width=ip_width, style="blue", no_wrap=True)

    # Update elapsed time for all statuses
    for status in all_statuses.values():
        status.update_elapsed_time()

    # Sort statuses for consistent display
    sorted_statuses = sorted(all_statuses.values(), key=lambda x: (x.region, x.zone))

    # Add rows to the table
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
    """Create a responsive layout that adapts to terminal size"""
    layout = Layout()

    # Calculate panel heights based on terminal height
    height = console.height
    progress_height = min(4, max(3, int(height * 0.1)))  # 10% for progress
    console_height = min(6, max(4, int(height * 0.2)))  # 20% for console

    # Create progress panel
    progress_panel = Panel(
        progress,
        title="Progress",
        border_style="green",
        padding=(1, 1),
    )

    # Create console panel for log messages
    console_panel = Panel(
        "",  # Start with empty content
        title="Console Output",
        border_style="blue",
        padding=(0, 1),
    )

    # Split layout with responsive sizing
    layout.split(
        Layout(progress_panel, size=progress_height),
        Layout(table),  # This will take the remaining space (about 70%)
        Layout(console_panel, size=console_height),
    )

    return layout


# Configure console handler to use rich console
class RichConsoleHandler(logging.Handler):
    def __init__(self, live, layout):
        super().__init__()
        self.live = live
        self.layout = layout  # Store the layout directly
        self.messages = ["Waiting for log messages..."]  # Start with a default message
        self.setFormatter(logging.Formatter("%(message)s"))
        self.setLevel(logging.INFO)

        # Initialize the console panel content right away
        console_panel = self.layout.children[-1].renderable
        console_panel.renderable = "\n".join(self.messages)

    def emit(self, record):
        try:
            msg = self.format(record)

            # If we still have the default message, clear it first
            if (
                len(self.messages) == 1
                and self.messages[0] == "Waiting for log messages..."
            ):
                self.messages = []

            self.messages.append(msg)

            # Keep only the last 10 messages
            if len(self.messages) > 10:
                self.messages = self.messages[-10:]

            # If no messages (unlikely now), show the waiting message
            if not self.messages:
                self.messages = ["Waiting for log messages..."]

            # Update the console panel content
            console_panel = self.layout.children[-1].renderable
            console_panel.renderable = "\n".join(self.messages)
        except Exception:
            self.handleError(record)


async def update_display(live):
    """Update the live display with current status information"""
    logger.debug("Entering update_display function")
    try:
        logger.debug("Creating progress bar")
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed} of {task.total}"),
            expand=True,
        )

        logger.debug(f"Adding task: {task_name} with total: {task_total}")
        task = progress.add_task(task_name, total=task_total)

        # Create initial layout
        logger.debug("Creating table")
        table = make_progress_table()
        logger.debug("Creating layout")
        layout = create_layout(progress, table)

        # Add handler if needed
        handlers = logger.handlers
        rich_handler = None
        for h in handlers:
            if isinstance(h, RichConsoleHandler):
                rich_handler = h
                break

        if rich_handler is None:
            logger.debug("Creating new RichConsoleHandler")
            rich_handler = RichConsoleHandler(live, layout)
            logger.addHandler(rich_handler)
        else:
            # Update the existing handler with the new layout
            logger.debug("Updating existing RichConsoleHandler")
            rich_handler.layout = layout

        logger.debug("Starting update loop")
        while not table_update_event.is_set():
            logger.debug("Processing status updates")
            async with status_lock:
                events_to_progress.clear()
                progress.update(task, completed=len(all_statuses), refresh=True)

            logger.debug("Creating table and layout")
            table = make_progress_table()
            layout = create_layout(progress, table)

            # Update the handler's layout reference
            rich_handler.layout = layout

            logger.debug("Updating live display")
            live.update(layout)

            await asyncio.sleep(0.2)

    except Exception as e:
        logger.error(f"Error updating display: {str(e)}", exc_info=True)
        # Don't re-raise the exception to keep the display running


def get_ec2_client(region):
    """Get EC2 client with proper configuration for the specified region"""
    logger.debug(f"Creating EC2 client for region {region}")
    try:
        # Create a boto3 client with explicit timeout configuration
        logger.debug(f"Configuring boto3 client with timeout={AWS_API_TIMEOUT}")
        config = botocore.config.Config(
            connect_timeout=AWS_API_TIMEOUT,
            read_timeout=AWS_API_TIMEOUT,
            retries={"max_attempts": 3, "mode": "standard"},
        )
        logger.debug("Creating boto3 client")
        client = boto3.client("ec2", region_name=region, config=config)
        logger.debug("Successfully created EC2 client")
        return client
    except Exception as e:
        logger.error(
            f"Error creating EC2 client for region {region}: {str(e)}", exc_info=True
        )
        raise


async def safe_aws_call(func, *args, **kwargs):
    """Execute AWS API calls with proper timeout handling"""
    try:
        # Set a timeout for the AWS API call
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs), timeout=AWS_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        error_msg = (
            f"AWS API call timed out after {AWS_API_TIMEOUT} seconds: {func.__name__}"
        )
        logging.error(error_msg)
        if "describe_instances" in func.__name__:
            logging.error(
                "This may be due to SSO credential issues. Please check your AWS credentials."
            )
            logging.error("Try running 'aws sso login' to refresh your credentials.")
        raise TimeoutError(error_msg)
    except botocore.exceptions.ClientError as e:
        if "ExpiredToken" in str(e) or "InvalidToken" in str(e):
            logging.error(
                "AWS credentials have expired. Please refresh your credentials."
            )
            logging.error("Try running 'aws sso login' to refresh your credentials.")
        raise
    except Exception as e:
        logging.error(f"Error in AWS API call {func.__name__}: {str(e)}")
        raise


async def get_availability_zones(ec2):
    response = await safe_aws_call(
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

            # Wait for spot instances to be fulfilled
            waiter = ec2.get_waiter("spot_instance_request_fulfilled")
            max_wait_time = 600  # 10 minutes timeout
            start_wait_time = time.time()
            
            # Update instance status
            thisInstanceStatusObject.status = "Waiting for fulfillment"
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
            events_to_progress.append(thisInstanceStatusObject)
            
            # Setup polling for spot request status with timeout
            async def poll_spot_request_status():
                timeout_reached = False
                while not timeout_reached:
                    # Check if timeout reached
                    if time.time() - start_wait_time > max_wait_time:
                        logging.error(f"Timeout waiting for spot instance in {region}-{zone}")
                        return None
                    
                    # Check spot request status
                    try:
                        describe_response = await asyncio.to_thread(
                            ec2.describe_spot_instance_requests,
                            SpotInstanceRequestIds=spot_request_ids,
                        )
                        
                        for request in describe_response["SpotInstanceRequests"]:
                            status_code = request["Status"]["Code"]
                            status_message = request["Status"].get("Message", "No message")
                            
                            # Update status object with details
                            thisInstanceStatusObject.detailed_status = f"{status_code}: {status_message}"
                            thisInstanceStatusObject.elapsed_time = time.time() - start_time
                            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                            events_to_progress.append(thisInstanceStatusObject)
                            
                            logging.debug(f"Status in {region}-{zone}: {status_code} - {status_message}")
                            
                            # Check for failures
                            if status_code in ["price-too-low", "capacity-not-available"]:
                                logging.error(f"Spot request failed: {status_code} - {status_message}")
                                return None
                            
                            # Check for success - instance ID is present
                            if "InstanceId" in request:
                                return describe_response
                    
                    except Exception as e:
                        logging.error(f"Error checking spot request status: {str(e)}")
                    
                    # Sleep before next poll
                    await asyncio.sleep(5)
                
                return None
            
            # Try to use waiter first (faster) with timeout protection
            waiter_task = asyncio.create_task(
                asyncio.wait_for(
                    asyncio.to_thread(
                        waiter.wait,
                        SpotInstanceRequestIds=spot_request_ids,
                        WaiterConfig={"MaxAttempts": 40, "Delay": 15},  # 40 attempts * 15 sec = 10 min max
                    ),
                    timeout=max_wait_time
                )
            )
            
            # Start the polling task as a backup
            polling_task = asyncio.create_task(poll_spot_request_status())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [waiter_task, polling_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel the pending task
            for task in pending:
                task.cancel()
            
            # Get results
            describe_response = None
            waiter_succeeded = False
            
            for task in done:
                try:
                    if task == waiter_task:
                        await task  # Just to get any exceptions
                        waiter_succeeded = True
                        logging.debug(f"Waiter succeeded for {region}-{zone}")
                    elif task == polling_task:
                        describe_response = await task
                
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                except Exception as e:
                    logging.error(f"Error in spot instance fulfillment: {str(e)}")
            
            # If waiter succeeded but we don't have response, get it now
            if waiter_succeeded and not describe_response:
                try:
                    describe_response = await asyncio.to_thread(
                        ec2.describe_spot_instance_requests,
                        SpotInstanceRequestIds=spot_request_ids,
                    )
                except Exception as e:
                    logging.error(f"Error getting spot request details: {str(e)}")
                    describe_response = None

            # Check if we got a valid response
            if describe_response is None:
                thisInstanceStatusObject.status = "Failed to request spot instance"
                thisInstanceStatusObject.detailed_status = "Timeout or API error"
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)
                continue  # Skip to next instance
                
            # Get instance IDs
            zone_instance_ids = [
                request["InstanceId"]
                for request in describe_response.get("SpotInstanceRequests", [])
                if "InstanceId" in request
            ]
            
            if not zone_instance_ids:
                thisInstanceStatusObject.status = "Failed to request spot instance"
                thisInstanceStatusObject.detailed_status = "No instance ID returned"
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)
                continue  # Skip to next instance
                
            # Add to our overall list of instance IDs
            instance_ids.extend(zone_instance_ids)
            
            # Process the first instance ID (we request only one per spot request)
            thisInstanceStatusObject.instance_id = zone_instance_ids[0]
            thisInstanceStatusObject.status = "Tagging"
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
            events_to_progress.append(thisInstanceStatusObject)

            try:
                # Run tagging and instance details fetching in parallel
                tagging_task = asyncio.create_task(
                    asyncio.to_thread(
                        ec2.create_tags,
                        Resources=zone_instance_ids,
                        Tags=[
                            {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                            {"Key": "Name", "Value": f"SpotInstance-{region}-{zone}"},
                            {"Key": "AZ", "Value": zone},
                        ],
                    )
                )
                
                fetching_task = asyncio.create_task(
                    asyncio.to_thread(
                        ec2.describe_instances,
                        InstanceIds=[thisInstanceStatusObject.instance_id],
                    )
                )
                
                # Wait for both tasks to complete with timeout
                done, pending = await asyncio.wait(
                    [tagging_task, fetching_task],
                    timeout=30
                )
                
                # Cancel any pending tasks that didn't complete
                for task in pending:
                    task.cancel()
                
                # Process the results
                instance_details = None
                tagging_completed = False
                
                for task in done:
                    try:
                        if task == tagging_task:
                            await task
                            tagging_completed = True
                        elif task == fetching_task:
                            instance_details = await task
                    except Exception as e:
                        logging.error(f"Error in instance initialization: {str(e)}")
                
                # Extract IP addresses if we got instance details
                if instance_details and instance_details.get("Reservations"):
                    instance = instance_details["Reservations"][0]["Instances"][0]
                    thisInstanceStatusObject.public_ip = instance.get("PublicIpAddress", "")
                    thisInstanceStatusObject.private_ip = instance.get("PrivateIpAddress", "")
                
                # Update final status
                if tagging_completed:
                    thisInstanceStatusObject.status = "Done"
                else:
                    thisInstanceStatusObject.status = "Tagged with warnings"
                    thisInstanceStatusObject.detailed_status = "Tagging may not have completed"
                
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)
                
            except Exception as e:
                logging.error(f"Error processing instance {thisInstanceStatusObject.instance_id}: {str(e)}")
                thisInstanceStatusObject.status = "Error processing instance"
                thisInstanceStatusObject.detailed_status = str(e)[:30]
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)

    except Exception as e:
        logging.error(f"An error occurred in {region}: {str(e)}", exc_info=True)
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


async def create_spot_instances():
    global task_name, task_total
    task_name = "Creating Spot Instances"
    task_total = MAX_NODES

    async def create_in_region(region):
        global global_node_count
        available_slots = MAX_NODES - global_node_count
        region_cfg = config.get_region_config(region)
        if available_slots <= 0:
            logging.warning(f"Reached maximum nodes. Skipping region: {region}")
            return [], {}

        instances_to_create = (
            min(INSTANCES_PER_REGION, available_slots)
            if region_cfg.get("node_count") == "auto"
            else (min(region_cfg.get("node_count"), available_slots))
        )

        if instances_to_create == 0:
            return [], {}

        logging.debug(
            f"Creating {instances_to_create} spot instances in region: {region}"
        )
        global_node_count += instances_to_create
        instance_ids = await create_spot_instances_in_region(
            config, instances_to_create, region
        )
        return instance_ids

    tasks = [create_in_region(region) for region in AWS_REGIONS]
    await asyncio.gather(*tasks)

    logging.debug("Waiting for public IP addresses...")
    await wait_for_public_ips()

    logging.debug("Finished creating spot instances")
    return


async def wait_for_public_ips():
    global all_statuses
    timeout = 300  # 5 minutes timeout
    start_time = time.time()
    poll_interval = 5  # seconds between polls

    # Group instances by region for parallel processing
    def get_instances_by_region():
        instances_by_region = {}
        for status in all_statuses.values():
            if not status.public_ip and status.instance_id and status.region:
                if status.region not in instances_by_region:
                    instances_by_region[status.region] = []
                instances_by_region[status.region].append(status.instance_id)
        return instances_by_region

    while True:
        # Check if we're done or timed out
        all_have_ips = all(
            status.public_ip or not status.instance_id  # Either has IP or no instance
            for status in all_statuses.values()
        )
        
        if all_have_ips or time.time() - start_time > timeout:
            # If we timed out, update status for instances without IPs
            if time.time() - start_time > timeout:
                for status in all_statuses.values():
                    if status.instance_id and not status.public_ip:
                        status.detailed_status = "No public IP after timeout"
                        events_to_progress.append(status)
                logging.warning(f"Timed out after {timeout}s waiting for public IPs")
            break

        # Get instances grouped by region
        instances_by_region = get_instances_by_region()
        if not instances_by_region:
            # No instances need IPs, we're done
            break
            
        # Create tasks to query each region in parallel
        async def query_region_instances(region, instance_ids):
            try:
                ec2 = get_ec2_client(region)
                response = await asyncio.to_thread(
                    ec2.describe_instances, InstanceIds=instance_ids
                )
                
                # Process results and update statuses
                updated_ips = {}
                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        public_ip = instance.get("PublicIpAddress", "")
                        private_ip = instance.get("PrivateIpAddress", "")
                        
                        if instance_id:
                            updated_ips[instance_id] = {
                                "public_ip": public_ip,
                                "private_ip": private_ip
                            }
                
                return updated_ips
            except Exception as e:
                logger.error(f"Error querying instances in {region}: {str(e)}")
                return {}
        
        # Create and run tasks for all regions in parallel
        tasks = [
            query_region_instances(region, instance_ids)
            for region, instance_ids in instances_by_region.items()
        ]
        
        if tasks:
            # Wait for all regions to be queried with timeout protection
            try:
                results = await asyncio.gather(*tasks)
                
                # Process all results and update instance statuses
                for result in results:
                    for instance_id, ips in result.items():
                        for status in all_statuses.values():
                            if status.instance_id == instance_id:
                                if ips.get("public_ip"):
                                    status.public_ip = ips["public_ip"]
                                if ips.get("private_ip"):
                                    status.private_ip = ips["private_ip"]
                                events_to_progress.append(status)
                
            except Exception as e:
                logger.error(f"Error waiting for public IPs: {str(e)}")
        
        # Wait before next poll
        await asyncio.sleep(poll_interval)


async def list_spot_instances():
    logger.debug("Entering list_spot_instances function")
    global all_statuses, events_to_progress, task_total
    logger.debug("Resetting global statuses and events")
    all_statuses = {}  # Reset the global statuses
    events_to_progress = []  # Clear the events list

    global task_name
    task_name = "Listing Spot Instances"
    task_total = 0  # We'll update this as we go

    logger.info("Starting to list spot instances")

    for region in AWS_REGIONS:
        logger.info(f"Processing region: {region}")
        logger.debug(f"Getting EC2 client for region {region}")
        ec2 = get_ec2_client(region)
        try:
            logger.info(f"Fetching availability zones for region {region}")
            az_response = await asyncio.to_thread(ec2.describe_availability_zones)
            availability_zones = [
                az["ZoneName"] for az in az_response["AvailabilityZones"]
            ]
            logger.info(
                f"Found {len(availability_zones)} availability zones in {region}: {', '.join(availability_zones)}"
            )

            for az in availability_zones:
                logger.info(f"Querying instances in {region}/{az}")
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

                instance_count = 0
                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_count += 1
                        logger.info(
                            f"Found instance: {instance['InstanceId']} in {region}/{az}"
                        )
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

                        logger.debug(
                            f"Adding instance {instance_id} to status tracking"
                        )
                        events_to_progress.append(instance_id)
                        all_statuses[instance_id] = thisInstanceStatusObject
                        task_total += 1

                if instance_count == 0:
                    logger.info(f"No instances found in {region}/{az}")

            logger.info(
                f"Completed scan of region {region}, found {sum(1 for status in all_statuses.values() if status.region == region)} instances"
            )

        except Exception as e:
            logger.error(
                f"An error occurred while listing instances in {region}: {str(e)}",
                exc_info=True,
            )

    logger.info(
        f"Finished listing spot instances, found {len(all_statuses)} instances in total"
    )
    return all_statuses


async def destroy_instances():
    instance_region_map = {}

    global task_name, task_total, events_to_progress
    task_name = "Terminating Spot Instances"
    events_to_progress = []

    logger.info("Identifying instances to terminate...")
    for region in AWS_REGIONS:
        logger.info(f"Checking region {region} for instances to terminate...")
        ec2 = get_ec2_client(region)
        try:
            # Use safe_aws_call instead of asyncio.to_thread directly
            logger.info(f"Querying AWS API for instances in {region}...")
            response = await safe_aws_call(
                ec2.describe_instances,
                Filters=[
                    {
                        "Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping", "stopped"],
                    },
                    {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
                ],
            )

            instance_count = 0
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_count += 1
                    instance_id = instance["InstanceId"]
                    az = instance["Placement"]["AvailabilityZone"]
                    vpc_id = instance.get("VpcId")
                    logger.info(f"Found instance {instance_id} in {az}")
                    thisInstanceStatusObject = InstanceStatus(region, az)
                    thisInstanceStatusObject.instance_id = instance_id
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

            if instance_count == 0:
                logger.info(f"No instances found in region {region}")

        except TimeoutError:
            logger.error(
                f"Timeout while listing instances in {region}. Check your AWS credentials."
            )
            continue
        except Exception as e:
            logger.error(
                f"An error occurred while listing instances in {region}: {str(e)}"
            )
            continue

    if not all_statuses:
        logger.info("No instances found to terminate.")
        return

    task_total = len(all_statuses)
    logger.info(f"Found {task_total} instances to terminate.")

    async def terminate_instances_in_region(region, region_instances):
        ec2 = get_ec2_client(region)
        try:
            logger.info(f"Terminating {len(region_instances)} instances in {region}...")
            await safe_aws_call(ec2.terminate_instances, InstanceIds=region_instances)
            logger.info(
                f"Instances terminate request sent in {region}, waiting for completion..."
            )

            waiter = ec2.get_waiter("instance_terminated")
            start_time = time.time()
            while True:
                try:
                    logger.info(f"Checking if instances in {region} are terminated...")
                    await safe_aws_call(
                        waiter.wait,
                        InstanceIds=region_instances,
                        WaiterConfig={"MaxAttempts": 1},
                    )
                    logger.info(f"All instances in {region} terminated successfully")
                    break
                except botocore.exceptions.WaiterError:
                    elapsed_time = time.time() - start_time
                    logger.info(
                        f"Instances in {region} still terminating after {elapsed_time:.0f}s"
                    )
                    for instance_id in region_instances:
                        thisInstanceStatusObject = all_statuses[instance_id]
                        thisInstanceStatusObject.elapsed_time = elapsed_time
                        thisInstanceStatusObject.detailed_status = (
                            f"Terminating ({elapsed_time:.0f}s)"
                        )
                        events_to_progress.append(thisInstanceStatusObject)
                        all_statuses[instance_id] = thisInstanceStatusObject
                    await asyncio.sleep(10)
                except TimeoutError:
                    # Handle timeout during waiter
                    logger.error(
                        f"Timeout waiting for instances to terminate in {region}"
                    )
                    for instance_id in region_instances:
                        thisInstanceStatusObject = all_statuses[instance_id]
                        thisInstanceStatusObject.status = "Timeout"
                        thisInstanceStatusObject.detailed_status = (
                            "AWS API timeout during termination"
                        )
                        events_to_progress.append(thisInstanceStatusObject)
                        all_statuses[instance_id] = thisInstanceStatusObject
                    break

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

            if vpcs_to_delete:
                logger.info(f"Cleaning up {len(vpcs_to_delete)} VPCs in {region}")
            else:
                logger.info(f"No VPCs to clean up in {region}")

            for vpc_id in vpcs_to_delete:
                try:
                    logger.info(f"Starting cleanup of VPC {vpc_id} in {region}")
                    for instance_id, status in all_statuses.items():
                        if status.vpc_id == vpc_id:
                            status.detailed_status = "Cleaning up VPC resources"
                            events_to_progress.append(status)

                    await clean_up_vpc_resources(ec2, vpc_id)
                    logger.info(f"Completed cleanup of VPC {vpc_id} in {region}")

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

    # Terminate instances in parallel
    termination_tasks = []
    for region, instances in region_instances.items():
        logger.info(
            f"Creating termination task for {len(instances)} instances in {region}"
        )
        termination_tasks.append(terminate_instances_in_region(region, instances))

    if termination_tasks:
        logger.info(f"Starting {len(termination_tasks)} parallel termination tasks")
        await asyncio.gather(*termination_tasks)
        logger.info("All termination tasks completed")
    else:
        logger.info("No termination tasks to execute")

    logger.info("All instances have been terminated.")


async def clean_up_vpc_resources(ec2, vpc_id):
    async def update_status(message):
        logger.info(message)
        for status in all_statuses.values():
            if status.vpc_id == vpc_id:
                status.detailed_status = message

    await update_status(f"Looking for security groups in VPC {vpc_id}")
    sgs = await asyncio.to_thread(
        ec2.describe_security_groups,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )

    sg_count = 0
    for sg in sgs["SecurityGroups"]:
        if sg["GroupName"] != "default":
            sg_count += 1
            await update_status(
                f"Deleting security group {sg['GroupId']} ({sg['GroupName']})"
            )
            await asyncio.to_thread(ec2.delete_security_group, GroupId=sg["GroupId"])

    if sg_count == 0:
        await update_status(f"No non-default security groups found in VPC {vpc_id}")

    await update_status(f"Looking for subnets in VPC {vpc_id}")
    subnets = await asyncio.to_thread(
        ec2.describe_subnets,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )

    subnet_count = 0
    for subnet in subnets["Subnets"]:
        subnet_count += 1
        await update_status(f"Deleting subnet {subnet['SubnetId']}")
        await asyncio.to_thread(ec2.delete_subnet, SubnetId=subnet["SubnetId"])

    if subnet_count == 0:
        await update_status(f"No subnets found in VPC {vpc_id}")

    await update_status(f"Looking for route tables in VPC {vpc_id}")
    rts = await asyncio.to_thread(
        ec2.describe_route_tables,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )

    rt_count = 0
    for rt in rts["RouteTables"]:
        if not any(
            association.get("Main", False) for association in rt.get("Associations", [])
        ):
            rt_count += 1
            await update_status(f"Deleting route table {rt['RouteTableId']}")
            await asyncio.to_thread(
                ec2.delete_route_table,
                RouteTableId=rt["RouteTableId"],
            )

    if rt_count == 0:
        await update_status(f"No non-main route tables found in VPC {vpc_id}")

    await update_status(f"Looking for internet gateways attached to VPC {vpc_id}")
    igws = await asyncio.to_thread(
        ec2.describe_internet_gateways,
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
    )

    igw_count = 0
    for igw in igws["InternetGateways"]:
        igw_count += 1
        await update_status(f"Detaching internet gateway {igw['InternetGatewayId']}")
        await asyncio.to_thread(
            ec2.detach_internet_gateway,
            InternetGatewayId=igw["InternetGatewayId"],
            VpcId=vpc_id,
        )
        await update_status(f"Deleting internet gateway {igw['InternetGatewayId']}")
        await asyncio.to_thread(
            ec2.delete_internet_gateway,
            InternetGatewayId=igw["InternetGatewayId"],
        )

    if igw_count == 0:
        await update_status(f"No internet gateways found attached to VPC {vpc_id}")

    await update_status(f"Deleting VPC {vpc_id}")
    await asyncio.to_thread(ec2.delete_vpc, VpcId=vpc_id)
    await update_status(f"VPC {vpc_id} successfully deleted")


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


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Manage spot instances across multiple AWS regions."
    )
    parser.add_argument(
        "action",  # Changed from --action to positional argument
        choices=["create", "destroy", "list", "delete_disconnected_aws_nodes"],
        help="Action to perform",
        nargs="?",  # Make it optional
        default="list",  # Default to list if not provided
    )
    parser.add_argument(
        "--format", choices=["default", "json"], default="default", help="Output format"
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="AWS API timeout in seconds"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose debug output"
    )

    args = parser.parse_args()

    # Configure logging based on verbose flag
    global file_handler
    # Truncate debug.log file if it exists or create a new one
    try:
        with open("debug.log", "w") as f:
            pass  # Just open in write mode to truncate
    except Exception as e:
        print(f"Warning: Could not truncate debug.log: {e}")

    # Create and configure file handler
    file_handler = logging.FileHandler("debug.log")
    file_handler.setFormatter(log_formatter)
    
    # Set file_handler level based on verbose flag
    if args.verbose:
        file_handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
    
    # Add the handler to our logger
    logger.addHandler(file_handler)
    
    # Log initial startup message
    logger.info(f"Starting with action: {args.action}, verbose: {args.verbose}")
    
    # Set global timeout from command line argument
    global AWS_API_TIMEOUT
    AWS_API_TIMEOUT = args.timeout
    logger.info(f"Set AWS API timeout to {AWS_API_TIMEOUT} seconds")

    # Set task name based on action
    global task_name, task_total
    if args.action == "create":
        task_name = "Creating Spot Instances"
        task_total = TOTAL_INSTANCES
    elif args.action == "destroy":
        task_name = "Terminating Spot Instances"
        task_total = 100  # Will be updated when we know how many instances to terminate
    elif args.action == "list":
        task_name = "Listing Spot Instances"
        task_total = 100  # Will be updated when we know how many instances to list
    elif args.action == "delete_disconnected_aws_nodes":
        task_name = "Deleting Disconnected AWS Nodes"
        task_total = 100  # Will be updated when we know how many nodes to delete

    logger.info(f"Set task: '{task_name}' with target: {task_total}")
    return args


async def perform_action():
    """Execute the requested action"""
    args = parse_args()
    logger.debug(f"Starting perform_action with action: {args.action}")
    try:
        if args.action == "create":
            logger.info("Initiating create_spot_instances")
            await create_spot_instances()
        elif args.action == "list":
            logger.info("Initiating list_spot_instances")
            await list_spot_instances()
        elif args.action == "destroy":
            logger.info("Initiating destroy_instances")
            await destroy_instances()
        elif args.action == "delete_disconnected_aws_nodes":
            logger.info("Initiating delete_disconnected_aws_nodes")
            await delete_disconnected_aws_nodes()
        logger.debug(f"Completed action: {args.action}")
    except TimeoutError as e:
        logger.error(f"TimeoutError occurred: {str(e)}")
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        console.print("[yellow]This may be due to AWS credential issues.[/yellow]")
        console.print(
            "[yellow]Try running 'aws sso login' to refresh your credentials.[/yellow]"
        )
        table_update_event.set()
        return
    except botocore.exceptions.ClientError as e:
        logger.error(f"AWS ClientError occurred: {str(e)}")
        if "ExpiredToken" in str(e) or "InvalidToken" in str(e):
            console.print("[bold red]AWS credentials have expired.[/bold red]")
            console.print(
                "[yellow]Try running 'aws sso login' to refresh your credentials.[/yellow]"
            )
        else:
            console.print(f"[bold red]AWS Error:[/bold red] {str(e)}")
        table_update_event.set()
        return
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        table_update_event.set()
        return


async def main():
    """Main execution function"""
    handler = None  # Initialize handler to None
    try:
        args = parse_args()

        # Set logging level based on verbosity
        if args.verbose:
            logger.setLevel(logging.DEBUG)
            logger.debug("Verbose logging enabled")
        else:
            logger.setLevel(logging.INFO)

        logger.info(f"Starting action: {args.action}")

        if args.format == "json":
            logger.info("Using JSON output format")
            await perform_action()
            print(json.dumps(all_statuses_to_dict(), indent=2))
            return

        # Create initial progress and table
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        )
        table = make_progress_table()

        # Create layout before using it in Live
        layout = create_layout(progress, table)

        # Initialize the live display with the layout
        with Live(
            layout,
            console=console,
            refresh_per_second=5,
            auto_refresh=True,
            screen=True,
            transient=False,  # Keep the display visible after exit
        ) as live:
            try:
                # Update our global flag to indicate terminal has been cleared
                global is_terminal_cleared
                is_terminal_cleared = True
                
                # Add the rich console handler for logging with separate layout reference
                handler = RichConsoleHandler(live, layout)  # Pass layout directly
                logger.addHandler(handler)

                # Start display update task in a separate thread
                loop = asyncio.get_event_loop()
                display_task = loop.create_task(update_display(live))

                # Set up exception handler for display_task
                def handle_display_task_exception(task):
                    try:
                        # Get the exception if any
                        task.result()
                    except Exception as e:
                        logger.error(f"Display task failed: {str(e)}", exc_info=True)
                        # We don't reraise here - just log it
                
                display_task.add_done_callback(handle_display_task_exception)

                # Perform the requested action
                await perform_action()

                # Signal display task to stop and wait for completion
                logger.debug("Signaling display task to stop")
                table_update_event.set()

                # Wait for display to finish updating with a timeout
                try:
                    logger.debug("Waiting for display task to complete")
                    await asyncio.wait_for(asyncio.shield(display_task), timeout=5.0)
                    logger.debug("Display task completed")
                except asyncio.TimeoutError:
                    logger.warning("Display task did not complete within timeout")
                    # We continue anyway, the task will be cancelled in the finally block

            except Exception as e:
                logger.error(f"Error in main execution: {str(e)}", exc_info=True)
                # Don't try to use rich console here, as it might be the source of the error
                # Error will be printed by our outer exception handler
                raise
            finally:
                # Stop the display task if it's still running
                if display_task and not display_task.done():
                    display_task.cancel()
                
                # Remove the rich console handler if it was added
                if handler is not None and handler in logger.handlers:
                    logger.removeHandler(handler)

    except Exception as e:
        logger.error(f"Fatal error occurred: {str(e)}", exc_info=True)
        console.print(f"\n[bold red]Fatal error:[/bold red] {str(e)}")
        raise


if __name__ == "__main__":
    # Store the original terminal settings to ensure we can properly display errors
    is_terminal_cleared = False
    
    # Function to print error outside of rich Live display context
    def print_error_message(message):
        if is_terminal_cleared:
            # If terminal was cleared by rich Live display, add newlines for visibility
            print("\n\n")
        print(f"\n[ERROR] {message}")
        print("Check debug.log for more details.")
        
    try:
        logger.info("Starting main execution")
        asyncio.run(main())
        logger.info("Main execution completed")
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print_error_message("Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        # Log detailed error
        logger.error(f"Fatal error occurred: {str(e)}", exc_info=True)
        
        # Print user-friendly error message outside of any rich context
        error_msg = f"Fatal error occurred: {str(e)}"
        
        # Add additional context for common errors
        if "TimeoutError" in str(e):
            error_msg += "\nThis may be due to AWS credential issues or network problems."
            error_msg += "\nTry running 'aws sso login' to refresh your credentials."
        elif "ExpiredToken" in str(e) or "InvalidToken" in str(e):
            error_msg += "\nAWS credentials have expired. Try running 'aws sso login'."
        elif "InstanceId" in str(e) and "does not exist" in str(e):
            error_msg += "\nThe specified instance may have been terminated or never created."
            
        print_error_message(error_msg)
        sys.exit(1)
