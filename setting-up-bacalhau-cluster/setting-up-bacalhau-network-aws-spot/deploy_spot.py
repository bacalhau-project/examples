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
from rich.table import Table, box
from util.config import Config
from util.scripts_provider import ScriptsProvider

# Set up logging with a unified approach - everything will go to the console panel
# and be written to the debug.log file as a backup

# Set up logging with a unified stream approach
# All logs will go to both debug.log and the Rich console panel

# Formatter for logs - concise but informative
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Set up main logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Default level, will be updated based on args
# Important: Prevent propagation to root logger to avoid stderr output
logger.propagate = False

# The file handler will be shared with the Rich console handler
file_handler = None

# Initialize console with auto-detection of width
console = Console()

# Default tag and naming values
FILTER_TAG_NAME = "ManagedBy"
FILTER_TAG_VALUE = "SpotInstanceScript"
CREATOR_VALUE = "BacalhauSpotScript"
RESOURCE_PREFIX = "SpotInstance"
VPC_NAME = "SpotInstanceVPC"


# Function to get user input with defaults
def get_user_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ")
    return user_input if user_input.strip() else default


# Function to configure tags and names
def configure_tags_and_names():
    global FILTER_TAG_NAME, FILTER_TAG_VALUE, CREATOR_VALUE, RESOURCE_PREFIX, VPC_NAME

    console.print("[bold]Configuring resource tags and names[/bold]")
    console.print("Press Enter to accept default values, or type custom values:")

    FILTER_TAG_NAME = get_user_input(
        "Tag name for identifying managed resources", FILTER_TAG_NAME
    )
    FILTER_TAG_VALUE = get_user_input(
        "Tag value for identifying managed resources", FILTER_TAG_VALUE
    )
    CREATOR_VALUE = get_user_input(
        "Creator identifier for resource tags", CREATOR_VALUE
    )
    RESOURCE_PREFIX = get_user_input("Prefix for named resources", RESOURCE_PREFIX)
    VPC_NAME = get_user_input("VPC name", VPC_NAME)

    console.print(
        "\n[green]✓[/green] Configuration complete. Using the following values:"
    )
    console.print(f"  • Tag: {FILTER_TAG_NAME}={FILTER_TAG_VALUE}")
    console.print(f"  • Creator: {CREATOR_VALUE}")
    console.print(f"  • Resource prefix: {RESOURCE_PREFIX}")
    console.print(f"  • VPC name: {VPC_NAME}")
    console.print()


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
        self.spot_request_id = None  # Track the spot request ID for monitoring
        self.fulfilled = False  # Track if the spot request was fulfilled

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
    """Unified console handler that shows log messages from debug.log in the Rich UI.

    This handler streams the debug.log content to the console panel in the Rich UI.
    It also forwards log records to the file handler, creating a single logging path.
    """

    def __init__(self, live, layout, file_handler=None):
        super().__init__()
        self.live = live
        self.layout = layout  # Store the layout directly
        self.messages = ["Logs will appear here..."]  # Start with a simple message

        # Use the same formatter as the file handler for consistency
        self.setFormatter(log_formatter)

        # Keep reference to file handler for forwarding
        self.file_handler = file_handler

        # Set the level to match the file handler if provided
        if file_handler:
            self.setLevel(file_handler.level)
        else:
            self.setLevel(logging.INFO)

        # Initialize the console panel content right away
        console_panel = self.layout.children[-1].renderable
        console_panel.renderable = "\n".join(self.messages)

        # Read any existing content from debug.log to show history
        self._load_existing_logs()

    def _load_existing_logs(self):
        """Load the last few lines from debug.log to provide context"""
        try:
            if os.path.exists("debug.log"):
                with open("debug.log", "r") as f:
                    # Get the last 10 lines from the file
                    lines = f.readlines()[-10:]
                    if lines:
                        # Replace our waiting message with actual log content
                        self.messages = [line.strip() for line in lines]

                        # Update the console panel right away
                        console_panel = self.layout.children[-1].renderable
                        console_panel.renderable = "\n".join(self.messages)
        except Exception:
            # If we can't read the log file, just continue with the default message
            pass

    def emit(self, record):
        """Process log records and update the console panel"""
        try:
            # Format the message using our formatter
            msg = self.format(record)

            # If we still have the default message, clear it first
            if (
                len(self.messages) == 1
                and self.messages[0] == "Logs will appear here..."
            ):
                self.messages = []

            # Add the new message
            self.messages.append(msg)

            # Keep only the last 20 messages (increased from 10 for more context)
            if len(self.messages) > 20:
                self.messages = self.messages[-20:]

            # Update the console panel content
            console_panel = self.layout.children[-1].renderable
            console_panel.renderable = "\n".join(self.messages)

            # Forward to file handler if we have one and it's not already handling this record
            if self.file_handler and record.levelno >= self.file_handler.level:
                self.file_handler.emit(record)

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

        # For display updates we don't need to create a new handler
        # Just update the existing one with the new layout
        rich_handler = None
        for h in logger.handlers:
            if isinstance(h, RichConsoleHandler):
                rich_handler = h
                break

        if rich_handler is None:
            logger.debug(
                "No existing RichConsoleHandler found - display updates may not work"
            )
        else:
            # Update the existing handler with the new layout
            logger.debug("Updating existing RichConsoleHandler layout")
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

            # Find and update the RichConsoleHandler with the new layout
            for h in logger.handlers:
                if isinstance(h, RichConsoleHandler):
                    h.layout = layout
                    break

            logger.debug("Updating live display")
            live.update(layout)

            # Slightly longer sleep to reduce log volume
            await asyncio.sleep(0.5)

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
                            {
                                "Key": "Name",
                                "Value": f"{RESOURCE_PREFIX}-{region}-{zone}",
                            },
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

            # Store the spot request ID in the status object for tracking
            if spot_request_ids:
                thisInstanceStatusObject.spot_request_id = spot_request_ids[0]

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
                        logging.error(
                            f"Timeout waiting for spot instance in {region}-{zone}"
                        )
                        return None

                    # Check spot request status
                    try:
                        describe_response = await asyncio.to_thread(
                            ec2.describe_spot_instance_requests,
                            SpotInstanceRequestIds=spot_request_ids,
                        )

                        for request in describe_response["SpotInstanceRequests"]:
                            status_code = request["Status"]["Code"]
                            status_message = request["Status"].get(
                                "Message", "No message"
                            )

                            # Update status object with details
                            thisInstanceStatusObject.detailed_status = (
                                f"{status_code}: {status_message}"
                            )
                            thisInstanceStatusObject.elapsed_time = (
                                time.time() - start_time
                            )
                            all_statuses[thisInstanceStatusObject.id] = (
                                thisInstanceStatusObject
                            )
                            events_to_progress.append(thisInstanceStatusObject)

                            logging.debug(
                                f"Status in {region}-{zone}: {status_code} - {status_message}"
                            )

                            # Check for failures
                            if status_code in [
                                "price-too-low",
                                "capacity-not-available",
                            ]:
                                logging.error(
                                    f"Spot request failed: {status_code} - {status_message}"
                                )
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
                        WaiterConfig={
                            "MaxAttempts": 40,
                            "Delay": 15,
                        },  # 40 attempts * 15 sec = 10 min max
                    ),
                    timeout=max_wait_time,
                )
            )

            # Start the polling task as a backup
            polling_task = asyncio.create_task(poll_spot_request_status())

            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [waiter_task, polling_task], return_when=asyncio.FIRST_COMPLETED
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
                            {
                                "Key": "Name",
                                "Value": f"{RESOURCE_PREFIX}-{region}-{zone}",
                            },
                            {"Key": "AZ", "Value": zone},
                            {"Key": "CreatedBy", "Value": CREATOR_VALUE},
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
                    [tagging_task, fetching_task], timeout=30
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
                    thisInstanceStatusObject.public_ip = instance.get(
                        "PublicIpAddress", ""
                    )
                    thisInstanceStatusObject.private_ip = instance.get(
                        "PrivateIpAddress", ""
                    )

                # Update final status
                if tagging_completed:
                    thisInstanceStatusObject.status = "Done"
                else:
                    thisInstanceStatusObject.status = "Tagged with warnings"
                    thisInstanceStatusObject.detailed_status = (
                        "Tagging may not have completed"
                    )

                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)

            except Exception as e:
                logging.error(
                    f"Error processing instance {thisInstanceStatusObject.instance_id}: {str(e)}"
                )
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
        ec2.describe_vpcs,
        Filters=[
            {"Name": "tag:Name", "Values": [VPC_NAME]},
            {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
        ],
    )
    if vpcs["Vpcs"]:
        return vpcs["Vpcs"][0]["VpcId"]
    else:
        vpc = await asyncio.to_thread(ec2.create_vpc, CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        await asyncio.to_thread(
            ec2.create_tags,
            Resources=[vpc_id],
            Tags=[
                {"Key": "Name", "Value": VPC_NAME},
                {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                {"Key": "CreatedBy", "Value": CREATOR_VALUE},
            ],
        )
        await asyncio.to_thread(
            ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsHostnames={"Value": True}
        )
        await asyncio.to_thread(
            ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsSupport={"Value": True}
        )
        return vpc_id


async def create_subnet(ec2, vpc_id, zone, cidr_block=None):
    # First, check if a subnet already exists in this zone and has our tag
    existing_subnets = await asyncio.to_thread(
        ec2.describe_subnets,
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "availability-zone", "Values": [zone]},
            {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
        ],
    )

    if existing_subnets["Subnets"]:
        # If a tagged subnet exists, return its ID
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

            # Tag the subnet for tracking
            subnet_id = subnet["Subnet"]["SubnetId"]
            await asyncio.to_thread(
                ec2.create_tags,
                Resources=[subnet_id],
                Tags=[
                    {"Key": "Name", "Value": f"{RESOURCE_PREFIX}-Subnet-{zone}"},
                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                    {"Key": "CreatedBy", "Value": CREATOR_VALUE},
                    {"Key": "Zone", "Value": zone},
                ],
            )

            return subnet_id
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
    # First, check if the VPC already has an Internet Gateway attached with our tag
    igws = await asyncio.to_thread(
        ec2.describe_internet_gateways,
        Filters=[
            {"Name": "attachment.vpc-id", "Values": [vpc_id]},
            {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
        ],
    )

    if igws["InternetGateways"]:
        # If a tagged Internet Gateway is already attached, return its ID
        return igws["InternetGateways"][0]["InternetGatewayId"]

    # Also check for any IGW attached to our VPC (even if not tagged)
    all_igws = await asyncio.to_thread(
        ec2.describe_internet_gateways,
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
    )

    if all_igws["InternetGateways"]:
        # Found an attached IGW, tag it and return its ID
        igw_id = all_igws["InternetGateways"][0]["InternetGatewayId"]
        await asyncio.to_thread(
            ec2.create_tags,
            Resources=[igw_id],
            Tags=[
                {"Key": "Name", "Value": f"{RESOURCE_PREFIX}-IGW"},
                {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                {"Key": "CreatedBy", "Value": CREATOR_VALUE},
            ],
        )
        return igw_id

    # If no Internet Gateway is attached, create and attach a new one
    igw = await asyncio.to_thread(ec2.create_internet_gateway)
    igw_id = igw["InternetGateway"]["InternetGatewayId"]

    # Tag the new IGW
    await asyncio.to_thread(
        ec2.create_tags,
        Resources=[igw_id],
        Tags=[
            {"Key": "Name", "Value": f"{RESOURCE_PREFIX}-IGW"},
            {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
            {"Key": "CreatedBy", "Value": CREATOR_VALUE},
        ],
    )

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
            # Found one after conflict, tag it and return
            existing_igw_id = igws["InternetGateways"][0]["InternetGatewayId"]
            await asyncio.to_thread(
                ec2.create_tags,
                Resources=[existing_igw_id],
                Tags=[
                    {"Key": "Name", "Value": f"{RESOURCE_PREFIX}-IGW"},
                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                    {"Key": "CreatedBy", "Value": CREATOR_VALUE},
                ],
            )
            return existing_igw_id
        else:
            # If still no IGW found, re-raise the original error
            raise

    return igw_id


async def create_route_table(ec2, vpc_id, igw_id):
    # Check if a tagged route table already exists for the VPC
    tagged_route_tables = await asyncio.to_thread(
        ec2.describe_route_tables,
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
        ],
    )

    # If we found tagged route tables, check and use the first one
    if tagged_route_tables["RouteTables"]:
        route_table_id = tagged_route_tables["RouteTables"][0]["RouteTableId"]
        routes = tagged_route_tables["RouteTables"][0].get("Routes", [])
        # Ensure it has the IGW route
        if not any(route.get("GatewayId") == igw_id for route in routes):
            await asyncio.to_thread(
                ec2.create_route,
                RouteTableId=route_table_id,
                DestinationCidrBlock="0.0.0.0/0",
                GatewayId=igw_id,
            )
        return route_table_id

    # Check if any route table exists for the VPC
    route_tables = await asyncio.to_thread(
        ec2.describe_route_tables,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )

    # Look for main route table
    for rt in route_tables["RouteTables"]:
        for association in rt.get("Associations", []):
            if association.get("Main", False):
                # Found the main route table, add a route to the IGW if it doesn't exist
                route_table_id = rt["RouteTableId"]
                routes = rt.get("Routes", [])

                # Tag it for future identification
                await asyncio.to_thread(
                    ec2.create_tags,
                    Resources=[route_table_id],
                    Tags=[
                        {"Key": "Name", "Value": f"{RESOURCE_PREFIX}-RouteTable"},
                        {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                        {"Key": "CreatedBy", "Value": CREATOR_VALUE},
                    ],
                )

                # Add route to IGW if it doesn't exist
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

    # Tag the new route table
    await asyncio.to_thread(
        ec2.create_tags,
        Resources=[route_table_id],
        Tags=[
            {"Key": "Name", "Value": f"{RESOURCE_PREFIX}-RouteTable"},
            {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
            {"Key": "CreatedBy", "Value": CREATOR_VALUE},
        ],
    )

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
    # First check for security groups with our tag
    tagged_security_groups = await asyncio.to_thread(
        ec2.describe_security_groups,
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]},
        ],
    )
    if tagged_security_groups["SecurityGroups"]:
        return tagged_security_groups["SecurityGroups"][0]["GroupId"]

    # Fall back to name-based search
    security_groups = await asyncio.to_thread(
        ec2.describe_security_groups,
        Filters=[
            {"Name": "group-name", "Values": [f"{RESOURCE_PREFIX}SG"]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ],
    )

    if security_groups["SecurityGroups"]:
        # Found by name, let's tag it for future lookups
        sg_id = security_groups["SecurityGroups"][0]["GroupId"]
        await asyncio.to_thread(
            ec2.create_tags,
            Resources=[sg_id],
            Tags=[
                {"Key": "Name", "Value": f"{RESOURCE_PREFIX}SG"},
                {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                {"Key": "CreatedBy", "Value": CREATOR_VALUE},
            ],
        )
        return sg_id
    else:
        # Create a new security group
        security_group = await asyncio.to_thread(
            ec2.create_security_group,
            GroupName=f"{RESOURCE_PREFIX}SG",
            Description="Security group for Spot Instances",
            VpcId=vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [
                        {"Key": "Name", "Value": f"{RESOURCE_PREFIX}SG"},
                        {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                        {"Key": "CreatedBy", "Value": CREATOR_VALUE},
                    ],
                }
            ],
        )
        security_group_id = security_group["GroupId"]

        # Configure the security group rules
        await asyncio.to_thread(
            ec2.authorize_security_group_ingress,
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH access"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1234,
                    "ToPort": 1234,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Bacalhau health check"}
                    ],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1235,
                    "ToPort": 1235,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Bacalhau service"}
                    ],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 6001,
                    "ToPort": 6001,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Bacalhau service"}
                    ],
                },
            ],
        )
        return security_group_id


async def create_spot_instances():
    """Create spot instances across all configured regions.

    This is the main function for instance creation that:
    1. Distributes instances across regions based on configuration
    2. Creates the instances in parallel
    3. Waits for all instances to get their public IPs
    4. Optionally waits for SSH and Bacalhau services to be available
    5. Displays comprehensive summary of all created instances

    The function waits for all spot requests to be either fulfilled or failed
    and ensures a complete summary is provided before exiting.

    Returns:
        bool: True if all instances were successfully created with IPs, False otherwise
    """
    global task_name, task_total
    task_name = "Creating Spot Instances"
    task_total = MAX_NODES

    # Track creation progress across all regions
    creation_results = {}
    for region in AWS_REGIONS:
        creation_results[region] = {
            "requested": 0,
            "fulfilled": 0,
            "ip_assigned": 0,
            "failed": 0,
            "zones": {},
        }

    logger.info(f"Starting spot instance creation - target: {MAX_NODES} instances")

    async def create_in_region(region):
        global global_node_count
        available_slots = MAX_NODES - global_node_count
        region_cfg = config.get_region_config(region)

        if available_slots <= 0:
            logger.warning(f"Reached maximum nodes. Skipping region: {region}")
            return [], {}

        instances_to_create = (
            min(INSTANCES_PER_REGION, available_slots)
            if region_cfg.get("node_count") == "auto"
            else (min(region_cfg.get("node_count"), available_slots))
        )

        if instances_to_create == 0:
            logger.info(f"No instances to create in region {region}")
            return [], {}

        # Update creation tracking
        creation_results[region]["requested"] = instances_to_create
        logger.info(
            f"Creating {instances_to_create} spot instances in region: {region}"
        )

        global_node_count += instances_to_create
        instance_ids = await create_spot_instances_in_region(
            config, instances_to_create, region
        )

        # Log success or failure
        if instance_ids:
            logger.info(
                f"Successfully created {len(instance_ids)} instances in {region}"
            )
            creation_results[region]["fulfilled"] = len(instance_ids)
        else:
            logger.warning(f"Failed to create any instances in {region}")
            creation_results[region]["failed"] = instances_to_create

        return instance_ids

    # Process regions in batches to start machine creation sooner
    # Choose a batch size that gives good parallelism without overwhelming the system
    batch_size = 10  # Process 10 regions at a time
    total_created = 0
    total_requested = 0
    logger.info(f"Creating instances in batches of {batch_size} regions")

    # Group regions into batches
    region_batches = [
        AWS_REGIONS[i : i + batch_size] for i in range(0, len(AWS_REGIONS), batch_size)
    ]

    # Process each batch
    for batch_num, region_batch in enumerate(region_batches, 1):
        logger.info(
            f"Processing batch {batch_num}/{len(region_batches)} with {len(region_batch)} regions"
        )

        # Create instances in this batch of regions in parallel
        create_tasks = [create_in_region(region) for region in region_batch]
        batch_results = await asyncio.gather(*create_tasks)

        # Count created instances in this batch
        batch_created = sum(len(ids) for ids in batch_results if ids)
        total_created += batch_created

        # Count total requested for this batch
        batch_requested = sum(
            creation_results[region]["requested"] for region in region_batch
        )
        total_requested += batch_requested

        logger.info(
            f"Batch {batch_num} requested {batch_requested} instances, created {batch_created}"
        )

        # Wait for public IPs for instances in this batch
        if batch_created > 0:
            logger.info(f"Waiting for public IPs for batch {batch_num}...")
            await wait_for_batch_public_ips()

            # Update IP assignment counts
            for region in region_batch:
                ip_count = sum(
                    1
                    for status in all_statuses.values()
                    if status.region == region and status.public_ip
                )
                creation_results[region]["ip_assigned"] = ip_count

    logger.info(
        f"All batches processed, requested {total_requested} instances, created {total_created} across all regions"
    )

    # For logging status of all instances
    fulfilled_instances = sum(
        1 for status in all_statuses.values() if status.instance_id
    )
    pending_spot_requests = sum(
        1
        for status in all_statuses.values()
        if status.spot_request_id and not status.instance_id
    )
    instances_with_ip = sum(1 for status in all_statuses.values() if status.public_ip)

    logger.info(
        f"Status summary: {fulfilled_instances} spot requests fulfilled, {pending_spot_requests} pending, {instances_with_ip} have IPs"
    )

    # Capture detailed error information even if no instances were created
    error_regions = []
    error_types = {
        "credential_issues": False,
        "capacity_issues": False,
        "price_issues": False,
        "config_issues": False,
    }

    # Look through all status objects for errors
    for status in all_statuses.values():
        status_text = status.detailed_status.lower() if status.detailed_status else ""

        # Capture region if there's an error
        if "error" in status_text or "failed" in status_text:
            error_regions.append(status.region)

        # Track specific error types
        if (
            "expired" in status_text
            or "invalid" in status_text
            or "token" in status_text
        ):
            error_types["credential_issues"] = True
        elif "capacity" in status_text or "not available" in status_text:
            error_types["capacity_issues"] = True
        elif "price" in status_text or "price-too-low" in status_text:
            error_types["price_issues"] = True
        elif "config" in status_text or "parameter" in status_text:
            error_types["config_issues"] = True

    # Don't continue with IP waiting if no instances were created
    if total_created == 0:
        logger.warning("No instances were created - creation failed")

        # Log detailed error information
        error_msg = "CREATION FAILED: No instances were created"
        logger.error(error_msg)

        if error_types["credential_issues"]:
            logger.error(
                "ERROR CAUSE: AWS credential issues detected - credentials may be expired or invalid"
            )
        elif error_types["capacity_issues"]:
            logger.error(
                "ERROR CAUSE: AWS capacity issues detected - requested instance types not available in the selected regions"
            )
        elif error_types["price_issues"]:
            logger.error(
                "ERROR CAUSE: AWS price issues detected - spot price may be too low for the requested instances"
            )
        elif error_types["config_issues"]:
            logger.error(
                "ERROR CAUSE: Configuration issues detected - check instance types and region settings in config"
            )
        else:
            logger.error(
                "ERROR CAUSE: Unknown - check AWS console for more details on spot request failures"
            )

        # Print an empty summary showing all regions with 0 nodes
        print_creation_summary(creation_results)

        # Print console error messages
        console.print()
        console.print(
            "[bold red]⚠ CREATION FAILED: No instances were created[/bold red]"
        )

        if error_types["credential_issues"]:
            console.print(
                "[red]AWS credential issues detected - credentials may be expired or invalid[/red]"
            )
            console.print(
                "[yellow]Try running 'aws sso login' to refresh your credentials[/yellow]"
            )
        elif error_types["capacity_issues"]:
            console.print(
                "[red]AWS capacity issues detected - requested instance types not available[/red]"
            )
            console.print(
                "[yellow]Try different instance types or regions in your config.yaml[/yellow]"
            )
        elif error_types["price_issues"]:
            console.print(
                "[red]Spot price issues detected - spot price may be too low[/red]"
            )
            console.print(
                "[yellow]Try different instance types or regions in your config.yaml[/yellow]"
            )
        elif error_types["config_issues"]:
            console.print("[red]Configuration issues detected in your setup[/red]")
            console.print(
                "[yellow]Check instance types and region settings in config.yaml[/yellow]"
            )
        else:
            console.print(
                "[red]Unknown issues encountered creating spot instances[/red]"
            )
            console.print(
                "[yellow]Check AWS console for more details on spot request failures[/yellow]"
            )

        console.print()
        return False

    # Wait for any remaining IP address assignments to complete with a reasonable timeout
    logger.info("Ensuring all instances have received public IP addresses...")
    ip_wait_timeout = 300  # 5 minutes
    ip_wait_start_time = time.time()
    all_ips_received = await wait_for_public_ips()
    ip_wait_elapsed = time.time() - ip_wait_start_time

    # Update IP assignment counts for all regions
    for region in AWS_REGIONS:
        ip_count = sum(
            1
            for status in all_statuses.values()
            if status.region == region and status.public_ip
        )
        creation_results[region]["ip_assigned"] = ip_count

        # Update zone information
        for status in all_statuses.values():
            if status.region == region:
                zone = status.zone
                if zone not in creation_results[region]["zones"]:
                    creation_results[region]["zones"][zone] = {
                        "requested": 0,
                        "fulfilled": 0,
                        "ip_assigned": 0,
                        "failed": 0,
                    }

                # Count request
                creation_results[region]["zones"][zone]["requested"] += 1

                # Count fulfilled
                if status.instance_id:
                    creation_results[region]["zones"][zone]["fulfilled"] += 1

                # Count IP assignment
                if status.public_ip:
                    creation_results[region]["zones"][zone]["ip_assigned"] += 1

                # Count failures
                if not status.instance_id or (
                    status.instance_id and not status.public_ip
                ):
                    creation_results[region]["zones"][zone]["failed"] += 1

    # Log IP assignment results
    if all_ips_received:
        logger.info(f"All instances received public IPs after {ip_wait_elapsed:.1f}s")
    else:
        logger.warning(
            f"Some instances did not receive public IPs within {ip_wait_timeout}s"
        )

        # For partially successful creations, log which regions had issues
        fulfilled_count = sum(
            1 for status in all_statuses.values() if status.instance_id
        )
        ip_count = sum(1 for status in all_statuses.values() if status.public_ip)
        failed_count = total_requested - ip_count

        if failed_count > 0:
            logger.error(
                f"CREATION PARTIALLY FAILED: {ip_count}/{total_requested} instances were created with IPs"
            )
            logger.error(f"Failed regions: {', '.join(set(error_regions))}")

            # Log specific error types
            if error_types["capacity_issues"]:
                logger.error(
                    "FAILURE CAUSE: AWS capacity issues detected in some regions"
                )
            elif error_types["price_issues"]:
                logger.error(
                    "FAILURE CAUSE: Spot price issues detected in some regions"
                )
            else:
                logger.error(
                    "FAILURE CAUSE: Various issues - see summary table for details"
                )

    # Always save machine information to MACHINES.json
    logger.info("Saving machine information to MACHINES.json")
    save_machines_to_json(operation="update")

    # Display the node table with current status
    logger.info("Printing node information table")
    print_node_table()

    # Print comprehensive creation summary
    print_creation_summary(creation_results)

    # For partially successful creations, print console warnings
    if not all_ips_received and total_created > 0:
        ip_count = sum(1 for status in all_statuses.values() if status.public_ip)
        failed_count = total_requested - ip_count

        console.print()
        console.print(
            f"[bold yellow]⚠ PARTIAL SUCCESS: {ip_count}/{total_requested} instances were created with IPs[/bold yellow]"
        )

        if error_types["capacity_issues"]:
            console.print(
                "[yellow]AWS capacity issues detected in some regions[/yellow]"
            )
            console.print(
                "[yellow]Try different instance types or regions in your config.yaml[/yellow]"
            )
        elif error_types["price_issues"]:
            console.print("[yellow]Spot price issues detected in some regions[/yellow]")
            console.print(
                "[yellow]Try different instance types or regions in your config.yaml[/yellow]"
            )
        else:
            console.print(
                "[yellow]Various issues encountered - see summary table for details[/yellow]"
            )

        console.print()

    return all_ips_received


def print_creation_summary(creation_results):
    """Print a comprehensive summary of instance creation results.

    Args:
        creation_results: Dictionary containing creation statistics by region and zone
    """
    # Create summary table
    table = Table(
        title="Spot Instance Creation Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold green",
    )

    # Add columns
    table.add_column("Region", style="cyan")
    table.add_column("Zone", style="blue")
    table.add_column("Requested", style="yellow", justify="right")
    table.add_column("Fulfilled", style="green", justify="right")
    table.add_column("With IP", style="magenta", justify="right")
    table.add_column("Failed", style="red", justify="right")

    # Track totals
    total_requested = 0
    total_fulfilled = 0
    total_with_ip = 0
    total_failed = 0

    # Add rows for each region and zone
    for region in sorted(creation_results.keys()):
        region_data = creation_results[region]
        region_requested = region_data.get("requested", 0)
        region_fulfilled = region_data.get("fulfilled", 0)
        region_with_ip = region_data.get("ip_assigned", 0)
        region_failed = region_requested - region_with_ip

        # Update totals
        total_requested += region_requested
        total_fulfilled += region_fulfilled
        total_with_ip += region_with_ip
        total_failed += region_failed

        # If no instances were requested in this region, show a single row
        if region_requested == 0:
            table.add_row(region, "[italic]No zones[/italic]", "0", "0", "0", "0")
            continue

        # Get zone data
        zones = region_data.get("zones", {})

        # If we have zone data, show it
        if zones:
            # Sort zones for consistent display
            for i, zone in enumerate(sorted(zones.keys())):
                zone_data = zones[zone]
                zone_requested = zone_data.get("requested", 0)
                zone_fulfilled = zone_data.get("fulfilled", 0)
                zone_with_ip = zone_data.get("ip_assigned", 0)
                zone_failed = zone_requested - zone_with_ip

                # First row shows region name
                if i == 0:
                    table.add_row(
                        region,
                        zone,
                        str(zone_requested),
                        str(zone_fulfilled),
                        str(zone_with_ip),
                        str(zone_failed),
                    )
                else:
                    # Subsequent rows don't repeat region
                    table.add_row(
                        "",
                        zone,
                        str(zone_requested),
                        str(zone_fulfilled),
                        str(zone_with_ip),
                        str(zone_failed),
                    )
        else:
            # No zone data available, just show region totals
            table.add_row(
                region,
                "All zones",
                str(region_requested),
                str(region_fulfilled),
                str(region_with_ip),
                str(region_failed),
            )

    # Add a total row
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        f"[bold]{total_requested}[/bold]",
        f"[bold]{total_fulfilled}[/bold]",
        f"[bold]{total_with_ip}[/bold]",
        f"[bold]{total_failed}[/bold]",
    )

    # Display the table
    console.print()
    console.print(table)
    console.print()

    # Add a status message
    if total_with_ip == total_requested and total_requested > 0:
        console.print(
            f"[bold green]✓[/bold green] All {total_requested} requested instances were successfully created with IPs"
        )
    elif total_with_ip > 0:
        console.print(
            f"[bold yellow]![/bold yellow] {total_with_ip} of {total_requested} requested instances were successfully created with IPs"
        )
        console.print(
            f"[yellow]Some instances may have failed due to capacity issues or other AWS limitations[/yellow]"
        )
    else:
        console.print(
            f"[bold red]✗[/bold red] No instances were successfully created with IPs"
        )
        console.print("[red]Please check AWS credentials, capacity, and limits[/red]")

    console.print()


def print_node_table():
    """Display a table of all nodes showing hostname, region, zone, and IP addresses.

    This presents a clean summary of all nodes that were created during the operation,
    making it easy for users to see what resources are available.

    This is a synchronous function to ensure it works outside of an async context.
    """
    # Get sorted list of statuses for consistent display
    sorted_statuses = sorted(all_statuses.values(), key=lambda x: (x.region, x.zone))

    # Only include instances that have a public IP (successfully created)
    nodes_with_ip = [s for s in sorted_statuses if s.public_ip]

    # Count pending spot requests that didn't get fulfilled
    pending_spot_requests = [
        s for s in sorted_statuses if s.spot_request_id and not s.instance_id
    ]

    # First create and show the successful nodes table
    if nodes_with_ip:
        # Create a new table specifically for the final display
        table = Table(
            title="Bacalhau Cluster Nodes",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )

        # Add columns with appropriate alignment and style
        table.add_column("Node #", style="dim", justify="right")
        table.add_column("Hostname", style="cyan")
        table.add_column("Region", style="green")
        table.add_column("Zone", style="blue")
        table.add_column("Public IP", style="yellow")
        table.add_column("Private IP", style="dim cyan")

        # Add rows for each node
        for i, status in enumerate(nodes_with_ip, 1):
            # Generate a hostname from region and zone
            hostname = f"bacalhau-{status.region}-{status.zone.split('-')[-1]}"

            table.add_row(
                str(i),
                hostname,
                status.region,
                status.zone,
                status.public_ip or "N/A",
                status.private_ip or "N/A",
            )

        # Log first for debug
        logger.info(f"Displaying final table with {len(nodes_with_ip)} nodes")

        # Display the table outside of the Live context
        console.print()  # Add some space
        console.print(table)
        console.print()  # Add some space after
    else:
        logger.warning("No nodes with IP addresses to display")
        console.print("[bold yellow]No nodes received IP addresses![/bold yellow]")
        console.print()

    # Show a summary of successful vs. pending spot requests
    console.print(f"[bold]Spot Instance Summary:[/bold]")
    console.print(
        f"- Successfully provisioned: [green]{len(nodes_with_ip)}[/green] nodes"
    )
    console.print(
        f"- Pending spot requests: [yellow]{len(pending_spot_requests)}[/yellow]"
    )
    console.print(f"- Total spot requests: [blue]{len(sorted_statuses)}[/blue]")
    console.print()

    # Also print a helpful message about how to connect to nodes with proper key authentication
    if nodes_with_ip:
        console.print(
            "[bold green]✓[/bold green] Your Bacalhau cluster is being provisioned!"
        )
        console.print(
            "[yellow]Machines have IP addresses but may need a few minutes to complete setup[/yellow]"
        )

        # Get the username and private key path from config
        username = config.get_username()
        private_key_path = config.get_private_ssh_key_path()

        # Create the SSH command with key file if available
        if private_key_path:
            ssh_cmd = f"ssh -i {private_key_path} {username}@<Public IP>"
        else:
            ssh_cmd = f"ssh {username}@<Public IP>"

        console.print(f"[dim]To connect to any node: {ssh_cmd}[/dim]")
    else:
        console.print(
            "[bold red]⚠ No instances were successfully provisioned with IP addresses.[/bold red]"
        )
        console.print(
            "[yellow]This could be due to spot capacity issues in the selected regions.[/yellow]"
        )
        console.print(
            "[yellow]Consider trying again, selecting different instance types, or using different regions.[/yellow]"
        )

    console.print()


async def wait_for_provisioning():
    """Wait for all instances to complete their provisioning process.

    This function checks SSH connectivity and whether the Bacalhau services
    are running on each instance. It updates the statuses throughout the
    provisioning process.

    Returns:
        bool: True when all instances are fully provisioned
    """
    global all_statuses
    max_timeout = 600  # 10 minutes timeout
    start_time = time.time()
    poll_interval = 15  # seconds between polls

    logger.info(
        f"Monitoring provisioning status for all instances (timeout: {max_timeout}s)"
    )

    # Count instances we're monitoring
    instances_to_monitor = [
        s for s in all_statuses.values() if s.instance_id and s.public_ip
    ]

    if not instances_to_monitor:
        logger.warning("No instances to monitor for provisioning")
        return False

    logger.info(f"Monitoring provisioning for {len(instances_to_monitor)} instances")

    # Initialize provisioning statuses
    for status in instances_to_monitor:
        status.detailed_status = "Waiting for provisioning"
        # Make sure to signal for UI update
        events_to_progress.append(status)

    # Track completion
    while True:
        # Check timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > max_timeout:
            logger.warning(
                f"Timeout reached after {max_timeout}s waiting for provisioning"
            )
            # Update statuses for those that didn't complete
            for status in instances_to_monitor:
                if status.detailed_status != "Provisioning complete":
                    status.detailed_status = "Provisioning timeout"
                    events_to_progress.append(status)
            return False

        # Check all instances in parallel
        async def check_instance(status):
            try:
                # Skip already completed instances
                if status.detailed_status == "Provisioning complete":
                    return True

                # Update status to show we're checking
                status.detailed_status = f"Checking provisioning ({int(elapsed_time)}s)"
                events_to_progress.append(status)

                # Check SSH connectivity first
                if not await check_ssh_connectivity(status.public_ip):
                    status.detailed_status = "Waiting for SSH access"
                    events_to_progress.append(status)
                    return False

                # Then check if Docker is running
                if not await check_docker_running(status.public_ip):
                    status.detailed_status = "Waiting for Docker"
                    events_to_progress.append(status)
                    return False

                # Finally check if Bacalhau service is running
                if not await check_bacalhau_service(status.public_ip):
                    status.detailed_status = "Waiting for Bacalhau"
                    events_to_progress.append(status)
                    return False

                # All checks passed, provisioning is complete
                status.detailed_status = "Provisioning complete"
                events_to_progress.append(status)
                return True

            except Exception as e:
                logger.error(f"Error checking instance {status.instance_id}: {str(e)}")
                status.detailed_status = f"Check error: {str(e)[:20]}"
                events_to_progress.append(status)
                return False

        # Check all instances in parallel
        check_tasks = [check_instance(status) for status in instances_to_monitor]
        results = await asyncio.gather(*check_tasks)

        # Count how many are complete
        complete_count = sum(1 for r in results if r)
        logger.info(
            f"Provisioning progress: {complete_count}/{len(instances_to_monitor)} instances ready"
        )

        # Check if all are complete
        if all(results):
            logger.info("All instances have completed provisioning")

            # Keep the display up for a few more seconds to show the final status
            logger.info(
                "Keeping display open for 5 more seconds to show provisioning complete"
            )
            await asyncio.sleep(5)

            return True

        # Wait before next check
        await asyncio.sleep(poll_interval)


async def check_ssh_connectivity(ip_address):
    """Check if an instance is accessible via SSH.

    Args:
        ip_address: The public IP address of the instance

    Returns:
        bool: True if SSH connection succeeds, False otherwise
    """
    try:
        # Use socket connection to check if port 22 is open
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip_address, 22), timeout=5.0
        )

        # Close the connection
        writer.close()
        await writer.wait_closed()

        return True
    except Exception:
        return False


async def check_docker_running(ip_address):
    """Check if Docker is running on the instance.

    Args:
        ip_address: The public IP address of the instance

    Returns:
        bool: True if docker appears to be running, False otherwise
    """
    # For now, we'll just check SSH since we can't easily run commands remotely
    # In a production version, this would use SSH to execute 'docker ps'
    return await check_ssh_connectivity(ip_address)


async def check_bacalhau_service(ip_address):
    """Check if the Bacalhau service is running on the instance.

    Args:
        ip_address: The public IP address of the instance

    Returns:
        bool: True if Bacalhau service appears to be running, False otherwise
    """
    try:
        # Try to connect to the bacalhau healthcheck port (assuming it's 1234)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip_address, 1234), timeout=5.0
        )

        # Close the connection
        writer.close()
        await writer.wait_closed()

        return True
    except Exception:
        return False


async def wait_for_batch_public_ips():
    """Wait for public IPs for instances in the most recent batch.

    This is a non-blocking function that can be called as a background task.
    It identifies instances without IPs that were created in recent batches
    and polls for their IP addresses.

    This allows us to start getting IPs while other machines are still creating.
    """
    # Find instances without public IPs among the most recently created ones
    # These will be instances that have an instance_id but no public_ip
    pending_instances = [
        status
        for status in all_statuses.values()
        if status.instance_id and not status.public_ip
    ]

    if not pending_instances:
        logger.debug("No pending instances waiting for IPs in this batch")
        return

    logger.info(
        f"Background task: Getting public IPs for {len(pending_instances)} new instances"
    )

    # Group instances by region for efficient API calls
    instances_by_region = {}
    for status in pending_instances:
        if status.region not in instances_by_region:
            instances_by_region[status.region] = []
        instances_by_region[status.region].append(status)

    # Set a reasonable timeout for this specific batch (shorter than the main wait)
    timeout = 120  # 2 minutes timeout per batch
    start_time = time.time()
    poll_interval = 5  # seconds between polls

    # Poll for public IPs
    while time.time() - start_time < timeout:
        # Count how many still need IPs
        still_pending = sum(1 for status in pending_instances if not status.public_ip)

        if still_pending == 0:
            logger.info(
                f"Background task: All {len(pending_instances)} instances in batch received IPs"
            )
            return

        logger.debug(
            f"Background task: Still waiting for {still_pending} instances to get public IPs"
        )

        # Update the IPs in parallel per region
        async def update_region_ips(region, statuses):
            # Skip if no instances still need IPs in this region
            if all(status.public_ip for status in statuses):
                return 0

            try:
                # Get EC2 client for this region
                ec2 = get_ec2_client(region)

                # Get instance IDs that still need IPs
                instance_ids = [
                    status.instance_id for status in statuses if not status.public_ip
                ]

                # Skip if no instances
                if not instance_ids:
                    return 0

                # Query AWS API for current instance information
                response = await asyncio.to_thread(
                    ec2.describe_instances, InstanceIds=instance_ids
                )

                # Process results and update statuses
                updated_count = 0
                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        public_ip = instance.get("PublicIpAddress", "")
                        private_ip = instance.get("PrivateIpAddress", "")

                        # Find the matching status
                        for status in statuses:
                            if status.instance_id == instance_id:
                                if public_ip and not status.public_ip:
                                    status.public_ip = public_ip
                                    status.detailed_status = "Public IP assigned"
                                    updated_count += 1
                                if private_ip:
                                    status.private_ip = private_ip
                                # Signal for UI update
                                events_to_progress.append(status)

                return updated_count

            except Exception as e:
                logger.error(f"Error updating IPs for region {region}: {str(e)}")
                return 0

        # Create tasks for each region
        tasks = [
            update_region_ips(region, statuses)
            for region, statuses in instances_by_region.items()
        ]

        # Run all tasks in parallel
        results = await asyncio.gather(*tasks)

        # Sum up the total updated
        updated_count = sum(results)
        if updated_count > 0:
            logger.info(f"Background task: Received {updated_count} new public IPs")

            # Save the updates to MACHINES.json
            save_machines_to_json(operation="update")

        # Wait before next poll
        await asyncio.sleep(poll_interval)

    # If we get here, we hit the timeout
    logger.warning(f"Background task: Timeout waiting for IPs after {timeout}s")


async def wait_for_public_ips():
    """Wait for all instances to get their public IP addresses.

    This function monitors the instance statuses and waits until all have IP addresses
    or until a timeout is reached. It updates the progress display throughout.

    Returns:
        bool: True if all instances got IPs, False if any timed out
    """
    global all_statuses
    timeout = 300  # 5 minutes timeout
    start_time = time.time()
    poll_interval = 5  # seconds between polls

    logger.info(f"Waiting for public IP addresses (timeout: {timeout}s)")

    # Count all instances we're waiting for - both spot requests and instances without IPs
    pending_spot_requests = sum(
        1
        for status in all_statuses.values()
        if status.spot_request_id and not status.instance_id
    )
    pending_ips = sum(
        1
        for status in all_statuses.values()
        if status.instance_id and not status.public_ip
    )

    total_pending = pending_spot_requests + pending_ips
    logger.info(
        f"Waiting for {total_pending} instances to complete ({pending_spot_requests} spot requests still pending, {pending_ips} awaiting IPs)"
    )

    # Group instances by region for parallel processing
    def get_instances_by_region():
        instances_by_region = {}
        spot_requests_by_region = {}

        # First, organize by region
        for status in all_statuses.values():
            region = status.region
            if not region:
                continue

            # Handle instances waiting for IP addresses
            if status.instance_id and not status.public_ip:
                if region not in instances_by_region:
                    instances_by_region[region] = []
                instances_by_region[region].append(status)

            # Handle spot requests waiting for fulfillment
            elif status.spot_request_id and not status.instance_id:
                if region not in spot_requests_by_region:
                    spot_requests_by_region[region] = []
                spot_requests_by_region[region].append(status)

        # Combine both mappings for return
        combined_by_region = {}
        all_regions = set(instances_by_region.keys()) | set(
            spot_requests_by_region.keys()
        )

        for region in all_regions:
            combined_by_region[region] = {
                "instances": instances_by_region.get(region, []),
                "spot_requests": spot_requests_by_region.get(region, []),
            }

        return combined_by_region

    # Track completion status
    all_ips_received = False

    while True:
        # Count pending spot requests and instances waiting for IPs
        pending_spot_requests = sum(
            1
            for status in all_statuses.values()
            if status.spot_request_id and not status.instance_id
        )
        pending_ips = sum(
            1
            for status in all_statuses.values()
            if status.instance_id and not status.public_ip
        )

        total_pending = pending_spot_requests + pending_ips

        # Check if we're done with both spot requests and IP assignment
        all_complete = total_pending == 0

        # Check for timeout
        time_elapsed = time.time() - start_time
        timed_out = time_elapsed > timeout

        # Exit conditions
        if all_complete:
            provisioned_count = sum(
                1 for status in all_statuses.values() if status.public_ip
            )
            logger.info(
                f"All instances processed - {provisioned_count} successfully provisioned with public IPs"
            )
            all_ips_received = True
            break

        if timed_out:
            # Update status for all pending instances
            for status in all_statuses.values():
                if status.spot_request_id and not status.instance_id:
                    status.detailed_status = "Spot request not fulfilled after timeout"
                    events_to_progress.append(status)
                elif status.instance_id and not status.public_ip:
                    status.detailed_status = "No public IP after timeout"
                    events_to_progress.append(status)

            provisioned_count = sum(
                1 for status in all_statuses.values() if status.public_ip
            )
            logger.warning(
                f"Timed out after {timeout}s - {provisioned_count} instances provisioned, {pending_spot_requests} spot requests pending, {pending_ips} instances missing IPs"
            )
            break

        # Get instances grouped by region
        instances_by_region = get_instances_by_region()
        if not instances_by_region:
            # No instances need IPs, we're done
            logger.info("No instances waiting for IPs")
            all_ips_received = True
            break

        # Log progress
        pending_count = sum(len(ids) for ids in instances_by_region.values())
        logger.info(
            f"Still waiting for {pending_count} instances to get public IPs ({int(time_elapsed)}s elapsed)"
        )

        # Create tasks to query each region in parallel
        async def query_region_instances(region, region_data):
            try:
                ec2 = get_ec2_client(region)
                updated_count = 0

                # First check spot request status for any pending requests
                spot_requests = region_data.get("spot_requests", [])
                if spot_requests:
                    # Get all the spot request IDs
                    spot_request_ids = [
                        sr.spot_request_id for sr in spot_requests if sr.spot_request_id
                    ]

                    if spot_request_ids:
                        logger.debug(
                            f"Checking {len(spot_request_ids)} spot requests in {region}"
                        )
                        try:
                            spot_response = await asyncio.to_thread(
                                ec2.describe_spot_instance_requests,
                                SpotInstanceRequestIds=spot_request_ids,
                            )

                            # Process spot request results
                            for request in spot_response.get(
                                "SpotInstanceRequests", []
                            ):
                                request_id = request.get("SpotInstanceRequestId")
                                instance_id = request.get("InstanceId")
                                status_code = request.get("Status", {}).get("Code", "")
                                status_message = request.get("Status", {}).get(
                                    "Message", ""
                                )

                                # Find the matching status object
                                for status in spot_requests:
                                    if status.spot_request_id == request_id:
                                        # Update status with details
                                        status.detailed_status = (
                                            f"{status_code}: {status_message}"
                                        )

                                        # If the request has an instance ID, it's fulfilled
                                        if instance_id:
                                            status.instance_id = instance_id
                                            status.fulfilled = True
                                            updated_count += 1

                                        # Signal for UI update
                                        events_to_progress.append(status)
                        except Exception as e:
                            logger.error(
                                f"Error checking spot requests in {region}: {str(e)}"
                            )

                # Now check for IP addresses for instances
                instances = region_data.get("instances", [])
                if instances:
                    # Get all instance IDs
                    instance_ids = [i.instance_id for i in instances if i.instance_id]

                    if instance_ids:
                        logger.debug(
                            f"Checking {len(instance_ids)} instances for IPs in {region}"
                        )
                        try:
                            instance_response = await asyncio.to_thread(
                                ec2.describe_instances, InstanceIds=instance_ids
                            )

                            # Process results and update statuses
                            for reservation in instance_response.get(
                                "Reservations", []
                            ):
                                for instance in reservation.get("Instances", []):
                                    instance_id = instance["InstanceId"]
                                    public_ip = instance.get("PublicIpAddress", "")
                                    private_ip = instance.get("PrivateIpAddress", "")

                                    # Find the matching status object
                                    for status in instances:
                                        if status.instance_id == instance_id:
                                            if public_ip and not status.public_ip:
                                                status.public_ip = public_ip
                                                status.detailed_status = (
                                                    "Public IP assigned"
                                                )
                                                updated_count += 1
                                            if private_ip:
                                                status.private_ip = private_ip
                                            # Signal for UI update
                                            events_to_progress.append(status)
                        except Exception as e:
                            logger.error(
                                f"Error checking instance IPs in {region}: {str(e)}"
                            )

                return updated_count
            except Exception as e:
                logger.error(f"Error querying region {region}: {str(e)}")
                return 0

        # Create and run tasks for all regions in parallel
        regions_to_query = get_instances_by_region()
        tasks = [
            query_region_instances(region, region_data)
            for region, region_data in regions_to_query.items()
        ]

        if tasks:
            # Wait for all regions to be queried with timeout protection
            try:
                results = await asyncio.gather(*tasks)

                # Sum up the total updated
                updated_count = sum(results)

                # Log how many updates we made
                if updated_count > 0:
                    # Count current success stats
                    fulfilled_requests = sum(
                        1
                        for status in all_statuses.values()
                        if status.spot_request_id and status.instance_id
                    )
                    ip_assigned = sum(
                        1
                        for status in all_statuses.values()
                        if status.instance_id and status.public_ip
                    )

                    logger.info(
                        f"Updated {updated_count} instances - {fulfilled_requests} spot requests fulfilled, {ip_assigned} instances have IPs"
                    )

                    # Save the updates to MACHINES.json
                    save_machines_to_json(operation="update")

            except Exception as e:
                logger.error(f"Error waiting for instances: {str(e)}")

        # Wait before next poll - we don't want to hammer the AWS API
        await asyncio.sleep(poll_interval)

    # Return whether all instances got IPs or not
    return all_ips_received


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
    """Destroy all managed instances across all regions.

    This function first loads instances from MACHINES.json, then queries AWS APIs to find
    any instances that might have been missed. It ensures all terminate operations complete
    before exiting, and prints a comprehensive summary at the end.
    """
    global task_name, task_total, events_to_progress
    task_name = "Terminating Spot Instances"
    events_to_progress = []

    # Start by loading MACHINES.json
    logger.info("Loading existing machine records from MACHINES.json")
    existing_data = load_machines_from_json()
    existing_machines = existing_data.get("machines", {})

    # If we have existing machines in the file, create status objects for them first
    if existing_machines:
        logger.info(
            f"Found {len(existing_machines)} existing machines in MACHINES.json"
        )
        for machine_id, machine_data in existing_machines.items():
            try:
                # Extract needed information for termination
                region = machine_data.get("region")
                zone = machine_data.get("zone")
                instance_id = machine_data.get("instance_id")
                vpc_id = machine_data.get("vpc_id")

                if not all([region, zone, instance_id]):
                    logger.warning(
                        f"Incomplete data for machine {machine_id}, skipping"
                    )
                    continue

                # Create a status object for tracking
                status = InstanceStatus(region, zone)
                status.instance_id = instance_id
                status.status = "Terminating"
                status.detailed_status = "From MACHINES.json"
                status.vpc_id = vpc_id
                all_statuses[instance_id] = status
                events_to_progress.append(status)

                logger.info(
                    f"Added instance {instance_id} in {region} for termination from MACHINES.json"
                )

            except Exception as e:
                logger.error(f"Error processing machine record {machine_id}: {str(e)}")

    # Now asynchronously query AWS APIs to find any instances we might have missed
    logger.info("Querying AWS APIs for instances across all regions...")

    # Create a map to track instance-to-region mapping for later termination
    instance_region_map = {}

    # Add all instances from MACHINES.json to our map
    for instance_id, status in all_statuses.items():
        instance_region_map[instance_id] = {
            "region": status.region,
            "vpc_id": status.vpc_id,
        }

    # Track all regions where we'll do the search
    regions_queried = set()
    regions_with_instances = set()

    # Query each region in parallel
    async def query_region_for_instances(region):
        nonlocal regions_queried
        regions_queried.add(region)
        logger.info(f"Checking region {region} for instances to terminate...")
        region_instances = {}  # Store instances found in this region

        try:
            ec2 = get_ec2_client(region)
            # Use safe_aws_call for proper timeout handling
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

                    # Track regions with instances
                    if instance_count > 0:
                        regions_with_instances.add(region)

                    # Check if we already have this instance in our tracking or instance_region_map
                    if (
                        instance_id not in all_statuses
                        and instance_id not in instance_region_map
                    ):
                        logger.info(
                            f"Found additional instance {instance_id} in {az} from AWS API"
                        )
                        thisInstanceStatusObject = InstanceStatus(region, az)
                        thisInstanceStatusObject.instance_id = instance_id
                        thisInstanceStatusObject.status = "Terminating"
                        thisInstanceStatusObject.detailed_status = "Found via AWS API"
                        thisInstanceStatusObject.vpc_id = vpc_id
                        all_statuses[instance_id] = thisInstanceStatusObject
                        region_instances[instance_id] = {
                            "region": region,
                            "vpc_id": vpc_id,
                        }

            if instance_count == 0:
                logger.info(f"No instances found in region {region}")

            return region_instances

        except TimeoutError:
            logger.error(
                f"Timeout while listing instances in {region}. Check your AWS credentials."
            )
            return {}
        except Exception as e:
            logger.error(
                f"An error occurred while listing instances in {region}: {str(e)}"
            )
            return {}

    # Query all regions in parallel
    query_tasks = [query_region_for_instances(region) for region in AWS_REGIONS]
    region_results = await asyncio.gather(*query_tasks)

    # Merge results from all regions
    for region_instances in region_results:
        instance_region_map.update(region_instances)

    # Check if we found any instances to terminate
    if not all_statuses:
        logger.info("No instances found to terminate.")
        # Still show summary with 0 instances for all regions
        empty_map = {
            f"none-{region}": {"region": region, "vpc_id": None}
            for region in AWS_REGIONS
        }
        print_termination_summary(empty_map)

        # Clear MACHINES.json since no instances were found
        logger.info("Clearing MACHINES.json since no instances were found")
        try:
            # Create empty machine data
            output_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "machines": {},
                "total_count": 0,
                "regions": [],
                "last_operation": "delete",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            # Write to temporary file first
            temp_file = "MACHINES.json.tmp"
            with open(temp_file, "w") as f:
                try:
                    import fcntl

                    fcntl.flock(f, fcntl.LOCK_EX)
                    json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
                    f.flush()
                    os.fsync(f.fileno())
                    fcntl.flock(f, fcntl.LOCK_UN)
                except (ImportError, AttributeError):
                    json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
                    f.flush()

            # Atomic rename
            os.replace(temp_file, "MACHINES.json")
            logger.info("Successfully cleared MACHINES.json")

        except Exception as e:
            logger.error(f"Error clearing MACHINES.json: {str(e)}")

        return

    task_total = len(all_statuses)
    logger.info(f"Found {task_total} instances to terminate.")

    # Track termination progress across all regions
    termination_results = {}
    for region in AWS_REGIONS:
        termination_results[region] = {
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "zones": {},
        }

    async def terminate_instances_in_region(region, region_instances):
        if not region_instances:
            logger.info(f"No instances to terminate in {region}")
            return

        # Deduplication check - double check for duplicates
        # This is an extra safeguard to ensure we don't try to terminate the same instance twice
        unique_instances = list(set(region_instances))

        if len(unique_instances) != len(region_instances):
            logger.warning(
                f"Removed {len(region_instances) - len(unique_instances)} duplicate instances in {region}"
            )
            region_instances = unique_instances

        # Update region statistics
        termination_results[region]["total"] = len(region_instances)

        # Collect zone info for each instance for later reporting
        for instance_id in region_instances:
            if instance_id in all_statuses:
                zone = all_statuses[instance_id].zone
                if zone not in termination_results[region]["zones"]:
                    termination_results[region]["zones"][zone] = {
                        "total": 0,
                        "succeeded": 0,
                        "failed": 0,
                    }
                termination_results[region]["zones"][zone]["total"] += 1

        ec2 = get_ec2_client(region)
        try:
            logger.info(f"Terminating {len(region_instances)} instances in {region}...")
            await safe_aws_call(ec2.terminate_instances, InstanceIds=region_instances)
            logger.info(
                f"Instances terminate request sent in {region}, waiting for completion..."
            )

            waiter = ec2.get_waiter("instance_terminated")
            start_time = time.time()
            max_wait_time = 600  # 10 minutes timeout

            while True:
                # Check if timeout reached
                if time.time() - start_time > max_wait_time:
                    logger.warning(
                        f"Reached timeout of {max_wait_time}s waiting for instances in {region}"
                    )

                    # Mark all remaining instances as timeout
                    for instance_id in region_instances:
                        thisInstanceStatusObject = all_statuses[instance_id]
                        if thisInstanceStatusObject.status != "Terminated":
                            thisInstanceStatusObject.status = "Timeout"
                            thisInstanceStatusObject.detailed_status = (
                                f"Timeout after {max_wait_time}s"
                            )
                            events_to_progress.append(thisInstanceStatusObject)
                            all_statuses[instance_id] = thisInstanceStatusObject

                            # Update statistics
                            zone = thisInstanceStatusObject.zone
                            if zone in termination_results[region]["zones"]:
                                termination_results[region]["zones"][zone][
                                    "failed"
                                ] += 1
                            termination_results[region]["failed"] += 1

                    # Break out of the loop if timeout
                    break

                try:
                    logger.info(f"Checking if instances in {region} are terminated...")
                    await safe_aws_call(
                        waiter.wait,
                        InstanceIds=region_instances,
                        WaiterConfig={"MaxAttempts": 1},
                    )
                    logger.info(f"All instances in {region} terminated successfully")

                    # Mark all instances as successfully terminated
                    for instance_id in region_instances:
                        thisInstanceStatusObject = all_statuses[instance_id]
                        thisInstanceStatusObject.status = "Terminated"
                        thisInstanceStatusObject.detailed_status = "Instance terminated"
                        events_to_progress.append(thisInstanceStatusObject)
                        all_statuses[instance_id] = thisInstanceStatusObject

                        # Update statistics
                        zone = thisInstanceStatusObject.zone
                        if zone in termination_results[region]["zones"]:
                            termination_results[region]["zones"][zone]["succeeded"] += 1
                        termination_results[region]["succeeded"] += 1

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

                        # Update statistics
                        zone = thisInstanceStatusObject.zone
                        if zone in termination_results[region]["zones"]:
                            termination_results[region]["zones"][zone]["failed"] += 1
                        termination_results[region]["failed"] += 1

                    break

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

            # Mark all instances in this region as failed
            for instance_id in region_instances:
                if instance_id in all_statuses:
                    thisInstanceStatusObject = all_statuses[instance_id]
                    thisInstanceStatusObject.status = "Failed"
                    thisInstanceStatusObject.detailed_status = f"Error: {str(e)[:30]}"
                    events_to_progress.append(thisInstanceStatusObject)

                    # Update statistics
                    zone = thisInstanceStatusObject.zone
                    if zone in termination_results[region]["zones"]:
                        termination_results[region]["zones"][zone]["failed"] += 1
                    termination_results[region]["failed"] += 1

    # Create a deduplicated mapping of instance_id to region/vpc info
    # This ensures we don't have duplicate entries for the same instance
    deduplicated_map = {}
    for instance_id, info in instance_region_map.items():
        # Check if we already have this instance (shouldn't happen, but just in case)
        if instance_id not in deduplicated_map:
            deduplicated_map[instance_id] = info
        else:
            logger.warning(
                f"Duplicate instance found: {instance_id} - keeping first entry"
            )

    # Group instances by region
    region_instances = {}
    for instance_id, info in deduplicated_map.items():
        region = info["region"]
        if region not in region_instances:
            region_instances[region] = []
        region_instances[region].append(instance_id)

    # Log the deduplication results
    if len(deduplicated_map) != len(instance_region_map):
        logger.info(
            f"Removed {len(instance_region_map) - len(deduplicated_map)} duplicate instances"
        )

    # Clear MACHINES.json before starting termination to provide immediate feedback
    if existing_machines:
        logger.info("Clearing MACHINES.json to provide immediate feedback")
        try:
            # Create empty machine data
            output_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "machines": {},
                "total_count": 0,
                "regions": [],
                "last_operation": "delete",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            # Write to temporary file first
            temp_file = "MACHINES.json.tmp"
            with open(temp_file, "w") as f:
                try:
                    import fcntl

                    fcntl.flock(f, fcntl.LOCK_EX)
                    json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
                    f.flush()
                    os.fsync(f.fileno())
                    fcntl.flock(f, fcntl.LOCK_UN)
                except (ImportError, AttributeError):
                    json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
                    f.flush()

            # Atomic rename
            os.replace(temp_file, "MACHINES.json")
            logger.info("Successfully cleared MACHINES.json")

        except Exception as e:
            logger.error(f"Error clearing MACHINES.json: {str(e)}")

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

    # Collect final statistics
    total_terminated = sum(
        region["succeeded"] for region in termination_results.values()
    )
    total_failed = sum(region["failed"] for region in termination_results.values())
    total_instances = total_terminated + total_failed

    logger.info(
        f"Termination complete: {total_terminated}/{total_instances} instances terminated successfully"
    )
    if total_failed > 0:
        logger.warning(f"{total_failed} instances failed to terminate properly")

    # Make sure all AWS regions are represented in the termination summary
    # even if we didn't find instances there
    for region in AWS_REGIONS:
        if region not in regions_with_instances and region not in deduplicated_map:
            # Add entry for region with no instances
            dummy_id = f"none-{region}"
            deduplicated_map[dummy_id] = {"region": region, "vpc_id": None}

    # Create and print a comprehensive summary of what was terminated
    print_termination_summary(deduplicated_map)


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


def print_termination_summary(instance_map):
    """Print a summary table of all terminated instances.

    Args:
        instance_map: Dictionary mapping instance IDs to region/vpc info
    """
    if not instance_map:
        console.print("[yellow]No instances were terminated[/yellow]")
        return

    # Collect zone information from status objects
    zone_info = {}
    for instance_id, info in instance_map.items():
        # Try to get zone from status object
        region = info.get("region", "unknown")

        # Look for the zone in the status object if available
        zone = "unknown"
        if instance_id in all_statuses:
            zone = all_statuses[instance_id].zone

        # Track by region and zone
        if region not in zone_info:
            zone_info[region] = {}

        if zone not in zone_info[region]:
            zone_info[region][zone] = 0

        zone_info[region][zone] += 1

    # Create a summary table
    table = Table(
        title="Terminated Instances Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold red",
    )

    # Add columns
    table.add_column("Region", style="cyan")
    table.add_column("Zone", style="blue")
    table.add_column("Instances", style="red", justify="right")

    # Add rows for each region and zone
    total_instances = 0

    # Get all AWS regions for comprehensive reporting
    all_regions = set(AWS_REGIONS)
    reported_regions = set(zone_info.keys())

    # Add any AWS regions that weren't in our tracked instances
    for region in sorted(all_regions):
        if region not in reported_regions:
            zone_info[region] = {}

    # Sort regions for consistent display
    for region in sorted(zone_info.keys()):
        regions_zones = zone_info[region]

        # If no zones were found for this region, report 0 nodes
        if not regions_zones:
            table.add_row(region, "[italic]No zones[/italic]", "0")
            continue

        # Sort zones within each region
        for zone in sorted(regions_zones.keys()):
            count = regions_zones[zone]
            total_instances += count

            # Only show region on first row for this region
            if table.row_count > 0 and zone != sorted(regions_zones.keys())[0]:
                table.add_row("", zone, str(count))
            else:
                table.add_row(region, zone, str(count))

    # Add a total row
    table.add_row("", "[bold]TOTAL[/bold]", f"[bold]{total_instances}[/bold]")

    # Display the table
    console.print()
    console.print(table)
    console.print()
    console.print(
        f"[bold red]✓[/bold red] Successfully terminated {total_instances} instances"
    )
    console.print()


async def delete_disconnected_aws_nodes():
    try:
        # Run bacalhau node list command and capture output
        logger.info("Running 'bacalhau node list' to find disconnected nodes")
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
            logger.info("No disconnected AWS nodes found.")
            return

        logger.info(f"Found {len(disconnected_aws_nodes)} disconnected AWS node(s).")

        for node_id in disconnected_aws_nodes:
            logger.info(f"Deleting node: {node_id}")
            try:
                # Run bacalhau admin node delete command
                subprocess.run(["bacalhau", "node", "delete", node_id], check=True)
                logger.info(f"Successfully deleted node: {node_id}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to delete node {node_id}. Error: {e}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running bacalhau node list: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON output: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


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
            "spot_request_id": status.spot_request_id,
            "fulfilled": getattr(status, "fulfilled", False),
            "public_ip": status.public_ip,
            "private_ip": status.private_ip,
            "vpc_id": status.vpc_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for status in all_statuses.values()
    }


def load_machines_from_json():
    """Atomically load machine data from MACHINES.json if it exists"""
    try:
        # Check if the file exists
        if not os.path.exists("MACHINES.json"):
            logger.debug("MACHINES.json does not exist yet")
            return {}

        # Open with exclusive access to ensure atomic read
        with open("MACHINES.json", "r") as f:
            # Use fcntl for file locking on Unix systems
            try:
                import fcntl

                fcntl.flock(f, fcntl.LOCK_SH)  # Shared lock for reading
                data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
            except (ImportError, AttributeError):
                # On Windows or if fcntl not available, just read without locking
                data = json.load(f)

        return data
    except json.JSONDecodeError:
        logger.warning(
            "MACHINES.json exists but contains invalid JSON, treating as empty"
        )
        return {}
    except Exception as e:
        logger.error(f"Failed to load machines from JSON: {str(e)}", exc_info=True)
        return {}


def save_machines_to_json(operation="update"):
    """Atomically save the current machine statuses to MACHINES.json

    Args:
        operation: String indicating the type of operation - "update" or "delete"
    """
    try:
        # Create temporary file first (atomic write pattern)
        temp_file = "MACHINES.json.tmp"

        # First try to load existing data
        existing_data = load_machines_from_json()
        existing_machines = existing_data.get("machines", {})

        # Convert all current instances to a dict
        current_machines = all_statuses_to_dict()

        if operation == "update":
            # Update existing machines with current ones
            machines_data = {**existing_machines, **current_machines}

            # Log operations
            new_count = len(
                set(current_machines.keys()) - set(existing_machines.keys())
            )
            updated_count = len(
                set(current_machines.keys()) & set(existing_machines.keys())
            )
            logger.info(
                f"Adding {new_count} new and updating {updated_count} existing machines"
            )

        elif operation == "delete":
            # For delete, remove current machines from existing ones
            machines_to_remove = set(current_machines.keys())
            machines_data = {
                k: v
                for k, v in existing_machines.items()
                if k not in machines_to_remove
            }

            # Log operation
            removed_count = len(machines_to_remove)
            logger.info(f"Removing {removed_count} machines from MACHINES.json")
        else:
            # Default to just using current machines
            machines_data = current_machines

        # Extract regions from the machines data (safely)
        regions = set()
        for machine_data in machines_data.values():
            # Check if the machine data has a region key
            if isinstance(machine_data, dict) and "region" in machine_data:
                region = machine_data["region"]
                if region:  # Only add non-empty regions
                    regions.add(region)

        # Include metadata
        output_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "machines": machines_data,
            "total_count": len(machines_data),
            "regions": list(regions),
            "last_operation": operation,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Write to temporary file first
        with open(temp_file, "w") as f:
            # Use fcntl for file locking on Unix systems
            try:
                import fcntl

                fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writing
                json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Sync filesystem
                fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
            except (ImportError, AttributeError):
                # On Windows or if fcntl not available
                json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
                f.flush()  # Ensure data is written to disk

        # Atomic rename to ensure file is either fully written or not at all
        os.replace(temp_file, "MACHINES.json")

        if operation == "update":
            logger.info(f"Saved {len(machines_data)} machine records to MACHINES.json")
        else:
            logger.info(f"Updated MACHINES.json - {len(machines_data)} machines remain")

        return True
    except Exception as e:
        logger.error(f"Failed to save machines to JSON: {str(e)}", exc_info=True)

        # Log more debug info to help diagnose the issue
        logger.debug(f"machines_data type: {type(machines_data)}")
        if isinstance(machines_data, dict):
            logger.debug(f"machines_data has {len(machines_data)} entries")
            # Log a sample of the data
            if machines_data:
                sample_key = next(iter(machines_data))
                sample_value = machines_data[sample_key]
                logger.debug(
                    f"Sample entry - key: {sample_key}, value type: {type(sample_value)}"
                )
                if isinstance(sample_value, dict):
                    logger.debug(f"Sample keys: {list(sample_value.keys())}")

        # Clean up temp file if it exists
        try:
            if os.path.exists("MACHINES.json.tmp"):
                os.remove("MACHINES.json.tmp")
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up temp file: {str(cleanup_error)}")

        return False


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Manage spot instances across multiple AWS regions."
    )
    parser.add_argument(
        "action",  # Changed from --action to positional argument
        choices=["create", "destroy", "list", "delete_disconnected_aws_nodes", "nuke"],
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force delete all resources without confirmation (for nuke action)",
    )

    args = parser.parse_args()

    # Configure unified logging - use the same file_handler for both log file and console
    global file_handler

    # Remove any existing handlers to ensure clean configuration
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create/truncate the debug.log file
    try:
        with open("debug.log", "w") as f:
            pass  # Just open in write mode to truncate
    except Exception as e:
        sys.stdout.write(f"Warning: Could not truncate debug.log: {e}\n")
        sys.stdout.flush()

    # Create and configure file handler
    file_handler = logging.FileHandler("debug.log")
    file_handler.setFormatter(log_formatter)

    # Set log levels based on verbose flag
    if args.verbose:
        file_handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)

    # Add the file handler to our logger - this will be shared with the console handler
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


async def check_aws_credentials():
    """Check if AWS credentials are valid before proceeding.

    Returns:
        bool: True if credentials are valid, False otherwise
    """
    logger.info("Checking AWS credentials validity...")
    try:
        # Try to use any region for the check - we'll use the first configured region
        region = AWS_REGIONS[0] if AWS_REGIONS else "us-east-1"
        ec2 = get_ec2_client(region)

        # Make a simple API call that requires valid credentials
        await safe_aws_call(ec2.describe_regions, RegionNames=[region])

        logger.info("AWS credentials are valid")
        return True
    except botocore.exceptions.ClientError as e:
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        error_msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))

        if error_code in ["ExpiredToken", "InvalidToken", "UnauthorizedOperation"]:
            logger.error(f"AWS credentials have expired or are invalid: {error_msg}")
            console.print(
                "[bold red]AWS credentials have expired or are invalid.[/bold red]"
            )
            console.print(
                "[yellow]Please run 'aws sso login' to refresh your credentials.[/yellow]"
            )
        else:
            logger.error(f"Error checking AWS credentials: {error_code} - {error_msg}")
            console.print(
                f"[bold red]AWS credentials error:[/bold red] {error_code} - {error_msg}"
            )

        return False
    except Exception as e:
        logger.error(f"Error checking AWS credentials: {str(e)}")
        console.print(f"[bold red]Error checking AWS credentials:[/bold red] {str(e)}")
        console.print(
            "[yellow]Please verify your AWS configuration and connectivity.[/yellow]"
        )
        return False


async def perform_action():
    """Execute the requested action"""
    args = parse_args()
    logger.debug(f"Starting perform_action with action: {args.action}")
    operation_result = {
        "success": False,
        "action": args.action,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": None,
        "result_summary": {},
    }

    # Check AWS credentials before performing any action that requires AWS API calls
    if args.action in ["create", "destroy", "list"]:
        credentials_valid = await check_aws_credentials()
        if not credentials_valid:
            operation_result["error"] = "Invalid AWS credentials"
            return operation_result

    try:
        if args.action == "create":
            logger.info("Initiating create_spot_instances")
            # Wait for the create operation to fully complete
            creation_success = await create_spot_instances()

            # Count successfully created instances by region
            created_instances = {}
            for status in all_statuses.values():
                if (
                    status.instance_id and status.public_ip
                ):  # Successfully created with IP
                    region = status.region
                    if region not in created_instances:
                        created_instances[region] = 0
                    created_instances[region] += 1

            total_created = sum(created_instances.values())

            # Count instances with public IPs and completed provisioning
            provisioned_instances = {}
            for status in all_statuses.values():
                if (
                    status.instance_id
                    and status.public_ip
                    and status.detailed_status == "Provisioning complete"
                ):
                    region = status.region
                    if region not in provisioned_instances:
                        provisioned_instances[region] = 0
                    provisioned_instances[region] += 1

            total_provisioned = sum(provisioned_instances.values())

            # Set operation result based on success of creation
            operation_result["success"] = total_created > 0
            operation_result["result_summary"] = {
                "instances_created": total_created,
                "instances_by_region": created_instances,
                "instances_provisioned": total_provisioned,
                "all_received_ips": creation_success,
            }

            # Save newly created instances to MACHINES.json (operation="update")
            if len(all_statuses) > 0:
                save_result = save_machines_to_json(operation="update")
                operation_result["result_summary"]["saved_to_file"] = save_result

            logger.info(
                f"Creation completed: {total_created} instances created, {total_provisioned} fully provisioned"
            )

            # If we didn't create any instances, log the issue but don't throw exception
            if total_created == 0:
                logger.warning(
                    "No instances were created - this may be due to AWS capacity limitations or credential issues"
                )
                console.print(
                    "[bold yellow]Warning:[/bold yellow] No instances were created"
                )
                console.print(
                    "[yellow]This may be due to AWS capacity limitations or credential issues[/yellow]"
                )
                console.print(
                    "[yellow]Try running 'aws sso login' to refresh your credentials or use different regions/instance types[/yellow]"
                )

        elif args.action == "list":
            logger.info("Initiating list_spot_instances")
            await list_spot_instances()

            # Count instances by status
            instance_counts = {}
            for status in all_statuses.values():
                if status.status not in instance_counts:
                    instance_counts[status.status] = 0
                instance_counts[status.status] += 1

            operation_result["success"] = True
            operation_result["result_summary"] = {
                "total_instances": len(all_statuses),
                "instances_by_status": instance_counts,
            }

            # Update MACHINES.json with current instances (operation="update")
            if len(all_statuses) > 0:
                save_machines_to_json(operation="update")

        elif args.action == "destroy":
            # Store counts before destruction for reporting
            initial_count = len(all_statuses)
            initial_regions = set(
                status.region for status in all_statuses.values() if status.region
            )

            # Create a dictionary to track instances per region and zone
            region_zone_counts = {}
            for status in all_statuses.values():
                if status.region and status.zone:
                    if status.region not in region_zone_counts:
                        region_zone_counts[status.region] = {}
                    if status.zone not in region_zone_counts[status.region]:
                        region_zone_counts[status.region][status.zone] = 0
                    region_zone_counts[status.region][status.zone] += 1

            # Skip doing any MACHINES.json operations if empty
            has_instances = initial_count > 0

            logger.info("Initiating destroy_instances")
            await destroy_instances()

            # Get summary of terminated instances
            operation_result["success"] = True
            operation_result["result_summary"] = {
                "instances_terminated": initial_count,
                "regions_affected": list(initial_regions),
                "region_zone_distribution": region_zone_counts,
                "cleanup_completed": True,
            }

            # Remove destroyed instances from MACHINES.json (operation="delete")
            if has_instances:
                save_machines_to_json(operation="delete")

        elif args.action == "delete_disconnected_aws_nodes":
            logger.info("Initiating delete_disconnected_aws_nodes")
            await delete_disconnected_aws_nodes()
            operation_result["success"] = True

        elif args.action == "nuke":
            logger.info("Initiating nuke_all_resources")
            nuke_success = await nuke_all_resources()
            operation_result["success"] = nuke_success
            operation_result["result_summary"] = {
                "nuke_completed": nuke_success,
                "tag_filter": f"{FILTER_TAG_NAME}={FILTER_TAG_VALUE}",
            }

        logger.debug(f"Completed action: {args.action}")

        # Set completion timestamp
        operation_result["end_time"] = datetime.now(timezone.utc).isoformat()

    except TimeoutError as e:
        logger.error(f"TimeoutError occurred: {str(e)}")
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        console.print("[yellow]This may be due to AWS credential issues.[/yellow]")
        console.print(
            "[yellow]Try running 'aws sso login' to refresh your credentials.[/yellow]"
        )
        table_update_event.set()
        operation_result["error"] = str(e)
        return operation_result

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
        operation_result["error"] = str(e)
        return operation_result

    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        table_update_event.set()
        operation_result["error"] = str(e)
        return operation_result

    return operation_result


async def nuke_all_resources():
    """Nuclear option: Delete ALL resources across ALL regions that match our tags.

    This function performs a comprehensive cleanup of every AWS resource that has been
    tagged with our management tags, across all AWS regions. This includes instances,
    VPCs, subnets, route tables, internet gateways, security groups, and any other
    resource types that have been tagged.
    """
    global task_name, task_total, events_to_progress
    task_name = "NUKING All Tagged Resources"
    task_total = 100  # Will update once we find resources

    args = parse_args()

    # Confirm the destructive action unless --force is used
    if not args.force:
        console.print("[bold red]!!! WARNING: NUCLEAR OPTION !!![/bold red]")
        console.print("This will delete ALL resources tagged with:")
        console.print(f"   {FILTER_TAG_NAME} = {FILTER_TAG_VALUE}")
        console.print("across ALL AWS regions.")
        console.print(
            "[bold red]This action is irreversible and may delete resources you care about![/bold red]"
        )
        console.print()
        confirmation = input("Type 'YES NUKE EVERYTHING' to continue: ")
        if confirmation != "YES NUKE EVERYTHING":
            console.print("[yellow]Operation cancelled.[/yellow]")
            return False

    logger.warning(
        f"!!! NUKE INITIATED !!! Deleting all resources tagged with {FILTER_TAG_NAME}={FILTER_TAG_VALUE}"
    )

    # Resource counts for tracking progress
    resource_counts = {
        "ec2_instances": 0,
        "vpcs": 0,
        "subnets": 0,
        "internet_gateways": 0,
        "route_tables": 0,
        "security_groups": 0,
        "spot_requests": 0,
        "other": 0,
    }

    # Results by region
    results_by_region = {}

    # Process each region
    for region in AWS_REGIONS:
        console.print(f"[bold]Scanning region: {region}[/bold]")
        results_by_region[region] = {
            "instances": 0,
            "vpcs": 0,
            "subnets": 0,
            "internet_gateways": 0,
            "route_tables": 0,
            "security_groups": 0,
            "spot_requests": 0,
            "other": 0,
            "errors": [],
        }

        try:
            # Create EC2 client for this region
            ec2 = get_ec2_client(region)

            # 1. Find and terminate all EC2 instances with our tag
            try:
                logger.info(f"Finding EC2 instances in {region}...")
                response = await safe_aws_call(
                    ec2.describe_instances,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                instance_ids = []
                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_ids.append(instance["InstanceId"])

                if instance_ids:
                    logger.info(
                        f"Terminating {len(instance_ids)} instances in {region}"
                    )
                    resource_counts["ec2_instances"] += len(instance_ids)
                    results_by_region[region]["instances"] = len(instance_ids)

                    # Terminate the instances
                    await safe_aws_call(
                        ec2.terminate_instances, InstanceIds=instance_ids
                    )

                    # Wait for instances to terminate fully before continuing to other resources
                    waiter = ec2.get_waiter("instance_terminated")
                    try:
                        await asyncio.wait_for(
                            safe_aws_call(
                                waiter.wait,
                                InstanceIds=instance_ids,
                                WaiterConfig={"Delay": 5, "MaxAttempts": 60},
                            ),
                            timeout=300,
                        )
                        logger.info(f"All instances in {region} terminated")
                    except (TimeoutError, asyncio.TimeoutError):
                        logger.warning(
                            f"Timeout waiting for instances to terminate in {region}"
                        )
                else:
                    logger.info(f"No instances found in {region}")
            except Exception as e:
                error_msg = f"Error terminating instances in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # 2. Cancel all spot instance requests with our tag
            try:
                logger.info(f"Finding spot requests in {region}...")
                response = await safe_aws_call(
                    ec2.describe_spot_instance_requests,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                spot_request_ids = []
                for request in response.get("SpotInstanceRequests", []):
                    spot_request_ids.append(request["SpotInstanceRequestId"])

                if spot_request_ids:
                    logger.info(
                        f"Canceling {len(spot_request_ids)} spot requests in {region}"
                    )
                    resource_counts["spot_requests"] += len(spot_request_ids)
                    results_by_region[region]["spot_requests"] = len(spot_request_ids)

                    # Cancel the spot requests
                    await safe_aws_call(
                        ec2.cancel_spot_instance_requests,
                        SpotInstanceRequestIds=spot_request_ids,
                    )
                else:
                    logger.info(f"No spot requests found in {region}")
            except Exception as e:
                error_msg = f"Error canceling spot requests in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # 3. Delete all security groups with our tag (after instances are gone)
            try:
                logger.info(f"Finding security groups in {region}...")
                response = await safe_aws_call(
                    ec2.describe_security_groups,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                security_group_ids = []
                for sg in response.get("SecurityGroups", []):
                    security_group_ids.append(sg["GroupId"])

                if security_group_ids:
                    logger.info(
                        f"Deleting {len(security_group_ids)} security groups in {region}"
                    )
                    resource_counts["security_groups"] += len(security_group_ids)
                    results_by_region[region]["security_groups"] = len(
                        security_group_ids
                    )

                    # Delete each security group (might need to wait for dependencies)
                    for sg_id in security_group_ids:
                        try:
                            await safe_aws_call(
                                ec2.delete_security_group, GroupId=sg_id
                            )
                            logger.info(f"Deleted security group {sg_id}")
                        except Exception as e:
                            # If it fails due to dependencies, we'll try again after other resources
                            logger.warning(
                                f"Could not delete security group {sg_id} yet: {str(e)}"
                            )
                else:
                    logger.info(f"No security groups found in {region}")
            except Exception as e:
                error_msg = f"Error deleting security groups in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # 4. Detach and delete internet gateways with our tag
            try:
                logger.info(f"Finding internet gateways in {region}...")
                response = await safe_aws_call(
                    ec2.describe_internet_gateways,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                igw_ids = []
                vpc_igw_mappings = {}  # Maps IGW to its attached VPCs

                for igw in response.get("InternetGateways", []):
                    igw_id = igw["InternetGatewayId"]
                    igw_ids.append(igw_id)
                    vpc_igw_mappings[igw_id] = [
                        attachment["VpcId"] for attachment in igw.get("Attachments", [])
                    ]

                if igw_ids:
                    logger.info(
                        f"Detaching and deleting {len(igw_ids)} internet gateways in {region}"
                    )
                    resource_counts["internet_gateways"] += len(igw_ids)
                    results_by_region[region]["internet_gateways"] = len(igw_ids)

                    # First detach then delete each IGW
                    for igw_id, vpc_ids in vpc_igw_mappings.items():
                        for vpc_id in vpc_ids:
                            try:
                                await safe_aws_call(
                                    ec2.detach_internet_gateway,
                                    InternetGatewayId=igw_id,
                                    VpcId=vpc_id,
                                )
                                logger.info(f"Detached IGW {igw_id} from VPC {vpc_id}")
                            except Exception as e:
                                logger.warning(
                                    f"Error detaching IGW {igw_id} from VPC {vpc_id}: {str(e)}"
                                )

                        # Now delete the IGW
                        try:
                            await safe_aws_call(
                                ec2.delete_internet_gateway, InternetGatewayId=igw_id
                            )
                            logger.info(f"Deleted IGW {igw_id}")
                        except Exception as e:
                            logger.warning(f"Error deleting IGW {igw_id}: {str(e)}")
                else:
                    logger.info(f"No internet gateways found in {region}")
            except Exception as e:
                error_msg = f"Error processing internet gateways in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # 5. Delete subnets with our tag
            try:
                logger.info(f"Finding subnets in {region}...")
                response = await safe_aws_call(
                    ec2.describe_subnets,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                subnet_ids = []
                for subnet in response.get("Subnets", []):
                    subnet_ids.append(subnet["SubnetId"])

                if subnet_ids:
                    logger.info(f"Deleting {len(subnet_ids)} subnets in {region}")
                    resource_counts["subnets"] += len(subnet_ids)
                    results_by_region[region]["subnets"] = len(subnet_ids)

                    # Delete each subnet
                    for subnet_id in subnet_ids:
                        try:
                            await safe_aws_call(ec2.delete_subnet, SubnetId=subnet_id)
                            logger.info(f"Deleted subnet {subnet_id}")
                        except Exception as e:
                            logger.warning(
                                f"Error deleting subnet {subnet_id}: {str(e)}"
                            )
                else:
                    logger.info(f"No subnets found in {region}")
            except Exception as e:
                error_msg = f"Error deleting subnets in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # 6. Delete route tables with our tag (non-main only)
            try:
                logger.info(f"Finding route tables in {region}...")
                response = await safe_aws_call(
                    ec2.describe_route_tables,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                route_table_ids = []
                for rt in response.get("RouteTables", []):
                    # Skip main route tables, which can't be deleted
                    is_main = any(
                        assoc.get("Main", False) for assoc in rt.get("Associations", [])
                    )
                    if not is_main:
                        route_table_ids.append(rt["RouteTableId"])

                if route_table_ids:
                    logger.info(
                        f"Deleting {len(route_table_ids)} route tables in {region}"
                    )
                    resource_counts["route_tables"] += len(route_table_ids)
                    results_by_region[region]["route_tables"] = len(route_table_ids)

                    # Delete each route table
                    for rt_id in route_table_ids:
                        try:
                            # First disassociate any subnets
                            rt_response = await safe_aws_call(
                                ec2.describe_route_tables, RouteTableIds=[rt_id]
                            )
                            if rt_response.get("RouteTables"):
                                for assoc in rt_response["RouteTables"][0].get(
                                    "Associations", []
                                ):
                                    if (
                                        not assoc.get("Main", False)
                                        and "AssociationId" in assoc
                                    ):
                                        await safe_aws_call(
                                            ec2.disassociate_route_table,
                                            AssociationId=assoc["AssociationId"],
                                        )

                            # Now delete the route table
                            await safe_aws_call(
                                ec2.delete_route_table, RouteTableId=rt_id
                            )
                            logger.info(f"Deleted route table {rt_id}")
                        except Exception as e:
                            logger.warning(
                                f"Error deleting route table {rt_id}: {str(e)}"
                            )
                else:
                    logger.info(f"No route tables found in {region}")
            except Exception as e:
                error_msg = f"Error deleting route tables in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # 7. Delete VPCs with our tag
            try:
                logger.info(f"Finding VPCs in {region}...")
                response = await safe_aws_call(
                    ec2.describe_vpcs,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                vpc_ids = []
                for vpc in response.get("Vpcs", []):
                    vpc_ids.append(vpc["VpcId"])

                if vpc_ids:
                    logger.info(f"Deleting {len(vpc_ids)} VPCs in {region}")
                    resource_counts["vpcs"] += len(vpc_ids)
                    results_by_region[region]["vpcs"] = len(vpc_ids)

                    # Delete each VPC
                    for vpc_id in vpc_ids:
                        try:
                            await safe_aws_call(ec2.delete_vpc, VpcId=vpc_id)
                            logger.info(f"Deleted VPC {vpc_id}")
                        except Exception as e:
                            logger.warning(f"Error deleting VPC {vpc_id}: {str(e)}")
                else:
                    logger.info(f"No VPCs found in {region}")
            except Exception as e:
                error_msg = f"Error deleting VPCs in {region}: {str(e)}"
                logger.error(error_msg)
                results_by_region[region]["errors"].append(error_msg)

            # Try one more time for security groups that failed earlier
            if results_by_region[region]["security_groups"] > 0:
                try:
                    logger.info(f"Retrying security group deletion in {region}...")
                    response = await safe_aws_call(
                        ec2.describe_security_groups,
                        Filters=[
                            {
                                "Name": f"tag:{FILTER_TAG_NAME}",
                                "Values": [FILTER_TAG_VALUE],
                            }
                        ],
                    )

                    for sg in response.get("SecurityGroups", []):
                        sg_id = sg["GroupId"]
                        try:
                            await safe_aws_call(
                                ec2.delete_security_group, GroupId=sg_id
                            )
                            logger.info(
                                f"Successfully deleted security group {sg_id} on retry"
                            )
                        except Exception as e:
                            logger.error(
                                f"Final attempt to delete security group {sg_id} failed: {str(e)}"
                            )
                except Exception as e:
                    logger.error(
                        f"Error in final security group cleanup for {region}: {str(e)}"
                    )

        except Exception as e:
            error_msg = f"Unexpected error processing region {region}: {str(e)}"
            logger.error(error_msg)
            results_by_region[region]["errors"].append(error_msg)

    # Print summary
    total_resources = sum(resource_counts.values())

    console.print("\n[bold]NUKE OPERATION SUMMARY[/bold]")

    summary_table = Table(title="Resources Deleted", box=box.ROUNDED)
    summary_table.add_column("Region", style="cyan")
    summary_table.add_column("Instances", style="green", justify="right")
    summary_table.add_column("VPCs", style="blue", justify="right")
    summary_table.add_column("Subnets", style="magenta", justify="right")
    summary_table.add_column("IGWs", style="yellow", justify="right")
    summary_table.add_column("Routes", style="red", justify="right")
    summary_table.add_column("SGs", style="cyan", justify="right")
    summary_table.add_column("Spot Reqs", style="green", justify="right")
    summary_table.add_column("Errors", style="red", justify="right")

    # Row for each region
    for region, results in sorted(results_by_region.items()):
        error_count = len(results["errors"])

        summary_table.add_row(
            region,
            str(results["instances"]),
            str(results["vpcs"]),
            str(results["subnets"]),
            str(results["internet_gateways"]),
            str(results["route_tables"]),
            str(results["security_groups"]),
            str(results["spot_requests"]),
            f"[bold red]{error_count}[/bold red]" if error_count > 0 else "0",
        )

    # Add totals row
    summary_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{resource_counts['ec2_instances']}[/bold]",
        f"[bold]{resource_counts['vpcs']}[/bold]",
        f"[bold]{resource_counts['subnets']}[/bold]",
        f"[bold]{resource_counts['internet_gateways']}[/bold]",
        f"[bold]{resource_counts['route_tables']}[/bold]",
        f"[bold]{resource_counts['security_groups']}[/bold]",
        f"[bold]{resource_counts['spot_requests']}[/bold]",
        f"[bold red]{sum(len(r['errors']) for r in results_by_region.values())}[/bold red]",
    )

    console.print(summary_table)

    # Also clear MACHINES.json
    try:
        with open("MACHINES.json", "w") as f:
            f.write(
                json.dumps(
                    {
                        "machines": {},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "total_count": 0,
                        "last_operation": "nuke",
                    },
                    indent=2,
                )
            )
        logger.info("Cleared MACHINES.json")
    except Exception as e:
        logger.error(f"Error clearing MACHINES.json: {str(e)}")

    if total_resources > 0:
        console.print(
            f"\n[bold green]✓[/bold green] Successfully nuked {total_resources} resources across {len(AWS_REGIONS)} regions"
        )
    else:
        console.print("\n[yellow]No resources found matching the tag criteria[/yellow]")

    error_count = sum(len(r["errors"]) for r in results_by_region.values())
    if error_count > 0:
        console.print(
            f"[bold red]![/bold red] {error_count} errors occurred during the operation. See logs for details."
        )

    return total_resources > 0


async def main():
    """Main execution function"""
    handler = None  # Initialize handler to None
    try:
        # Set up prompt for resource tagging if this is a create operation
        if len(sys.argv) > 1 and sys.argv[1] == "create":
            configure_tags_and_names()

        args = parse_args()

        # Logging has been configured in parse_args
        # We'll see these log messages in both debug.log and the Rich console panel
        if args.verbose:
            logger.debug("Verbose logging enabled")

        logger.info(f"Starting action: {args.action}")

        if args.format == "json":
            logger.info("Using JSON output format")
            operation_result = await perform_action()
            # Machine updates in MACHINES.json are now handled within perform_action()

            # For JSON output, also show MACHINES.json contents if it exists
            machines_from_file = load_machines_from_json().get("machines", {})

            # Use direct stdout before rich console is initialized
            output = {
                "current_machines": all_statuses_to_dict(),
                "saved_machines_count": len(machines_from_file),
                "operation_result": operation_result,
            }
            sys.stdout.write(json.dumps(output, indent=2, default=str) + "\n")
            sys.stdout.flush()
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

                # Add the rich console handler for logging, sharing the file handler
                handler = RichConsoleHandler(
                    live, layout, file_handler
                )  # Pass layout and file handler
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
                operation_result = await perform_action()

                # Display summary after operation completes (if successful)
                if operation_result.get("success", False):
                    # Create a nice summary table
                    summary_table = Table(
                        title=f"{args.action.capitalize()} Operation Summary",
                        show_header=True,
                        header_style="bold cyan",
                        box=box.ROUNDED,
                    )

                    # Add columns based on the action
                    if args.action == "create":
                        summary_table.add_column("Total Created", style="green")
                        summary_table.add_column("Regions", style="blue")
                        summary_table.add_column("Distribution", style="cyan")

                        # Get summary data
                        summary = operation_result["result_summary"]
                        total = summary.get("instances_created", 0)
                        by_region = summary.get("instances_by_region", {})
                        all_ips = summary.get("all_received_ips", True)

                        # Add the IP status column
                        summary_table.add_column("IP Status", style="green")

                        # Format region distribution
                        region_list = (
                            ", ".join(by_region.keys()) if by_region else "None"
                        )
                        distribution = (
                            " | ".join(
                                [
                                    f"{region}: {count}"
                                    for region, count in by_region.items()
                                ]
                            )
                            if by_region
                            else "None"
                        )

                        # Format IP status message
                        ip_status = (
                            "✓ All Received" if all_ips else "⚠ Some missing IPs"
                        )

                        # Add the row with status
                        summary_table.add_row(
                            str(total), region_list, distribution, ip_status
                        )

                    elif args.action == "destroy":
                        summary_table.add_column("Instances Terminated", style="red")
                        summary_table.add_column("Regions Affected", style="cyan")
                        summary_table.add_column("Result", style="magenta")

                        # Get summary data
                        summary = operation_result["result_summary"]
                        terminated = summary.get("instances_terminated", 0)
                        regions = summary.get("regions_affected", [])

                        # Format for display
                        region_text = ", ".join(regions) if regions else "None"

                        # Add the row - show if machines file was updated
                        if terminated > 0:
                            summary_table.add_row(
                                str(terminated), region_text, "✓ Successful"
                            )
                        else:
                            summary_table.add_row(
                                str(terminated), region_text, "No machines found"
                            )

                    # Print the summary
                    console.print("\n")  # Add some space
                    console.print(summary_table)
                    console.print("\n")  # Add some space after

                    # Show appropriate message based on the operation
                    if (
                        args.action == "create"
                        and operation_result.get("result_summary", {}).get(
                            "instances_created", 0
                        )
                        > 0
                    ):
                        console.print(
                            "[green]✓ Machine information saved to MACHINES.json[/green]"
                        )
                    elif (
                        args.action == "list"
                        and operation_result.get("result_summary", {}).get(
                            "total_instances", 0
                        )
                        > 0
                    ):
                        console.print(
                            "[green]✓ Machine information updated in MACHINES.json[/green]"
                        )
                    elif (
                        args.action == "destroy"
                        and operation_result.get("result_summary", {}).get(
                            "instances_terminated", 0
                        )
                        > 0
                    ):
                        console.print(
                            "[red]✓ Terminated machines removed from MACHINES.json[/red]"
                        )

                # Signal display task to stop and wait for completion
                logger.debug("Signaling display task to stop")
                table_update_event.set()

                # For create action, make sure we keep the display up just long enough
                # to let users see the results but not block on full provisioning
                if args.action == "create":
                    # Just wait a short time to ensure users see the final IP table
                    logger.debug("Keeping display open briefly to show final IP table")
                    await asyncio.sleep(5.0)

                # Signal display task to stop (normal case)
                logger.debug("Ending display task")

                # Wait for display to finish updating with a timeout
                try:
                    logger.debug("Waiting for display task to complete")

                    # Short timeout for display task cleanup
                    display_timeout = 5.0
                    await asyncio.wait_for(
                        asyncio.shield(display_task), timeout=display_timeout
                    )
                    logger.debug("Display task completed")
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Display task did not complete within {display_timeout}s timeout"
                    )
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
        # Ensure we're writing directly to stdout to avoid stderr
        if is_terminal_cleared:
            # If terminal was cleared by rich Live display, add newlines for visibility
            sys.stdout.write("\n\n")
        sys.stdout.write(f"\n[ERROR] {message}\n")
        sys.stdout.write("Check debug.log for more details.\n")
        sys.stdout.flush()

    # Add a simple info message directly to console for initial startup
    # This is only for user feedback before the rich console is ready
    sys.stdout.write("Initializing...\n")
    sys.stdout.flush()

    try:
        # Log to file only, not stdout
        logger.info("Starting main execution")
        asyncio.run(main())
        logger.info("Main execution completed")
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.stderr = open(os.devnull, "w")  # Suppress any stderr output
        print_error_message("Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        # Log detailed error
        logger.error(f"Fatal error occurred: {str(e)}", exc_info=True)

        # Silence stderr completely
        sys.stderr = open(os.devnull, "w")

        # Print user-friendly error message outside of any rich context
        error_msg = f"Fatal error occurred: {str(e)}"

        # Add additional context for common errors
        if "TimeoutError" in str(e):
            error_msg += (
                "\nThis may be due to AWS credential issues or network problems."
            )
            error_msg += "\nTry running 'aws sso login' to refresh your credentials."
        elif "ExpiredToken" in str(e) or "InvalidToken" in str(e):
            error_msg += "\nAWS credentials have expired. Try running 'aws sso login'."
        elif "InstanceId" in str(e) and "does not exist" in str(e):
            error_msg += (
                "\nThe specified instance may have been terminated or never created."
            )

        print_error_message(error_msg)
        sys.exit(1)
