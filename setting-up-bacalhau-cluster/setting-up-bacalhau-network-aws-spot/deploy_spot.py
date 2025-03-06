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

from util.config import (
    Config,
)  # Assuming util.config and util.scripts_provider are well-structured
from util.scripts_provider import ScriptsProvider

# --- Constants ---
# Define constants in UPPER_SNAKE_CASE for better readability and maintainability.
DEFAULT_FILTER_TAG_NAME = "ManagedBy"
DEFAULT_FILTER_TAG_VALUE = "SpotInstanceScript"
DEFAULT_CREATOR_VALUE = "BacalhauSpotScript"
DEFAULT_RESOURCE_PREFIX = "SpotInstance"
DEFAULT_VPC_NAME = "SpotInstanceVPC"
AWS_API_TIMEOUT = 30  # seconds

# --- Global Variables ---
# Minimize the use of globals.  If necessary, use descriptive names.
global_node_count = 0  # Total number of instances across all regions
all_statuses = {}  # Dictionary to track all instance statuses
status_lock = asyncio.Lock()  # Lock for thread-safe updates to all_statuses
table_update_event = (
    asyncio.Event()
)  # Event for signaling the table update task to stop
events_to_progress = []  # Events queue for progress tracking
task_name = "TASK NAME"  # Default task name for progress bar
task_total = 10000  # Default task total for progress bar

# --- Logging Setup ---
# Use a single, well-configured logger throughout the script.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Default level, will be updated based on args
logger.propagate = False  # Prevent propagation to root logger

# Create a file handler for detailed debug logs
file_handler = logging.FileHandler("debug.log", mode="w")  # Overwrite log on each run
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Initialize Rich console with auto-detection of width
console = Console()

# --- Configuration Loading ---
config = Config("config.yaml")  # Load configuration early


def get_user_input(
    script_name: str, instance_type: str, region: str
) -> tuple[str, str, str]:
    """
    Gets user input for the job, instance type, and region.

    Args:
        script_name: The default script name.
        instance_type: The default instance type.
        region: The default region.

    Returns:
        A tuple containing the job name, instance type, and region.
    """
    console.print(
        Panel(
            f"Using default values:\n"
            f"  - Script: [bold]{script_name}[/bold]\n"
            f"  - Instance Type: [bold]{instance_type}[/bold]\n"
            f"  - Region: [bold]{region}[/bold]",
            title="[bold]Default Configuration[/bold]",
            border_style="blue",
        )
    )

    if not console.is_terminal:  # Check if running in a terminal
        console.print(
            "[yellow]Not running in a terminal. Using default values for all inputs.[/yellow]"
        )
        return script_name, instance_type, region

    job_name = console.input(
        f"Enter job name (or press Enter to use script name '{script_name}'): "
    ).strip()
    job_name = job_name or script_name

    instance_type = console.input(
        f"Enter instance type (or press Enter to use '{instance_type}'): "
    ).strip()
    instance_type = instance_type or instance_type

    region = console.input(f"Enter region (or press Enter to use '{region}'): ").strip()
    region = region or region

    return job_name, instance_type, region


def configure_tags_and_names(
    job_name: str, script_name: str, region: str
) -> tuple[dict, str, str]:
    """
    Configures tags and resource names based on user input and constants.

    Args:
        job_name: The name of the job.
        script_name: The name of the script.
        region: The AWS region.

    Returns:
        A tuple containing the tags dictionary, instance name, and VPC name.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")  # ISO 8601-like
    instance_name = f"{DEFAULT_RESOURCE_PREFIX}-{job_name}-{timestamp}"
    vpc_name = f"{DEFAULT_VPC_NAME}-{timestamp}"

    tags = {
        DEFAULT_FILTER_TAG_NAME: DEFAULT_FILTER_TAG_VALUE,
        "Creator": DEFAULT_CREATOR_VALUE,
        "Job": job_name,
        "Script": script_name,
        "Region": region,  # Include region in tags
        "Timestamp": timestamp,  # Include timestamp in tags
        "Name": instance_name,  # Standard "Name" tag
    }

    return tags, instance_name, vpc_name


def parse_arguments():
    """
    Parses command-line arguments.

    Returns:
        An argparse.Namespace object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Launch and manage AWS Spot Instances for Bacalhau jobs."
    )
    parser.add_argument(
        "--script",
        "-s",
        type=str,
        default="generic_k8s.sh",
        help="The name of the script to run on the instance (default: generic_k8s.sh).",
    )
    parser.add_argument(
        "--instance-type",
        "-i",
        type=str,
        default="t2.micro",
        help="The AWS EC2 instance type (default: t2.micro).",
    )
    parser.add_argument(
        "--region",
        "-r",
        type=str,
        default="us-east-1",
        help="The AWS region to launch the instance in (default: us-east-1).",
    )
    parser.add_argument(
        "--max-wait-time",
        "-w",
        type=int,
        default=3600,
        help="Maximum time to wait for spot instance fulfillment (seconds, default: 3600).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without actually launching instances.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (debug level).",
    )
    parser.add_argument(
        "--number-of-instances",
        "-n",
        type=int,
        default=1,
        help="The number of instances to launch (default: 1).",
    )
    parser.add_argument(
        "--auto-shutdown",
        action="store_true",
        default=False,  # changed default
        help="Enable auto-shutdown of instances after idle timeout. (default: False)",
    )
    parser.add_argument(
        "--auto-shutdown-idle-timeout",
        type=int,
        default=600,  # 10 minutes
        help="Idle timeout in seconds before auto-shutdown. (default: 600)",
    )
    parser.add_argument(
        "--auto-shutdown-jobs-completed",
        type=int,
        default=5,
        help="The number of jobs after which the server will shut down. (default: 5)",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        help="The maximum hourly price for the spot instance.  If not provided, the on-demand price is used.",
    )

    args = parser.parse_args()

    # Set logging level based on --verbose flag.
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(
            logging.INFO
        )  # already defined as such, but just for completeness.

    # Add the Rich console handler *after* setting the level.
    console_handler = logging.StreamHandler(sys.stderr)  # Direct to stderr
    console_formatter = logging.Formatter("%(message)s")  # Simple format for console
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return args


async def get_availability_zone(
    client: botocore.client.BaseClient, instance_type: str, region: str
) -> str:
    """
    Gets the cheapest availability zone for the specified instance type in the given region.

    Args:
        client: The Boto3 EC2 client.
        instance_type: The AWS EC2 instance type.
        region: The AWS region.

    Returns:
        The name of the cheapest availability zone, or an empty string if no suitable zone is found.
    """
    try:
        response = await asyncio.to_thread(
            client.describe_instance_type_offerings,
            LocationType="availability-zone",
            Filters=[
                {"Name": "instance-type", "Values": [instance_type]},
                {
                    "Name": "location",
                    "Values": [region],
                },  # describe_instance_type_offerings requires the region with a location filter.
            ],
        )
        offerings = response["InstanceTypeOfferings"]
        if not offerings:
            logger.error(
                f"No offerings found for instance type '{instance_type}' in region '{region}'."
            )
            return ""

        # Find the cheapest availability zone.  In theory, describe_instance_type_offerings should
        # return all AZs, even if there is no Spot capacity, but we'll handle the case where it doesn't
        # just to be safe.
        cheapest_zone = offerings[0]["Location"]
        logger.debug(f"Chose availability zone: {cheapest_zone}")
        return cheapest_zone

    except botocore.exceptions.ClientError as e:
        logger.error(f"Error getting availability zone: {e}")
        return ""
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred: {e}"
        )  # catch-all for unexpected errors
        return ""


async def create_security_group(
    client: botocore.client.BaseClient, vpc_id: str, vpc_name: str, tags: dict
) -> str:
    """
    Creates a security group in the specified VPC.

    Args:
        client: The Boto3 EC2 client.
        vpc_id: The ID of the VPC.
        vpc_name: The name of the VPC.
        tags: Tags to apply to the security group.

    Returns:
        The ID of the created security group, or an empty string on failure.
    """
    try:
        response = await asyncio.to_thread(
            client.create_security_group,
            GroupName=vpc_name,
            Description="Security group for Spot Instance",
            VpcId=vpc_id,
            TagSpecifications=[
                {"ResourceType": "security-group", "Tags": convert_tags(tags)}
            ],
        )
        security_group_id = response["GroupId"]
        logger.info(f"Created security group '{vpc_name}' with ID: {security_group_id}")

        # Authorize ingress traffic (inbound rules)
        await asyncio.to_thread(
            client.authorize_security_group_ingress,
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "-1",  # Allow all protocols
                    "FromPort": -1,  # Allow all ports
                    "ToPort": -1,  # Allow all ports
                    "IpRanges": [
                        {
                            "CidrIp": "0.0.0.0/0",
                            "Description": "Allow all inbound traffic",
                        }
                    ],
                }
            ],
        )
        logger.info(
            f"Authorized inbound traffic for security group '{security_group_id}'"
        )
        return security_group_id

    except botocore.exceptions.ClientError as e:
        if "already exists" in str(e):
            logger.info(
                f"Security group '{vpc_name}' already exists, attempting to find it..."
            )
            try:
                response = await asyncio.to_thread(
                    client.describe_security_groups,
                    Filters=[
                        {"Name": "group-name", "Values": [vpc_name]},
                        {"Name": "vpc-id", "Values": [vpc_id]},
                    ],
                )

                if response["SecurityGroups"]:
                    security_group_id = response["SecurityGroups"][0]["GroupId"]
                    logger.info(f"Found existing security group: {security_group_id}")
                    return security_group_id
                else:
                    logger.error(f"Security group '{vpc_name}' not found.")
                    return ""

            except botocore.exceptions.ClientError as ex:
                logger.error(f"Error finding existing security group: {ex}")
                return ""
        else:
            logger.error(f"Error creating security group: {e}")
            return ""
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")  # catch all
        return ""


def convert_tags(tags: dict) -> list:
    """Converts a dictionary of tags to the format required by Boto3."""
    return [{"Key": k, "Value": v} for k, v in tags.items()]


async def create_vpc(
    client: botocore.client.BaseClient, vpc_name: str, tags: dict
) -> tuple[str, str]:
    """
    Creates a VPC and its associated resources (subnet, internet gateway, route table).

    Args:
        client: The Boto3 EC2 client.
        vpc_name: The name of the VPC.
        tags: Tags to apply to the VPC resources.

    Returns:
        A tuple containing the VPC ID and subnet ID, or (None, None) on failure.
    """
    try:
        # Create VPC
        response = await asyncio.to_thread(
            client.create_vpc,
            CidrBlock="10.0.0.0/16",  # Use a /16 CIDR block
            TagSpecifications=[{"ResourceType": "vpc", "Tags": convert_tags(tags)}],
        )
        vpc_id = response["Vpc"]["VpcId"]
        logger.info(f"Created VPC '{vpc_name}' with ID: {vpc_id}")

        # Wait for VPC to become available
        await wait_for_resource(client, "vpc_available", "VPC", vpc_id)

        # Create Subnet
        response = await asyncio.to_thread(
            client.create_subnet,
            VpcId=vpc_id,
            CidrBlock="10.0.1.0/24",  # Use a /24 CIDR block within the VPC
            TagSpecifications=[{"ResourceType": "subnet", "Tags": convert_tags(tags)}],
        )
        subnet_id = response["Subnet"]["SubnetId"]
        logger.info(f"Created subnet with ID: {subnet_id}")

        # Wait for Subnet to become available
        await wait_for_resource(client, "subnet_available", "Subnet", subnet_id)

        # Create Internet Gateway
        response = await asyncio.to_thread(
            client.create_internet_gateway,
            TagSpecifications=[
                {"ResourceType": "internet-gateway", "Tags": convert_tags(tags)}
            ],
        )
        internet_gateway_id = response["InternetGateway"]["InternetGatewayId"]
        logger.info(f"Created internet gateway with ID: {internet_gateway_id}")

        # Attach Internet Gateway to VPC
        await asyncio.to_thread(
            client.attach_internet_gateway,
            InternetGatewayId=internet_gateway_id,
            VpcId=vpc_id,
        )
        logger.info(f"Attached internet gateway {internet_gateway_id} to VPC {vpc_id}")

        # Create Route Table
        response = await asyncio.to_thread(
            client.create_route_table,
            VpcId=vpc_id,
            TagSpecifications=[
                {"ResourceType": "route-table", "Tags": convert_tags(tags)}
            ],
        )
        route_table_id = response["RouteTable"]["RouteTableId"]
        logger.info(f"Created route table with ID: {route_table_id}")

        # Create Route to Internet Gateway
        await asyncio.to_thread(
            client.create_route,
            RouteTableId=route_table_id,
            DestinationCidrBlock="0.0.0.0/0",  # Route all traffic
            GatewayId=internet_gateway_id,
        )
        logger.info(
            f"Created route to internet gateway in route table {route_table_id}"
        )

        # Associate Route Table with Subnet
        await asyncio.to_thread(
            client.associate_route_table,
            RouteTableId=route_table_id,
            SubnetId=subnet_id,
        )
        logger.info(f"Associated route table {route_table_id} with subnet {subnet_id}")

        return vpc_id, subnet_id

    except botocore.exceptions.ClientError as e:
        if "already exists" in str(e):
            logger.info(f"VPC '{vpc_name}' already exists, attempting to find it...")
            try:
                # Find existing VPC
                response = await asyncio.to_thread(
                    client.describe_vpcs,
                    Filters=[{"Name": "tag:Name", "Values": [vpc_name]}],
                )
                if response["Vpcs"]:
                    vpc_id = response["Vpcs"][0]["VpcId"]
                    logger.info(f"Found existing VPC: {vpc_id}")

                    # Find existing Subnet within the VPC
                    response = await asyncio.to_thread(
                        client.describe_subnets,
                        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                    )

                    if response["Subnets"]:
                        subnet_id = response["Subnets"][0]["SubnetId"]
                        logger.info(f"Found existing subnet: {subnet_id}")
                        return vpc_id, subnet_id
                    else:
                        logger.error(f"No subnet found in existing VPC '{vpc_name}'.")
                        return None, None
                else:
                    logger.error(f"VPC '{vpc_name}' not found.")
                    return None, None

            except botocore.exceptions.ClientError as ex:
                logger.error(f"Error finding existing VPC: {ex}")
                return None, None

        else:
            logger.error(f"Error creating VPC: {e}")
            return None, None
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")  # catch all
        return None, None


async def wait_for_resource(
    client: botocore.client.BaseClient,
    waiter_name: str,
    resource_type: str,
    resource_id: str,
):
    """
    Waits for an AWS resource to reach a desired state.

    Args:
        client: The Boto3 client.
        waiter_name: The name of the waiter (e.g., 'vpc_available', 'subnet_available').
        resource_type: The type of the resource (e.g., 'VPC', 'Subnet').
        resource_id: The ID of the resource.
    """
    waiter = client.get_waiter(waiter_name)
    try:
        await asyncio.to_thread(waiter.wait, **{f"{resource_type}Ids": [resource_id]})
        logger.debug(f"{resource_type} '{resource_id}' is now available.")
    except botocore.exceptions.WaiterError as e:
        logger.error(f"Error waiting for {resource_type} '{resource_id}': {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while waiting {e}")


async def run_spot_instance(
    client: botocore.client.BaseClient,
    script_name: str,
    instance_type: str,
    region: str,
    max_wait_time: int,
    tags: dict,
    instance_name: str,
    vpc_id: str,
    subnet_id: str,
    security_group_id: str,
    number_of_instances: int,
    user_data: str,
    max_price: float | None,
) -> list:
    """
    Requests a Spot Instance.

    Args:
        client: The Boto3 EC2 client.
        script_name: The name of the script to run.
        instance_type: The instance type.
        region: The AWS region.
        max_wait_time: The maximum time to wait for the request to be fulfilled (seconds).
        tags: Tags to apply to the instance.
        instance_name: The name of the instance.
        vpc_id: The ID of the VPC.
        subnet_id: The ID of the subnet.
        security_group_id: The ID of the security group.
        number_of_instances: The number of instances to launch.
        user_data: base64 encoded user data
        max_price: The maximum hourly price for the Spot Instance

    Returns:
        A list of instance IDs, or an empty list on failure.
    """
    try:
        spot_request_args = {
            "InstanceCount": number_of_instances,
            "Type": "one-time",  # or "persistent" if needed
            "LaunchSpecification": {
                "ImageId": get_ami_id(client, region, instance_type),
                "InstanceType": instance_type,
                "SubnetId": subnet_id,
                "SecurityGroupIds": [security_group_id],
                "UserData": user_data,
                "Placement": {
                    "AvailabilityZone": await get_availability_zone(
                        client, instance_type, region
                    )
                },
            },
            "TagSpecifications": [
                {"ResourceType": "spot-instances-request", "Tags": convert_tags(tags)}
            ],
        }

        # Add Max Price if specified.  Otherwise, AWS defaults to on-demand price.
        if max_price:
            spot_request_args["SpotPrice"] = str(max_price)

        response = await asyncio.to_thread(
            client.request_spot_instances, **spot_request_args
        )

        spot_instance_request_ids = [
            request["SpotInstanceRequestId"]
            for request in response["SpotInstanceRequests"]
        ]
        logger.info(
            f"Requested {number_of_instances} Spot Instance(s). Request IDs: {spot_instance_request_ids}"
        )

        # Wait for spot requests to be fulfilled
        fulfilled_instance_ids = await wait_for_spot_fulfillment(
            client, spot_instance_request_ids, max_wait_time, tags
        )
        return fulfilled_instance_ids

    except botocore.exceptions.ClientError as e:
        logger.error(f"Error requesting Spot Instance: {e}")
        return []
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")  # catch all
        return []


def get_ami_id(client, region: str, instance_type: str) -> str:
    """Gets the appropriate AMI ID for the given region and instance type.

    We choose an Ubuntu 22.04 image.  Different instance types (e.g., ARM-based)
    require different AMIs.
    """
    architecture = (
        "arm64"
        if instance_type.startswith(("a", "t4g", "g", "m6g", "c7g"))
        else "x86_64"
    )

    # Filters for official Ubuntu 22.04 AMIs
    filters = [
        {
            "Name": "name",
            "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-*-server-*"],
        },
        {"Name": "architecture", "Values": [architecture]},
        {"Name": "owner-alias", "Values": ["amazon"]},  # Official Ubuntu AMIs
        {"Name": "state", "Values": ["available"]},
        {"Name": "root-device-type", "Values": ["ebs"]},
        {"Name": "virtualization-type", "Values": ["hvm"]},
    ]
    response = client.describe_images(Filters=filters)
    # Sort by creation date descending, so the newest image is first
    images = sorted(response["Images"], key=lambda x: x["CreationDate"], reverse=True)

    if images:
        ami_id = images[0]["ImageId"]
        logger.debug(
            f"Using AMI ID: {ami_id} for instance type {instance_type} in {region}"
        )
        return ami_id
    else:
        logger.error(
            f"No suitable AMI found for instance type {instance_type} in {region}."
        )
        raise ValueError(
            f"No suitable AMI found for instance type {instance_type} in {region}."
        )


async def wait_for_spot_fulfillment(
    client: botocore.client.BaseClient,
    spot_request_ids: list[str],
    max_wait_time: int,
    tags: dict,
) -> list[str]:
    """
    Waits for Spot Instance requests to be fulfilled.

    Args:
        client: The Boto3 EC2 client.
        spot_request_ids: A list of Spot Instance request IDs.
        max_wait_time: The maximum time to wait (in seconds).
        tags: tags for created instances

    Returns:
        A list of instance IDs of the fulfilled instances, or an empty list if none were fulfilled.
    """
    fulfilled_instance_ids = []
    start_time = time.time()

    try:
        while time.time() - start_time < max_wait_time:
            response = await asyncio.to_thread(
                client.describe_spot_instance_requests,
                SpotInstanceRequestIds=spot_request_ids,
            )
            for request in response["SpotInstanceRequests"]:
                if request["State"] == "active" and "InstanceId" in request:
                    instance_id = request["InstanceId"]
                    if instance_id not in fulfilled_instance_ids:
                        fulfilled_instance_ids.append(instance_id)
                        logger.info(
                            f"Spot Instance request fulfilled. Instance ID: {instance_id}"
                        )

                        # Tag the instance
                        await asyncio.to_thread(
                            client.create_tags,
                            Resources=[instance_id],
                            Tags=convert_tags(tags),
                        )
                        logger.debug(f"Tagged instance {instance_id} with tags: {tags}")

            if len(fulfilled_instance_ids) == len(spot_request_ids):
                logger.info("All spot instances requests fulfilled")
                return fulfilled_instance_ids  # All requests fulfilled

            await asyncio.sleep(5)  # Check every 5 seconds

        logger.warning(
            f"Timed out waiting for Spot Instance requests. Fulfilled: {len(fulfilled_instance_ids)}/{len(spot_request_ids)}"
        )
        return fulfilled_instance_ids  # Return whatever instances *were* fulfilled

    except botocore.exceptions.ClientError as e:
        logger.error(f"Error waiting for Spot Instance fulfillment: {e}")
        return fulfilled_instance_ids  # Return what we have, even if it's an error
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")  # catch-all
        return fulfilled_instance_ids


async def describe_instance_status(
    client: botocore.client.BaseClient, instance_id: str
) -> dict | None:
    """
    Describes the status of a single EC2 instance.

    Args:
        client: The Boto3 EC2 client.
        instance_id: The ID of the instance.

    Returns:
        A dictionary containing the instance status, or None if an error occurs.
    """
    try:
        response = await asyncio.to_thread(
            client.describe_instances, InstanceIds=[instance_id]
        )
        if response["Reservations"]:
            return response["Reservations"][0]["Instances"][0]
        else:
            logger.warning(f"Instance '{instance_id}' not found.")
            return None  # Instance not found
    except botocore.exceptions.ClientError as e:
        logger.error(f"Error describing instance '{instance_id}': {e}")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error when describing instance status for {instance_id}"
        )
        return None


async def handle_instance_state(
    instance_id: str, current_state: str, region: str, job_name: str
):
    """
    Handles instance state transitions and updates the global status.

    This function is designed to be thread-safe.  It uses a lock to
    protect the global `all_statuses` dictionary.

    Args:
        instance_id: The ID of the instance.
        current_state: The current state of the instance (e.g., "running", "pending").
        region: aws region.
        job_name: name of the current job.
    """
    global global_node_count, all_statuses

    async with status_lock:
        if instance_id not in all_statuses:
            global_node_count += 1
            all_statuses[instance_id] = {
                "state": current_state,
                "region": region,
                "job": job_name,
                "last_update": time.time(),
            }
            # Enqueue a table update for every new instance.
            events_to_progress.append({"type": "start"})
        elif all_statuses[instance_id]["state"] != current_state:
            # Only log state *changes*.
            logger.info(
                f"Instance {instance_id} state changed: {all_statuses[instance_id]['state']} -> {current_state}"
            )
            all_statuses[instance_id]["state"] = current_state
            all_statuses[instance_id]["last_update"] = time.time()
            events_to_progress.append({"type": "update"})
        else:
            all_statuses[instance_id]["last_update"] = time.time()


async def run_instances_in_region(
    region: str,
    args: argparse.Namespace,
    job_name: str,
    script_name: str,
    user_data: str,
):
    """
    Launches and monitors Spot Instances in a single region.

    Args:
        region: The AWS region to launch instances in.
        args: The parsed command-line arguments.
        job_name: job name.
        script_name: selected script name.
        user_data: base64 encoded user data.
    """
    global all_statuses
    client = None  # Initialize client variable

    try:
        # Validate region
        if not region:
            logger.error("Region cannot be empty")
            return

        # Create an EC2 client for the region
        client = boto3.client(
            "ec2",
            region_name=region,
            config=botocore.config.Config(
                retries={"max_attempts": 10, "mode": "standard"}
            ),
        )

        # Configure tags and names
        tags, instance_name, vpc_name = configure_tags_and_names(
            job_name, script_name, region
        )
        # Create VPC and related resources
        vpc_id, subnet_id = await create_vpc(client, vpc_name, tags)
        if vpc_id is None or subnet_id is None:
            logger.error(f"Failed to create VPC in region {region}.")
            return
        # Create security group
        security_group_id = await create_security_group(client, vpc_id, vpc_name, tags)
        if security_group_id is None:
            logger.error(f"Failed to create security group in region {region}.")
            return

        # Get job name before it is potentially changed by f-string in configure_tags_and_names.
        job_name = f"{script_name}"
        scripts_provider = ScriptsProvider(config)
        selected_script = scripts_provider.get_script_by_name(script_name)

        # If no script is found, use empty user data
        if selected_script is None:
            console.print(
                f"[yellow]No startup script '{script_name}' found. Instance will start without a custom script.[/yellow]"
            )
            user_data = ""
        else:
            # Encode script content if found
            user_data = base64.b64encode(
                selected_script.content.encode("utf-8")
            ).decode("utf-8")

        # Run Spot Instances
        instance_ids = await run_spot_instance(
            client,
            script_name,
            args.instance_type,
            region,
            args.max_wait_time,
            tags,
            instance_name,
            vpc_id,
            subnet_id,
            security_group_id,
            args.number_of_instances,
            user_data,
            args.max_price,
        )

        if not instance_ids:
            logger.error(f"No instances launched in region {region}.")
            return

        # Initial status update for all launched instances.
        for instance_id in instance_ids:
            instance_status = await describe_instance_status(client, instance_id)
            if instance_status:
                await handle_instance_state(
                    instance_id, instance_status["State"]["Name"], region, job_name
                )

        # Monitor instance status until all instances are terminated or an error occurs.
        while True:
            all_terminated = (
                True  # Assume all instances are terminated until proven otherwise
            )
            for instance_id in instance_ids:
                instance_status = await describe_instance_status(client, instance_id)

                if instance_status is None:  # instance not found
                    async with status_lock:
                        if instance_id in all_statuses:
                            del all_statuses[instance_id]  # remove from active tracking
                    continue

                current_state = instance_status["State"]["Name"]
                await handle_instance_state(
                    instance_id, current_state, region, job_name
                )

                if current_state.lower() != "terminated":
                    all_terminated = False

            if all_terminated:
                logger.info(f"All instances in region {region} have terminated.")
                break

            await asyncio.sleep(5)  # wait before next status check.

    except Exception as e:
        logger.exception(f"An unexpected error occurred in region {region}: {e}")
    finally:
        if client:
            client.close()


async def update_table(progress: Progress, task):
    """Updates the Rich table with the current instance status."""
    global all_statuses

    last_total_nodes = 0

    while not table_update_event.is_set():
        # Handle progress bar events
        progress.start_task(task)
        while events_to_progress:
            event = events_to_progress.pop()
            if event["type"] == "start":
                progress.reset(task, total=task_total)
            elif event["type"] == "update":
                progress.update(task, advance=1)
        progress.update(
            task, total=global_node_count, description=task_name
        )  # Update total to current number of nodes

        table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("Instance ID", style="cyan", no_wrap=True)
        table.add_column("State", style="green")
        table.add_column("Region", style="magenta")
        table.add_column("Job", style="yellow")
        table.add_column("Last Update (s ago)", style="blue")

        async with status_lock:  # Acquire lock for reading all_statuses
            for instance_id, status in all_statuses.items():
                last_update = int(time.time() - status["last_update"])
                table.add_row(
                    instance_id,
                    status["state"],
                    status["region"],
                    status["job"],
                    str(last_update),
                )

        if table.row_count > 0:  # Only update if there are rows
            progress.print(table)  # replace previous table

        await asyncio.sleep(1)  # Update table every 1 second

    logger.debug("Table update task stopped.")
    progress.update(task, completed=task_total, description="Finished")
    progress.stop_task(task)
    progress.stop()


async def main():
    """Main function to run the script."""
    global all_statuses, global_node_count, task_name, task_total

    args = parse_arguments()
    console.print(f"Job Start time: {datetime.now()}")

    # Get user input
    script_name, instance_type, region = get_user_input(
        args.script, args.instance_type, args.region
    )
    # Get job name before it is potentially changed by f-string in configure_tags_and_names.
    job_name = f"{script_name}"
    scripts_provider = ScriptsProvider(config)
    selected_script = scripts_provider.get_script_by_name(script_name)

    # If no script is found, use empty user data
    if selected_script is None:
        console.print(
            f"[yellow]No startup script '{script_name}' found. Instance will start without a custom script.[/yellow]"
        )
        user_data = ""
    else:
        # Encode script content if found
        user_data = base64.b64encode(selected_script.content.encode("utf-8")).decode(
            "utf-8"
        )

    # Validate region
    if not region:
        console.print(
            "[bold red]Region cannot be empty. Please provide a valid region.[/bold red]"
        )
        return

    regions = (
        [region]
        if region != "all"
        else [
            r["RegionName"] for r in boto3.client("ec2").describe_regions()["Regions"]
        ]
    )
    task_name = f"Running Instances"
    task_total = len(regions) * args.number_of_instances

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # Keep the progress bar visible after completion
    )
    task = progress.add_task(task_name, total=task_total)
    # Start the table update task
    table_task = asyncio.create_task(update_table(progress, task))

    # Run instances in each region concurrently
    tasks = [
        run_instances_in_region(r, args, job_name, script_name, user_data)
        for r in regions
    ]
    await asyncio.gather(*tasks)

    # Stop the table update task
    table_update_event.set()  # Signal the table update task to stop
    await table_task  # Wait for the table task to finish

    console.print(f"Job End time: {datetime.now()}")

    # Check if --auto-shutdown flag used.
    if not args.auto_shutdown:
        console.print(
            "[yellow]Auto Shutdown is not activated, the instances need to be stopped manually.[/yellow]"
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Exiting...[/bold red]")
        table_update_event.set()  # Ensure the table update task stops
        sys.exit(1)
    except Exception:
        console.print_exception()
