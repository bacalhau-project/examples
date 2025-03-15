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

# Set up logging to both console and file
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Clear existing handlers
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
    logger.error(f"Failed to set up file logging: {e}")

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

# List to store operations logs
operations_logs = []
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
    
    # Add to the operations logs
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


def update_all_statuses(status):
    async def update_all_statuses_async(status):
        all_statuses_lock = asyncio.Lock()

        async with all_statuses_lock:
            all_statuses[status.id] = status

    update_all_statuses_async(status)


class InstanceStatus:
    def __init__(self, region, zone, index, instance_id=None):
        self.id = str(uuid.uuid4())
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
        
    def combined_status(self):
        """Returns a combined status string for display in the table."""
        if self.detailed_status:
            return f"{self.status}: {self.detailed_status}"
        return self.status

    def to_dict(self):
        return {
            "id": self.id,
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
    ops_content = "\n".join(operations_logs) if operations_logs else "[dim]No operations logged yet...[/dim]"
    operations_panel = Panel(
        ops_content,
        title="AWS Operations",
        border_style="yellow",
        padding=(1, 1),
    )
    
    # Split layout into three sections
    layout.split(
        Layout(progress_panel, size=5),
        Layout(table, size=15),
        Layout(operations_panel, size=10),
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

        while not table_update_event.is_set():
            while events_to_progress:
                event = events_to_progress.pop(0)
                if isinstance(event, str):
                    # For list operation, event is instance_id
                    all_statuses[event].status = "Listed"
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

            # Create table and layout
            table = make_progress_table()
            layout = create_layout(progress, table)
            
            # Always update the operations log panel to show latest operations
            if "operations" in layout:
                ops_content = "\n".join(operations_logs) if operations_logs else "[dim]No operations logged yet...[/dim]"
                layout["operations"].update(
                    Panel(
                        ops_content,
                        title="AWS Operations",
                        border_style="yellow",
                        padding=(1, 1),
                    )
                )
            
            # Update the live display
            live.update(layout)

            # Update elapsed time for all instances
            now = time.time()
            for status in all_statuses.values():
                status.elapsed_time = now - status.start_time

            await asyncio.sleep(0.05)  # Reduce sleep time for more frequent updates

    except Exception as e:
        logger.error(f"Error in update_table: {str(e)}")
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

        async with machine_state.update() as machines:
            for i in range(instances_to_create):
                zone = zones[i % len(zones)]
                log_operation(f"Creating instance {i+1}/{instances_to_create} in zone {zone}", "info", region)

                log_operation(f"Creating subnet in zone {zone}", "info", region)
                subnet_id = await create_subnet(ec2, vpc_id, zone, f"10.0.{i}.0/24")
                log_operation(f"Subnet created: {subnet_id}", "info", region)
                
                log_operation(f"Associating route table with subnet", "info", region)
                try:
                    await associate_route_table(ec2, route_table_id, subnet_id)
                    log_operation(f"Route table associated successfully", "info", region)
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
                        already_msg = f"Route table already associated in {region}-{zone}"
                        logger.info(already_msg)
                        log_operation(already_msg, "info", region)
                    else:
                        error_msg = f"Error associating route table in {region}-{zone}: {str(e)}"
                        logger.warning(error_msg)
                        log_operation(error_msg, "warning", region)

                thisInstanceStatusObject = InstanceStatus(region, zone, i)
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
                events_to_progress.append(thisInstanceStatusObject)

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
                events_to_progress.append(thisInstanceStatusObject)

                instance_id = await handle_spot_request(
                    ec2, launch_specification, region, zone, thisInstanceStatusObject
                )

                if instance_id is None:
                    thisInstanceStatusObject.status = "N/A"
                    thisInstanceStatusObject.detailed_status = (
                        "No spot capacity available"
                    )
                    events_to_progress.append(thisInstanceStatusObject)
                    continue

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

                    # Save to MACHINES.json
                    machines[instance_id] = thisInstanceStatusObject.to_dict()

                thisInstanceStatusObject.status = "Done"
                events_to_progress.append(thisInstanceStatusObject)

    except Exception as e:
        logger.error(f"An error occurred in {region}: {str(e)}", exc_info=True)
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
            logger.debug(f"Creating subnet in {zone} with CIDR block {cidrBlock}")
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
            logger.debug(
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

        create_msg = f"Creating {instances_to_create} spot instances in region: {region}"
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

    logger.debug("Waiting for public IP addresses...")
    log_operation("Waiting for public IP addresses to be assigned...")
    await wait_for_public_ips()
    log_operation("IP address assignment complete")

    logger.debug("Finished creating spot instances")
    log_operation("Finished creating spot instances")
    return


async def wait_for_public_ips():
    global all_statuses
    timeout = 300  # 5 minutes timeout
    start_time = time.time()

    NO_IP_STATUS = "-----"
    log_operation("Checking for public IP addresses on all instances")

    # Count how many instances still need IP addresses
    instances_without_ip = len([
        status for status in all_statuses.values()
        if not status.public_ip and status.status != NO_IP_STATUS
    ])
    log_operation(f"Waiting for IP addresses for {instances_without_ip} instances")

    check_count = 0
    while True:
        all_have_ips = all(
            status.public_ip or status.status == NO_IP_STATUS
            for status in all_statuses.values()
        )
        
        if all_have_ips:
            log_operation("All instances have IP addresses assigned")
            break
            
        if time.time() - start_time > timeout:
            log_operation("Timed out waiting for IP addresses", "warning")
            break

        # Only log status occasionally to avoid flooding
        if check_count % 6 == 0:  # Every ~30 seconds
            instances_without_ip = len([
                status for status in all_statuses.values()
                if not status.public_ip and status.status != NO_IP_STATUS
            ])
            elapsed = int(time.time() - start_time)
            log_operation(f"Still waiting for {instances_without_ip} IP addresses... ({elapsed}s elapsed)")
        
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
                    and status.instance_id is not None
                )
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
                                    log_operation(f"Instance {instance_id} got IP: {public_ip}", "info", region)

        await asyncio.sleep(5)  # Wait 5 seconds before checking again


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

    # Check if MACHINES.json exists
    if not os.path.exists("MACHINES.json"):
        logger.info("MACHINES.json not found. No instances to terminate.")
        return

    machines = await machine_state.load()

    if not machines:
        logger.info("MACHINES.json exists but contains no instances to terminate.")
        return

    task_total = len(machines)
    logger.info(f"Found {task_total} instances to terminate.")

    # Log instance details before termination
    for instance_id, machine in machines.items():
        logger.info(
            f"  Instance {instance_id} in {machine['region']}-{machine['zone']}"
        )

    # Group instances by region
    region_instances = {}
    for instance_id, machine in machines.items():
        region = machine["region"]
        if region not in region_instances:
            region_instances[region] = []
        region_instances[region].append(instance_id)

        # Initialize status object
        thisInstanceStatusObject = InstanceStatus(
            machine["region"], machine["zone"], 0, instance_id
        )
        thisInstanceStatusObject.status = "Terminating"
        thisInstanceStatusObject.detailed_status = "Initializing termination"
        thisInstanceStatusObject.vpc_id = machine["vpc_id"]
        all_statuses[instance_id] = thisInstanceStatusObject

    async def terminate_instances_in_region(region, region_instances):
        ec2 = get_ec2_client(region)
        try:
            # Terminate instances
            await asyncio.to_thread(
                ec2.terminate_instances, InstanceIds=region_instances
            )

            # Wait for termination
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
                    await asyncio.sleep(10)

            # Update status for terminated instances
            for instance_id in region_instances:
                thisInstanceStatusObject = all_statuses[instance_id]
                thisInstanceStatusObject.status = "Terminated"
                thisInstanceStatusObject.detailed_status = "Instance terminated"
                events_to_progress.append(thisInstanceStatusObject)

            # Clean up resources for each VPC
            vpcs_to_delete = set(
                all_statuses[instance_id].vpc_id
                for instance_id in region_instances
                if all_statuses[instance_id].vpc_id
            )

            for vpc_id in vpcs_to_delete:
                try:
                    for instance_id in region_instances:
                        if all_statuses[instance_id].vpc_id == vpc_id:
                            all_statuses[
                                instance_id
                            ].detailed_status = "Cleaning up VPC resources"
                            events_to_progress.append(all_statuses[instance_id])

                    await clean_up_vpc_resources(ec2, vpc_id)

                except Exception as e:
                    logger.error(
                        f"Error cleaning up VPC {vpc_id} in {region}: {str(e)}"
                    )

            # Remove terminated instances from MACHINES.json
            async with machine_state.update() as current_machines:
                for instance_id in region_instances:
                    current_machines.pop(instance_id, None)

        except Exception as e:
            logger.error(f"Error cleaning up resources in {region}: {str(e)}")

    # Terminate instances in parallel
    await asyncio.gather(
        *[
            terminate_instances_in_region(region, instances)
            for region, instances in region_instances.items()
        ]
    )

    logger.info("All instances have been terminated.")


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
        self.lock = asyncio.Lock()

    async def load(self):
        try:
            async with self.lock:
                if os.path.exists(self.filename):
                    with open(self.filename, "r") as f:
                        return json.load(f)
        except Exception as e:
            logger.error(f"Error loading machine state: {e}")
        return {}

    async def save(self, machines):
        try:
            async with self.lock:
                with open(self.filename, "w") as f:
                    json.dump(machines, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving machine state: {e}")

    @asynccontextmanager
    async def update(self):
        current = await self.load()
        try:
            yield current
        finally:
            await self.save(current)


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
    for attempt in range(max_retries):
        try:
            attempt_msg = f"Attempting spot request in {region}-{zone} (attempt {attempt + 1}/{max_retries})"
            logger.debug(attempt_msg)
            log_operation(attempt_msg, "info", region)
            
            # Add info about instance type being requested
            instance_type = launch_specification.get("InstanceType", "unknown")
            log_operation(f"Requesting instance type: {instance_type}", "info", region)
            
            response = await asyncio.to_thread(
                ec2.request_spot_instances,
                InstanceCount=1,
                Type="one-time",
                InstanceInterruptionBehavior="terminate",
                LaunchSpecification=launch_specification,
            )

            request_id = response["SpotInstanceRequests"][0]["SpotInstanceRequestId"]
            logger.debug(f"Spot request {request_id} created in {region}-{zone}")
            log_operation(f"Spot request {request_id} created successfully", "info", region)

            # Update instance status to reflect spot request creation
            instance_status.spot_request_id = request_id
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
            async with machine_state.update() as machines:
                machines[instance_status.id] = instance_status.to_dict()
            
            log_operation(f"Waiting for spot request fulfillment...", "info", region)
            
            async with asyncio.timeout(300):
                status_check_count = 0
                while True:
                    status = await get_spot_request_status(ec2, request_id)
                    logger.debug(f"Spot request {request_id} status: {status}")
                    
                    # Only log every 3rd check to avoid flooding the operations log
                    if status_check_count % 3 == 0:
                        log_operation(f"Spot request status: {status['state']}", "info", region)
                    status_check_count += 1

                    if status["state"] == "fulfilled":
                        fulfilled_msg = f"Spot request {request_id} fulfilled with instance {status['instance_id']}"
                        logger.info(fulfilled_msg)
                        log_operation(fulfilled_msg, "info", region)
                        
                        # Update instance status for provisioning phase
                        instance_status.update_creation_state(
                            "provisioning",
                            {
                                "instance_id": status["instance_id"],
                                "fulfillment_time": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            },
                        )
                        async with machine_state.update() as machines:
                            machines[instance_status.id] = instance_status.to_dict()
                        
                        log_operation(f"Instance {status['instance_id']} is being provisioned", "info", region)
                        return status["instance_id"]
                    elif status["state"] in ["capacity-not-available", "price-too-low"]:
                        error_msg = f"Spot capacity not available in {region}-{zone}: {status['message']}"
                        logger.warning(error_msg)
                        log_operation(error_msg, "warning", region)
                        
                        # Update instance status for failure
                        instance_status.update_creation_state(
                            "failed",
                            {"reason": status["state"], "message": status["message"]},
                        )
                        async with machine_state.update() as machines:
                            machines[instance_status.id] = instance_status.to_dict()
                        return None
                    elif status["state"] in ["failed", "cancelled", "closed"]:
                        if attempt < max_retries - 1:
                            retry_msg = f"Spot request {request_id} {status['state']}, retrying..."
                            logger.warning(retry_msg)
                            log_operation(retry_msg, "warning", region)
                            await asyncio.sleep(5 * (attempt + 1))
                            break
                        
                        error_msg = f"Spot request {request_id} failed after all retries: {status['message']}"
                        logger.error(error_msg)
                        log_operation(error_msg, "error", region)
                        
                        # Update instance status for failure
                        instance_status.update_creation_state(
                            "failed",
                            {
                                "reason": status["state"],
                                "message": status["message"],
                                "final_attempt": True,
                            },
                        )
                        async with machine_state.update() as machines:
                            machines[instance_status.id] = instance_status.to_dict()
                        return None
                    await asyncio.sleep(5)

        except asyncio.TimeoutError:
            timeout_msg = f"Timeout waiting for spot request in {region}-{zone}"
            logger.warning(timeout_msg)
            log_operation(timeout_msg, "warning", region)
            
            # Update instance status for timeout
            instance_status.update_creation_state(
                "failed",
                {
                    "reason": "timeout",
                    "message": f"Request timed out after {300} seconds",
                },
            )
            async with machine_state.update() as machines:
                machines[instance_status.id] = instance_status.to_dict()
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                error_msg = f"Error in spot request for {region}-{zone}, retrying: {e}"
                logger.warning(error_msg)
                log_operation(error_msg, "warning", region)
                await asyncio.sleep(5 * (attempt + 1))
                continue
            
            error_msg = f"Error requesting spot instance in {region}-{zone}: {str(e)}"
            logger.exception(error_msg)
            log_operation(error_msg, "error", region)
            
            # Update instance status for error
            instance_status.update_creation_state(
                "failed", {"reason": "error", "message": str(e), "final_attempt": True}
            )
            async with machine_state.update() as machines:
                machines[instance_status.id] = instance_status.to_dict()
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
    args = parser.parse_args()
    logger.debug(f"Parsed arguments: {args}")

    # Log the action being performed at INFO level for better visibility
    logger.info(f"Starting {args.action} operation...")

    machines = await machine_state.load()
    logger.info(f"Loaded {len(machines)} machines from MACHINES.json")

    if machines:
        logger.debug("MACHINES.json contains the following instances:")
        for instance_id, machine in machines.items():
            logger.debug(
                f"  Instance {instance_id} in {machine['region']}-{machine['zone']}"
            )
    elif args.action == "destroy":
        logger.info("MACHINES.json is empty. No instances to process.")
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
                log_operation(f"Delete_disconnected_aws_nodes action completed successfully")
            logger.debug(f"Action {args.action} completed successfully")
        except Exception as e:
            error_msg = f"Error performing action {args.action}: {str(e)}"
            logger.exception(error_msg)
            log_operation(error_msg, "error")
            raise

    if args.format == "json":
        logger.debug("Using JSON output format")
        try:
            await perform_action()
            result = all_statuses_to_dict()
            if not result and args.action != "destroy":
                logger.warning("Operation completed but no instances were processed")
            print(json.dumps(result, indent=2))
        except Exception as e:
            logger.error(f"Operation failed: {str(e)}")
            raise
    else:
        logger.debug("Using default (live) output format")
        with Live(console=console, refresh_per_second=20) as live:
            update_task = asyncio.create_task(update_table(live))
            try:
                await perform_action()
                await asyncio.sleep(1)
                logger.debug("Main execution completed successfully")
            except Exception:
                logger.exception("Error in main execution")
                raise
            finally:
                logger.debug("Cleaning up and shutting down")
                table_update_event.set()
                await update_task

    logger.info(f"Completed {args.action} operation successfully")


if __name__ == "__main__":
    try:
        logger.debug("Script starting")
        asyncio.run(main())
        logger.debug("Script completed successfully")
    except Exception:
        logger.exception("Script failed with unhandled exception")
        raise
