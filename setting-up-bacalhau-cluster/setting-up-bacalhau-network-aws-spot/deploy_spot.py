#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "botocore",
#     "rich",
#     "aiosqlite",
#     "aiofiles",
#     "pyyaml",
# ]
# ///

import argparse
import asyncio
import base64
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite
import boto3
import botocore
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from util.config import Config
from util.scripts_provider import ScriptsProvider

# Tag to filter instances by
FILTER_TAG_NAME = "ManagedBy"
FILTER_TAG_VALUE = "SpotInstanceScript"

# Create console instance for rich output
console = Console()

# Set up logging to file only (no console output)
logger = logging.getLogger(__name__)
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
    open("debug_deploy_spot.log", "w").close()
    file_handler = logging.FileHandler("debug_deploy_spot.log")
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
events_to_progress_lock = (
    asyncio.Lock()
)  # Lock for thread-safe updates to events_to_progress

# List to store operations logs
operations_logs = []
operations_logs_lock = asyncio.Lock()  # Lock for thread-safe updates to operations logs
MAX_OPERATIONS_LOGS = 20  # Maximum number of operations logs to keep

# Initialize global state manager
machine_state = None
state_manager = None


def log_operation(message, level="info", region=None):
    """
    Adds an operation log message to the operations_logs list.
    Args:
        message: The message to log
        level: The log level (info, warning, error)
        region: Optional region context
    """
    global operations_logs, MAX_OPERATIONS_LOGS

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Format the message with color based on level
    if level == "error":
        formatted_message = f"[red]{timestamp} ERROR:[/red] "
    elif level == "warning":
        formatted_message = f"[yellow]{timestamp} WARN:[/yellow] "
    else:
        formatted_message = f"[green]{timestamp} INFO:[/green] "

    # Add region if provided
    if region:
        formatted_message += f"[cyan]{region}:[/cyan] "

    formatted_message += message

    # Thread-safe update to operations logs
    try:
        # For synchronous contexts, we can't use the async lock
        # This is not ideal but better than no logging at all
        operations_logs.append(formatted_message)

        # Keep only the most recent logs
        if len(operations_logs) > MAX_OPERATIONS_LOGS:
            operations_logs = operations_logs[-MAX_OPERATIONS_LOGS:]
    except Exception as e:
        logger.error(f"Error updating operations logs: {e}")

    # Also log to the standard logger
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


# Async version for when called from async code
async def log_operation_async(message, level="info", region=None):
    """
    Async version of log_operation that properly uses the lock
    """
    global operations_logs, MAX_OPERATIONS_LOGS, operations_logs_lock

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Format the message with color based on level
    if level == "error":
        formatted_message = f"[red]{timestamp} ERROR:[/red] "
    elif level == "warning":
        formatted_message = f"[yellow]{timestamp} WARN:[/yellow] "
    else:
        formatted_message = f"[green]{timestamp} INFO:[/green] "

    # Add region if provided
    if region:
        formatted_message += f"[cyan]{region}:[/cyan] "

    formatted_message += message

    # Thread-safe update to operations logs
    async with operations_logs_lock:
        operations_logs.append(formatted_message)

        # Keep only the most recent logs
        if len(operations_logs) > MAX_OPERATIONS_LOGS:
            operations_logs = operations_logs[-MAX_OPERATIONS_LOGS:]

    # Also log to the standard logger
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


# Global lock for thread-safe updates to shared state
all_statuses_lock = asyncio.Lock()


def update_all_statuses(status):
    """
    Update the global status dictionary (sync version)
    This must be called from synchronous code
    """
    all_statuses[status.id] = status


async def update_all_statuses_async(status):
    """
    Update the global status dictionary (async version)
    This must be called from async code
    """
    async with all_statuses_lock:
        all_statuses[status.id] = status
        # Also add to events_to_progress to trigger UI update
        events_to_progress.append(status)


class InstanceStatus:
    def __init__(self, region, zone, index, instance_id=None):
        # For tracking purposes, we'll use a temporary UUID until we get an AWS instance ID
        # Once we have the AWS instance ID, we'll use that as our primary identifier
        self._temp_id = str(uuid.uuid4())
        self.region = region
        self.zone = zone
        self.index = index
        self.instance_id = instance_id
        self.spot_request_id = None
        self.status = "Initializing"
        self.detailed_status = "Starting spot instance creation"
        self.elapsed_time = 0
        self.start_time = time.time()
        self.public_ip = ""
        self.private_ip = ""
        self.vpc_id = ""
        self.creation_state = {
            "phase": "initializing",  # initializing, requesting, provisioning, finalized
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {},
        }

    @property
    def id(self):
        """Return the instance ID if available, otherwise return the temporary ID.
        This ensures that once we have a real AWS instance ID, we use that as our identifier.
        """
        if self.instance_id:
            return self.instance_id
        return self._temp_id

    def combined_status(self):
        """Returns a combined status string for display in the table."""
        if self.detailed_status:
            return f"{self.status}: {self.detailed_status}"
        return self.status

    def to_dict(self):
        return {
            "id": self.id,  # This will be instance_id if available
            "_temp_id": self._temp_id,  # Keep the temp ID for reference
            "region": self.region,
            "zone": self.zone,
            "index": self.index,
            "instance_id": self.instance_id,
            "spot_request_id": self.spot_request_id,
            "status": self.status,
            "detailed_status": self.detailed_status,
            "elapsed_time": self.elapsed_time,
            "start_time": self.start_time,
            "public_ip": self.public_ip,
            "private_ip": self.private_ip,
            "vpc_id": self.vpc_id,
            "creation_state": self.creation_state,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def update_creation_state(self, phase, details=None):
        """Update the creation state with a new phase and optional details."""
        self.creation_state = {
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }


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
    table.add_column("ID", width=5, style="cyan", no_wrap=True)
    table.add_column("Region", width=15, style="cyan", no_wrap=True)
    table.add_column("Zone", width=15, style="cyan", no_wrap=True)
    table.add_column(
        "Status", width=40, style="yellow", no_wrap=True
    )  # Increased from 20 to 40
    table.add_column(
        "Elapsed", width=10, justify="right", style="magenta", no_wrap=True
    )  # Reduced from 20 to 10
    table.add_column(
        "Instance ID", width=25, style="blue", no_wrap=True
    )  # Increased from 20 to 25
    table.add_column(
        "Public IP", width=15, style="blue", no_wrap=True
    )  # Reduced from 20 to 15
    table.add_column(
        "Private IP", width=15, style="blue", no_wrap=True
    )  # Reduced from 20 to 15

    # Define the failed status list for display consistency
    FAILED_STATUSES = ["Failed", "Bad Instance", "Error", "Timeout"]

    # Sort statuses in the following order:
    # 1. Prioritize instances waiting for IP addresses at the very top
    # 2. Then instances that are initializing/in-progress
    # 3. Then completed instances (have IPs) in the middle
    # 4. Failed instances after completed ones
    # 5. Finally terminated instances at the bottom
    # Within each priority group, sort by region/zone
    def sort_key(status):
        # Define a priority score (lower = higher in the list)
        if status.status == "Terminated":
            priority = 6  # Terminated instances at the bottom
        elif status.status in FAILED_STATUSES:
            priority = 5  # Failed instances just above terminated ones
        elif status.instance_id and not status.public_ip:
            # Instance exists but has no public IP - highest priority
            priority = 0  # Waiting for IP instances at the very top
            if "Waiting for IP" not in status.detailed_status:
                status.detailed_status = "Waiting for IP address..."
        elif status.instance_id and not status.private_ip:
            # Has public IP but no private IP
            priority = 1  # Still high priority but below waiting for public IP
        elif not status.instance_id:
            # Initializing (no instance ID yet)
            priority = 2
        elif status.public_ip and status.private_ip and "Done" in status.status:
            # Completed instances
            priority = 3
        elif status.public_ip and status.private_ip:
            # Instances with IPs but not marked as Done
            priority = 4
        else:
            # Default case
            priority = 2

        # Return tuple for sorting: (priority, region, zone, id)
        # This will sort first by priority, then by region/zone within each priority group
        return (priority, status.region, status.zone, status.id)

    sorted_statuses = sorted(all_statuses.values(), key=sort_key)

    for status in sorted_statuses:
        # Apply appropriate styling based on instance status
        status_style = ""
        if status.status in FAILED_STATUSES:
            status_style = "bold red"
        elif status.status == "Done":
            status_style = "bold green"
        elif status.status == "Terminated":
            status_style = "dim"

        # Format combined status with appropriate styling
        combined_status = status.combined_status()
        if status_style:
            combined_status = f"[{status_style}]{combined_status}[/{status_style}]"

        # Display "Waiting..." in the public IP column for instances that exist but have no IP yet
        # Don't show "Waiting..." for failed or terminated instances
        public_ip_display = status.public_ip
        if (
            not status.public_ip
            and status.instance_id
            and status.status not in FAILED_STATUSES
            and status.status != "Terminated"
        ):
            public_ip_display = "[yellow]Waiting...[/yellow]"
        elif status.status in FAILED_STATUSES:
            public_ip_display = "[red]N/A[/red]"

        # Display "Waiting..." in the private IP column for instances that exist but have no private IP yet
        # Don't show "Waiting..." for failed or terminated instances
        private_ip_display = status.private_ip
        if (
            not status.private_ip
            and status.instance_id
            and status.status not in FAILED_STATUSES
            and status.status != "Terminated"
        ):
            private_ip_display = "[yellow]Waiting...[/yellow]"
        elif status.status in FAILED_STATUSES:
            private_ip_display = "[red]N/A[/red]"

        # Apply appropriate styling to the instance ID based on status
        instance_id_display = status.instance_id or ""
        if status.status == "Failed":
            instance_id_display = "[red]Failed[/red]"
        elif status.status == "Bad Instance":
            instance_id_display = "[red]Bad Type[/red]"
        elif status.status == "Error":
            instance_id_display = "[red]Error[/red]"
        elif status.status == "Timeout":
            instance_id_display = "[red]Timeout[/red]"

        table.add_row(
            status.id,
            status.region,
            status.zone,
            combined_status,
            f"{status.elapsed_time:.1f}s",
            instance_id_display,
            public_ip_display,
            private_ip_display,
        )
    return table


def create_layout(progress, table):
    # Create main layout
    layout = Layout()

    # Progress panel
    progress_panel = Panel(
        progress,
        title="Progress",
        border_style="green",
        padding=(1, 1),
    )

    # Operations log panel
    global operations_logs
    ops_content = (
        "\n".join(operations_logs)
        if operations_logs
        else "[dim]No operations logged yet...[/dim]"
    )
    operations_panel = Panel(
        ops_content,
        title="AWS Operations",
        border_style="yellow",
        padding=(1, 1),
    )

    # Split layout into three sections, with operations at the bottom
    layout.split(
        Layout(progress_panel, name="progress", size=4),
        Layout(table, name="table", ratio=10),
        Layout(operations_panel, name="operations", ratio=1),
    )

    return layout


async def update_table(live):
    global \
        table_update_running, \
        task_total, \
        events_to_progress, \
        all_statuses, \
        console, \
        task_name, \
        operations_logs
    if table_update_running:
        logger.debug("Table update already running. Exiting.")
        return

    logger.debug("Starting table update.")

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

        # Initial layout creation
        table = make_progress_table()
        layout = create_layout(progress, table)
        live.update(layout)

        # Track last operations update time to ensure updates even when idle
        last_ops_update = time.time()
        ops_update_interval = 1.0  # Update operations panel at least every second

        while not table_update_event.is_set():
            update_needed = False

            # Process pending events with proper locking
            current_events = []
            try:
                # Get a snapshot of events_to_progress to process, using a non-blocking approach
                if events_to_progress:
                    # Make a copy to process without holding the lock for too long
                    current_events = events_to_progress.copy()
                    events_to_progress.clear()
            except Exception as e:
                logger.error(f"Error processing events: {e}")

            # Process the events we captured
            if current_events:
                update_needed = True
                for event in current_events:
                    try:
                        if isinstance(event, str):
                            # For list operation, event is instance_id
                            all_statuses[event].status = "Listed"
                        else:
                            # For create and destroy operations, event is InstanceStatus object
                            all_statuses[event.id] = event
                    except Exception as e:
                        logger.error(f"Error processing event {event}: {e}")

                # Log how many events we processed to help with debugging
                if len(current_events) > 5:
                    logger.debug(f"Processed {len(current_events)} UI events")

            # Calculate progress
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
                update_needed = True

            # Update progress
            progress.update(task, completed=completed)

            # Update elapsed time for all instances
            now = time.time()
            for status in all_statuses.values():
                status.elapsed_time = now - status.start_time

            # Check if operations panel needs updating
            force_ops_update = (now - last_ops_update) >= ops_update_interval

            # Determine if we need to update any part of the UI
            ops_update_needed = force_ops_update
            table_update_needed = update_needed

            if ops_update_needed or table_update_needed:
                logger.debug(
                    f"UI update: ops={ops_update_needed}, table={table_update_needed}"
                )

                # Always rebuild table if we have updates
                if table_update_needed:
                    table = make_progress_table()

                # Get operations content
                ops_content = (
                    "\n".join(operations_logs)
                    if operations_logs
                    else "[dim]No operations logged yet...[/dim]"
                )

                # Strategy: Only rebuild entire layout if we absolutely must
                # Otherwise just update the parts that changed
                if hasattr(live, "_layout") and live._layout is not None:
                    # If we have a layout already, try to update parts individually
                    if "operations" in live._layout and ops_update_needed:
                        live._layout["operations"].update(
                            Panel(
                                ops_content,
                                title="AWS Operations",
                                border_style="yellow",
                                padding=(1, 1),
                            )
                        )

                    if "table" in live._layout and table_update_needed:
                        live._layout["table"].update(table)

                    # Only refresh if we updated something
                    if ops_update_needed or table_update_needed:
                        live.refresh()
                else:
                    # First time or layout was reset - create full layout
                    layout = create_layout(progress, table)
                    live.update(layout)

                # Reset the update timer
                if ops_update_needed:
                    last_ops_update = now

            # More responsive sleep - short interval for better UI responsiveness
            await asyncio.sleep(0.05)

    except Exception as e:
        logger.error(f"Error in update_table: {str(e)}", exc_info=True)
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

    log_operation("Starting instance creation in region", "info", region)
    ec2 = get_ec2_client(region)
    region_cfg = config.get_region_config(region)
    log_operation("Connected to AWS EC2 API", "info", region)

    try:
        # Create cloud-init script
        log_operation("Generating startup script", "info", region)
        user_data = scripts_provider.create_cloud_init_script()
        if not user_data:
            error_msg = "User data is empty. Stopping creation."
            logger.error(error_msg)
            log_operation(error_msg, "error", region)
            return [], {}

        encoded_user_data = base64.b64encode(user_data.encode()).decode()
        log_operation("Startup script generated successfully", "info", region)

        # Create VPC and networking resources
        log_operation("Creating/checking VPC", "info", region)
        vpc_id = await create_vpc_if_not_exists(ec2)
        log_operation(f"VPC ready: {vpc_id}", "info", region)

        log_operation("Setting up internet gateway", "info", region)
        igw_id = await create_internet_gateway(ec2, vpc_id)
        log_operation(f"Internet gateway ready: {igw_id}", "info", region)

        log_operation("Creating route table", "info", region)
        route_table_id = await create_route_table(ec2, vpc_id, igw_id)
        log_operation(f"Route table ready: {route_table_id}", "info", region)

        log_operation("Setting up security group", "info", region)
        security_group_id = await create_security_group_if_not_exists(ec2, vpc_id)
        log_operation(f"Security group ready: {security_group_id}", "info", region)

        instance_ids = []
        log_operation("Getting available zones", "info", region)
        zones = await get_availability_zones(ec2)
        log_operation(f"Available zones: {', '.join(zones)}", "info", region)

        # We'll create instances one by one
        for i in range(instances_to_create):
            zone = zones[i % len(zones)]
            log_operation(
                f"Creating instance {i + 1}/{instances_to_create} in zone {zone}",
                "info",
                region,
            )

            log_operation(f"Creating subnet in zone {zone}", "info", region)
            subnet_id = await create_subnet(ec2, vpc_id, zone, f"10.0.{i}.0/24")
            log_operation(f"Subnet created: {subnet_id}", "info", region)

            log_operation("Associating route table with subnet", "info", region)
            try:
                await associate_route_table(ec2, route_table_id, subnet_id)
                log_operation("Route table associated successfully", "info", region)
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
                    already_msg = f"Route table already associated in {region}-{zone}"
                    logger.info(already_msg)
                    log_operation(already_msg, "info", region)
                else:
                    error_msg = (
                        f"Error associating route table in {region}-{zone}: {str(e)}"
                    )
                    logger.warning(error_msg)
                    log_operation(error_msg, "warning", region)

            thisInstanceStatusObject = InstanceStatus(region, zone, i)
            thisInstanceStatusObject.vpc_id = (
                vpc_id  # Store VPC ID early so it's available for cleanup if needed
            )

            # Add to global tracking with proper thread safety - this updates the UI but doesn't save to MACHINES.json
            await update_all_statuses_async(thisInstanceStatusObject)

            # IMPORTANT: We're not saving anything to machines.db at this stage.
            # We'll only save instances with valid AWS IDs once the spot request is fulfilled.

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
            thisInstanceStatusObject.detailed_status = "Sending spot request"
            await update_all_statuses_async(thisInstanceStatusObject)

            instance_id = await handle_spot_request(
                ec2, launch_specification, region, zone, thisInstanceStatusObject
            )

            if instance_id is None:
                # Spot instance request failed - mark as failed and continue
                thisInstanceStatusObject.status = "Failed"
                thisInstanceStatusObject.detailed_status = "No spot capacity available"
                await update_all_statuses_async(thisInstanceStatusObject)

                # For failed instances, we don't save to MACHINES.json
                # since they don't have AWS instance IDs
                await log_operation_async(
                    f"Instance request failed in {region}-{zone}", "warning", region
                )

                # Continue to the next instance in the loop
                continue

            # Set the instance ID - this changes the ID property to use AWS instance ID
            thisInstanceStatusObject.instance_id = instance_id
            instance_ids.append(instance_id)

            # Tag instances
            await asyncio.to_thread(
                ec2.create_tags,
                Resources=[instance_id],
                Tags=[
                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                    {"Key": "Name", "Value": f"SpotInstance-{region}-{zone}"},
                    {"Key": "AZ", "Value": zone},
                ],
            )

            # Fetch instance details
            instance_details = await asyncio.to_thread(
                ec2.describe_instances,
                InstanceIds=[instance_id],
            )
            if instance_details["Reservations"]:
                instance = instance_details["Reservations"][0]["Instances"][0]
                thisInstanceStatusObject.public_ip = instance.get("PublicIpAddress", "")
                thisInstanceStatusObject.private_ip = instance.get(
                    "PrivateIpAddress", ""
                )
                thisInstanceStatusObject.vpc_id = vpc_id

            # Save to MACHINES.json using the AWS instance ID as the key
            # This ensures each machine has a proper AWS identifier in the state file
            machine_state.set(
                thisInstanceStatusObject.id, thisInstanceStatusObject.to_dict()
            )
            await log_operation_async(f"Saved instance {instance_id} to MACHINES.json")

            # Mark the instance as done when it's been created successfully
            thisInstanceStatusObject.status = "Done"
            thisInstanceStatusObject.detailed_status = "Instance created successfully"
            # Force UI update
            await update_all_statuses_async(thisInstanceStatusObject)

            # Update the status in MACHINES.json
            machine_state.set(
                thisInstanceStatusObject.id, thisInstanceStatusObject.to_dict()
            )

    except Exception as e:
        logger.error(f"An error occurred in {region}: {str(e)}", exc_info=True)
        return [], {}

    return instance_ids


async def create_vpc_if_not_exists(ec2):
    # Log at the start of the function
    logger.debug("Checking for existing VPC")
    await log_operation_async("Checking for existing VPC tagged as SpotInstanceVPC")

    try:
        vpcs = await asyncio.to_thread(
            ec2.describe_vpcs,
            Filters=[{"Name": "tag:Name", "Values": ["SpotInstanceVPC"]}],
        )

        if vpcs["Vpcs"]:
            vpc_id = vpcs["Vpcs"][0]["VpcId"]
            await log_operation_async(f"Found existing VPC: {vpc_id}")
            return vpc_id
        else:
            await log_operation_async("No existing VPC found, creating new VPC")
            logger.debug("Creating new VPC with CIDR 10.0.0.0/16")

            vpc = await asyncio.to_thread(ec2.create_vpc, CidrBlock="10.0.0.0/16")
            vpc_id = vpc["Vpc"]["VpcId"]
            await log_operation_async(f"Created new VPC: {vpc_id}")

            await log_operation_async("Tagging VPC")
            await asyncio.to_thread(
                ec2.create_tags,
                Resources=[vpc_id],
                Tags=[{"Key": "Name", "Value": "SpotInstanceVPC"}],
            )

            await log_operation_async("Enabling DNS hostnames for VPC")
            await asyncio.to_thread(
                ec2.modify_vpc_attribute,
                VpcId=vpc_id,
                EnableDnsHostnames={"Value": True},
            )

            await log_operation_async("Enabling DNS support for VPC")
            await asyncio.to_thread(
                ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsSupport={"Value": True}
            )

            await log_operation_async(f"VPC {vpc_id} setup complete")
            return vpc_id
    except Exception as e:
        error_msg = f"Error creating/checking VPC: {str(e)}"
        logger.error(error_msg)
        await log_operation_async(error_msg, "error")
        raise


async def create_subnet(ec2, vpc_id, zone, cidr_block=None):
    # First, check if a subnet already exists in this zone
    await log_operation_async(f"Checking for existing subnet in zone {zone}")
    existing_subnets = await asyncio.to_thread(
        ec2.describe_subnets,
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "availability-zone", "Values": [zone]},
        ],
    )

    if existing_subnets["Subnets"]:
        # If a subnet exists, return its ID
        subnet_id = existing_subnets["Subnets"][0]["SubnetId"]
        await log_operation_async(f"Found existing subnet: {subnet_id} in zone {zone}")
        return subnet_id

    # If no subnet exists, try to create one
    await log_operation_async(f"Creating new subnet in zone {zone}")
    cidr_base_prefix = "10.0."
    cidr_base_suffix = ".0/24"
    for i in range(256):
        try:
            cidrBlock = (
                cidr_block
                if cidr_block
                else cidr_base_prefix + str(i) + cidr_base_suffix
            )
            logger.debug(f"Creating subnet in {zone} with CIDR block {cidrBlock}")
            await log_operation_async(
                f"Attempting CIDR block {cidrBlock} in zone {zone}"
            )
            subnet = await asyncio.to_thread(
                ec2.create_subnet,
                VpcId=vpc_id,
                CidrBlock=cidrBlock,
                AvailabilityZone=zone,
            )
            subnet_id = subnet["Subnet"]["SubnetId"]
            await log_operation_async(
                f"Created subnet {subnet_id} in zone {zone} with CIDR {cidrBlock}"
            )
            return subnet_id
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "InvalidSubnet.Conflict":
                # If this CIDR is in use, try the next one
                await log_operation_async(
                    f"CIDR {cidrBlock} already in use, trying next one", "info"
                )
                continue
            else:
                # If it's a different error, raise it
                await log_operation_async(f"Error creating subnet: {str(e)}", "error")
                raise

    # If we've tried all possible CIDRs and none worked, raise an error
    error_msg = f"Unable to create subnet in {zone}. All CIDR blocks are in use."
    await log_operation_async(error_msg, "error")
    raise Exception(error_msg)


async def create_internet_gateway(ec2, vpc_id):
    await log_operation_async(
        f"Checking for existing Internet Gateway attached to VPC {vpc_id}"
    )
    # First, check if the VPC already has an Internet Gateway attached
    igws = await asyncio.to_thread(
        ec2.describe_internet_gateways,
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
    )

    if igws["InternetGateways"]:
        # If an Internet Gateway is already attached, return its ID
        igw_id = igws["InternetGateways"][0]["InternetGatewayId"]
        await log_operation_async(f"Found existing Internet Gateway: {igw_id}")
        return igw_id

    # If no Internet Gateway is attached, create and attach a new one
    await log_operation_async("No existing Internet Gateway found, creating new one")
    igw = await asyncio.to_thread(ec2.create_internet_gateway)
    igw_id = igw["InternetGateway"]["InternetGatewayId"]
    await log_operation_async(f"Created Internet Gateway: {igw_id}")

    try:
        await log_operation_async(
            f"Attaching Internet Gateway {igw_id} to VPC {vpc_id}"
        )
        await asyncio.to_thread(
            ec2.attach_internet_gateway, InternetGatewayId=igw_id, VpcId=vpc_id
        )
        await log_operation_async(f"Internet Gateway {igw_id} attached successfully")
    except botocore.exceptions.ClientError as e:
        await log_operation_async(
            f"Error attaching Internet Gateway: {str(e)}", "warning"
        )
        # If an error occurs during attachment, delete the created IGW
        await log_operation_async(f"Cleaning up Internet Gateway {igw_id}")
        await asyncio.to_thread(ec2.delete_internet_gateway, InternetGatewayId=igw_id)

        # Re-check for existing IGW in case one was attached concurrently
        await log_operation_async(
            "Checking if an Internet Gateway was attached concurrently"
        )
        igws = await asyncio.to_thread(
            ec2.describe_internet_gateways,
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
        )
        if igws["InternetGateways"]:
            igw_id = igws["InternetGateways"][0]["InternetGatewayId"]
            await log_operation_async(f"Found concurrent Internet Gateway: {igw_id}")
            return igw_id
        else:
            # If still no IGW found, re-raise the original error
            await log_operation_async(
                "No Internet Gateway found and failed to create one", "error"
            )
            raise

    return igw_id


async def create_route_table(ec2, vpc_id, igw_id):
    # Check if a route table already exists for the VPC
    await log_operation_async(f"Looking for existing route tables in VPC {vpc_id}")
    route_tables = await asyncio.to_thread(
        ec2.describe_route_tables,
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )

    for rt in route_tables["RouteTables"]:
        for association in rt.get("Associations", []):
            if association.get("Main", False):
                # Found the main route table, check if we need to add a route to the IGW
                route_table_id = rt["RouteTableId"]
                await log_operation_async(f"Found main route table: {route_table_id}")

                routes = rt.get("Routes", [])
                if not any(route.get("GatewayId") == igw_id for route in routes):
                    await log_operation_async(
                        f"Adding internet route to existing route table {route_table_id}"
                    )
                    await asyncio.to_thread(
                        ec2.create_route,
                        RouteTableId=route_table_id,
                        DestinationCidrBlock="0.0.0.0/0",
                        GatewayId=igw_id,
                    )
                    await log_operation_async(
                        f"Added internet route (0.0.0.0/0) via {igw_id}"
                    )
                else:
                    await log_operation_async(
                        "Internet route already exists in route table"
                    )
                return route_table_id

    # If no route table exists, create a new one
    await log_operation_async(f"Creating new route table for VPC {vpc_id}")
    route_table = await asyncio.to_thread(ec2.create_route_table, VpcId=vpc_id)
    route_table_id = route_table["RouteTable"]["RouteTableId"]
    await log_operation_async(f"Created route table: {route_table_id}")

    # Create a route to the Internet Gateway
    await log_operation_async(f"Adding internet route (0.0.0.0/0) via {igw_id}")
    await asyncio.to_thread(
        ec2.create_route,
        RouteTableId=route_table_id,
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=igw_id,
    )
    await log_operation_async("Internet route added successfully")

    # Associate the route table with the VPC (make it the main route table)
    await log_operation_async("Associating route table with VPC (making it main)")
    await asyncio.to_thread(
        ec2.associate_route_table,
        RouteTableId=route_table_id,
        VpcId=vpc_id,
    )
    await log_operation_async("Route table association complete")

    return route_table_id


async def associate_route_table(ec2, route_table_id, subnet_id):
    await log_operation_async(
        f"Associating route table {route_table_id} with subnet {subnet_id}"
    )
    try:
        await asyncio.to_thread(
            ec2.associate_route_table, RouteTableId=route_table_id, SubnetId=subnet_id
        )
        await log_operation_async("Route table association completed successfully")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
            await log_operation_async(
                "Route table already associated with subnet", "info"
            )
            logger.debug(
                "Route table already associated in {route_table_id}-{subnet_id}: {str(e)}"
            )
        else:
            await log_operation_async(
                f"Error associating route table: {str(e)}", "error"
            )
            raise


async def create_security_group_if_not_exists(ec2, vpc_id):
    await log_operation_async("Checking for existing security group in VPC")
    security_groups = await asyncio.to_thread(
        ec2.describe_security_groups,
        Filters=[
            {"Name": "group-name", "Values": ["SpotInstanceSG"]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ],
    )
    if security_groups["SecurityGroups"]:
        sg_id = security_groups["SecurityGroups"][0]["GroupId"]
        await log_operation_async(f"Found existing security group: {sg_id}")
        return sg_id
    else:
        await log_operation_async("Creating new security group named 'SpotInstanceSG'")
        security_group = await asyncio.to_thread(
            ec2.create_security_group,
            GroupName="SpotInstanceSG",
            Description="Security group for Spot Instances",
            VpcId=vpc_id,
        )
        security_group_id = security_group["GroupId"]
        await log_operation_async(f"Created security group: {security_group_id}")

        await log_operation_async(
            "Adding security group ingress rules (SSH port 22, Bacalhau ports 1234-1235, and EC2 Instance Connect)"
        )

        # EC2 Instance Connect IP ranges vary by region
        # Format: ec2-instance-connect.{region}.amazonaws.com
        ec2_connect_cidr = (
            "18.206.107.24/29"  # This is a common CIDR for EC2 Instance Connect
        )

        await asyncio.to_thread(
            ec2.authorize_security_group_ingress,
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0"},
                        {
                            "CidrIp": ec2_connect_cidr,
                            "Description": "EC2 Instance Connect",
                        },
                    ],
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
        await log_operation_async(f"Security group setup complete: {security_group_id}")
        return security_group_id


async def create_spot_instances():
    global task_name, task_total
    task_name = "Creating Spot Instances"
    task_total = MAX_NODES

    logger.debug(f"Starting spot instance creation. MAX_NODES: {MAX_NODES}")
    log_operation(f"Starting spot instance creation. Maximum nodes: {MAX_NODES}")
    log_operation(f"Will work across {len(AWS_REGIONS)} AWS regions")

    async def create_in_region(region):
        global global_node_count
        available_slots = MAX_NODES - global_node_count
        region_cfg = config.get_region_config(region)
        logger.debug(f"Region {region} config: {region_cfg}")

        if available_slots <= 0:
            skip_msg = f"Reached maximum nodes ({MAX_NODES}). Skipping region: {region}"
            logger.warning(skip_msg)
            log_operation(skip_msg, "warning", region)
            return [], {}

        instances_to_create = (
            min(INSTANCES_PER_REGION, available_slots)
            if region_cfg.get("node_count") == "auto"
            else (min(region_cfg.get("node_count"), available_slots))
        )

        if instances_to_create == 0:
            logger.debug(f"No instances to create in region {region}")
            log_operation("No instances to create", "info", region)
            return [], {}

        create_msg = (
            f"Creating {instances_to_create} spot instances in region: {region}"
        )
        logger.debug(create_msg)
        log_operation(create_msg, "info", region)
        global_node_count += instances_to_create

        try:
            instance_ids = await create_spot_instances_in_region(
                config, instances_to_create, region
            )
            result_msg = f"Created {len(instance_ids)} instances"
            logger.debug(f"Created instances in {region}: {instance_ids}")
            log_operation(result_msg, "info", region)
            return instance_ids
        except Exception as e:
            error_msg = f"Failed to create instances: {str(e)}"
            logger.exception(f"Failed to create instances in region {region}")
            log_operation(error_msg, "error", region)
            return [], {}

    try:
        log_operation("Launching creation tasks in parallel across regions")
        tasks = [create_in_region(region) for region in AWS_REGIONS]
        results = await asyncio.gather(*tasks)
        log_operation("All region creation tasks completed")
        logger.debug(f"All region creation tasks completed. Results: {results}")
    except Exception as e:
        error_msg = f"Failed during instance creation: {str(e)}"
        logger.exception("Failed during instance creation across regions")
        log_operation(error_msg, "error")
        raise

    # Check for any failed instances before waiting for IPs
    FAILED_STATUSES = ["Failed", "Bad Instance", "Error", "Timeout"]
    failed_instances = [
        status.id
        for status in all_statuses.values()
        if status.status in FAILED_STATUSES
    ]

    if failed_instances:
        await log_operation_async(
            f"Detected {len(failed_instances)} failed instance requests", "warning"
        )
        # Log details about the failed instances
        for status_id in failed_instances:
            status = all_statuses[status_id]
            await log_operation_async(
                f"Instance failed in {status.region}-{status.zone}: {status.detailed_status}",
                "warning",
                status.region,
            )

    # Count valid instances that are waiting for IPs
    waiting_instances = [
        status
        for status in all_statuses.values()
        if status.instance_id
        and not status.public_ip
        and status.status not in FAILED_STATUSES
    ]

    if waiting_instances:
        logger.debug("Waiting for public IP addresses...")
        await log_operation_async(
            f"Waiting for public IP addresses to be assigned to {len(waiting_instances)} instances..."
        )
        await wait_for_public_ips()
        await log_operation_async("IP address assignment complete")
    else:
        await log_operation_async("No instances waiting for IP addresses")

    # Before logging a summary, ensure all instances with IPs are marked as Done
    # and saved to MACHINES.json with their final state
    await log_operation_async(
        "Final pass - updating all completed instances to 'Done' status"
    )
    completion_count = 0

    # Update all instances that have IPs to Done status
    for status in all_statuses.values():
        if status.public_ip and status.private_ip and status.instance_id:
            # Mark as done if not already
            if status.status != "Done":
                status.status = "Done"
                status.detailed_status = (
                    f"Ready - {datetime.now().strftime('%H:%M:%S')}"
                )
                await update_all_statuses_async(status)

            # Save to MACHINES.json via the thread-safe dictionary
            machine_state.set(status.id, status.to_dict())
            completion_count += 1

    if completion_count > 0:
        await log_operation_async(
            f"Updated {completion_count} completed instances to final state"
        )

    # Get a summary of the machine state
    valid_machines = machine_state.get_all()
    valid_count = len(valid_machines)

    # Count failed instances in all_statuses for accurate reporting
    FAILED_STATUSES = ["Failed", "Bad Instance", "Error", "Timeout"]
    failed_instances = [
        status for status in all_statuses.values() if status.status in FAILED_STATUSES
    ]

    # Create a detailed summary
    await log_operation_async(
        f"MACHINES.json summary: {valid_count} instances with AWS IDs "
        + f"({len(failed_instances)} failed requests during creation)"
    )

    if valid_count == 0:
        if len(failed_instances) > 0:
            # If all instances failed, provide a clear error message
            await log_operation_async(
                f"WARNING: All {len(failed_instances)} instance requests failed - check logs for details",
                "warning",
            )
            # Summarize failures by region
            failures_by_region = {}
            for status in failed_instances:
                if status.region not in failures_by_region:
                    failures_by_region[status.region] = []
                failures_by_region[status.region].append(
                    f"{status.id} ({status.detailed_status})"
                )

            for region, failures in failures_by_region.items():
                await log_operation_async(
                    f"Region {region} failures: {', '.join(failures)}", "warning"
                )
        else:
            await log_operation_async(
                "WARNING: No AWS instance IDs found in MACHINES.json", "warning"
            )

        # Dump the all_statuses to help diagnose the issue
        status_summary = ", ".join(
            [f"{s.id}:{s.status}" for s in all_statuses.values()]
        )
        logger.debug(f"Current status objects: {status_summary}")
    else:
        if len(failed_instances) > 0:
            # Some instances succeeded but some failed
            await log_operation_async(
                f"Successfully provisioned {valid_count} instances "
                + f"({len(failed_instances)} requests failed, most likely due to capacity issues)",
                "info",
            )
        else:
            # All instances succeeded
            await log_operation_async(
                f"Successfully provisioned {valid_count} instances"
            )

    logger.debug("Finished creating spot instances")
    await log_operation_async("Finished creating spot instances")
    return


async def update_instance_status(status, public_ip="", private_ip="", mark_done=False):
    """Helper function to update instance status and IPs."""
    status_changed = False

    # Update IPs if provided
    if public_ip and not status.public_ip:
        status.public_ip = public_ip
        status_changed = True
        await log_operation_async(
            f"Instance {status.instance_id} got public IP: {public_ip}",
            "info",
            status.region,
        )

    if private_ip and not status.private_ip:
        status.private_ip = private_ip
        status_changed = True
        await log_operation_async(
            f"Instance {status.instance_id} got private IP: {private_ip}",
            "info",
            status.region,
        )

    # Update status based on current state
    if mark_done and status.public_ip and status.private_ip and status.status != "Done":
        status.status = "Done"
        status.detailed_status = f"Ready - {datetime.now().strftime('%H:%M:%S')}"
        status_changed = True
    elif status.public_ip and not status.private_ip:
        status.detailed_status = "Public IP assigned, waiting for private IP..."
        status_changed = True
    elif not status.public_ip and status.private_ip:
        status.detailed_status = "Private IP assigned, waiting for public IP..."
        status_changed = True
    elif not status.public_ip:
        status.detailed_status = "Waiting for public IP address..."
        status_changed = True
    elif not status.private_ip:
        status.detailed_status = "Waiting for private IP address..."
        status_changed = True

    # Update UI and state file if needed
    if status_changed:
        await update_all_statuses_async(status)
        if status.status == "Done" and status.instance_id:
            machine_state.set(status.id, status.to_dict())

    return status_changed


def get_instances_without_ip(statuses, no_ip_status, failed_statuses):
    """Helper function to count instances still waiting for IPs."""
    return [
        status
        for status in statuses.values()
        if not status.public_ip
        and status.status != no_ip_status
        and status.status not in failed_statuses
    ]


async def wait_for_public_ips():
    global all_statuses
    timeout = 300  # 5 minutes timeout
    start_time = time.time()

    NO_IP_STATUS = "-----"
    FAILED_STATUSES = ["Failed", "Bad Instance", "Error", "Timeout"]
    await log_operation_async("Checking for public IP addresses on all instances")

    # Count initial instances without IPs
    instances_without_ip = get_instances_without_ip(
        all_statuses, NO_IP_STATUS, FAILED_STATUSES
    )
    await log_operation_async(
        f"Waiting for IP addresses for {len(instances_without_ip)} instances"
    )

    # Identify failed instances that we won't wait for
    failed_instances = [
        status.id
        for status in all_statuses.values()
        if status.status in FAILED_STATUSES
    ]
    if failed_instances:
        await log_operation_async(
            f"Ignoring {len(failed_instances)} failed instances: {', '.join(failed_instances)}",
            "warning",
        )

    check_count = 0
    try:
        while True:
            # Check if all instances have required IPs or are in terminal states
            all_have_ips = all(
                status.public_ip
                or status.status == NO_IP_STATUS
                or status.status in FAILED_STATUSES
                for status in all_statuses.values()
            )

            if all_have_ips:
                await log_operation_async(
                    "All non-failed instances have IP addresses assigned"
                )
                # Mark all valid instances as done
                for status in all_statuses.values():
                    await update_instance_status(status, mark_done=True)
                break

            # Check for timeout
            if time.time() - start_time > timeout:
                await log_operation_async(
                    "Timed out waiting for IP addresses", "warning"
                )
                # Mark instances with IPs as done
                for status in all_statuses.values():
                    await update_instance_status(status, mark_done=True)

                # Report instances still waiting
                still_waiting = [
                    f"{status.id} ({status.region})"
                    for status in get_instances_without_ip(
                        all_statuses, NO_IP_STATUS, FAILED_STATUSES
                    )
                ]
                if still_waiting:
                    await log_operation_async(
                        f"Giving up on waiting for IPs for instances: {', '.join(still_waiting)}",
                        "warning",
                    )
                break

            # Periodic status update
            if check_count % 6 == 0:  # Every ~30 seconds
                waiting_count = len(
                    get_instances_without_ip(
                        all_statuses, NO_IP_STATUS, FAILED_STATUSES
                    )
                )
                elapsed = int(time.time() - start_time)
                await log_operation_async(
                    f"Still waiting for {waiting_count} IP addresses... ({elapsed}s elapsed)"
                )

            check_count += 1

            # Check each region for IP updates
            for region in AWS_REGIONS:
                ec2 = get_ec2_client(region)
                instance_ids = [
                    status.instance_id
                    for status in all_statuses.values()
                    if (
                        status.region == region
                        and not status.public_ip
                        and status.status != NO_IP_STATUS
                        and status.status not in FAILED_STATUSES
                        and status.instance_id is not None
                    )
                ]

                if not instance_ids:
                    continue

                try:
                    # Update status to show we're checking
                    for instance_id in instance_ids:
                        for status in all_statuses.values():
                            if status.instance_id == instance_id:
                                status.detailed_status = "🔄 Checking IP addresses..."
                                await update_all_statuses_async(status)

                    # Get instance information from AWS
                    response = await asyncio.to_thread(
                        ec2.describe_instances, InstanceIds=instance_ids
                    )

                    # Process each instance
                    for reservation in response["Reservations"]:
                        for instance in reservation["Instances"]:
                            instance_id = instance["InstanceId"]
                            public_ip = instance.get("PublicIpAddress", "")
                            private_ip = instance.get("PrivateIpAddress", "")

                            # Update matching status
                            for status in all_statuses.values():
                                if status.instance_id == instance_id:
                                    await update_instance_status(
                                        status,
                                        public_ip=public_ip,
                                        private_ip=private_ip,
                                    )

                except Exception as e:
                    logger.warning(f"Error checking IPs in region {region}: {str(e)}")
                    await log_operation_async(
                        f"Error checking IPs: {str(e)}", "warning", region
                    )

            # Short sleep with cancellation check
            for _ in range(5):
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("IP address check was cancelled")
        await log_operation_async("IP address check was cancelled", "warning")
        raise


async def list_spot_instances():
    global all_statuses, events_to_progress, task_total
    all_statuses = {}
    events_to_progress = []

    global task_name
    task_name = "Listing Spot Instances"
    task_total = 0

    logger.debug("Starting to list spot instances")

    # First load from MACHINES.json
    machines = await machine_state.load()
    task_total = len(machines)

    # Verify each instance in MACHINES.json still exists and update its status
    for instance_id, machine in machines.items():
        region = machine["region"]
        ec2 = get_ec2_client(region)

        try:
            response = await asyncio.to_thread(
                ec2.describe_instances, InstanceIds=[instance_id]
            )

            if response["Reservations"]:
                instance = response["Reservations"][0]["Instances"][0]
                thisInstanceStatusObject = InstanceStatus(
                    machine["region"], machine["zone"], 0, instance_id
                )
                thisInstanceStatusObject.status = instance["State"]["Name"].capitalize()
                thisInstanceStatusObject.elapsed_time = (
                    datetime.now(timezone.utc) - instance["LaunchTime"]
                ).total_seconds()
                thisInstanceStatusObject.public_ip = instance.get("PublicIpAddress", "")
                thisInstanceStatusObject.private_ip = instance.get(
                    "PrivateIpAddress", ""
                )
                thisInstanceStatusObject.vpc_id = machine["vpc_id"]

                events_to_progress.append(instance_id)
                all_statuses[instance_id] = thisInstanceStatusObject
            else:
                # Instance no longer exists, remove from MACHINES.json
                machine_state.delete(instance_id)
                logger.debug(
                    f"Removed non-existent instance {instance_id} from state file"
                )

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                # Instance no longer exists, remove from MACHINES.json
                machine_state.delete(instance_id)
                logger.debug(f"Removed invalid instance {instance_id} from state file")
            else:
                logger.error(f"Error checking instance {instance_id}: {str(e)}")

    logger.debug("Finished listing spot instances")
    return all_statuses


async def destroy_instances():
    global task_name, task_total, events_to_progress
    task_name = "Terminating Spot Instances"
    events_to_progress = []

    logger.info("Loading instance information from machines.db...")
    log_operation("Loading instance information from machines.db...")

    # Check if machines.db exists and has instances
    if machine_state.count() == 0:
        msg = "No instances found in database. No instances to terminate."
        logger.info(msg)
        log_operation(msg, "warning")

        # Clean up empty database file if it exists
        if os.path.exists(machine_state.db_path):
            try:
                os.remove(machine_state.db_path)
                logger.info("Removed empty machines.db file")
                log_operation("Removed empty machines.db file")
            except Exception as e:
                logger.warning(f"Failed to remove machines.db: {str(e)}")
        return

    machines = await machine_state.load()

    if not machines:
        msg = "Database exists but contains no instances to terminate."
        logger.info(msg)
        log_operation(msg, "warning")

        # Clean up empty database file
        if os.path.exists(machine_state.db_path):
            try:
                os.remove(machine_state.db_path)
                logger.info("Removed empty machines.db file")
                log_operation("Removed empty machines.db file")
            except Exception as e:
                logger.warning(f"Failed to remove machines.db: {str(e)}")
        return

    task_total = len(machines)
    logger.info(f"Found {task_total} instances to terminate.")
    log_operation(f"Found {task_total} instances to terminate.")

    # Group instances by region and collect actual instance IDs
    region_instances = {}
    region_spot_requests = {}
    status_by_machine_id = {}

    # First, create status objects for all machines in the state file
    for machine_id, machine in machines.items():
        region = machine["region"]
        instance_id = machine.get("instance_id", None)
        spot_request_id = machine.get("spot_request_id", None)

        # Setup region containers if not already created
        if region not in region_instances:
            region_instances[region] = []
        if region not in region_spot_requests:
            region_spot_requests[region] = []

        # Handle machines with instance IDs
        if instance_id:
            logger.info(
                f"Will terminate instance {instance_id} in {region}-{machine['zone']}"
            )
            log_operation(
                f"Will terminate instance {instance_id} in {region}-{machine['zone']}",
                "info",
                region,
            )

            # Add this instance to the region's instance list
            region_instances[region].append(instance_id)

            # Create status object for tracking
            thisInstanceStatusObject = InstanceStatus(
                machine["region"], machine["zone"], 0, instance_id
            )
            thisInstanceStatusObject.status = "Terminating"
            thisInstanceStatusObject.detailed_status = "Initializing termination"
            thisInstanceStatusObject.vpc_id = machine.get("vpc_id", "")
            thisInstanceStatusObject.public_ip = machine.get("public_ip", "")
            thisInstanceStatusObject.private_ip = machine.get("private_ip", "")
            thisInstanceStatusObject.spot_request_id = spot_request_id

            # Store using both keys - we'll need both for tracking
            all_statuses[instance_id] = thisInstanceStatusObject
            status_by_machine_id[machine_id] = thisInstanceStatusObject

        # Handle machines with spot request IDs but no instance IDs yet
        elif spot_request_id:
            logger.info(
                f"Found spot request {spot_request_id} in {region}-{machine['zone']} with no instance yet"
            )
            log_operation(f"Will cancel spot request {spot_request_id}", "info", region)

            # Add this spot request to the region's spot request list
            region_spot_requests[region].append(spot_request_id)

            # Create status object for tracking using the machine ID as the key
            # since there's no instance ID
            thisInstanceStatusObject = InstanceStatus(
                machine["region"], machine["zone"], 0, None
            )
            thisInstanceStatusObject.spot_request_id = spot_request_id
            thisInstanceStatusObject.status = "Cancelling"
            thisInstanceStatusObject.detailed_status = "Cancelling spot request"
            thisInstanceStatusObject.vpc_id = machine.get("vpc_id", "")

            # Store using machine ID as the key
            all_statuses[machine_id] = thisInstanceStatusObject
            status_by_machine_id[machine_id] = thisInstanceStatusObject
        else:
            logger.warning(
                f"No instance ID or spot request ID for machine {machine_id}. Skipping."
            )
            log_operation(
                f"No instance ID or spot request ID for machine {machine_id}. Skipping.",
                "warning",
                region,
            )

    # Check if we have any valid resources to clean up
    has_resources_to_clean = any(region_instances.values()) or any(
        region_spot_requests.values()
    )

    if not has_resources_to_clean:
        msg = "No valid instances or spot requests to terminate."
        logger.info(msg)
        log_operation(msg, "warning")
        return

    async def terminate_instances_in_region(region, instance_ids):
        ec2 = get_ec2_client(region)
        log_operation(
            f"Starting termination of {len(instance_ids)} instances", "info", region
        )

        try:
            # Check which instances actually exist first
            try:
                existing = await asyncio.to_thread(
                    ec2.describe_instances, InstanceIds=instance_ids
                )
                valid_instance_ids = []
                for reservation in existing["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        valid_instance_ids.append(instance_id)
                        state = instance["State"]["Name"]

                        if state == "terminated":
                            # Instance already terminated
                            all_statuses[instance_id].status = "Terminated"
                            all_statuses[
                                instance_id
                            ].detailed_status = "Already terminated"
                            events_to_progress.append(all_statuses[instance_id])
                            log_operation(
                                f"Instance {instance_id} is already terminated",
                                "info",
                                region,
                            )

                # If no valid instances left, exit early
                if not valid_instance_ids:
                    log_operation(
                        f"No active instances found in {region}", "warning", region
                    )
                    return

                # Update the instance list to only valid instances
                instance_ids = [id for id in instance_ids if id in valid_instance_ids]

            except botocore.exceptions.ClientError as e:
                if "InvalidInstanceID.NotFound" in str(e):
                    # One or more instances no longer exist
                    log_operation(
                        f"One or more instances not found: {str(e)}", "warning", region
                    )

                    # Try to find which instances still exist
                    existing_instances = []
                    for instance_id in instance_ids:
                        try:
                            await asyncio.to_thread(
                                ec2.describe_instances, InstanceIds=[instance_id]
                            )
                            existing_instances.append(instance_id)
                        except botocore.exceptions.ClientError:
                            # This instance doesn't exist
                            if instance_id in all_statuses:
                                all_statuses[instance_id].status = "N/A"
                                all_statuses[
                                    instance_id
                                ].detailed_status = "Instance not found"
                                events_to_progress.append(all_statuses[instance_id])
                                log_operation(
                                    f"Instance {instance_id} not found",
                                    "warning",
                                    region,
                                )

                    instance_ids = existing_instances

                    if not instance_ids:
                        log_operation(
                            f"No existing instances in {region}", "warning", region
                        )
                        return
                else:
                    # Unexpected error
                    log_operation(
                        f"Error checking instances: {str(e)}", "error", region
                    )
                    return

            # Terminate instances if we have any left
            if instance_ids:
                log_operation(
                    f"Terminating {len(instance_ids)} instances", "info", region
                )

                # Remove from MACHINES.json before termination
                async with machine_state.update() as current_machines:
                    # Find machine IDs associated with these instance IDs
                    for machine_id in list(current_machines.keys()):
                        machine = current_machines[machine_id]
                        if machine.get("instance_id") in instance_ids:
                            log_operation(
                                f"Removing {machine_id} from state file before termination",
                                "info",
                                region,
                            )
                            current_machines.pop(machine_id, None)

                for instance_id in instance_ids:
                    if instance_id in all_statuses:
                        all_statuses[
                            instance_id
                        ].detailed_status = "Sending terminate command"
                        events_to_progress.append(all_statuses[instance_id])

                try:
                    # Terminate instances
                    await asyncio.to_thread(
                        ec2.terminate_instances, InstanceIds=instance_ids
                    )
                    log_operation("Terminate command sent successfully", "info", region)

                    # Wait for termination
                    waiter = ec2.get_waiter("instance_terminated")
                    start_time = time.time()

                    for instance_id in instance_ids:
                        if instance_id in all_statuses:
                            all_statuses[
                                instance_id
                            ].detailed_status = "Waiting for termination"
                            events_to_progress.append(all_statuses[instance_id])

                    while True:
                        try:
                            log_operation(
                                "Checking termination status...", "info", region
                            )
                            await asyncio.to_thread(
                                waiter.wait,
                                InstanceIds=instance_ids,
                                WaiterConfig={"MaxAttempts": 1},
                            )
                            log_operation(
                                "All instances terminated successfully", "info", region
                            )
                            break
                        except botocore.exceptions.WaiterError:
                            elapsed_time = time.time() - start_time
                            log_operation(
                                f"Still waiting for termination ({elapsed_time:.0f}s)",
                                "info",
                                region,
                            )

                            # Update status for instances still terminating
                            for instance_id in instance_ids:
                                if instance_id in all_statuses:
                                    all_statuses[
                                        instance_id
                                    ].elapsed_time = elapsed_time
                                    all_statuses[
                                        instance_id
                                    ].detailed_status = (
                                        f"Terminating ({elapsed_time:.0f}s)"
                                    )
                                    events_to_progress.append(all_statuses[instance_id])

                            # Break out if taking too long
                            if elapsed_time > 300:  # 5 minutes timeout
                                log_operation(
                                    "Termination taking too long, continuing...",
                                    "warning",
                                    region,
                                )
                                break

                            await asyncio.sleep(10)

                    # Update status for terminated instances
                    for instance_id in instance_ids:
                        if instance_id in all_statuses:
                            all_statuses[instance_id].status = "Terminated"
                            all_statuses[
                                instance_id
                            ].detailed_status = "Instance terminated"
                            events_to_progress.append(all_statuses[instance_id])
                except Exception as e:
                    log_operation(
                        f"Error during termination: {str(e)}", "error", region
                    )
                    logger.error(f"Error terminating instances in {region}: {str(e)}")
                    return

            # Clean up resources for each VPC
            vpcs_to_delete = set(
                all_statuses[instance_id].vpc_id
                for instance_id in instance_ids
                if instance_id in all_statuses and all_statuses[instance_id].vpc_id
            )

            for vpc_id in vpcs_to_delete:
                if not vpc_id.startswith("vpc-"):
                    log_operation(
                        f"Invalid VPC ID: {vpc_id}, skipping cleanup", "warning", region
                    )
                    continue

                try:
                    log_operation(f"Cleaning up VPC {vpc_id}", "info", region)

                    for instance_id in instance_ids:
                        if (
                            instance_id in all_statuses
                            and all_statuses[instance_id].vpc_id == vpc_id
                        ):
                            all_statuses[
                                instance_id
                            ].detailed_status = "Cleaning up VPC resources"
                            events_to_progress.append(all_statuses[instance_id])

                    await clean_up_vpc_resources(ec2, vpc_id)
                    log_operation(f"VPC {vpc_id} cleanup complete", "info", region)

                except Exception as e:
                    error_msg = f"Error cleaning up VPC {vpc_id}: {str(e)}"
                    logger.error(error_msg)
                    log_operation(error_msg, "error", region)

        except Exception as e:
            error_msg = f"Error cleaning up resources: {str(e)}"
            logger.error(error_msg)
            log_operation(error_msg, "error", region)

    # Define a function to cancel spot requests
    async def cancel_spot_requests_in_region(region, spot_request_ids):
        if not spot_request_ids:
            return

        ec2 = get_ec2_client(region)
        log_operation(
            f"Starting cancellation of {len(spot_request_ids)} spot requests",
            "info",
            region,
        )

        try:
            # Cancel the spot requests
            log_operation(
                f"Cancelling spot requests: {', '.join(spot_request_ids)}",
                "info",
                region,
            )

            # Update status for each spot request
            for spot_id in spot_request_ids:
                # Find the status object for this spot request ID
                for status_id, status in all_statuses.items():
                    if status.spot_request_id == spot_id:
                        status.detailed_status = "Cancelling request"
                        events_to_progress.append(status)

            try:
                # Request cancellation via AWS API
                await asyncio.to_thread(
                    ec2.cancel_spot_instance_requests,
                    SpotInstanceRequestIds=spot_request_ids,
                )

                # Update status for successful cancellation
                for spot_id in spot_request_ids:
                    for status_id, status in all_statuses.items():
                        if status.spot_request_id == spot_id:
                            status.status = "Cancelled"
                            status.detailed_status = "Spot request cancelled"
                            events_to_progress.append(status)
                            log_operation(
                                f"Spot request {spot_id} cancelled successfully",
                                "info",
                                region,
                            )

                # Remove from MACHINES.json
                async with machine_state.update() as current_machines:
                    # Remove machines with these spot request IDs
                    keys_to_remove = []
                    for machine_id, machine in current_machines.items():
                        if machine.get("spot_request_id") in spot_request_ids:
                            keys_to_remove.append(machine_id)
                            log_operation(
                                f"Removing machine {machine_id} from state file",
                                "info",
                                region,
                            )

                    # Remove after iteration to avoid modifying dict during iteration
                    for key in keys_to_remove:
                        current_machines.pop(key, None)

            except botocore.exceptions.ClientError as e:
                log_operation(
                    f"Error cancelling spot requests: {str(e)}", "error", region
                )
                logger.error(f"Error cancelling spot requests in {region}: {str(e)}")

                # Update status for failed cancellation
                for spot_id in spot_request_ids:
                    for status_id, status in all_statuses.items():
                        if status.spot_request_id == spot_id:
                            status.status = "Failed"
                            status.detailed_status = (
                                f"Cancellation failed: {str(e)[:30]}"
                            )
                            events_to_progress.append(status)

        except Exception as e:
            log_operation(f"Error processing spot requests: {str(e)}", "error", region)
            logger.error(f"Error in spot request cancellation for {region}: {str(e)}")

    try:
        # Track what tasks need to be run
        termination_tasks = []
        cancellation_tasks = []

        # Add termination tasks if needed
        if any(region_instances.values()):
            log_operation(
                f"Starting parallel termination in {sum(1 for v in region_instances.values() if v)} regions"
            )
            termination_tasks = [
                terminate_instances_in_region(region, instances)
                for region, instances in region_instances.items()
                if instances
            ]

        # Add cancellation tasks if needed
        if any(region_spot_requests.values()):
            log_operation(
                f"Starting spot request cancellation in {sum(1 for v in region_spot_requests.values() if v)} regions"
            )
            cancellation_tasks = [
                cancel_spot_requests_in_region(region, spot_requests)
                for region, spot_requests in region_spot_requests.items()
                if spot_requests
            ]

        # Execute all tasks in parallel
        all_tasks = termination_tasks + cancellation_tasks
        if all_tasks:
            await asyncio.gather(*all_tasks)

        # Log completion messages for each resource type
        if termination_tasks:
            log_operation("All instance termination operations completed")
        if cancellation_tasks:
            log_operation("All spot request cancellation operations completed")

    except Exception as e:
        error_msg = f"Error during termination operations: {str(e)}"
        logger.exception(error_msg)
        log_operation(error_msg, "error")

    logger.info("All instances and spot requests have been terminated.")

    # After all instances are terminated and database is empty, remove the file
    if machine_state.count() == 0 and os.path.exists(machine_state.db_path):
        try:
            os.remove(machine_state.db_path)
            logger.info("Cleanup complete - removed machines.db file")
            log_operation("Cleanup complete - removed machines.db file")
        except Exception as e:
            logger.warning(f"Failed to remove machines.db after cleanup: {str(e)}")
            log_operation("Warning: Could not remove machines.db file", "warning")


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


class SQLiteMachineStateManager:
    def __init__(self, db_path="machines.db"):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create the database and table if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS machines (
                    instance_id TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    vpc_id TEXT,
                    public_ip TEXT,
                    private_ip TEXT,
                    spot_request_id TEXT,
                    status TEXT,
                    detailed_status TEXT,
                    creation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data JSON
                )
            """)
            conn.commit()

    async def check_existing_file(self, overwrite=False):
        """Check if there are existing machines in the database"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM machines")
            count = (await cursor.fetchone())[0]

            if count > 0 and not overwrite:
                print(
                    f"WARNING: Database already contains {count} instances. Cannot proceed without --overwrite flag."
                )
                print(
                    "Use --overwrite flag to continue anyway, or --action destroy to delete existing instances first."
                )
                return False

            if overwrite:
                await db.execute("DELETE FROM machines")
                await db.commit()

            return True

    def get(self, instance_id, default=None):
        """Get machine data by instance ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM machines WHERE instance_id = ?", (instance_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return default

    def set(self, instance_id, data):
        """Set machine data by instance ID"""
        if not (
            isinstance(data, dict)
            and data.get("instance_id")
            and str(data.get("instance_id")).startswith("i-")
        ):
            return False

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO machines (
                    instance_id, region, zone, vpc_id, public_ip, private_ip,
                    spot_request_id, status, detailed_status, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    instance_id,
                    data.get("region"),
                    data.get("zone"),
                    data.get("vpc_id"),
                    data.get("public_ip"),
                    data.get("private_ip"),
                    data.get("spot_request_id"),
                    data.get("status"),
                    data.get("detailed_status"),
                    json.dumps(data),
                ),
            )
            conn.commit()
            return True

    def delete(self, instance_id):
        """Delete machine data by instance ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM machines WHERE instance_id = ?", (instance_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    async def load(self):
        """Load all machine data"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT data FROM machines")
            rows = await cursor.fetchall()
            return {
                json.loads(row[0])["instance_id"]: json.loads(row[0]) for row in rows
            }

    def get_all(self):
        """Get all machine data"""
        with sqlite3.connect(self.db_path) as conn:
            # Ensure table exists before querying
            self._ensure_db_exists()
            cursor = conn.execute("SELECT data FROM machines")
            return {
                json.loads(row[0])["instance_id"]: json.loads(row[0])
                for row in cursor.fetchall()
            }

    def count(self):
        """Count valid machines"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM machines")
            return cursor.fetchone()[0]

    def clear(self):
        """Clear all machines"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM machines")
            conn.commit()

    def debug_state(self):
        """Print debug information about the current machine state"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data FROM machines")
            machines = {
                json.loads(row[0])["instance_id"]: json.loads(row[0])
                for row in cursor.fetchall()
            }

            aws_instance_ids = [m.get("instance_id") for m in machines.values()]

            logger.debug(f"Database has {len(machines)} valid AWS instances")
            if machines:
                logger.debug(f"Instance IDs: {aws_instance_ids}")

            return {
                "total": len(machines),
                "aws_ids": len(machines),
                "aws_id_list": aws_instance_ids,
                "machines": machines,
            }

    @asynccontextmanager
    async def update(self):
        """
        Async context manager for atomic updates to the machine state.
        This ensures that all updates within the context are atomic.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute("SELECT instance_id, data FROM machines")
                rows = await cursor.fetchall()
                machines = {row[0]: json.loads(row[1]) for row in rows}

                yield machines

                # Update all machines in the transaction
                await db.execute("DELETE FROM machines")
                for instance_id, data in machines.items():
                    await db.execute(
                        """
                        INSERT INTO machines (
                            instance_id, region, zone, vpc_id, public_ip, private_ip,
                            spot_request_id, status, detailed_status, data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            instance_id,
                            data.get("region"),
                            data.get("zone"),
                            data.get("vpc_id"),
                            data.get("public_ip"),
                            data.get("private_ip"),
                            data.get("spot_request_id"),
                            data.get("status"),
                            data.get("detailed_status"),
                            json.dumps(data),
                        ),
                    )
                await db.commit()
            except:
                await db.rollback()
                raise


# Replace the JSON-based manager with the SQLite-based one
machine_state = SQLiteMachineStateManager()


async def handle_spot_request(
    ec2, launch_specification, region, zone, instance_status, max_retries=3
):
    """
    Handle spot instance request and track its status.

    Args:
        ec2: EC2 client
        launch_specification: Launch specification for the spot instance
        region: AWS region
        zone: Availability zone
        instance_status: InstanceStatus object to track the instance
        max_retries: Maximum number of retries for spot request

    Returns:
        Instance ID if successful, None otherwise
    """
    # We no longer save the initial state - only save instances with actual AWS IDs
    # This is critical to prevent accumulation of temporary IDs in MACHINES.json

    for attempt in range(max_retries):
        try:
            attempt_msg = f"Attempting spot request in {region}-{zone} (attempt {attempt + 1}/{max_retries})"
            logger.debug(attempt_msg)
            await log_operation_async(attempt_msg, "info", region)

            # Add info about instance type being requested
            instance_type = launch_specification.get("InstanceType", "unknown")
            await log_operation_async(
                f"Requesting spot instance type: {instance_type}", "info", region
            )

            try:
                await log_operation_async(
                    "Sending spot request to AWS with one-time request type",
                    "info",
                    region,
                )
                response = await asyncio.to_thread(
                    ec2.request_spot_instances,
                    InstanceCount=1,
                    Type="one-time",
                    InstanceInterruptionBehavior="terminate",
                    LaunchSpecification=launch_specification,
                )
            except botocore.exceptions.ClientError as e:
                # Handle specific instance type errors
                if (
                    "InvalidParameterValue" in str(e)
                    and "instance type" in str(e).lower()
                ):
                    error_msg = f"Invalid instance type '{instance_type}' in {region}-{zone}: {str(e)}"
                    logger.error(error_msg)
                    await log_operation_async(error_msg, "error", region)

                    # Mark as bad instance type and update status
                    instance_status.status = "Bad Instance"
                    instance_status.detailed_status = (
                        f"Invalid instance type: {instance_type}"
                    )
                    instance_status.update_creation_state(
                        "failed",
                        {
                            "reason": "invalid_instance_type",
                            "message": str(e),
                            "instance_type": instance_type,
                        },
                    )
                    # We don't save failed instance types to MACHINES.json anymore
                    await update_all_statuses_async(instance_status)
                    return None
                # Rethrow other client errors to be handled by the outer exception handler
                raise

            request_id = response["SpotInstanceRequests"][0]["SpotInstanceRequestId"]
            logger.debug(f"Spot request {request_id} created in {region}-{zone}")
            await log_operation_async(
                f"Spot request {request_id} created successfully", "info", region
            )

            # Update instance status to reflect spot request creation
            instance_status.spot_request_id = request_id
            instance_status.detailed_status = "Waiting for spot request fulfillment"
            instance_status.update_creation_state(
                "requesting",
                {
                    "spot_request_id": request_id,
                    "attempt": attempt + 1,
                    "launch_specification": {
                        k: v
                        for k, v in launch_specification.items()
                        if k not in ["UserData"]  # Exclude UserData as it's too large
                    },
                },
            )
            # Only update the UI, don't save to MACHINES.json yet
            await update_all_statuses_async(instance_status)

            await log_operation_async(
                "Waiting for spot request fulfillment...", "info", region
            )

            async with asyncio.timeout(300):
                status_check_count = 0
                while True:
                    status = await get_spot_request_status(ec2, request_id)
                    logger.debug(f"Spot request {request_id} status: {status}")

                    # Only log every 3rd check to avoid flooding the operations log
                    if status_check_count % 3 == 0:
                        await log_operation_async(
                            f"Spot request status: {status['state']}", "info", region
                        )
                    status_check_count += 1

                    if status["state"] == "fulfilled":
                        fulfilled_msg = f"Spot request {request_id} fulfilled with instance {status['instance_id']}"
                        logger.info(fulfilled_msg)
                        await log_operation_async(fulfilled_msg, "info", region)

                        # Set the instance ID - this will change the ID property
                        instance_status.instance_id = status["instance_id"]

                        # Update the key in all_statuses to use the new instance ID
                        old_id = instance_status._temp_id
                        all_statuses[status["instance_id"]] = instance_status
                        if old_id in all_statuses:
                            del all_statuses[old_id]

                        # Update instance status for provisioning phase
                        instance_status.detailed_status = "Spot request fulfilled"
                        instance_status.update_creation_state(
                            "provisioning",
                            {
                                "instance_id": status["instance_id"],
                                "fulfillment_time": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            },
                        )

                        # Now that we have a valid AWS instance ID, save it to MACHINES.json
                        # The thread-safe dict will handle the write to disk
                        machine_state.set(instance_status.id, instance_status.to_dict())
                        await log_operation_async(
                            f"Saved instance {instance_status.id} to MACHINES.json"
                        )

                        # Make sure UI is updated with new ID
                        await update_all_statuses_async(instance_status)

                        await log_operation_async(
                            f"Instance {status['instance_id']} is being provisioned",
                            "info",
                            region,
                        )
                        return status["instance_id"]
                    elif status["state"] in ["capacity-not-available", "price-too-low"]:
                        error_msg = f"Spot capacity not available in {region}-{zone}: {status['message']}"
                        logger.warning(error_msg)
                        await log_operation_async(error_msg, "warning", region)

                        # Update instance status for failure
                        instance_status.status = "Failed"
                        instance_status.detailed_status = "No capacity available"
                        instance_status.update_creation_state(
                            "failed",
                            {"reason": status["state"], "message": status["message"]},
                        )

                        # We don't save failed capacity instances to MACHINES.json
                        # since they don't have AWS instance IDs
                        await log_operation_async(
                            "Abandoning spot request due to no capacity",
                            "warning",
                            region,
                        )

                        # Update UI then return to abandon this attempt
                        await update_all_statuses_async(instance_status)
                        return None
                    elif status["state"] in ["failed", "cancelled", "closed"]:
                        if attempt < max_retries - 1:
                            retry_msg = f"Spot request {request_id} {status['state']}, retrying..."
                            logger.warning(retry_msg)
                            await log_operation_async(retry_msg, "warning", region)

                            # Update status for retry
                            instance_status.detailed_status = (
                                f"Request {status['state']}, retrying..."
                            )
                            await update_all_statuses_async(instance_status)

                            await asyncio.sleep(5 * (attempt + 1))
                            break

                        error_msg = f"Spot request {request_id} failed after all retries: {status['message']}"
                        logger.error(error_msg)
                        await log_operation_async(error_msg, "error", region)

                        # Update instance status for failure
                        instance_status.status = "Failed"
                        instance_status.detailed_status = (
                            f"Request failed: {status['state']}"
                        )
                        instance_status.update_creation_state(
                            "failed",
                            {
                                "reason": status["state"],
                                "message": status["message"],
                                "final_attempt": True,
                            },
                        )
                        # We don't save to MACHINES.json for failed instances anymore
                        await update_all_statuses_async(instance_status)
                        return None

                    # Update status periodically during waiting
                    if status_check_count % 5 == 0:
                        instance_status.detailed_status = (
                            f"Waiting for request: {status['state']}"
                        )
                        await update_all_statuses_async(instance_status)
                        # We don't save intermediate state to MACHINES.json anymore
                        # Just log a status update for visibility every 15 checks
                        if status_check_count % 15 == 0:
                            await log_operation_async(
                                f"Still waiting for spot request {request_id}: {status['state']}",
                                "info",
                                region,
                            )

                    await asyncio.sleep(5)

        except asyncio.TimeoutError:
            timeout_msg = f"Timeout waiting for spot request in {region}-{zone}"
            logger.warning(timeout_msg)
            await log_operation_async(timeout_msg, "warning", region)

            # Update instance status for timeout
            instance_status.status = "Timeout"
            instance_status.detailed_status = "Request timed out"
            instance_status.update_creation_state(
                "failed",
                {
                    "reason": "timeout",
                    "message": f"Request timed out after {300} seconds",
                },
            )
            # We don't save timeout instances to MACHINES.json anymore
            await update_all_statuses_async(instance_status)
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                error_msg = f"Error in spot request for {region}-{zone}, retrying: {e}"
                logger.warning(error_msg)
                await log_operation_async(error_msg, "warning", region)

                # Update status for retry
                instance_status.detailed_status = f"Error, retrying: {str(e)[:50]}"
                await update_all_statuses_async(instance_status)

                await asyncio.sleep(5 * (attempt + 1))
                continue

            error_msg = f"Error requesting spot instance in {region}-{zone}: {str(e)}"
            logger.exception(error_msg)
            await log_operation_async(error_msg, "error", region)

            # Update instance status for error
            instance_status.status = "Error"
            instance_status.detailed_status = f"Request error: {str(e)[:50]}"
            instance_status.update_creation_state(
                "failed", {"reason": "error", "message": str(e), "final_attempt": True}
            )
            # We don't save error instances to MACHINES.json anymore
            await update_all_statuses_async(instance_status)
            return None
    return None


async def get_spot_request_status(ec2, request_id):
    try:
        response = await asyncio.to_thread(
            ec2.describe_spot_instance_requests, SpotInstanceRequestIds=[request_id]
        )
        request = response["SpotInstanceRequests"][0]
        return {
            "state": request["Status"]["Code"],
            "message": request["Status"].get("Message", ""),
            "instance_id": request.get("InstanceId"),
        }
    except Exception as e:
        logger.error(f"Error getting spot request status: {e}")
        return {"state": "failed", "message": str(e), "instance_id": None}


def print_machines_table():
    """Print a simple text table of machine information."""
    machines = machine_state.get_all()
    if not machines:
        print("No machines found in database")
        return

    # Define column widths
    col_widths = {
        "instance_id": 20,
        "region": 15,
        "vpc_id": 22,  # VPC IDs are 'vpc-' followed by 17 chars
        "status": 15,
        "public_ip": 16,
        "private_ip": 16,
    }

    # Print header
    header = (
        f"{'Instance ID':<{col_widths['instance_id']}} "
        f"{'Region':<{col_widths['region']}} "
        f"{'VPC ID':<{col_widths['vpc_id']}} "
        f"{'Status':<{col_widths['status']}} "
        f"{'Public IP':<{col_widths['public_ip']}} "
        f"{'Private IP':<{col_widths['private_ip']}}"
    )
    print("\n" + "=" * (sum(col_widths.values()) + 6))
    print(header)
    print("-" * (sum(col_widths.values()) + 6))

    # Print each machine
    for machine_id, machine in machines.items():
        instance_id = machine.get("instance_id", "N/A")
        region = machine.get("region", "N/A")
        vpc_id = machine.get("vpc_id", "N/A")
        status = machine.get("status", "N/A")
        public_ip = machine.get("public_ip", "N/A")
        private_ip = machine.get("private_ip", "N/A")

        row = (
            f"{instance_id:<{col_widths['instance_id']}} "
            f"{region:<{col_widths['region']}} "
            f"{vpc_id:<{col_widths['vpc_id']}} "
            f"{status:<{col_widths['status']}} "
            f"{public_ip:<{col_widths['public_ip']}} "
            f"{private_ip:<{col_widths['private_ip']}}"
        )
        print(row)

    print("=" * (sum(col_widths.values()) + 6) + "\n")


def check_aws_sso_token() -> bool:
    """Check if AWS SSO token is valid."""
    try:
        logger.info("Checking AWS SSO token")
        logger.debug("Inside of check_aws_sso_token")
        result = boto3.client("sts").get_caller_identity()
        logger.debug(f"Result of get_caller_identity: {result}")
        logger.info(
            f"Successfully authenticated as {result.get('Arn', 'unknown user')}"
        )
        return True
    except Exception as e:
        logger.error(f"Error checking AWS SSO token: {str(e)}")
        if hasattr(e, "response"):
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            if error_code in ["ExpiredToken", "InvalidClientTokenId"]:
                console.print("\n[bold red]Authentication Error[/bold red]")
                console.print(
                    "[yellow]AWS SSO token has expired. Please follow these steps:[/yellow]"
                )
                console.print("1. Run: [bold]aws sso login[/bold]")
                console.print("2. Wait for authentication to complete in your browser")
                console.print("3. Try running this script again\n")
                logger.error(f"AWS SSO token expired: {error_msg}")
            else:
                console.print("\n[bold red]AWS Authentication Error[/bold red]")
                console.print(f"[yellow]Error: {error_msg}[/yellow]")
                console.print("Please check your AWS credentials and try again.\n")
                logger.error(f"AWS authentication error: {error_msg}")
        else:
            console.print("\n[bold red]AWS Authentication Error[/bold red]")
            console.print(f"[yellow]Error: {str(e)}[/yellow]")
            console.print("Please check your AWS configuration and try again.\n")
            logger.error(f"AWS authentication error: {str(e)}")
        return False


def check_ssh_key() -> bool:
    """Check if SSH key exists and has proper permissions."""
    private_ssh_key_path = config.get("private_ssh_key_path")
    public_ssh_key_path = config.get("public_ssh_key_path")

    logger.debug(f"Checking private SSH key at: {private_ssh_key_path}")
    logger.debug(f"Checking public SSH key at: {public_ssh_key_path}")

    if not private_ssh_key_path or not public_ssh_key_path:
        error_msg = "Both private_ssh_key_path and public_ssh_key_path must be specified in config.yaml"
        logger.error(error_msg)
        console.print(f"\n[bold red]ERROR:[/bold red] {error_msg}")
        return False

    # Expand paths
    private_ssh_key_path = os.path.expanduser(private_ssh_key_path)
    public_ssh_key_path = os.path.expanduser(public_ssh_key_path)

    # Check file permissions on private key
    try:
        mode = os.stat(private_ssh_key_path).st_mode
        if (mode & 0o077) != 0:
            error_msg = f"Private key file {private_ssh_key_path} has too open permissions. Please run: chmod 600 {private_ssh_key_path}"
            logger.error(error_msg)
            console.print(f"\n[bold red]ERROR:[/bold red] {error_msg}")
            return False
        return True
    except Exception as e:
        error_msg = f"Error checking private key permissions: {str(e)}"
        logger.error(error_msg)
        console.print(f"\n[bold red]ERROR:[/bold red] {error_msg}")
        return False


async def main():
    global table_update_running
    table_update_running = False

    # Check AWS SSO token first
    if not check_aws_sso_token():
        return 1

    logger.debug("Starting main execution")
    parser = argparse.ArgumentParser(
        description="Manage spot instances across multiple AWS regions."
    )
    parser.add_argument(
        "--action",
        choices=[
            "create",
            "destroy",
            "list",
            "print-database",
        ],
        help="Action to perform",
        default="list",
    )
    parser.add_argument(
        "--format", choices=["default", "json"], default="default", help="Output format"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite database if it exists"
    )
    args = parser.parse_args()

    try:
        # Log the action being performed at INFO level for better visibility
        action_msg = f"Starting {args.action} operation..."
        logger.info(action_msg)
        log_operation(action_msg)

        # Load existing machine state
        log_operation("Loading machine state...")
        machines = await machine_state.load()

        if args.action == "print-database":
            print_machines_table()
            return 0

        # For 'create' action, check if database exists and would be overwritten
        if args.action == "create" and not args.overwrite:
            can_proceed = await machine_state.check_existing_file(
                overwrite=args.overwrite
            )
            if not can_proceed:
                logger.error(
                    "Cannot proceed with create operation - database already contains instances"
                )
                log_operation(
                    "Cannot proceed without --overwrite flag when database contains instances",
                    "error",
                )
                return 1

        # Report valid AWS instances
        valid_count = machine_state.count()
        print(f"Loaded {valid_count} valid AWS instances from database")
        log_operation(f"Found {valid_count} valid AWS instances in database")

        with Live(console=console, refresh_per_second=4, screen=True) as live:
            update_task = asyncio.create_task(update_table(live))

            try:
                if args.action == "list":
                    log_operation("Starting 'list' action")
                    await list_spot_instances()
                    # Ensure table is visible
                    await update_table_now()
                    await asyncio.sleep(1)
                    log_operation("List action completed successfully")
                elif args.action == "create":
                    log_operation("Starting 'create' action")
                    await create_spot_instances()
                    # Ensure table is visible
                    await update_table_now()
                    await asyncio.sleep(1)
                    log_operation("Create action completed successfully")
                elif args.action == "destroy":
                    log_operation("Starting 'destroy' action")
                    await destroy_instances()
                    log_operation("Destroy action completed successfully")

                logger.debug("Action %s completed successfully", args.action)
                logger.debug("Main execution completed successfully")
                logger.info("Operation completed successfully")

                # Give time for final table update to be visible
                if args.action in ["list", "create"]:
                    await asyncio.sleep(2)

            finally:
                # Stop the table update task
                table_update_event.set()
                await update_task

    except Exception as e:
        logger.exception("Error in main execution")
        log_operation(f"Operation failed: {str(e)}", "error")
        return 1
    finally:
        # Cleanup phase
        logger.debug("Cleaning up and shutting down")
        logger.info("Cleaning up...")

        if args.action in ["list", "create"]:
            logger.info(f"Completed {args.action} operation successfully")

        print_machines_table()

        logger.debug("Script completed successfully")

    return 0


async def update_table_now():
    """Force an immediate table update."""
    # Update all statuses to trigger a UI refresh
    for status in all_statuses.values():
        await update_all_statuses_async(status)
    await asyncio.sleep(0.1)  # Small delay to ensure update is visible


if __name__ == "__main__":
    try:
        logger.info("Starting deploy_spot.py")

        # Check AWS SSO token before anything else
        if not check_aws_sso_token():
            logger.error("Script exiting due to AWS authentication failure")
            sys.exit(1)

        # Check SSH key before proceeding
        if not check_ssh_key():
            logger.error("Script exiting due to SSH key issues")
            sys.exit(1)

        asyncio.run(main())
        logger.debug("Script completed successfully")
    except KeyboardInterrupt:
        logger.info("Script was manually interrupted by user (Ctrl+C)")
        console.print("\n[yellow]Operation cancelled by user (Ctrl+C)[/yellow]")
    except Exception as e:
        logger.exception("Script failed with unhandled exception")
        console.print(
            "\n[bold red]ERROR:[/bold red] Operation failed unexpectedly.",
            f"Error: {str(e)}",
            "\nSee debug_deploy_spot.log for details.",
        )
        sys.exit(1)
