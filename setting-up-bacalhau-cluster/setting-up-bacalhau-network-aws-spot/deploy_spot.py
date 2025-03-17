import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
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
from util.scripts_provider import ScriptsProvider

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
events_to_progress_lock = asyncio.Lock()  # Lock for thread-safe updates to events_to_progress

# List to store operations logs
operations_logs = []
operations_logs_lock = asyncio.Lock()  # Lock for thread-safe updates to operations logs
MAX_OPERATIONS_LOGS = 20  # Maximum number of operations logs to keep


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
    table.add_column("Region", width=20, style="cyan", no_wrap=True)
    table.add_column("Zone", width=20, style="cyan", no_wrap=True)
    table.add_column("Status", width=20, style="yellow", no_wrap=True)
    table.add_column(
        "Elapsed", width=20, justify="right", style="magenta", no_wrap=True
    )
    table.add_column("Instance ID", width=20, style="blue", no_wrap=True)
    table.add_column("Public IP", width=20, style="blue", no_wrap=True)
    table.add_column("Private IP", width=20, style="blue", no_wrap=True)

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
        if (not status.public_ip 
            and status.instance_id 
            and status.status not in FAILED_STATUSES
            and status.status != "Terminated"):
            public_ip_display = "[yellow]Waiting...[/yellow]"
        elif status.status in FAILED_STATUSES:
            public_ip_display = "[red]N/A[/red]"

        # Display "Waiting..." in the private IP column for instances that exist but have no private IP yet
        # Don't show "Waiting..." for failed or terminated instances
        private_ip_display = status.private_ip
        if (not status.private_ip 
            and status.instance_id 
            and status.status not in FAILED_STATUSES
            and status.status != "Terminated"):
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
                logger.debug(f"UI update: ops={ops_update_needed}, table={table_update_needed}")
                
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

    log_operation(f"Starting instance creation in region", "info", region)
    ec2 = get_ec2_client(region)
    region_cfg = config.get_region_config(region)
    log_operation(f"Connected to AWS EC2 API", "info", region)

    try:
        # Create cloud-init script
        log_operation(f"Generating startup script", "info", region)
        user_data = scripts_provider.create_cloud_init_script()
        if not user_data:
            error_msg = "User data is empty. Stopping creation."
            logger.error(error_msg)
            log_operation(error_msg, "error", region)
            return [], {}

        encoded_user_data = base64.b64encode(user_data.encode()).decode()
        log_operation(f"Startup script generated successfully", "info", region)

        # Create VPC and networking resources
        log_operation(f"Creating/checking VPC", "info", region)
        vpc_id = await create_vpc_if_not_exists(ec2)
        log_operation(f"VPC ready: {vpc_id}", "info", region)

        log_operation(f"Setting up internet gateway", "info", region)
        igw_id = await create_internet_gateway(ec2, vpc_id)
        log_operation(f"Internet gateway ready: {igw_id}", "info", region)

        log_operation(f"Creating route table", "info", region)
        route_table_id = await create_route_table(ec2, vpc_id, igw_id)
        log_operation(f"Route table ready: {route_table_id}", "info", region)

        log_operation(f"Setting up security group", "info", region)
        security_group_id = await create_security_group_if_not_exists(ec2, vpc_id)
        log_operation(f"Security group ready: {security_group_id}", "info", region)

        instance_ids = []
        log_operation(f"Getting available zones", "info", region)
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

            log_operation(f"Associating route table with subnet", "info", region)
            try:
                await associate_route_table(ec2, route_table_id, subnet_id)
                log_operation(
                    f"Route table associated successfully", "info", region
                )
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
                    already_msg = (
                        f"Route table already associated in {region}-{zone}"
                    )
                    logger.info(already_msg)
                    log_operation(already_msg, "info", region)
                else:
                    error_msg = f"Error associating route table in {region}-{zone}: {str(e)}"
                    logger.warning(error_msg)
                    log_operation(error_msg, "warning", region)

            thisInstanceStatusObject = InstanceStatus(region, zone, i)
            thisInstanceStatusObject.vpc_id = vpc_id  # Store VPC ID early so it's available for cleanup if needed
            
            # Add to global tracking with proper thread safety - this updates the UI but doesn't save to MACHINES.json
            await update_all_statuses_async(thisInstanceStatusObject)
            
            # IMPORTANT: We're not saving anything to MACHINES.json at this stage.
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

            # Add KeyName if specified in config
            pem_path = config.get("pem_path")
            if pem_path:
                # Extract key name from path (without .pem extension)
                key_name = os.path.splitext(os.path.basename(pem_path))[0]
                try:
                    # Check if key pair exists in AWS
                    key_pairs = await asyncio.to_thread(ec2.describe_key_pairs)
                    key_exists = any(
                        kp["KeyName"] == key_name
                        for kp in key_pairs.get("KeyPairs", [])
                    )

                    if key_exists:
                        launch_specification["KeyName"] = key_name
                        logger.info(f"Using SSH key pair: {key_name}")
                    else:
                        logger.warning(
                            f"SSH key pair {key_name} not found in AWS. Instance will be created without SSH access."
                        )
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error checking SSH key pair: {e}")

            thisInstanceStatusObject.status = "Requesting"
            thisInstanceStatusObject.detailed_status = "Sending spot request"
            await update_all_statuses_async(thisInstanceStatusObject)

            instance_id = await handle_spot_request(
                ec2, launch_specification, region, zone, thisInstanceStatusObject
            )

            if instance_id is None:
                # Spot instance request failed - mark as failed and continue
                thisInstanceStatusObject.status = "Failed"
                thisInstanceStatusObject.detailed_status = (
                    "No spot capacity available"
                )
                await update_all_statuses_async(thisInstanceStatusObject)
                
                # For failed instances, we don't save to MACHINES.json 
                # since they don't have AWS instance IDs
                await log_operation_async(f"Instance request failed in {region}-{zone}", "warning", region)
                
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
                thisInstanceStatusObject.public_ip = instance.get(
                    "PublicIpAddress", ""
                )
                thisInstanceStatusObject.private_ip = instance.get(
                    "PrivateIpAddress", ""
                )
                thisInstanceStatusObject.vpc_id = vpc_id
            
            # Save to MACHINES.json using the AWS instance ID as the key
            # This ensures each machine has a proper AWS identifier in the state file
            machine_state.set(thisInstanceStatusObject.id, thisInstanceStatusObject.to_dict())
            await log_operation_async(f"Saved instance {instance_id} to MACHINES.json")

            # Mark the instance as done when it's been created successfully
            thisInstanceStatusObject.status = "Done"
            thisInstanceStatusObject.detailed_status = "Instance created successfully"
            # Force UI update
            await update_all_statuses_async(thisInstanceStatusObject)
            
            # Update the status in MACHINES.json
            machine_state.set(thisInstanceStatusObject.id, thisInstanceStatusObject.to_dict())

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
            ec2.describe_vpcs, Filters=[{"Name": "tag:Name", "Values": ["SpotInstanceVPC"]}]
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
                ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsHostnames={"Value": True}
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
            await log_operation_async(f"Attempting CIDR block {cidrBlock} in zone {zone}")
            subnet = await asyncio.to_thread(
                ec2.create_subnet,
                VpcId=vpc_id,
                CidrBlock=cidrBlock,
                AvailabilityZone=zone,
            )
            subnet_id = subnet["Subnet"]["SubnetId"]
            await log_operation_async(f"Created subnet {subnet_id} in zone {zone} with CIDR {cidrBlock}")
            return subnet_id
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "InvalidSubnet.Conflict":
                # If this CIDR is in use, try the next one
                await log_operation_async(f"CIDR {cidrBlock} already in use, trying next one", "info")
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
    await log_operation_async(f"Checking for existing Internet Gateway attached to VPC {vpc_id}")
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
        await log_operation_async(f"Attaching Internet Gateway {igw_id} to VPC {vpc_id}")
        await asyncio.to_thread(
            ec2.attach_internet_gateway, InternetGatewayId=igw_id, VpcId=vpc_id
        )
        await log_operation_async(f"Internet Gateway {igw_id} attached successfully")
    except botocore.exceptions.ClientError as e:
        await log_operation_async(f"Error attaching Internet Gateway: {str(e)}", "warning")
        # If an error occurs during attachment, delete the created IGW
        await log_operation_async(f"Cleaning up Internet Gateway {igw_id}")
        await asyncio.to_thread(ec2.delete_internet_gateway, InternetGatewayId=igw_id)
        
        # Re-check for existing IGW in case one was attached concurrently
        await log_operation_async("Checking if an Internet Gateway was attached concurrently")
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
            await log_operation_async("No Internet Gateway found and failed to create one", "error")
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
                    await log_operation_async(f"Adding internet route to existing route table {route_table_id}")
                    await asyncio.to_thread(
                        ec2.create_route,
                        RouteTableId=route_table_id,
                        DestinationCidrBlock="0.0.0.0/0",
                        GatewayId=igw_id,
                    )
                    await log_operation_async(f"Added internet route (0.0.0.0/0) via {igw_id}")
                else:
                    await log_operation_async(f"Internet route already exists in route table")
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
    await log_operation_async(f"Internet route added successfully")

    # Associate the route table with the VPC (make it the main route table)
    await log_operation_async(f"Associating route table with VPC (making it main)")
    await asyncio.to_thread(
        ec2.associate_route_table,
        RouteTableId=route_table_id,
        VpcId=vpc_id,
    )
    await log_operation_async(f"Route table association complete")

    return route_table_id


async def associate_route_table(ec2, route_table_id, subnet_id):
    await log_operation_async(f"Associating route table {route_table_id} with subnet {subnet_id}")
    try:
        await asyncio.to_thread(
            ec2.associate_route_table, RouteTableId=route_table_id, SubnetId=subnet_id
        )
        await log_operation_async(f"Route table association completed successfully")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
            await log_operation_async(f"Route table already associated with subnet", "info")
            logger.debug(
                f"Route table already associated in {route_table_id}-{subnet_id}: {str(e)}"
            )
        else:
            await log_operation_async(f"Error associating route table: {str(e)}", "error")
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
        
        await log_operation_async("Adding security group ingress rules (SSH port 22, Bacalhau ports 1234-1235)")
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
            log_operation(f"No instances to create", "info", region)
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
        log_operation(f"Launching creation tasks in parallel across regions")
        tasks = [create_in_region(region) for region in AWS_REGIONS]
        results = await asyncio.gather(*tasks)
        log_operation(f"All region creation tasks completed")
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
        await log_operation_async(f"Detected {len(failed_instances)} failed instance requests", "warning")
        # Log details about the failed instances
        for status_id in failed_instances:
            status = all_statuses[status_id]
            await log_operation_async(
                f"Instance failed in {status.region}-{status.zone}: {status.detailed_status}",
                "warning",
                status.region
            )
    
    # Count valid instances that are waiting for IPs
    waiting_instances = [
        status
        for status in all_statuses.values()
        if status.instance_id and not status.public_ip and status.status not in FAILED_STATUSES
    ]
    
    if waiting_instances:
        logger.debug("Waiting for public IP addresses...")
        await log_operation_async(f"Waiting for public IP addresses to be assigned to {len(waiting_instances)} instances...")
        await wait_for_public_ips()
        await log_operation_async("IP address assignment complete")
    else:
        await log_operation_async("No instances waiting for IP addresses")
    
    # Before logging a summary, ensure all instances with IPs are marked as Done
    # and saved to MACHINES.json with their final state
    await log_operation_async("Final pass - updating all completed instances to 'Done' status")
    completion_count = 0
    
    # Update all instances that have IPs to Done status
    for status in all_statuses.values():
        if status.public_ip and status.private_ip and status.instance_id:
            # Mark as done if not already
            if status.status != "Done":
                status.status = "Done" 
                status.detailed_status = f"Ready - {datetime.now().strftime('%H:%M:%S')}"
                await update_all_statuses_async(status)
                
            # Save to MACHINES.json via the thread-safe dictionary
            machine_state.set(status.id, status.to_dict())
            completion_count += 1
    
    if completion_count > 0:
        await log_operation_async(f"Updated {completion_count} completed instances to final state")
            
    # Get a summary of the machine state
    valid_machines = machine_state.get_all()
    valid_count = len(valid_machines)
    
    # Count failed instances in all_statuses for accurate reporting
    FAILED_STATUSES = ["Failed", "Bad Instance", "Error", "Timeout"]
    failed_instances = [
        status for status in all_statuses.values()
        if status.status in FAILED_STATUSES
    ]
    
    # Create a detailed summary
    await log_operation_async(
        f"MACHINES.json summary: {valid_count} instances with AWS IDs " +
        f"({len(failed_instances)} failed requests during creation)"
    )
    
    if valid_count == 0:
        if len(failed_instances) > 0:
            # If all instances failed, provide a clear error message
            await log_operation_async(
                f"WARNING: All {len(failed_instances)} instance requests failed - check logs for details", 
                "warning"
            )
            # Summarize failures by region
            failures_by_region = {}
            for status in failed_instances:
                if status.region not in failures_by_region:
                    failures_by_region[status.region] = []
                failures_by_region[status.region].append(f"{status.id} ({status.detailed_status})")
            
            for region, failures in failures_by_region.items():
                await log_operation_async(
                    f"Region {region} failures: {', '.join(failures)}",
                    "warning"
                )
        else:
            await log_operation_async("WARNING: No AWS instance IDs found in MACHINES.json", "warning")
            
        # Dump the all_statuses to help diagnose the issue
        status_summary = ", ".join([f"{s.id}:{s.status}" for s in all_statuses.values()])
        logger.debug(f"Current status objects: {status_summary}")
    else:
        if len(failed_instances) > 0:
            # Some instances succeeded but some failed
            await log_operation_async(
                f"Successfully provisioned {valid_count} instances " +
                f"({len(failed_instances)} requests failed, most likely due to capacity issues)",
                "info"
            )
        else:
            # All instances succeeded
            await log_operation_async(f"Successfully provisioned {valid_count} instances")
    
    logger.debug("Finished creating spot instances")
    await log_operation_async("Finished creating spot instances")
    return


async def wait_for_public_ips():
    global all_statuses
    timeout = 300  # 5 minutes timeout
    start_time = time.time()

    NO_IP_STATUS = "-----"
    FAILED_STATUSES = ["Failed", "Bad Instance", "Error", "Timeout"]
    await log_operation_async("Checking for public IP addresses on all instances")

    # Count how many instances still need IP addresses
    instances_without_ip = len(
        [
            status
            for status in all_statuses.values()
            if not status.public_ip 
            and status.status != NO_IP_STATUS
            and status.status not in FAILED_STATUSES
        ]
    )
    await log_operation_async(f"Waiting for IP addresses for {instances_without_ip} instances")

    # Identify failed instances that we won't wait for
    failed_instances = [
        status.id
        for status in all_statuses.values()
        if status.status in FAILED_STATUSES
    ]
    if failed_instances:
        await log_operation_async(f"Ignoring {len(failed_instances)} failed instances: {', '.join(failed_instances)}", "warning")

    check_count = 0
    try:
        while True:
            # Check if all instances either: have IPs, are marked as NO_IP_STATUS, or are in a failed state
            all_have_ips = all(
                status.public_ip or status.status == NO_IP_STATUS or status.status in FAILED_STATUSES
                for status in all_statuses.values()
            )

            if all_have_ips:
                await log_operation_async("All non-failed instances have IP addresses assigned")
                # Mark all instances with IPs as Done
                for status in all_statuses.values():
                    if status.public_ip and status.private_ip and status.status != "Done":
                        # Update final status to Done with a timestamp
                        status.status = "Done"
                        status.detailed_status = f"Ready - {datetime.now().strftime('%H:%M:%S')}"
                        # Update UI
                        await update_all_statuses_async(status)
                        # Update MACHINES.json to record final state
                        if status.instance_id:
                            machine_state.set(status.id, status.to_dict())
                                
                # Now break out of the loop since all valid instances have IPs
                break

            if time.time() - start_time > timeout:
                await log_operation_async("Timed out waiting for IP addresses", "warning")
                # Mark all instances with IPs as Done, even on timeout
                for status in all_statuses.values():
                    if status.public_ip and status.private_ip and status.status != "Done":
                        # Update final status to Done with a timestamp
                        status.status = "Done"
                        status.detailed_status = f"Ready - {datetime.now().strftime('%H:%M:%S')}"
                        # Update UI
                        await update_all_statuses_async(status)
                        # Update MACHINES.json to record final state
                        if status.instance_id:
                            machine_state.set(status.id, status.to_dict())
                
                # Identify any instances still waiting for IPs
                still_waiting = [
                    f"{status.id} ({status.region})" 
                    for status in all_statuses.values()
                    if not status.public_ip 
                    and status.status != NO_IP_STATUS
                    and status.status not in FAILED_STATUSES
                ]
                
                if still_waiting:
                    await log_operation_async(f"Giving up on waiting for IPs for instances: {', '.join(still_waiting)}", "warning")
                
                break

            # Only log status occasionally to avoid flooding
            if check_count % 6 == 0:  # Every ~30 seconds
                instances_without_ip = len(
                    [
                        status
                        for status in all_statuses.values()
                        if not status.public_ip 
                        and status.status != NO_IP_STATUS
                        and status.status not in FAILED_STATUSES
                    ]
                )
                elapsed = int(time.time() - start_time)
                await log_operation_async(
                    f"Still waiting for {instances_without_ip} IP addresses... ({elapsed}s elapsed)"
                )

            check_count += 1

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
                if instance_ids:
                    try:
                        # Update detailed status to show we're checking IPs
                        for instance_id in instance_ids:
                            for status in all_statuses.values():
                                if status.instance_id == instance_id:
                                    # Make the status message clear that we're actively checking for IPs
                                    if not status.public_ip:
                                        status.detailed_status = "🔄 Checking for public IP address..."
                                    elif not status.private_ip:
                                        status.detailed_status = "🔄 Checking for private IP address..."
                                    else:
                                        status.detailed_status = "🔄 Verifying IP addresses..."
                                    # Force update to UI
                                    await update_all_statuses_async(status)

                        response = await asyncio.to_thread(
                            ec2.describe_instances, InstanceIds=instance_ids
                        )
                        for reservation in response["Reservations"]:
                            for instance in reservation["Instances"]:
                                instance_id = instance["InstanceId"]
                                public_ip = instance.get("PublicIpAddress", "")
                                private_ip = instance.get("PrivateIpAddress", "")

                                # Update status for this instance
                                for status in all_statuses.values():
                                    if status.instance_id == instance_id:
                                        # Track if we need to update the status
                                        status_changed = False
                                        
                                        # Update public IP if available
                                        if public_ip and not status.public_ip:
                                            status.public_ip = public_ip
                                            
                                            # Update status based on IPs
                                            if private_ip or status.private_ip:
                                                # If we have both IPs, mark as done
                                                status.status = "Done"
                                                status.detailed_status = "All IP addresses assigned"
                                            else:
                                                status.detailed_status = "Public IP assigned, waiting for private IP..."
                                                
                                            status_changed = True
                                            await log_operation_async(
                                                f"Instance {instance_id} got public IP: {public_ip}",
                                                "info",
                                                region,
                                            )

                                        # Update private IP if available and not already set
                                        if private_ip and not status.private_ip:
                                            status.private_ip = private_ip
                                            
                                            # Update status based on IPs
                                            if status.public_ip:
                                                # If we have both IPs, mark as done
                                                status.status = "Done"
                                                status.detailed_status = "All IP addresses assigned"
                                            else:
                                                status.detailed_status = "Private IP assigned, waiting for public IP..."
                                                
                                            status_changed = True
                                            await log_operation_async(
                                                f"Instance {instance_id} got private IP: {private_ip}",
                                                "info",
                                                region,
                                            )

                                        # If we're still waiting for public IP, update status
                                        if not status.public_ip:
                                            status.detailed_status = (
                                                "Waiting for public IP address..."
                                            )
                                            status_changed = True
                                        
                                        # If we're still waiting for private IP but have public IP
                                        elif not status.private_ip:
                                            status.detailed_status = (
                                                "Waiting for private IP address..."
                                            )
                                            status_changed = True
                                            
                                        # If status changed, update the UI
                                        if status_changed:
                                            await update_all_statuses_async(status)
                    except Exception as e:
                        logger.warning(
                            f"Error checking IPs in region {region}: {str(e)}"
                        )
                        await log_operation_async(
                            f"Error checking IPs: {str(e)}", "warning", region
                        )

            # Use a shorter sleep time and check for cancellation
            # Break into smaller sleeps to be more responsive to cancellation
            for _ in range(5):
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("IP address check was cancelled")
        await log_operation_async("IP address check was cancelled", "warning")
        # Let the cancellation propagate
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
                async with machine_state.update() as current_machines:
                    current_machines.pop(instance_id, None)

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                # Instance no longer exists, remove from MACHINES.json
                async with machine_state.update() as current_machines:
                    current_machines.pop(instance_id, None)
            else:
                logger.error(f"Error checking instance {instance_id}: {str(e)}")

    logger.debug("Finished listing spot instances")
    return all_statuses


async def destroy_instances():
    global task_name, task_total, events_to_progress
    task_name = "Terminating Spot Instances"
    events_to_progress = []

    logger.info("Loading instance information from MACHINES.json...")
    log_operation("Loading instance information from MACHINES.json...")

    # Check if MACHINES.json exists
    if not os.path.exists("MACHINES.json"):
        msg = "MACHINES.json not found. No instances to terminate."
        logger.info(msg)
        log_operation(msg, "warning")
        return

    machines = await machine_state.load()

    if not machines:
        msg = "MACHINES.json exists but contains no instances to terminate."
        logger.info(msg)
        log_operation(msg, "warning")
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
                    log_operation(
                        f"Terminate command sent successfully", "info", region
                    )

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
                                f"Checking termination status...", "info", region
                            )
                            await asyncio.to_thread(
                                waiter.wait,
                                InstanceIds=instance_ids,
                                WaiterConfig={"MaxAttempts": 1},
                            )
                            log_operation(
                                f"All instances terminated successfully", "info", region
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
                                    f"Termination taking too long, continuing...",
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

            # Remove terminated instances from MACHINES.json
            async with machine_state.update() as current_machines:
                # Find machine IDs associated with these instance IDs
                for machine_id in list(current_machines.keys()):
                    machine = current_machines[machine_id]
                    if machine.get("instance_id") in instance_ids:
                        log_operation(
                            f"Removing {machine_id} from state file", "info", region
                        )
                        current_machines.pop(machine_id, None)

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
            "public_ip": status.public_ip,
            "private_ip": status.private_ip,
            "vpc_id": status.vpc_id,
        }
        for status in all_statuses.values()
    }


class MachineStateManager:
    def __init__(self, filename="MACHINES.json"):
        self.filename = filename
        # Use a thread-safe dictionary (no locks needed)
        from threading import RLock
        self.machines = {}
        self._write_lock = RLock()  # Only used for file I/O operations
        self.overwrite_confirmed = False

    def _write_to_disk(self):
        """
        Write the current machines dictionary to disk immediately.
        This is called every time the dictionary is updated.
        """
        try:
            with self._write_lock:  # Thread-safe file writing
                # Filter out entries that don't have valid AWS instance IDs
                valid_machines = {
                    k: v for k, v in self.machines.items()
                    if isinstance(v, dict) and v.get("instance_id") and str(v.get("instance_id")).startswith("i-")
                }
                
                # Create parent directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(self.filename)), exist_ok=True)
                
                # Use atomic write pattern for reliability
                temp_file = f"{self.filename}.tmp"
                try:
                    with open(temp_file, "w") as f:
                        json.dump(valid_machines, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp_file, self.filename)
                    logger.debug(f"Wrote {len(valid_machines)} instances to {self.filename}")
                finally:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
        except Exception as e:
            logger.error(f"Error writing machine state to disk: {e}")

    async def check_existing_file(self, overwrite=False):
        """
        Check if MACHINES.json already exists and warn the user if it does.
        
        Args:
            overwrite: If True, allow overwriting existing file without warning.
            
        Returns:
            bool: True if it's safe to proceed, False if the user should be warned
        """
        if os.path.exists(self.filename) and not self.overwrite_confirmed and not overwrite:
            existing_count = 0
            try:
                with open(self.filename, "r") as f:
                    existing_data = json.load(f)
                    existing_count = len(existing_data)
            except:
                pass
                
            if existing_count > 0:
                await log_operation_async(
                    f"WARNING: {self.filename} already exists with {existing_count} instances.", 
                    "warning"
                )
                await log_operation_async(
                    "Use --overwrite flag to continue anyway, or --action destroy to delete existing instances first.",
                    "warning"
                )
                return False
        
        # Either the file doesn't exist, is empty, or overwrite is confirmed
        self.overwrite_confirmed = True
        return True

    def get(self, instance_id, default=None):
        """Get an instance by ID"""
        return self.machines.get(instance_id, default)

    def set(self, instance_id, data):
        """Set an instance and immediately write to disk"""
        # Only store instances with valid AWS IDs
        if not (isinstance(data, dict) and data.get("instance_id") and 
                str(data.get("instance_id")).startswith("i-")):
            return False
            
        self.machines[instance_id] = data
        # Write to disk immediately after every change
        self._write_to_disk()
        return True

    def delete(self, instance_id):
        """Delete an instance and immediately write to disk"""
        if instance_id in self.machines:
            del self.machines[instance_id]
            # Write to disk immediately after every change
            self._write_to_disk()
            return True
        return False
    
    def load(self):
        """Load machine state from disk"""
        if not os.path.exists(self.filename):
            return {}
            
        try:
            with open(self.filename, "r") as f:
                data = json.load(f)
                # Update our in-memory copy
                self.machines.clear()
                self.machines.update(data)
                return data
        except Exception as e:
            logger.error(f"Error loading machine state: {e}")
            # Create a backup if the file seems corrupted
            try:
                backup_name = f"{self.filename}.backup.{int(time.time())}"
                with open(self.filename, "r") as src, open(backup_name, "w") as dst:
                    dst.write(src.read())
                logger.warning(f"Created backup of {self.filename} at {backup_name}")
            except:
                pass
            return {}
    
    def get_all(self):
        """Get all valid machines"""
        # Return only machines with valid AWS instance IDs
        return {
            k: v for k, v in self.machines.items()
            if isinstance(v, dict) and v.get("instance_id") and str(v.get("instance_id")).startswith("i-")
        }
    
    def count(self):
        """Count valid machines"""
        return len(self.get_all())
    
    def clear(self):
        """Clear all machines and write to disk"""
        self.machines.clear()
        self._write_to_disk()
    
    def debug_state(self):
        """Print debug information about the current machine state"""
        valid_machines = self.get_all()
        aws_instance_ids = [m.get("instance_id") for m in valid_machines.values()]
        
        logger.debug(f"MACHINES.json has {len(valid_machines)} valid AWS instances")
        if valid_machines:
            logger.debug(f"Instance IDs: {aws_instance_ids}")
        
        return {
            "total": len(valid_machines),
            "aws_ids": len(valid_machines),
            "aws_id_list": aws_instance_ids,
            "machines": valid_machines
        }


machine_state = MachineStateManager()


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
            await log_operation_async(f"Requesting spot instance type: {instance_type}", "info", region)

            try:
                await log_operation_async(f"Sending spot request to AWS with one-time request type", "info", region)
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
            instance_status.detailed_status = f"Waiting for spot request fulfillment"
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

            await log_operation_async(f"Waiting for spot request fulfillment...", "info", region)

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
                        
                        # Update instance status for provisioning phase
                        instance_status.detailed_status = f"Spot request fulfilled"
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
                        await log_operation_async(f"Saved instance {instance_status.id} to MACHINES.json")
                            
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
                        instance_status.detailed_status = (
                            f"No capacity available"
                        )
                        instance_status.update_creation_state(
                            "failed",
                            {"reason": status["state"], "message": status["message"]},
                        )
                        
                        # We don't save failed capacity instances to MACHINES.json
                        # since they don't have AWS instance IDs
                        await log_operation_async(f"Abandoning spot request due to no capacity", "warning", region)
                        
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
                                region
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


async def main():
    global table_update_running
    table_update_running = False

    logger.debug("Starting main execution")
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
        "--overwrite", action="store_true", help="Overwrite MACHINES.json if it exists"
    )
    args = parser.parse_args()
    logger.debug(f"Parsed arguments: {args}")

    # Log the action being performed at INFO level for better visibility
    action_msg = f"Starting {args.action} operation..."
    logger.info(action_msg)
    log_operation(action_msg)

    # Load existing machine state
    log_operation(f"Loading machine state...")
    machines = machine_state.load()
    
    # For 'create' action, check if MACHINES.json exists and would be overwritten
    if args.action == "create" and not args.overwrite:
        can_proceed = await machine_state.check_existing_file(overwrite=args.overwrite)
        if not can_proceed:
            logger.error("Cannot proceed with create operation - MACHINES.json already exists")
            log_operation("Cannot proceed without --overwrite flag when MACHINES.json exists", "error")
            # Exit with error code
            return 1
    
    # Report valid AWS instances    
    valid_count = machine_state.count()
    logger.info(f"Loaded {valid_count} valid AWS instances from MACHINES.json")
    log_operation(f"Found {valid_count} valid AWS instances in state file")

    if machines:
        logger.debug("MACHINES.json contains the following instances:")
        for instance_id, machine in machines.items():
            logger.debug(
                f"  Instance {instance_id} in {machine['region']}-{machine['zone']}"
            )
    elif args.action == "destroy":
        msg = "MACHINES.json is empty. No instances to process."
        logger.info(msg)
        log_operation(msg, "warning")
        logger.info("Please run 'deploy_spot.py --action create' to create instances.")
        logger.info(
            "Or run 'delete_vpcs.py' if there are still resources that need to be cleaned up."
        )
        return

    async def perform_action():
        logger.debug(f"Performing action: {args.action}")
        try:
            if args.action == "create":
                log_operation(f"Starting 'create' action")
                await create_spot_instances()
                log_operation(f"Create action completed successfully")
            elif args.action == "list":
                log_operation(f"Starting 'list' action")
                await list_spot_instances()
                log_operation(f"List action completed successfully")
            elif args.action == "destroy":
                log_operation(f"Starting 'destroy' action")
                await destroy_instances()
                log_operation(f"Destroy action completed successfully")
            elif args.action == "delete_disconnected_aws_nodes":
                log_operation(f"Starting 'delete_disconnected_aws_nodes' action")
                await delete_disconnected_aws_nodes()
                log_operation(
                    f"Delete_disconnected_aws_nodes action completed successfully"
                )
            logger.debug(f"Action {args.action} completed successfully")
        except asyncio.CancelledError:
            cancel_msg = f"Action {args.action} was cancelled by user"
            logger.info(cancel_msg)
            log_operation(cancel_msg, "warning")
            raise
        except Exception as e:
            error_msg = f"Error performing action {args.action}: {str(e)}"
            logger.exception(error_msg)
            log_operation(error_msg, "error")
            raise

    if args.format == "json":
        logger.debug("Using JSON output format")
        try:
            # Create a fake console that only logs operations
            with Live(
                console=console, refresh_per_second=4, auto_refresh=True, screen=True
            ) as live:
                # Create an initial layout with just the operations panel
                ops_content = "[dim]Starting operation...[/dim]"
                layout = Layout(
                    Panel(
                        ops_content,
                        title="AWS Operations",
                        border_style="yellow",
                        padding=(1, 1),
                    )
                )
                live.update(layout)

                # Set up operations logging
                update_task = asyncio.create_task(update_table(live))

                # Run the action
                try:
                    await perform_action()
                    result = all_statuses_to_dict()
                    if not result and args.action != "destroy":
                        logger.warning(
                            "Operation completed but no instances were processed"
                        )
                        log_operation(
                            "Operation completed but no instances were processed",
                            "warning",
                        )

                    # Output is only sent to the operations panel, not to stdout
                    logger.debug(f"JSON result: {json.dumps(result, indent=2)}")
                    log_operation(
                        "Operation completed successfully. Results available in debug log."
                    )
                except Exception as e:
                    logger.error(f"Operation failed: {str(e)}")
                    log_operation(f"Operation failed: {str(e)}", "error")
                    raise
                finally:
                    # Clean up
                    table_update_event.set()
                    await update_task
        except Exception as e:
            # This should never print to console
            logger.error(f"Live display error: {str(e)}")
            raise
    else:
        logger.debug("Using default (live) output format")
        try:
            with Live(console=console, refresh_per_second=4, screen=True) as live:
                update_task = asyncio.create_task(update_table(live))
                try:
                    # Initial message to show the UI is working
                    log_operation(f"Initializing {args.action} operation...")
                    await perform_action()
                    await asyncio.sleep(1)
                    logger.debug("Main execution completed successfully")
                    log_operation("Operation completed successfully", "info")
                except asyncio.CancelledError:
                    logger.info("Operation was cancelled by user")
                    log_operation("Operation was cancelled by user", "warning")
                    raise
                except Exception as e:
                    error_msg = f"Operation failed: {str(e)}"
                    logger.exception("Error in main execution")
                    log_operation(error_msg, "error")
                    raise
                finally:
                    logger.debug("Cleaning up and shutting down")
                    log_operation("Cleaning up...", "info")
                    table_update_event.set()
                    await update_task
        except KeyboardInterrupt:
            # Don't log to console, only to file
            logger.info("Operation was manually interrupted")
            raise

    logger.info(f"Completed {args.action} operation successfully")


if __name__ == "__main__":
    try:
        logger.debug("Script starting")
        asyncio.run(main())
        logger.debug("Script completed successfully")
    except KeyboardInterrupt:
        logger.info("Script was manually interrupted by user (Ctrl+C)")
        # Don't print to console - all user feedback is in the Rich UI
    except Exception:
        logger.exception("Script failed with unhandled exception")
        # Only print error message if the Rich UI hasn't started yet
        console.print(
            "\n[bold red]ERROR:[/bold red] Operation failed unexpectedly.",
            "See debug_deploy_spot.log for details.",
        )
        raise
