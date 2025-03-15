import argparse
import asyncio
import base64  # Used in create_spot_instances_in_region which is imported elsewhere
import datetime
import hashlib
import json
import logging
import os
import signal
import sys
import time

# Truncate the debug.log file at the start of every run
if os.path.exists("debug.log"):
    with open("debug.log", "w") as f:
        f.truncate(0)

import boto3
import botocore
import yaml
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from util.config import Config
from util.scripts_provider import ScriptsProvider

# Tag to filter instances by
FILTER_TAG_NAME = "ManagedBy"
FILTER_TAG_VALUE = "SpotInstanceScript"

# Use dynamic console width based on terminal size
console = Console()

# Configure root logger to debug level
logging.basicConfig(level=logging.DEBUG)

# Create file handler for debug messages
file_handler = logging.FileHandler("debug.log")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)

# Create console handler for info messages
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

# Get the root logger and add handlers
root_logger = logging.getLogger()
root_logger.handlers = []  # Remove default handlers
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Set boto3 and botocore loggers to WARNING to reduce noise
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

config = Config("config.yaml")
scripts_provider = ScriptsProvider(config)

AWS_REGIONS = config.get_regions()
TOTAL_INSTANCES = config.get_total_instances()
global_node_count = 0
INSTANCES_PER_REGION = (
    TOTAL_INSTANCES // len(AWS_REGIONS)
    if TOTAL_INSTANCES != "auto"
    else TOTAL_INSTANCES
)  # Evenly distribute instances if set to 'auto' in config

MAX_NODES = (
    config.get_total_instances()
)  # Global limit for total nodes across all regions
current_dir = os.path.dirname(__file__)

SCRIPT_DIR = "instance/scripts"

all_statuses = {}  # Moved to global scope
global_node_count = 0
queried_zones = set()  # New set to track queried zones

table_update_running = False
table_update_event = asyncio.Event()

task_name = "TASK NAME"
task_total = 10000
task_count = 0
events_to_progress = []

shutdown_in_progress = False
shutdown_event = asyncio.Event()


async def check_aws_credentials():
    """Check if AWS credentials are valid and not expired"""
    try:
        # Suppress boto3 logging during credential check to avoid stack traces
        logging.getLogger("botocore").setLevel(logging.CRITICAL)
        logging.getLogger("boto3").setLevel(logging.CRITICAL)

        # Log that we're checking credentials
        logging.debug("Checking AWS credentials...")

        # Create a session with the default credentials
        session = boto3.Session()
        credentials = session.get_credentials()

        if credentials is None:
            logging.error("No AWS credentials found")
            return False, "No AWS credentials found. Please configure AWS credentials."

        # Log credential details (without exposing secrets)
        logging.debug(
            f"Found credentials with access key ID: {credentials.access_key[:4]}...{credentials.access_key[-4:]}"
        )

        # Check if credentials are expired
        if hasattr(credentials, "expiry_time") and credentials.expiry_time:
            expiry_time = credentials.expiry_time
            current_time = datetime.datetime.now()

            logging.debug(f"Credential expiry time: {expiry_time}")
            logging.debug(f"Current time: {current_time}")

            if expiry_time < current_time:
                logging.error("AWS credentials have expired")
                return (
                    False,
                    "AWS credentials have expired. Please refresh your credentials.",
                )

        # Try to use the credentials to make a simple API call
        try:
            # Use us-east-1 as a test region
            ec2 = session.client("ec2", region_name="us-east-1")
            logging.debug("Making test API call to verify credentials...")
            # Call describe_regions which should work with minimal permissions
            ec2.describe_regions(RegionNames=["us-east-1"])
            logging.debug("AWS credentials are valid")
            return True, "AWS credentials are valid"
        except Exception as e:
            logging.error(f"Error validating AWS credentials: {str(e)}")
            return False, f"Error validating AWS credentials: {str(e)}"
    except Exception as e:
        logging.error(f"Error checking AWS credentials: {str(e)}")
        return False, f"Error checking AWS credentials: {str(e)}"
    finally:
        # Restore normal logging levels
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("boto3").setLevel(logging.WARNING)


async def get_ec2_client(region):
    """Get an EC2 client for the specified region, checking credentials first"""
    # Check credentials before proceeding
    credentials_valid, error_message = await check_aws_credentials()
    if not credentials_valid:
        logging.error(f"Invalid or expired AWS credentials: {error_message}")
        raise Exception(f"Invalid or expired AWS credentials. {error_message}")

    # Create and return the EC2 client
    try:
        logging.debug(f"Creating EC2 client for region {region}")
        # Create the boto3 client directly - boto3 operations are thread-safe
        client = boto3.client("ec2", region_name=region)
        logging.debug(f"Successfully created EC2 client for region {region}")
        return client
    except Exception as e:
        logging.error(f"Error creating EC2 client for region {region}: {str(e)}")
        logging.exception("Detailed exception information:")
        raise


async def all_statuses_to_dict():
    """Convert all_statuses to a dictionary for JSON serialization"""
    result = {}
    for key, status in all_statuses.items():
        result[key] = {
            "instance_id": status.instance_id,
            "region": status.region,
            "az": status.az
            if hasattr(status, "az")
            else (status.zone if hasattr(status, "zone") else None),
            "status": status.status,
            "elapsed_time": status.elapsed_time,
            "ip": status.ip if hasattr(status, "ip") else None,
            "public_ip": status.public_ip if hasattr(status, "public_ip") else None,
            "private_ip": status.private_ip if hasattr(status, "private_ip") else None,
            "task_id": status.task_id if hasattr(status, "task_id") else None,
            "task_total": status.task_total if hasattr(status, "task_total") else None,
            "task_completed": status.task_completed
            if hasattr(status, "task_completed")
            else None,
        }
    return result


async def create_spot_instances(args):
    """Create spot instances in the specified regions and availability zones"""
    global task_name, task_total, events_to_progress, all_statuses, queried_zones
    
    logging.debug("Starting create_spot_instances function")
    
    # Check AWS credentials before proceeding
    is_valid, message = await check_aws_credentials()
    if not is_valid:
        logging.error(message)
        print(f"\n⚠️  {message}")
        print("\nPlease refresh your AWS credentials and try again.")
        sys.exit(1)
    
    logging.debug("AWS credentials check passed")
    
    # Reset global variables
    all_statuses = {}
    events_to_progress = []
    queried_zones = set()
    
    # Set up the task name and total
    task_name = "Creating Spot Instances"
    
    # Get the total number of instances to create from config
    config_path = "config.yaml"
    logging.debug(f"Loading config from {config_path}")
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        max_instances = config.get("max_instances", 0)
        regions_config = config.get("regions", [])
        
        logging.debug(f"Max instances from config: {max_instances}")
        logging.debug(f"Regions from config: {regions_config}")
        
        if not regions_config:
            logging.error("No regions found in config")
            print("\n⚠️  No regions found in config.yaml")
            return
        
        # Count how many instances we'll create
        task_total = 0
        regions_to_process = []
        
        for region_dict in regions_config:
            for region, settings in region_dict.items():
                node_count = settings.get("node_count", "auto")
                if node_count == "auto":
                    # Auto-distribute instances among regions
                    node_count = max(1, max_instances // len(regions_config))
                else:
                    try:
                        node_count = int(node_count)
                    except (ValueError, TypeError):
                        node_count = 1
                
                task_total += node_count
                regions_to_process.append((region, settings, node_count))
        
        logging.debug(f"Total instances to create: {task_total}")
        
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}")
        logging.exception("Detailed exception information:")
        print(f"\n⚠️  Error loading config: {str(e)}")
        return
    
    logging.debug("Creating progress bar and UI components")
    
    # Create progress bar
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    )
    
    # Create table for instance information
    table = Table(show_header=True, header_style="bold")
    table.add_column("Instance ID")
    table.add_column("Region")
    table.add_column("AZ")
    table.add_column("Status")
    table.add_column("Public IP")
    table.add_column("Private IP")
    
    # Create zones panel to show which zones are being processed
    zones_panel = Panel(
        Text("Processing zones...", style="yellow"),
        title="Zones Being Processed",
        border_style="blue",
        padding=(1, 1),
    )
    
    # Create layout with progress, table, and zones panel
    layout = create_layout(progress, table, zones_panel)
    
    logging.debug("Starting live display")
    
    # Start the live display
    with Live(layout, refresh_per_second=4) as live:
        # Start the table update task
        logging.debug("Creating table update task")
        table_update_task = asyncio.create_task(update_table(live))
        
        # Start a task to update the zones panel
        logging.debug("Creating zones panel update task")
        async def update_zones_panel():
            logging.debug("Starting zones panel update loop")
            while not shutdown_event.is_set():
                try:
                    zones_text = (
                        "\n".join(sorted(queried_zones))
                        if queried_zones
                        else "Processing zones..."
                    )
                    zones_panel.renderable = Text(zones_text, style="yellow")
                    live.refresh()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logging.error(f"Error updating zones panel: {str(e)}")
                    logging.exception("Detailed exception information:")
                    await asyncio.sleep(1)
        
        zones_update_task = asyncio.create_task(update_zones_panel())
        
        # Add a task to the progress bar
        logging.debug("Adding task to progress bar")
        task_id = progress.add_task(task_name, total=task_total)
        
        try:
            # Create instances in each region
            logging.debug(f"Starting to create instances in {len(regions_to_process)} regions")
            
            # Create instances in parallel across regions
            region_tasks = []
            for region, settings, node_count in regions_to_process:
                if shutdown_event.is_set():
                    logging.debug(f"Shutdown event set, skipping region {region}")
                    break
                
                logging.debug(f"Creating task for region {region} with {node_count} instances")
                task = asyncio.create_task(
                    create_instances_in_region(
                        region, settings, node_count, progress, task_id
                    )
                )
                region_tasks.append(task)
            
            # Wait for all region tasks to complete
            if region_tasks:
                logging.debug(f"Waiting for {len(region_tasks)} region tasks to complete")
                await asyncio.gather(*region_tasks)
                logging.debug("All region tasks completed")
            
            # Update progress to show completion
            progress.update(
                task_id,
                description=f"Created {len(all_statuses)} instances",
                completed=len(all_statuses),
            )
            
            # Wait a moment to show final status
            logging.debug("Waiting to show final status")
            await asyncio.sleep(2)
            
            logging.debug("Create operation completed")
            
        except Exception as e:
            logging.error(f"Error creating instances: {str(e)}")
            logging.exception("Detailed exception information:")
            progress.update(task_id, description=f"Error: {str(e)}")
            await asyncio.sleep(2)
            
        finally:
            logging.debug("Cleaning up tasks")
            # Cancel the update tasks
            table_update_task.cancel()
            zones_update_task.cancel()
            try:
                logging.debug("Waiting for tasks to cancel")
                await table_update_task
                await zones_update_task
                logging.debug("Tasks cancelled successfully")
            except asyncio.CancelledError:
                logging.debug("Tasks cancelled")
                pass
            except Exception as e:
                logging.error(f"Error during task cleanup: {str(e)}")
                logging.exception("Detailed exception information:")


async def create_instances_in_region(region, settings, node_count, progress, task_id):
    """Create instances in a specific region"""
    global all_statuses, queried_zones
    
    logging.debug(f"Starting to create instances in region {region}")
    
    try:
        # Get the EC2 client for this region
        logging.debug(f"Getting EC2 client for region {region}")
        ec2 = await get_ec2_client(region)
        if not ec2:
            logging.error(f"Failed to get EC2 client for region {region}")
            return
        
        # Get all availability zones for this region
        logging.debug(f"Getting availability zones for region {region}")
        try:
            response = await asyncio.to_thread(ec2.describe_availability_zones)
            azs = [az["ZoneName"] for az in response["AvailabilityZones"]]
            logging.debug(f"Found {len(azs)} availability zones in region {region}: {azs}")
        except Exception as e:
            logging.error(f"Error getting availability zones for region {region}: {str(e)}")
            logging.exception(f"Detailed exception for region {region}:")
            return
        
        # Distribute instances across availability zones
        instances_per_az = max(1, node_count // len(azs))
        remaining_instances = node_count % len(azs)
        
        logging.debug(f"Distributing {node_count} instances across {len(azs)} AZs in region {region}")
        logging.debug(f"Base instances per AZ: {instances_per_az}, remaining: {remaining_instances}")
        
        # Create instances in each AZ
        az_tasks = []
        for i, az in enumerate(azs):
            if shutdown_event.is_set():
                logging.debug(f"Shutdown event set, skipping AZ {az} in region {region}")
                break
            
            # Add extra instance to first few AZs if we have remaining instances
            az_instances = instances_per_az
            if i < remaining_instances:
                az_instances += 1
            
            if az_instances <= 0:
                continue
            
            logging.debug(f"Creating task for {az_instances} instances in AZ {az} in region {region}")
            queried_zones.add(f"{region} - {az}")
            
            task = asyncio.create_task(
                create_instances_in_az(
                    region, az, ec2, settings, az_instances, progress, task_id
                )
            )
            az_tasks.append(task)
        
        # Wait for all AZ tasks to complete
        if az_tasks:
            logging.debug(f"Waiting for {len(az_tasks)} AZ tasks to complete in region {region}")
            await asyncio.gather(*az_tasks)
            logging.debug(f"All AZ tasks completed for region {region}")
        else:
            logging.debug(f"No AZ tasks created for region {region}")
    
    except Exception as e:
        logging.error(f"Error creating instances in region {region}: {str(e)}")
        logging.exception(f"Detailed exception for region {region}:")


async def create_instances_in_az(region, az, ec2, settings, instance_count, progress, task_id):
    """Create instances in a specific availability zone"""
    global all_statuses
    
    logging.debug(f"Starting to create {instance_count} instances in AZ {az} in region {region}")
    
    try:
        # Get settings for this region
        machine_type = settings.get("machine_type", "t3.medium")
        image = settings.get("image", "auto")
        
        # If image is auto, find the latest Amazon Linux 2 AMI
        if image == "auto":
            logging.debug(f"Finding latest Amazon Linux 2 AMI in region {region}")
            try:
                response = await asyncio.to_thread(
                    ec2.describe_images,
                    Owners=["amazon"],
                    Filters=[
                        {"Name": "name", "Values": ["amzn2-ami-hvm-*-x86_64-gp2"]},
                        {"Name": "state", "Values": ["available"]},
                    ],
                )
                
                # Sort by creation date (newest first)
                images = sorted(
                    response["Images"],
                    key=lambda x: x.get("CreationDate", ""),
                    reverse=True,
                )
                
                if images:
                    image = images[0]["ImageId"]
                    logging.debug(f"Found latest Amazon Linux 2 AMI: {image}")
                else:
                    logging.error(f"No Amazon Linux 2 AMI found in region {region}")
                    return
                
            except Exception as e:
                logging.error(f"Error finding AMI in region {region}: {str(e)}")
                logging.exception(f"Detailed exception for AMI search in {region}:")
                return
        
        # Create instances
        for i in range(instance_count):
            if shutdown_event.is_set():
                logging.debug(f"Shutdown event set, stopping instance creation in AZ {az}")
                break
            
            instance_name = f"bacalhau-{region}-{az}-{i}"
            logging.debug(f"Creating instance {instance_name} in AZ {az} in region {region}")
            
            try:
                # Create a status object for tracking
                status = InstanceStatus(region, az, i)
                status.status = "Creating"
                status.detailed_status = "Requesting spot instance"
                all_statuses[status.id] = status
                
                # Request spot instance
                response = await asyncio.to_thread(
                    ec2.request_spot_instances,
                    InstanceCount=1,
                    LaunchSpecification={
                        "ImageId": image,
                        "InstanceType": machine_type,
                        "Placement": {"AvailabilityZone": az},
                        "SecurityGroups": ["default"],
                        "TagSpecifications": [
                            {
                                "ResourceType": "instance",
                                "Tags": [
                                    {"Key": "Name", "Value": instance_name},
                                    {"Key": FILTER_TAG_NAME, "Value": FILTER_TAG_VALUE},
                                ],
                            }
                        ],
                    },
                )
                
                # Update status with spot request ID
                spot_request_id = response["SpotInstanceRequests"][0]["SpotInstanceRequestId"]
                status.detailed_status = f"Spot request ID: {spot_request_id}"
                logging.debug(f"Created spot request {spot_request_id} for {instance_name}")
                
                # Update progress
                progress.update(task_id, advance=1)
                
            except Exception as e:
                logging.error(f"Error creating instance in AZ {az} in region {region}: {str(e)}")
                logging.exception(f"Detailed exception for instance creation:")
                # Still advance progress even on error
                progress.update(task_id, advance=1)
        
        logging.debug("Completed creating {0} instances in AZ {1} in region {2}".format(instance_count, az, region))
    
    except Exception as e:
        logging.error(f"Error in create_instances_in_az for {region}/{az}: {str(e)}")
        logging.exception(f"Detailed exception for AZ {az} in region {region}:")


async def delete_disconnected_aws_nodes(args):
    """Delete disconnected AWS nodes"""
    logging.debug("Starting delete_disconnected_aws_nodes function")

    # This is a placeholder implementation
    print("\nFeature not yet implemented: delete_disconnected_aws_nodes")
    print(
        "This feature will allow you to delete AWS nodes that are disconnected from the Bacalhau network."
    )

    logging.debug("delete_disconnected_aws_nodes operation completed")


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()

    def handle_signal(sig):
        global shutdown_in_progress

        if shutdown_in_progress:
            logging.warning("Forced exit requested, terminating immediately")
            sys.exit(1)

        logging.info(f"Received signal {sig.name}, initiating graceful shutdown...")
        shutdown_in_progress = True
        shutdown_event.set()

        # Schedule task cancellation
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()

    # Add signal handlers for SIGINT (Ctrl+C) and SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    logging.debug("Signal handlers installed")


async def cleanup_resources():
    """Perform cleanup of resources before shutdown."""
    logging.info("Cleaning up resources...")

    # Close any open AWS client sessions
    # This is a placeholder - boto3 handles session cleanup automatically

    # Any additional cleanup tasks can be added here

    logging.info("Cleanup completed")


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
    table = Table(show_header=True, header_style="bold magenta", show_lines=False)
    table.overflow = "ellipsis"
    # Use ratio-based widths instead of fixed widths for dynamic terminal sizing
    table.add_column("ID", ratio=1, style="cyan", no_wrap=True)
    table.add_column("Region", ratio=2, style="cyan", no_wrap=True)
    table.add_column("Zone", ratio=2, style="cyan", no_wrap=True)
    table.add_column("Status", ratio=2, style="yellow", no_wrap=True)
    table.add_column("Elapsed", ratio=1, justify="right", style="magenta", no_wrap=True)
    table.add_column("Instance ID", ratio=3, style="blue", no_wrap=True)
    table.add_column("Public IP", ratio=2, style="blue", no_wrap=True)
    table.add_column("Private IP", ratio=2, style="blue", no_wrap=True)

    sorted_statuses = sorted(all_statuses.values(), key=lambda x: (x.region, x.zone))
    for status in sorted_statuses:
        table.add_row(
            status.id,
            status.region,
            status.zone,
            status.combined_status(),
            format_elapsed_time(status.elapsed_time),
            status.instance_id,
            status.public_ip,
            status.private_ip,
        )
    return table


def create_layout(progress, table, zones_panel=None):
    layout = Layout()
    progress_panel = Panel(
        progress,
        title="Progress",
        border_style="green",
        padding=(1, 1),
    )

    if zones_panel:
        layout.split(
            Layout(progress_panel, size=5),
            Layout(table),
            Layout(zones_panel, size=10),
        )
    else:
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
        task_name, \
        queried_zones
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

        # Create initial layout
        table = make_progress_table()

        # Create zones panel if we're listing or destroying
        zones_panel = None
        if task_name in ["Listing Spot Instances", "Terminating Spot Instances"]:
            zones_panel = Panel(
                Text("Initializing...", style="yellow"),
                title="Queried Zones",
                border_style="blue",
                padding=(1, 1),
            )

        layout = create_layout(progress, table, zones_panel)
        live.update(layout)  # Initial update
        live.refresh()  # Force refresh immediately

        # Only update when there are changes or every second
        last_update_time = time.time()
        last_completed = 0

        while not table_update_event.is_set():
            changes_made = False

            # Process events
            while events_to_progress:
                event = events_to_progress.pop(0)
                if isinstance(event, str):
                    # For list operation, event is instance_id
                    all_statuses[event].status = "Listed"
                else:
                    # For create and destroy operations, event is InstanceStatus object
                    all_statuses[event.id] = event
                changes_made = True

            # Calculate completed tasks
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
                changes_made = True

            # Update progress if completed count changed
            if completed != last_completed:
                progress.update(task, completed=completed)
                last_completed = completed
                changes_made = True

            current_time = time.time()
            time_elapsed = current_time - last_update_time

            # Only update the display if there are changes or a second has passed
            if changes_made or time_elapsed >= 1.0:
                table = make_progress_table()

                # Update zones panel if needed
                if zones_panel and queried_zones:
                    zones_text = "\n".join(
                        [f"• {zone}" for zone in sorted(queried_zones)]
                    )
                    zones_panel.renderable = Text(zones_text, style="yellow")
                    layout = create_layout(progress, table, zones_panel)
                    live.update(layout)
                    live.refresh()  # Explicitly refresh the display
                    last_update_time = current_time

            await asyncio.sleep(0.5)  # Reduced update frequency

    except Exception as e:
        logging.error(f"Error in update_table: {str(e)}")
        logging.exception("Detailed exception information:")
    finally:
        table_update_running = False
        logging.debug("Table update stopped.")


async def list_instances_in_region(region, start_time):
    """List instances in a specific region in parallel"""
    global queried_zones

    logging.debug(f"Starting to list instances in region {region}")

    try:
        # Get the EC2 client for this region
        logging.debug(f"Getting EC2 client for region {region}")
        ec2 = await get_ec2_client(region)
        if not ec2:
            logging.error(f"Failed to get EC2 client for region {region}")
            return

        # Get all availability zones for this region
        logging.debug(f"Getting availability zones for region {region}")
        try:
            response = await asyncio.to_thread(ec2.describe_availability_zones)
            azs = [az["ZoneName"] for az in response["AvailabilityZones"]]
            logging.debug(
                f"Found {len(azs)} availability zones in region {region}: {azs}"
            )
        except Exception as e:
            logging.error(
                f"Error getting availability zones for region {region}: {str(e)}"
            )
            logging.exception(f"Detailed exception for region {region}:")
            return

        # Create tasks for each availability zone
        az_tasks = []
        for az in azs:
            if shutdown_event.is_set():
                logging.debug(
                    f"Shutdown event set, skipping AZ {az} in region {region}"
                )
                break
            logging.debug(f"Creating task for AZ {az} in region {region}")
            task = asyncio.create_task(
                list_instances_in_az(region, az, ec2, start_time)
            )
            az_tasks.append(task)

        # Wait for all AZ tasks to complete
        if az_tasks:
            logging.debug(
                f"Waiting for {len(az_tasks)} AZ tasks to complete in region {region}"
            )
            await asyncio.gather(*az_tasks)
            logging.debug(f"All AZ tasks completed for region {region}")
        else:
            logging.debug(f"No AZ tasks created for region {region}")

    except Exception as e:
        logging.error(f"Error listing instances in region {region}: {str(e)}")
        logging.exception(f"Detailed exception for region {region}:")


async def list_instances_in_az(region, az, ec2, start_time):
    """List instances in a specific availability zone"""
    global all_statuses, queried_zones, task_total

    logging.debug(f"Starting to list instances in AZ {az} in region {region}")

    try:
        # Add this zone to the queried zones set
        queried_zones.add(f"{region} - {az}")

        # Get instances in this AZ with the specified tag
        logging.debug(f"Querying EC2 instances in AZ {az} in region {region}")
        try:
            response = await asyncio.to_thread(
                ec2.describe_instances,
                Filters=[
                    {"Name": "availability-zone", "Values": [az]},
                    {"Name": "instance-state-name", "Values": ["running", "pending"]},
                    {"Name": "tag:" + FILTER_TAG_NAME, "Values": [FILTER_TAG_VALUE]},
                ],
            )
            logging.debug(f"Query completed for AZ {az} in region {region}")
        except Exception as e:
            logging.error(
                f"Error querying instances in AZ {az} in region {region}: {str(e)}"
            )
            logging.exception(f"Detailed exception for AZ {az} in region {region}:")
            return

        # Process the response
        instances = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instances.append(instance)

        logging.debug(f"Found {len(instances)} instances in AZ {az} in region {region}")

        # Update task_total with the number of instances found
        for instance in instances:
            instance_id = instance["InstanceId"]

            # Create a status object for this instance
            status = InstanceStatus(region, az, instance_id=instance_id)

            # Set the status
            status.status = instance["State"]["Name"]
            status.detailed_status = instance["State"]["Name"]

            # Set the IPs
            if "PublicIpAddress" in instance:
                status.public_ip = instance["PublicIpAddress"]
            if "PrivateIpAddress" in instance:
                status.private_ip = instance["PrivateIpAddress"]

            # Set the VPC ID
            if "VpcId" in instance:
                status.vpc_id = instance["VpcId"]

            # Set the elapsed time
            status.elapsed_time = int(time.time() - start_time)

            # Add the status to the global dictionary
            all_statuses[instance_id] = status

            # Increment task_total
            task_total += 1

        logging.debug(
            f"Processed {len(instances)} instances in AZ {az} in region {region}"
        )

    except Exception as e:
        logging.error(
            f"Error processing instances in AZ {az} in region {region}: {str(e)}"
        )
        logging.exception(f"Detailed exception for AZ {az} in region {region}:")


async def destroy_instances():
    global \
        instance_region_map, \
        task_name, \
        task_total, \
        events_to_progress, \
        all_statuses, \
        queried_zones
    # Check AWS credentials before proceeding
    is_valid, message = await check_aws_credentials()
    if not is_valid:
        logging.error(message)
        print(f"\n⚠️  {message}")
        print("\nPlease refresh your AWS credentials and try again.")
        sys.exit(1)

    instance_region_map = {}
    all_statuses = {}  # Reset the global statuses
    events_to_progress = []  # Clear the events list
    queried_zones = set()  # Reset the queried zones set

    task_name = "Terminating Spot Instances"
    task_total = 0

    logging.debug("Starting to terminate spot instances")

    # Create progress bar
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    )

    # Create table for instance information
    table = Table(show_header=True, header_style="bold")
    table.add_column("Instance ID")
    table.add_column("Region")
    table.add_column("AZ")
    table.add_column("Status")
    table.add_column("Elapsed Time")

    # Create zones panel to show which zones are being queried
    zones_panel = Panel(
        Text("Querying zones...", style="yellow"),
        title="Zones Being Queried",
        border_style="blue",
        padding=(1, 1),
    )

    # Create layout with progress, table, and zones panel
    layout = create_layout(progress, table, zones_panel)

    # Start the live display
    with Live(layout, refresh_per_second=4) as live:
        # Start the table update task
        table_update_task = asyncio.create_task(update_table(live))

        # Start a task to update the zones panel
        async def update_zones_panel():
            while not shutdown_event.is_set():
                try:
                    zones_text = (
                        "\n".join(sorted(queried_zones))
                        if queried_zones
                        else "Querying zones..."
                    )
                    zones_panel.renderable = Text(zones_text, style="yellow")
                    live.refresh()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logging.error(f"Error updating zones panel: {str(e)}")
                    await asyncio.sleep(1)

        zones_update_task = asyncio.create_task(update_zones_panel())

        # Add a task to the progress bar
        task_id = progress.add_task(task_name, total=None)

        try:
            # First, find all instances across all regions in parallel
            instances_to_terminate = []

            async def find_instances_in_region(region):
                if shutdown_event.is_set():
                    return

                try:
                    ec2 = await get_ec2_client(region)

                    # Get all availability zones for this region
                    availability_zones = await asyncio.to_thread(
                        lambda: [
                            az["ZoneName"]
                            for az in ec2.describe_availability_zones()[
                                "AvailabilityZones"
                            ]
                        ]
                    )

                    # Query all availability zones in parallel
                    async def find_instances_in_az(az):
                        if shutdown_event.is_set():
                            return

                        queried_zones.add(f"{region}/{az}")  # Add the zone to the set
                        logging.debug(f"Querying instances in {region}/{az}")

                        try:
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
                                    # Get the hostname from tags or use instance ID if not available
                                    hostname = instance_id
                                    for tag in instance.get("Tags", []):
                                        if tag["Key"] == "Name":
                                            hostname = tag["Value"]
                                            break

                                    # Add to the instance_region_map for termination
                                    instance_region_map[instance_id] = region

                                    # Create a status object for tracking
                                    thisInstanceStatusObject = InstanceStatus(
                                        region, az, 0, hostname
                                    )
                                    thisInstanceStatusObject.status = (
                                        "Pending termination"
                                    )
                                    thisInstanceStatusObject.instance_id = instance_id
                                    thisInstanceStatusObject.public_ip = instance.get(
                                        "PublicIpAddress", ""
                                    )
                                    thisInstanceStatusObject.private_ip = instance.get(
                                        "PrivateIpAddress", ""
                                    )

                                    # Add to the global status tracking
                                    all_statuses[hostname] = thisInstanceStatusObject
                                    instances_to_terminate.append((instance_id, region))
                        except Exception as e:
                            logging.error(
                                f"Error querying instances in {region}/{az}: {str(e)}"
                            )
                            logging.exception("Detailed exception information:")
                            await asyncio.sleep(1)

                    # Query all AZs in parallel
                    az_tasks = []
                    for az in availability_zones:
                        if shutdown_event.is_set():
                            break
                        az_tasks.append(asyncio.create_task(find_instances_in_az(az)))

                    await asyncio.gather(*az_tasks)

                except Exception as e:
                    logging.error(f"Error querying region {region}: {str(e)}")
                    logging.exception("Detailed exception information:")

            # Query all regions in parallel
            region_tasks = []
            for region in AWS_REGIONS:
                if shutdown_event.is_set():
                    break
                region_tasks.append(
                    asyncio.create_task(find_instances_in_region(region))
                )

            await asyncio.gather(*region_tasks)

            # Update task total with the number of instances found
            task_total = len(instances_to_terminate)

            if task_total == 0:
                progress.update(task_id, description="No instances found to terminate")
                await asyncio.sleep(2)  # Give time for the message to be seen
                return

            # Update progress with the total number of instances
            progress.update(
                task_id,
                total=task_total,
                description=f"Terminating {task_total} instances",
            )

            # Terminate all instances in parallel
            termination_tasks = []
            for instance_id, region in instances_to_terminate:
                if shutdown_event.is_set():
                    logging.info("Shutdown requested, stopping instance termination")
                    break
                task = asyncio.create_task(terminate_instance(instance_id, region))
                termination_tasks.append(task)

            # Wait for all termination tasks to complete
            await asyncio.gather(*termination_tasks)

            # Update progress to show completion
            progress.update(
                task_id, completed=task_total, description="Termination complete"
            )

            logging.debug("Finished terminating spot instances")

        except asyncio.CancelledError:
            if shutdown_event.is_set():
                logging.info(
                    "Termination operation cancelled due to controlled shutdown"
                )
            else:
                logging.error("Termination operation was cancelled unexpectedly")
                logging.debug("Stack trace:", exc_info=True)
        except Exception as e:
            logging.error(f"Error terminating instances: {str(e)}")
            logging.exception("Detailed exception information:")
        finally:
            # Signal the table update to stop if it hasn't already
            table_update_event.set()

            # Cancel the update tasks
            table_update_task.cancel()
            zones_update_task.cancel()

            try:
                await table_update_task
                await zones_update_task
            except asyncio.CancelledError:
                pass

            # Update progress if task_id was created
            if "task_id" in locals():
                progress.update(task_id, description="Operation complete")


async def list_spot_instances():
    global task_name, task_total, events_to_progress, all_statuses, queried_zones
    # Check AWS credentials before proceeding
    logging.debug("Starting list_spot_instances function")
    is_valid, message = await check_aws_credentials()
    if not is_valid:
        logging.error(message)
        print(f"\n⚠️  {message}")
        print("\nPlease refresh your AWS credentials and try again.")
        sys.exit(1)

    logging.debug("AWS credentials check passed")

    # Reset global variables
    all_statuses = {}
    events_to_progress = []
    queried_zones = set()

    # Set up the task name and total
    task_name = "Listing Spot Instances"
    task_total = 0  # Will be updated as we find instances

    logging.debug("Creating progress bar and UI components")

    # Create progress bar
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    )

    # Create table for instance information
    table = Table(show_header=True, header_style="bold")
    table.add_column("Instance ID")
    table.add_column("Region")
    table.add_column("AZ")
    table.add_column("Status")
    table.add_column("Public IP")
    table.add_column("Private IP")

    # Create zones panel to show which zones are being queried
    zones_panel = Panel(
        Text("Querying zones...", style="yellow"),
        title="Zones Being Queried",
        border_style="blue",
        padding=(1, 1),
    )

    # Create layout with progress, table, and zones panel
    layout = create_layout(progress, table, zones_panel)

    logging.debug("Starting live display")

    # Start the live display
    with Live(layout, refresh_per_second=4) as live:
        # Start the table update task
        logging.debug("Creating table update task")
        table_update_task = asyncio.create_task(update_table(live))

        # Start a task to update the zones panel
        logging.debug("Creating zones panel update task")

        async def update_zones_panel():
            logging.debug("Starting zones panel update loop")
            while not shutdown_event.is_set():
                try:
                    zones_text = (
                        "\n".join(sorted(queried_zones))
                        if queried_zones
                        else "Querying zones..."
                    )
                    zones_panel.renderable = Text(zones_text, style="yellow")
                    live.refresh()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logging.error(f"Error updating zones panel: {str(e)}")
                    logging.exception("Detailed exception information:")
                    await asyncio.sleep(1)

        zones_update_task = asyncio.create_task(update_zones_panel())

        # Add a task to the progress bar
        logging.debug("Adding task to progress bar")
        task_id = progress.add_task(task_name, total=None)

        try:
            # Get the start time for elapsed time calculation
            start_time = time.time()

            logging.debug("Starting to query AWS regions")

            # Query all regions in parallel
            region_tasks = []
            for region in AWS_REGIONS:
                if shutdown_event.is_set():
                    logging.debug(f"Shutdown event set, skipping region {region}")
                    break
                logging.debug(f"Creating task for region {region}")
                task = asyncio.create_task(
                    list_instances_in_region(region, start_time)
                )
                region_tasks.append(task)

            # Wait for all region tasks to complete
            logging.debug(f"Waiting for {len(region_tasks)} region tasks to complete")
            await asyncio.gather(*region_tasks)
            logging.debug("All region tasks completed")

            # Update task total with the number of instances found
            task_total = len(all_statuses)
            logging.debug(f"Found {task_total} instances total")

            if task_total == 0:
                logging.debug("No instances found")
                progress.update(task_id, description="No instances found")
            else:
                logging.debug(f"Updating progress with {task_total} instances")
                progress.update(
                    task_id,
                    total=task_total,
                    completed=task_total,
                    description=f"Found {task_total} instances",
                )

            # Wait a moment to show final status
            logging.debug("Waiting to show final status")
            await asyncio.sleep(2)
            logging.debug("List operation completed successfully")

        except Exception as e:
            logging.error(f"Error listing instances: {str(e)}")
            logging.exception("Detailed exception information:")
            progress.update(task_id, description=f"Error: {str(e)}")
            await asyncio.sleep(2)

        finally:
            logging.debug("Cleaning up tasks")
            # Cancel the update tasks
            table_update_task.cancel()
            zones_update_task.cancel()
            try:
                logging.debug("Waiting for tasks to cancel")
                await table_update_task
                await zones_update_task
                logging.debug("Tasks cancelled successfully")
            except asyncio.CancelledError:
                logging.debug("Tasks cancelled")
                pass
            except Exception as e:
                logging.error(f"Error during task cleanup: {str(e)}")
                logging.exception("Detailed exception information:")


async def terminate_instance(instance_id, region):
    """Terminate a specific instance and update its status"""
    global all_statuses, events_to_progress

    # Find the status object for this instance
    status_obj = None
    for status in all_statuses.values():
        if status.instance_id == instance_id:
            status_obj = status
            break

    if not status_obj:
        logging.error(f"No status object found for instance {instance_id}")
        return

    try:
        ec2 = await get_ec2_client(region)
        logging.info(f"Terminating instance {instance_id} in {region}")

        # Update status
        status_obj.status = "Terminating"
        events_to_progress.append(status_obj)

        # Terminate the instance
        await asyncio.to_thread(ec2.terminate_instances, InstanceIds=[instance_id])

        # Wait for termination to complete
        start_time = time.time()
        while True:
            try:
                response = await asyncio.to_thread(
                    ec2.describe_instances, InstanceIds=[instance_id]
                )

                if not response["Reservations"]:
                    break

                instance = response["Reservations"][0]["Instances"][0]
                current_state = instance["State"]["Name"]

                if current_state == "terminated":
                    break

                # Update elapsed time
                status_obj.elapsed_time = time.time() - start_time
                events_to_progress.append(status_obj)

                # Wait before checking again
                await asyncio.sleep(5)

            except botocore.exceptions.ClientError as e:
                if "InvalidInstanceID.NotFound" in str(e):
                    # Instance is gone
                    break
                logging.error(f"Error checking instance status: {str(e)}")
                await asyncio.sleep(5)

        # Update final status
        status_obj.status = "Terminated"
        events_to_progress.append(status_obj)
        logging.info(f"Instance {instance_id} terminated successfully")

    except Exception as e:
        logging.error(f"Error terminating instance {instance_id}: {str(e)}")
        status_obj.status = "Termination Failed"
        events_to_progress.append(status_obj)


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
        default="list",
    )
    parser.add_argument(
        "--format", choices=["default", "json"], default="default", help="Output format"
    )
    args = parser.parse_args()

    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()
    # Check AWS credentials early if the action requires AWS access
    # Skip credential check for actions that don't need AWS
    if args.action != "delete_disconnected_aws_nodes":
        # Temporarily disable boto3 and botocore logging completely
        boto3_logger = logging.getLogger("boto3")
        botocore_logger = logging.getLogger("botocore")
        original_boto3_level = boto3_logger.level
        original_botocore_level = botocore_logger.level
        boto3_logger.setLevel(logging.CRITICAL)
        botocore_logger.setLevel(logging.CRITICAL)
        try:
            is_valid, message = await check_aws_credentials()
            if not is_valid:
                print(f"\n⚠️  {message}")
                print("\nPlease refresh your AWS credentials and try again.")
                return  # Exit early without starting the console
        finally:
            # Restore original logging levels
            boto3_logger.setLevel(original_boto3_level)
            botocore_logger.setLevel(original_botocore_level)

    async def perform_action():
        if args.action == "create":
            await create_spot_instances(args)
        elif args.action == "list":
            await list_spot_instances()
        elif args.action == "destroy":
            await destroy_instances()
        elif args.action == "delete_disconnected_aws_nodes":
            await delete_disconnected_aws_nodes(args)

    if args.format == "json":
        try:
            await perform_action()
            print(json.dumps(await all_statuses_to_dict(), indent=2))
        except asyncio.CancelledError:
            if shutdown_event.is_set():
                logging.info(
                    "JSON output operation cancelled due to controlled shutdown"
                )
            else:
                logging.error("Operation was cancelled unexpectedly")
                logging.debug("Stack trace:", exc_info=True)
        except Exception as e:
            logging.error(f"Error during execution: {str(e)}")
            logging.exception("Detailed exception information:")
        finally:
            if shutdown_event.is_set():
                await cleanup_resources()
    else:
        with Live(
            console=console, refresh_per_second=2, auto_refresh=False, transient=False
        ) as live:
            update_task = asyncio.create_task(update_table(live))
            try:
                await perform_action()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                if shutdown_event.is_set():
                    logging.info("Operation cancelled due to controlled shutdown")
                else:
                    logging.error("Operation was cancelled unexpectedly")
                    logging.debug("Stack trace:", exc_info=True)
            except Exception as e:
                logging.error(f"Error in main: {str(e)}")
                logging.exception("Detailed exception information:")
            finally:
                table_update_event.set()
                try:
                    await update_task
                except Exception as e:
                    logging.error(f"Error during update task cleanup: {str(e)}")

                if shutdown_event.is_set():
                    await cleanup_resources()
                    logging.info("Graceful shutdown completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This handles the case where KeyboardInterrupt happens outside of the asyncio event loop
        logging.info("Keyboard interrupt received outside of asyncio loop, exiting")
    except Exception as e:
        logging.error(f"Unhandled exception: {str(e)}")
        logging.exception("Detailed exception information:")
        sys.exit(1)
