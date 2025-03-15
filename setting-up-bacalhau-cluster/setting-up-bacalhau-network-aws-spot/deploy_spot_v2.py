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

# AWS regions where we can launch instances
AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-north-1",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "sa-east-1",
    "ca-central-1",
]

# Tags for identifying resources created by this script
FILTER_TAG_NAME = DEFAULT_FILTER_TAG_NAME
FILTER_TAG_VALUE = DEFAULT_FILTER_TAG_VALUE

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
operation_logs = []  # Queue of operation logs to display in the console
operation_logs_lock = asyncio.Lock()  # Lock for thread-safe updates to operation logs
max_operation_logs = 15  # Maximum number of operation logs to keep

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
file_handler.setLevel(logging.DEBUG)  # Ensure file gets all logs
logger.addHandler(file_handler)

# Disable other loggers that might print to stderr
logging.getLogger("botocore").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)


# Null IO for redirecting stdout/stderr
class NullIO:
    def write(self, *args, **kwargs):
        pass

    def flush(self, *args, **kwargs):
        pass


# Initialize Rich console with auto-detection of width and force terminal colors
console = Console(force_terminal=True, color_system="auto")

# --- Configuration Loading ---
config = Config("config.yaml")  # Load configuration early


# Add machine tracking to JSON file
def save_machines_to_json(machines: dict):
    """Save machine information to MACHINES.json file"""
    try:
        with open("MACHINES.json", "w") as f:
            json.dump(machines, f, indent=2)
        logger.info("Machine information saved to MACHINES.json")
    except Exception as e:
        logger.error(f"Failed to save machine information to MACHINES.json: {e}")


def load_machines_from_json() -> dict:
    """Load machine information from MACHINES.json file if it exists"""
    try:
        with open("MACHINES.json", "r") as f:
            raw_machines = json.load(f)

        # Validate and clean up loaded data
        valid_machines = {}
        invalid_count = 0

        for instance_id, info in raw_machines.items():
            # Make sure each entry is a dictionary with the required fields
            if isinstance(info, dict) and "state" in info and "region" in info:
                valid_machines[instance_id] = info
            else:
                invalid_count += 1
                logger.warning(
                    f"Invalid entry in MACHINES.json for instance {instance_id}: {info}"
                )

        if invalid_count > 0:
            logger.warning(
                f"Removed {invalid_count} invalid entries from MACHINES.json"
            )
            # Save the cleaned data back to the file
            with open("MACHINES.json", "w") as f:
                json.dump(valid_machines, f, indent=2)

        logger.info(
            f"Loaded information for {len(valid_machines)} machines from MACHINES.json"
        )
        return valid_machines
    except FileNotFoundError:
        logger.info("No MACHINES.json file found, starting with empty state")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Malformed MACHINES.json file: {e}")
        # Backup the problematic file
        try:
            os.rename("MACHINES.json", f"MACHINES.json.bak.{int(time.time())}")
            logger.info("Backed up corrupted MACHINES.json file")
        except Exception as backup_error:
            logger.error(f"Failed to backup corrupted MACHINES.json: {backup_error}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load MACHINES.json: {e}")
        return {}


def get_config_values(args: argparse.Namespace, config: Config) -> tuple[str, str, str]:
    """
    Gets values from config.yaml or command-line arguments without user interaction.

    Args:
        args: The parsed command-line arguments.
        config: The loaded configuration.

    Returns:
        A tuple containing the job name (script name), instance type (may be None for multi-region), and region.

    Raises:
        ValueError: If a required value is missing from both config and arguments.
    """
    # Get script name - command line has priority
    script_name = args.script
    if not script_name:
        # Could try to get a default script from config here if needed
        raise ValueError("Script name is required but not provided in arguments")

    # Get region - from command line
    region = args.region

    # If not specified, try to get from config
    if not region:
        # Try to get the first region from config
        try:
            first_region_dict = config.get("regions", [])[0]
            region = next(iter(first_region_dict.keys()))
        except (IndexError, StopIteration, AttributeError, TypeError):
            raise ValueError(
                "Region is required but not provided in arguments or config"
            )

    # For instance_type - only get it here if we're working with a single region
    # Otherwise, it will be handled in run_instances_in_region for each specific region
    instance_type = None
    if region != "all" and args.instance_type:
        # If specified in args, use that
        instance_type = args.instance_type
    elif region != "all":
        # Find this region in config
        region_config = None
        for region_entry in config.get("regions", []):
            if region in region_entry:
                region_config = region_entry[region]
                break

        if region_config and region_config.get("machine_type") != "auto":
            instance_type = region_config.get("machine_type")
            logger.info(
                f"Using instance type {instance_type} for region {region} from config.yaml"
            )
        else:
            # Get instance type from available_regions if not in config
            try:
                from available_regions import REGION_DETAILS

                if region in REGION_DETAILS:
                    instance_type = REGION_DETAILS[region]["instance_type"]
                    logger.info(
                        f"Using instance type {instance_type} for region {region} from available_regions.py"
                    )
                else:
                    instance_type = "t3.medium"  # Default fallback
                    logger.info(
                        f"No instance type found for region {region}, using default: {instance_type}"
                    )
            except (ImportError, KeyError):
                instance_type = "t3.medium"  # Default fallback
                logger.info(
                    f"Could not determine instance type for region {region}, using default: {instance_type}"
                )

    # For "all" regions case, we'll determine the instance type per region in run_instances_in_region
    if region == "all":
        logger.info(
            "Using per-region instance types from config.yaml for multi-region deployment"
        )
    else:
        logger.info(
            f"Using non-interactive values - Script: {script_name}, Instance Type: {instance_type}, Region: {region}"
        )

    return script_name, instance_type, region


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
    Parses command-line arguments with subcommands for create, destroy, and nuke operations.

    Returns:
        An argparse.Namespace object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Launch and manage AWS Spot Instances for Bacalhau jobs."
    )

    # Global arguments that apply to all commands
    parser.add_argument(
        "--format",
        choices=["json"],
        help="Output format. If 'json' is specified, output will be in JSON format.",
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create command - default if no command is specified
    create_parser = subparsers.add_parser("create", help="Create new spot instances")
    create_parser.add_argument(
        "--script",
        "-s",
        type=str,
        default="generic_k8s.sh",
        help="The name of the script to run on the instance (default: generic_k8s.sh).",
    )
    create_parser.add_argument(
        "--instance-type",
        "-i",
        type=str,
        default=None,
        help="The AWS EC2 instance type (default: from config or t3.medium).",
    )
    create_parser.add_argument(
        "--region",
        "-r",
        type=str,
        default=None,
        help="The AWS region to launch the instance in (default: from config or us-east-1).",
    )
    create_parser.add_argument(
        "--max-wait-time",
        "-w",
        type=int,
        default=3600,
        help="Maximum time to wait for spot instance fulfillment (seconds, default: 3600).",
    )
    create_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without actually launching instances.",
    )
    create_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (debug level).",
    )
    create_parser.add_argument(
        "--number-of-instances",
        "-n",
        type=int,
        default=1,
        help="The number of instances to launch (default: 1).",
    )
    create_parser.add_argument(
        "--auto-shutdown",
        action="store_true",
        default=False,
        help="Enable auto-shutdown of instances after idle timeout. (default: False)",
    )
    create_parser.add_argument(
        "--auto-shutdown-idle-timeout",
        type=int,
        default=600,  # 10 minutes
        help="Idle timeout in seconds before auto-shutdown. (default: 600)",
    )
    create_parser.add_argument(
        "--auto-shutdown-jobs-completed",
        type=int,
        default=5,
        help="The number of jobs after which the server will shut down. (default: 5)",
    )
    create_parser.add_argument(
        "--max-price",
        type=float,
        help="The maximum hourly price for the spot instance. If not provided, the on-demand price is used.",
    )

    # Destroy command - terminates instances based on criteria
    destroy_parser = subparsers.add_parser(
        "destroy", help="Terminate specific instances"
    )
    destroy_parser.add_argument(
        "--region",
        "-r",
        type=str,
        default=None,
        help="Terminate instances in a specific region (default: all regions)",
    )
    destroy_parser.add_argument(
        "--job",
        "-j",
        type=str,
        help="Terminate instances running a specific job",
    )
    destroy_parser.add_argument(
        "--instance-id",
        "-i",
        type=str,
        help="Terminate a specific instance by ID",
    )
    destroy_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (debug level).",
    )
    destroy_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    # Nuke command - terminates all instances created by this script
    nuke_parser = subparsers.add_parser(
        "nuke", help="Terminate all instances created by this script"
    )
    nuke_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )
    nuke_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (debug level).",
    )

    args = parser.parse_args()

    # If no command is provided, default to 'create'
    if not args.command:
        args.command = "create"

    # Set logging level based on --verbose flag.
    if hasattr(args, "verbose") and args.verbose:
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

    except botocore.exceptions.TokenRetrievalError as e:
        logger.error(f"AWS authentication error: {e}")
        console.print(f"[bold red]AWS Authentication Error: {e}[/bold red]")
        console.print(
            "[yellow]Please refresh your AWS credentials by running:[/yellow]"
        )
        console.print(
            "[blue]aws sso login[/blue] or the appropriate authentication command for your setup"
        )
        return None, None
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
        # Map resource types to their correct AWS parameter names
        param_mapping = {
            "VPC": "VpcIds",
            "Subnet": "SubnetIds",
            "Instance": "InstanceIds",
            "SecurityGroup": "GroupIds",
            "InternetGateway": "InternetGatewayIds",
        }
        param_name = param_mapping.get(resource_type)
        if not param_name:
            param_name = f"{resource_type}Ids"  # Fallback for unmapped types

        await asyncio.to_thread(waiter.wait, **{param_name: [resource_id]})
        logger.debug(f"{resource_type} '{resource_id}' is now available.")
    except botocore.exceptions.WaiterError as e:
        logger.error(f"Error waiting for {resource_type} '{resource_id}': {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while waiting: {e}")


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
    """Gets the appropriate AMI ID for the given region and instance type."""
    # Determine the architecture based on instance type
    architecture = (
        "arm64"
        if instance_type.startswith("a1") or instance_type.startswith("t4g")
        else "x86_64"
    )

    # First try to load from cached file
    try:
        with open("ubuntu_amis.json", "r") as f:
            ami_data = json.load(f)
            if region in ami_data and architecture in ami_data[region]:
                return ami_data[region][architecture]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning(
            f"Could not load AMI ID from ubuntu_amis.json: {e}. Will query AWS API instead."
        )

    # Fallback to querying AWS API if file method failed
    try:
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
        images = sorted(
            response["Images"],
            key=lambda x: x["CreationDate"],
            reverse=True,
        )
        if not images:
            raise ValueError(
                f"No suitable Ubuntu AMI found for {architecture} in {region}"
            )
        return images[0]["ImageId"]
    except Exception as e:
        logger.error(f"Error getting AMI ID: {str(e)}")
        raise


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
    region = client.meta.region_name  # Get region from client
    
    # Log the initial spot request status
    await log_operation(f"Waiting for {len(spot_request_ids)} spot request(s) to be fulfilled", "info", region)
    for req_id in spot_request_ids:
        await log_operation(f"Monitoring spot request: {req_id}", "info", region)

    try:
        progress_updates = 0
        while time.time() - start_time < max_wait_time:
            response = await asyncio.to_thread(
                client.describe_spot_instance_requests,
                SpotInstanceRequestIds=spot_request_ids,
            )
            
            for request in response["SpotInstanceRequests"]:
                request_id = request["SpotInstanceRequestId"]
                request_state = request.get("State", "unknown")
                request_status = request.get("Status", {}).get("Code", "unknown")
                
                # Log status updates but avoid flooding logs with repeated messages
                if "InstanceId" not in request and progress_updates % 6 == 0:  # Every ~30 seconds
                    await log_operation(f"Spot request {request_id} status: {request_state}/{request_status}", "info", region)
                
                if request_state == "active" and "InstanceId" in request:
                    instance_id = request["InstanceId"]
                    if instance_id not in fulfilled_instance_ids:
                        fulfilled_instance_ids.append(instance_id)
                        logger.info(
                            f"Spot Instance request fulfilled. Instance ID: {instance_id}"
                        )
                        await log_operation(f"Spot request fulfilled! Instance ID: {instance_id}", "info", region)

                        # Tag the instance
                        await asyncio.to_thread(
                            client.create_tags,
                            Resources=[instance_id],
                            Tags=convert_tags(tags),
                        )
                        logger.debug(f"Tagged instance {instance_id} with tags: {tags}")
                        await log_operation(f"Tagged instance with metadata", "info", region)
                elif request_state == "failed":
                    # Log failed spot requests with error details
                    error_code = request.get("Status", {}).get("Code", "Unknown")
                    error_message = request.get("Status", {}).get("Message", "No error message")
                    await log_operation(f"Spot request {request_id} failed: {error_code} - {error_message}", "error", region)

            if len(fulfilled_instance_ids) == len(spot_request_ids):
                logger.info("All spot instances requests fulfilled")
                await log_operation(f"All {len(spot_request_ids)} spot requests fulfilled!", "info", region)
                return fulfilled_instance_ids  # All requests fulfilled

            # Increment progress counter for throttling log messages
            progress_updates += 1
            
            await asyncio.sleep(5)  # Check every 5 seconds

        # If we reach here, we timed out
        pending_count = len(spot_request_ids) - len(fulfilled_instance_ids)
        logger.warning(
            f"Timed out waiting for Spot Instance requests. Fulfilled: {len(fulfilled_instance_ids)}/{len(spot_request_ids)}"
        )
        await log_operation(
            f"Timed out waiting for {pending_count} spot request(s). {len(fulfilled_instance_ids)} were fulfilled.", 
            "warn", 
            region
        )
        return fulfilled_instance_ids  # Return whatever instances *were* fulfilled

    except botocore.exceptions.ClientError as e:
        logger.error(f"Error waiting for Spot Instance fulfillment: {e}")
        await log_operation(f"Error waiting for spot fulfillment: {str(e)}", "error", region)
        return fulfilled_instance_ids  # Return what we have, even if it's an error
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")  # catch-all
        await log_operation(f"Unexpected error: {str(e)}", "error", region)
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
        if response["Reservations"] and response["Reservations"][0]["Instances"]:
            return response["Reservations"][0]["Instances"][0]
        else:
            logger.warning(f"Instance '{instance_id}' not found.")
            return None  # Instance not found
    except botocore.exceptions.ClientError as e:
        if "InvalidInstanceID.NotFound" in str(e):
            logger.info(f"Instance '{instance_id}' no longer exists.")
            return None
        logger.error(f"Error describing instance '{instance_id}': {e}")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error when describing instance status for {instance_id}"
        )
        return None


async def handle_instance_state(
    instance_id: str,
    current_state: str,
    region: str,
    job_name: str,
    instance_status: dict = None,
):
    """
    Handles instance state transitions and updates the global status.

    This function is designed to be thread-safe. It uses a lock to
    protect the global `all_statuses` dictionary and updates MACHINES.json.

    Args:
        instance_id: The ID of the instance.
        current_state: The current state of the instance (e.g., "running", "pending").
        region: aws region.
        job_name: name of the current job.
        instance_status: Full instance status data (optional)
    """
    global global_node_count, all_statuses
    timestamp = time.time()

    async with status_lock:
        # Track if this is a new or changed instance for MACHINES.json updates
        is_new = instance_id not in all_statuses
        is_changed = not is_new and all_statuses[instance_id]["state"] != current_state

        if is_new:
            global_node_count += 1
            all_statuses[instance_id] = {
                "state": current_state,
                "region": region,
                "job": job_name,
                "last_update": timestamp,
                "created_at": timestamp,
            }

            # Add additional info from instance_status if available
            if instance_status:
                if "PublicIpAddress" in instance_status:
                    all_statuses[instance_id]["public_ip"] = instance_status[
                        "PublicIpAddress"
                    ]
                if "PrivateIpAddress" in instance_status:
                    all_statuses[instance_id]["private_ip"] = instance_status[
                        "PrivateIpAddress"
                    ]
                if "InstanceType" in instance_status:
                    all_statuses[instance_id]["instance_type"] = instance_status[
                        "InstanceType"
                    ]

            # Enqueue a table update for every new instance.
            events_to_progress.append({"type": "start"})
        elif is_changed:
            # Only log state *changes*.
            logger.info(
                f"Instance {instance_id} state changed: {all_statuses[instance_id]['state']} -> {current_state}"
            )
            all_statuses[instance_id]["state"] = current_state
            all_statuses[instance_id]["last_update"] = timestamp

            # Update additional info from instance_status if available
            if instance_status:
                if "PublicIpAddress" in instance_status:
                    all_statuses[instance_id]["public_ip"] = instance_status[
                        "PublicIpAddress"
                    ]
                if "PrivateIpAddress" in instance_status:
                    all_statuses[instance_id]["private_ip"] = instance_status[
                        "PrivateIpAddress"
                    ]

            events_to_progress.append({"type": "update"})
        else:
            all_statuses[instance_id]["last_update"] = timestamp

        # Save machine state to MACHINES.json on every change
        if is_new or is_changed:
            save_machines_to_json(all_statuses)


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
            await log_operation("Region cannot be empty", "error")
            return {
                "success": False,
                "result_summary": {"error": "Region cannot be empty"},
            }

        # Log the attempt to create in this region
        await log_operation(f"Starting spot instance creation in region", "info", region)

        # Create an EC2 client for the region
        client = boto3.client(
            "ec2",
            region_name=region,
            config=botocore.config.Config(
                retries={"max_attempts": 10, "mode": "standard"}
            ),
        )
        await log_operation(f"Connected to AWS EC2 API", "info", region)

        # Priority for instance_type:
        # 1. Command line argument (if specified)
        # 2. Config.yaml for specific region
        # 3. Available_regions.py data
        # 4. Default fallback (t3.medium)

        # Start with command line argument (may be None)
        instance_type = args.instance_type

        # If not specified in args, get from config for this specific region
        if not instance_type:
            try:
                # Find this region in config.yaml
                region_config = None
                for region_entry in config.get("regions", []):
                    if region in region_entry:
                        region_config = region_entry[region]
                        break

                if region_config and region_config.get("machine_type") != "auto":
                    instance_type = region_config.get("machine_type")
                else:
                    # Get instance type from available_regions if not in config or is "auto"
                    try:
                        from available_regions import REGION_DETAILS

                        if region in REGION_DETAILS:
                            instance_type = REGION_DETAILS[region]["instance_type"]
                        else:
                            instance_type = "t3.medium"  # Default fallback
                    except (ImportError, KeyError):
                        instance_type = "t3.medium"  # Default fallback
            except (KeyError, AttributeError, TypeError, StopIteration):
                instance_type = "t3.medium"  # Default fallback

        # Ensure instance_type is not None at this point
        if not instance_type:
            instance_type = "t3.medium"
            
        await log_operation(f"Using instance type: {instance_type}", "info", region)

        # Configure tags and names
        tags, instance_name, vpc_name = configure_tags_and_names(
            job_name, script_name, region
        )
        await log_operation(f"Configured instance name: {instance_name}", "info", region)

        # Create VPC and related resources
        await log_operation(f"Creating VPC and networking resources", "info", region)
        vpc_id, subnet_id = await create_vpc(client, vpc_name, tags)
        if vpc_id is None or subnet_id is None:
            logger.error(f"Failed to create VPC in region {region}.")
            await log_operation(f"Failed to create VPC", "error", region)
            return {
                "success": False,
                "result_summary": {
                    "error": f"Failed to create VPC in region {region}."
                },
            }
        await log_operation(f"VPC created successfully: {vpc_id}", "info", region)

        # Create security group
        await log_operation(f"Creating security group", "info", region)
        security_group_id = await create_security_group(client, vpc_id, vpc_name, tags)
        if security_group_id is None:
            logger.error(f"Failed to create security group in region {region}.")
            await log_operation(f"Failed to create security group", "error", region)
            return {
                "success": False,
                "result_summary": {
                    "error": f"Failed to create security group in region {region}."
                },
            }
        await log_operation(f"Security group created: {security_group_id}", "info", region)

        # Get instance count from config if possible
        number_of_instances = args.number_of_instances
        try:
            # Find this region in config.yaml
            region_config = None
            for region_entry in config.get("regions", []):
                if region in region_entry:
                    region_config = region_entry[region]
                    break

            if region_config and region_config.get("node_count") != "auto":
                config_node_count = region_config.get("node_count")
                if isinstance(config_node_count, int) and config_node_count > 0:
                    number_of_instances = config_node_count
                    logger.info(
                        f"Using node count {number_of_instances} for region {region} from config"
                    )
        except (KeyError, AttributeError, TypeError, StopIteration) as e:
            logger.warning(
                f"Error getting node count from config: {e}. Using default: {number_of_instances}"
            )
            
        await log_operation(f"Requesting {number_of_instances} instance(s)", "info", region)

        # Run Spot Instances
        await log_operation(f"Submitting spot instance request", "info", region)
        instance_ids = await run_spot_instance(
            client,
            script_name,
            instance_type,
            region,
            args.max_wait_time,
            tags,
            instance_name,
            vpc_id,
            subnet_id,
            security_group_id,
            number_of_instances,
            user_data,
            args.max_price,
        )

        if not instance_ids:
            logger.error(f"No instances launched in region {region}.")
            await log_operation(f"No instances launched", "error", region)
            return {
                "success": False,
                "result_summary": {
                    "error": f"No instances launched in region {region}."
                },
            }
            
        await log_operation(f"Successfully launched {len(instance_ids)} instance(s)", "info", region)

        # Initial status update for all launched instances.
        await log_operation(f"Monitoring status of {len(instance_ids)} instance(s)", "info", region)
        for instance_id in instance_ids:
            instance_status = await describe_instance_status(client, instance_id)
            if instance_status:
                state = instance_status["State"]["Name"]
                await log_operation(f"Instance {instance_id} initial state: {state}", "info", region)
                await handle_instance_state(
                    instance_id,
                    state,
                    region,
                    job_name,
                    instance_status,
                )
            else:
                await log_operation(f"Could not get initial status for instance {instance_id}", "warn", region)

        # Monitor instance status until all instances are terminated or an error occurs.
        update_counter = 0
        while True:
            all_terminated = (
                True  # Assume all instances are terminated until proven otherwise
            )
            
            # Log status updates occasionally to show progress
            if update_counter % 6 == 0:  # Every ~30 seconds
                await log_operation(f"Checking status of {len(instance_ids)} instance(s)", "info", region)
                
            for instance_id in instance_ids:
                instance_status = await describe_instance_status(client, instance_id)

                if instance_status is None:  # instance not found
                    async with status_lock:
                        if instance_id in all_statuses:
                            # Mark as terminated if it was present before
                            await log_operation(f"Instance {instance_id} no longer found, marking as terminated", "info", region)
                            await handle_instance_state(
                                instance_id, "terminated", region, job_name
                            )
                    continue

                current_state = instance_status["State"]["Name"]
                previous_state = None
                async with status_lock:
                    if instance_id in all_statuses:
                        previous_state = all_statuses[instance_id].get("state")
                
                # Log state transitions
                if previous_state and previous_state != current_state:
                    await log_operation(f"Instance {instance_id} changed state: {previous_state} → {current_state}", "info", region)
                
                await handle_instance_state(
                    instance_id, current_state, region, job_name, instance_status
                )

                if current_state.lower() != "terminated":
                    all_terminated = False

            if all_terminated:
                logger.info(f"All instances in region {region} have terminated.")
                await log_operation(f"All instances have terminated", "info", region)
                return {
                    "success": True,
                    "result_summary": {
                        "instances_created": len(instance_ids),
                        "region": region,
                    },
                }

            update_counter += 1
            await asyncio.sleep(5)  # wait before next status check.

    except Exception as e:
        error_msg = f"An unexpected error occurred in region {region}: {e}"
        logger.exception(error_msg)
        return {"success": False, "result_summary": {"error": error_msg}}
    finally:
        if client:
            client.close()


async def terminate_instance(instance_id: str, region: str) -> bool:
    """
    Terminates a specific EC2 instance.

    Args:
        instance_id: The ID of the instance to terminate.
        region: The AWS region where the instance is running.

    Returns:
        True if successful, False otherwise.
    """
    try:
        client = boto3.client(
            "ec2",
            region_name=region,
            config=botocore.config.Config(
                retries={"max_attempts": 10, "mode": "standard"}
            ),
        )

        logger.info(f"Terminating instance {instance_id} in region {region}...")
        response = await asyncio.to_thread(
            client.terminate_instances, InstanceIds=[instance_id]
        )

        # Check if termination was successful
        for instance in response.get("TerminatingInstances", []):
            if instance["InstanceId"] == instance_id:
                prev_state = instance.get("PreviousState", {}).get("Name", "unknown")
                new_state = instance.get("CurrentState", {}).get("Name", "unknown")
                logger.info(
                    f"Instance {instance_id} state changed: {prev_state} -> {new_state}"
                )

                # Update our tracking if we're tracking this instance
                async with status_lock:
                    if instance_id in all_statuses:
                        all_statuses[instance_id]["state"] = new_state
                        all_statuses[instance_id]["last_update"] = time.time()
                        # Save the updated state
                        save_machines_to_json(all_statuses)

                return True

        logger.warning(
            f"No termination confirmation received for instance {instance_id}"
        )
        return False

    except botocore.exceptions.ClientError as e:
        if "InvalidInstanceID.NotFound" in str(e):
            logger.warning(
                f"Instance {instance_id} not found, may already be terminated"
            )

            # Remove from our tracking if we're tracking it
            async with status_lock:
                if instance_id in all_statuses:
                    all_statuses.pop(instance_id)
                    save_machines_to_json(all_statuses)

            return True

        logger.error(f"Error terminating instance {instance_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error terminating instance {instance_id}: {e}")
        return False


async def delete_vpc_and_dependencies(
    client: botocore.client.BaseClient, vpc_id: str
) -> bool:
    """
    Deletes a VPC and all its dependencies (internet gateways, route tables, etc.).
    """
    try:
        # Get all dependencies
        vpc_response = await asyncio.to_thread(client.describe_vpcs, VpcIds=[vpc_id])
        if not vpc_response["Vpcs"]:
            logger.warning(f"VPC {vpc_id} not found")
            return True

        # Delete any NAT Gateways first
        nat_response = await asyncio.to_thread(
            client.describe_nat_gateways,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        for nat in nat_response.get("NatGateways", []):
            try:
                if nat["State"] not in ["deleted", "deleting"]:
                    await asyncio.to_thread(
                        client.delete_nat_gateway, NatGatewayId=nat["NatGatewayId"]
                    )
                    # Wait for NAT Gateway to be deleted
                    while True:
                        nat_status = await asyncio.to_thread(
                            client.describe_nat_gateways,
                            NatGatewayIds=[nat["NatGatewayId"]],
                        )
                        if not nat_status["NatGateways"] or nat_status["NatGateways"][
                            0
                        ]["State"] in ["deleted", "failed"]:
                            break
                        await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error deleting NAT Gateway {nat['NatGatewayId']}: {e}")

        # Delete Network Interfaces
        eni_response = await asyncio.to_thread(
            client.describe_network_interfaces,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        for eni in eni_response.get("NetworkInterfaces", []):
            try:
                if eni.get("Attachment"):
                    await asyncio.to_thread(
                        client.detach_network_interface,
                        AttachmentId=eni["Attachment"]["AttachmentId"],
                        Force=True,
                    )
                await asyncio.to_thread(
                    client.delete_network_interface,
                    NetworkInterfaceId=eni["NetworkInterfaceId"],
                )
            except Exception as e:
                logger.error(
                    f"Error deleting Network Interface {eni['NetworkInterfaceId']}: {e}"
                )

        # Delete Internet Gateways
        igw_response = await asyncio.to_thread(
            client.describe_internet_gateways,
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
        )
        for igw in igw_response.get("InternetGateways", []):
            try:
                await asyncio.to_thread(
                    client.detach_internet_gateway,
                    InternetGatewayId=igw["InternetGatewayId"],
                    VpcId=vpc_id,
                )
                await asyncio.to_thread(
                    client.delete_internet_gateway,
                    InternetGatewayId=igw["InternetGatewayId"],
                )
            except Exception as e:
                logger.error(
                    f"Error deleting Internet Gateway {igw['InternetGatewayId']}: {e}"
                )

        # Delete all non-default security groups
        sg_response = await asyncio.to_thread(
            client.describe_security_groups,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        for sg in sg_response.get("SecurityGroups", []):
            if sg["GroupName"] != "default":
                try:
                    # Remove all ingress/egress rules first
                    await asyncio.to_thread(
                        client.revoke_security_group_ingress,
                        GroupId=sg["GroupId"],
                        IpPermissions=sg.get("IpPermissions", []),
                    )
                    await asyncio.to_thread(
                        client.revoke_security_group_egress,
                        GroupId=sg["GroupId"],
                        IpPermissions=sg.get("IpPermissionsEgress", []),
                    )
                    # Then delete the security group
                    await asyncio.to_thread(
                        client.delete_security_group, GroupId=sg["GroupId"]
                    )
                except Exception as e:
                    logger.error(f"Error deleting Security Group {sg['GroupId']}: {e}")

        # Delete Subnets
        subnet_response = await asyncio.to_thread(
            client.describe_subnets, Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )
        for subnet in subnet_response.get("Subnets", []):
            try:
                await asyncio.to_thread(
                    client.delete_subnet, SubnetId=subnet["SubnetId"]
                )
            except Exception as e:
                logger.error(f"Error deleting Subnet {subnet['SubnetId']}: {e}")

        # Delete Route Tables (except main)
        rt_response = await asyncio.to_thread(
            client.describe_route_tables,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        for rt in rt_response.get("RouteTables", []):
            if not any(
                assoc.get("Main", False) for assoc in rt.get("Associations", [])
            ):
                try:
                    # Delete route table associations first
                    for assoc in rt.get("Associations", []):
                        await asyncio.to_thread(
                            client.disassociate_route_table,
                            AssociationId=assoc["RouteTableAssociationId"],
                        )
                    # Then delete the route table
                    await asyncio.to_thread(
                        client.delete_route_table, RouteTableId=rt["RouteTableId"]
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting Route Table {rt['RouteTableId']}: {e}"
                    )

        # Finally delete the VPC
        try:
            await asyncio.to_thread(client.delete_vpc, VpcId=vpc_id)
            logger.info(f"Successfully deleted VPC {vpc_id}")
            return True
        except botocore.exceptions.ClientError as e:
            if "has dependencies" in str(e):
                # If we still can't delete, log what's left
                logger.error(f"VPC {vpc_id} still has dependencies: {e}")
                return False
            raise

    except botocore.exceptions.ClientError as e:
        if "does not exist" in str(e):
            return True
        logger.error(f"Error deleting VPC {vpc_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting VPC {vpc_id}: {e}")
        return False


async def wait_for_instance_termination(
    client: botocore.client.BaseClient, instance_id: str, timeout: int = 300
):
    """
    Waits for an instance to fully terminate.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = await asyncio.to_thread(
                client.describe_instances, InstanceIds=[instance_id]
            )
            if not response["Reservations"]:
                return True

            state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
            if state == "terminated":
                return True

            await asyncio.sleep(5)
        except botocore.exceptions.ClientError as e:
            if "InvalidInstanceID.NotFound" in str(e):
                return True
            raise

    raise TimeoutError(
        f"Instance {instance_id} did not terminate within {timeout} seconds"
    )


async def cleanup_resources(instance_id: str, region: str) -> bool:
    """
    Cleans up all resources associated with an instance.
    """
    try:
        client = boto3.client(
            "ec2",
            region_name=region,
            config=botocore.config.Config(
                retries={"max_attempts": 10, "mode": "standard"}
            ),
        )

        # Get instance details from MACHINES.json first
        machines = load_machines_from_json()
        instance_info = machines.get(instance_id, {})

        # Get instance details from AWS
        try:
            instance_response = await asyncio.to_thread(
                client.describe_instances, InstanceIds=[instance_id]
            )
            if instance_response["Reservations"]:
                instance = instance_response["Reservations"][0]["Instances"][0]
                vpc_id = instance.get("VpcId")

                # Store resource IDs
                instance_info.update(
                    {
                        "vpc_id": vpc_id,
                        "subnet_id": instance.get("SubnetId"),
                        "security_groups": [
                            sg["GroupId"] for sg in instance.get("SecurityGroups", [])
                        ],
                    }
                )

                # Update MACHINES.json with resource information
                machines[instance_id] = instance_info
                save_machines_to_json(machines)
        except botocore.exceptions.ClientError as e:
            if "InvalidInstanceID.NotFound" not in str(e):
                logger.error(f"Error getting instance details: {e}")
            # Continue with cleanup using stored information

        # Terminate instance if it exists
        await terminate_instance(instance_id, region)

        # Clean up associated resources
        if instance_info.get("vpc_id"):
            await delete_vpc_and_dependencies(client, instance_info["vpc_id"])

        # Remove from MACHINES.json
        async with status_lock:
            machines = load_machines_from_json()
            if instance_id in machines:
                del machines[instance_id]
                save_machines_to_json(machines)

        return True
    except Exception as e:
        logger.error(f"Error cleaning up resources for instance {instance_id}: {e}")
        return False


async def destroy_instances(args: argparse.Namespace) -> bool:
    """
    Destroy instances and all associated resources based on filters in arguments.
    Also cleans up any orphaned VPCs with our tags that have no instances.
    """
    machines = load_machines_from_json()
    if not machines:
        console.print("[yellow]No managed instances found in MACHINES.json[/yellow]")
        return {
            "success": True,
            "result_summary": {
                "instances_terminated": 0,
                "regions_affected": [],
                "message": "No managed instances found",
            },
        }

    # First scan for orphaned VPCs in all regions
    orphaned_vpcs = []
    if (
        not args.instance_id
    ):  # Only scan for orphaned VPCs if not targeting a specific instance
        for region in AWS_REGIONS:
            if args.region and args.region != region:
                continue

            try:
                client = boto3.client("ec2", region_name=region)
                vpc_response = await asyncio.to_thread(
                    client.describe_vpcs,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                for vpc in vpc_response.get("Vpcs", []):
                    # Check if this VPC has any running instances
                    instances_response = await asyncio.to_thread(
                        client.describe_instances,
                        Filters=[{"Name": "vpc-id", "Values": [vpc["VpcId"]]}],
                    )

                    has_running_instances = False
                    for res in instances_response.get("Reservations", []):
                        for inst in res.get("Instances", []):
                            if inst.get("State", {}).get("Name") not in [
                                "terminated",
                                "shutting-down",
                            ]:
                                has_running_instances = True
                                break
                        if has_running_instances:
                            break

                    if not has_running_instances:
                        orphaned_vpcs.append((vpc["VpcId"], region))
            except Exception as e:
                logger.error(
                    f"Error scanning for orphaned VPCs in region {region}: {e}"
                )

    # Filter instances based on command line arguments
    instances_to_cleanup = []
    for instance_id, info in machines.items():
        # Skip already terminated instances
        if info.get("state") in ["terminated", "shutting-down"]:
            continue

        # Apply filters
        if args.instance_id and args.instance_id != instance_id:
            continue
        if args.region and args.region != info.get("region"):
            continue
        if args.job and args.job != info.get("job"):
            continue

        instances_to_cleanup.append((instance_id, info.get("region")))

    if not instances_to_cleanup and not orphaned_vpcs:
        console.print(
            "[yellow]No instances found matching the specified filters[/yellow]"
        )
        return {
            "success": True,
            "result_summary": {
                "instances_terminated": 0,
                "regions_affected": [],
                "message": "No instances match filters",
            },
        }

    # Create a live updating table
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        title="Resource Cleanup Status",
        title_style="bold blue",
    )

    # Define columns for the single-line display
    table.add_column("Resource ID", style="cyan", no_wrap=True)
    table.add_column("Region", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Resources", style="green")
    table.add_column("Progress", style="blue")

    # Initialize table with one row per resource
    resource_rows = {}
    for instance_id, region in instances_to_cleanup:
        # Add a single row for each instance
        resource_rows[instance_id] = table.add_row(
            instance_id,
            region,
            "Pending",
            "Waiting to start",
            "0/5 resources",
        )

    # Add rows for orphaned VPCs
    for vpc_id, region in orphaned_vpcs:
        resource_rows[vpc_id] = table.add_row(
            vpc_id,
            region,
            "Pending",
            "Orphaned VPC",
            "0/1 resources",
        )

    # Display initial table
    with Live(table, refresh_per_second=4) as live_display:
        # Track terminated instances and affected regions
        terminated_count = 0
        affected_regions = set()

        # Set current live display
        set_current_live(live_display)

        # Process each orphaned VPC first
        success = True
        for vpc_id, region in orphaned_vpcs:
            try:
                client = boto3.client("ec2", region_name=region)

                # Update status
                row_index = resource_rows.get(vpc_id)
                if row_index is not None:
                    table.rows[row_index].cells[2].value = "In Progress"
                    table.rows[row_index].cells[2].style = "yellow"

                # Delete the VPC and its dependencies
                await delete_vpc_and_dependencies(client, vpc_id)

                # Update status
                if row_index is not None:
                    table.rows[row_index].cells[2].value = "Complete"
                    table.rows[row_index].cells[2].style = "green"
                    table.rows[row_index].cells[3].value = "VPC Deleted"
                    table.rows[row_index].cells[4].value = "1/1 resources"

                terminated_count += 1
                affected_regions.add(region)

            except Exception as e:
                logger.error(f"Error deleting orphaned VPC {vpc_id}: {e}")
                row_index = resource_rows.get(vpc_id)
                if row_index is not None:
                    table.rows[row_index].cells[2].value = "Failed"
                    table.rows[row_index].cells[2].style = "red"
                    table.rows[row_index].cells[3].value = f"Error: {str(e)}"
                success = False

        # Process each instance
        for instance_id, region in instances_to_cleanup:
            try:
                # Get instance details from AWS
                client = boto3.client("ec2", region_name=region)

                # Update status to show we're working on this instance
                row_index = resource_rows.get(instance_id)
                if row_index is not None:
                    table.rows[row_index].cells[2].value = "In Progress"
                    table.rows[row_index].cells[2].style = "yellow"

                # Get VPC ID from instance details
                vpc_id = None
                try:
                    instance_response = await asyncio.to_thread(
                        client.describe_instances, InstanceIds=[instance_id]
                    )
                    if instance_response.get("Reservations") and instance_response[
                        "Reservations"
                    ][0].get("Instances"):
                        vpc_id = instance_response["Reservations"][0]["Instances"][
                            0
                        ].get("VpcId")
                except botocore.exceptions.ClientError as e:
                    if "InvalidInstanceID.NotFound" not in str(e):
                        logger.error(f"Error getting instance details: {e}")

                # Terminate instance
                result = await terminate_instance(instance_id, region)
                resources_completed = 1
                row_index = resource_rows.get(instance_id)
                if row_index is not None:
                    table.rows[row_index].cells[
                        4
                    ].value = f"{resources_completed}/5 resources"
                    table.rows[row_index].cells[3].value = f"Terminated instance"

                if result and vpc_id:
                    # Clean up Internet Gateway
                    igw_response = await asyncio.to_thread(
                        client.describe_internet_gateways,
                        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
                    )
                    for igw in igw_response.get("InternetGateways", []):
                        await asyncio.to_thread(
                            client.detach_internet_gateway,
                            InternetGatewayId=igw["InternetGatewayId"],
                            VpcId=vpc_id,
                        )
                        await asyncio.to_thread(
                            client.delete_internet_gateway,
                            InternetGatewayId=igw["InternetGatewayId"],
                        )
                    resources_completed += 1
                    row_index = resource_rows.get(instance_id)
                    if row_index is not None:
                        table.rows[row_index].cells[
                            4
                        ].value = f"{resources_completed}/5 resources"
                        table.rows[row_index].cells[3].value = f"Removed IGW"

                    # Clean up Subnet
                    subnet_response = await asyncio.to_thread(
                        client.describe_subnets,
                        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                    )
                    for subnet in subnet_response.get("Subnets", []):
                        await asyncio.to_thread(
                            client.delete_subnet, SubnetId=subnet["SubnetId"]
                        )
                    resources_completed += 1
                    row_index = resource_rows.get(instance_id)
                    if row_index is not None:
                        table.rows[row_index].cells[
                            4
                        ].value = f"{resources_completed}/5 resources"
                        table.rows[row_index].cells[3].value = f"Removed Subnet"

                    # Clean up Route Tables
                    rt_response = await asyncio.to_thread(
                        client.describe_route_tables,
                        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                    )
                    for rt in rt_response.get("RouteTables", []):
                        if not rt.get("Associations", []) or not rt["Associations"][
                            0
                        ].get("Main", False):
                            await asyncio.to_thread(
                                client.delete_route_table,
                                RouteTableId=rt["RouteTableId"],
                            )
                    resources_completed += 1
                    row_index = resource_rows.get(instance_id)
                    if row_index is not None:
                        table.rows[row_index].cells[
                            4
                        ].value = f"{resources_completed}/5 resources"
                        table.rows[row_index].cells[3].value = f"Removed Route Tables"

                    # Clean up Security Groups
                    sg_response = await asyncio.to_thread(
                        client.describe_security_groups,
                        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                    )
                    for sg in sg_response.get("SecurityGroups", []):
                        if sg["GroupName"] != "default":
                            await asyncio.to_thread(
                                client.delete_security_group, GroupId=sg["GroupId"]
                            )
                    resources_completed += 1
                    row_index = resource_rows.get(instance_id)
                    if row_index is not None:
                        table.rows[row_index].cells[
                            4
                        ].value = f"{resources_completed}/5 resources"
                        table.rows[row_index].cells[
                            3
                        ].value = f"Removed Security Groups"

                    # Finally delete the VPC
                    await asyncio.to_thread(client.delete_vpc, VpcId=vpc_id)

                # Update final status
                row_index = resource_rows.get(instance_id)
                if row_index is not None:
                    table.rows[row_index].cells[2].value = "Complete"
                    table.rows[row_index].cells[2].style = "green"
                    table.rows[row_index].cells[3].value = "All resources removed"
                    table.rows[row_index].cells[4].value = "5/5 resources"

            except botocore.exceptions.ClientError as e:
                if "InvalidInstanceID.NotFound" not in str(e):
                    logger.error(f"Error getting instance details: {e}")
                    row_index = resource_rows.get(instance_id)
                    if row_index is not None:
                        table.rows[row_index].cells[2].value = "Failed"
                        table.rows[row_index].cells[2].style = "red"
                        table.rows[row_index].cells[3].value = f"Error: {str(e)}"
                    success = False

            # Remove from MACHINES.json
            async with status_lock:
                machines = load_machines_from_json()
                if instance_id in machines:
                    del machines[instance_id]
                    save_machines_to_json(machines)
                    terminated_count += 1
                    affected_regions.add(region)

    return {
        "success": success,
        "result_summary": {
            "instances_terminated": terminated_count,
            "regions_affected": list(affected_regions),
        },
    }


async def nuke_all_instances(args: argparse.Namespace) -> dict:
    """Aggressively terminates all instances and resources created by this script."""
    all_resources = []
    terminated_count = 0
    affected_regions = set()

    # First, scan all regions for resources
    with Progress() as progress:
        scan_task = progress.add_task("Scanning regions", total=len(AWS_REGIONS))

        for region in AWS_REGIONS:
            try:
                client = boto3.client("ec2", region_name=region)

                # Find instances with our tag
                response = await asyncio.to_thread(
                    client.describe_instances,
                    Filters=[
                        {"Name": f"tag:{FILTER_TAG_NAME}", "Values": [FILTER_TAG_VALUE]}
                    ],
                )

                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        if instance.get("State", {}).get("Name") not in [
                            "terminated",
                            "shutting-down",
                        ]:
                            all_resources.append(
                                {
                                    "type": "instance",
                                    "id": instance["InstanceId"],
                                    "region": region,
                                    "source": "tagged",
                                    "vpc_id": instance.get("VpcId"),
                                }
                            )

                # Find orphaned VPCs (those with our tag or name pattern)
                response = await asyncio.to_thread(
                    client.describe_vpcs,
                    Filters=[
                        {
                            "Name": "tag:Name",
                            "Values": ["SpotInstance-*", "SpotInstanceVPC"],
                        }
                    ],
                )

                for vpc in response.get("Vpcs", []):
                    all_resources.append(
                        {
                            "type": "vpc",
                            "id": vpc["VpcId"],
                            "region": region,
                            "source": "orphaned",
                        }
                    )

            except Exception as e:
                logger.error(f"Error scanning region {region}: {e}")
            finally:
                progress.update(scan_task, advance=1)

    if not all_resources:
        return {
            "success": True,
            "result_summary": {"instances_terminated": 0, "regions_affected": []},
        }

    # Require --force flag for nuke operation
    if not args.force:
        return {
            "success": False,
            "result_summary": {"instances_terminated": 0, "regions_affected": []},
        }

    # Nuke everything
    success = True
    with Progress() as progress:
        nuke_task = progress.add_task(
            "[red]NUKING resources[/red]", total=len(all_resources)
        )

        # First, clean up instances
        for resource in all_resources:
            try:
                client = boto3.client("ec2", region_name=resource["region"])

                if resource["type"] == "instance":
                    if await terminate_instance(resource["id"], resource["region"]):
                        terminated_count += 1
                        affected_regions.add(resource["region"])
                        if resource.get("vpc_id"):
                            try:
                                await delete_vpc_and_dependencies(
                                    client, resource["vpc_id"]
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error deleting VPC {resource['vpc_id']}: {e}"
                                )
                elif resource["type"] == "vpc":
                    try:
                        await delete_vpc_and_dependencies(client, resource["id"])
                        affected_regions.add(resource["region"])
                    except Exception as e:
                        logger.error(f"Error deleting VPC {resource['id']}: {e}")
                        success = False
            except Exception as e:
                logger.error(f"Error nuking resource {resource['id']}: {e}")
                success = False
            finally:
                progress.update(nuke_task, advance=1)

        # Update MACHINES.json
        machines = load_machines_from_json()
        for resource in all_resources:
            if resource["type"] == "instance" and resource["id"] in machines:
                del machines[resource["id"]]
        save_machines_to_json(machines)

    return {
        "success": success,
        "result_summary": {
            "instances_terminated": terminated_count,
            "regions_affected": list(affected_regions),
        },
    }


class RichConsoleHandler(logging.Handler):
    """Custom logging handler that updates a Rich console panel."""

    def __init__(self, live, layout, file_handler):
        super().__init__()
        self.live = live
        self.layout = layout
        self.file_handler = file_handler
        self.setFormatter(logging.Formatter("%(message)s"))
        self.log_messages = []
        self.max_messages = 10  # Keep last N messages

    def emit(self, record):
        try:
            # Always write to file
            self.file_handler.emit(record)

            # For console, format the message with color based on level
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                msg = f"[red bold]ERROR:[/red bold] {msg}"
            elif record.levelno >= logging.WARNING:
                msg = f"[yellow bold]WARNING:[/yellow bold] {msg}"
            else:
                msg = f"[green]INFO:[/green] {msg}"

            # Add timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"[dim]{timestamp}[/dim] {msg}"

            # Add to message list and keep only the last N messages
            self.log_messages.append(msg)
            if len(self.log_messages) > self.max_messages:
                self.log_messages.pop(0)

            # Join all messages with newlines
            all_messages = "\n".join(self.log_messages)

            # Update the logs panel
            if "logs" in self.layout:
                self.layout["logs"].update(
                    Panel(
                        all_messages,
                        title="[bold]Logs[/bold]",
                        border_style="blue",
                    )
                )
            
            # Update the operations panel
            if "operations" in self.layout:
                global operation_logs
                ops_content = "\n".join(operation_logs) if operation_logs else "[dim]No operations logged yet...[/dim]"
                self.layout["operations"].update(
                    Panel(
                        ops_content,
                        title="[bold]AWS Operations[/bold]",
                        border_style="yellow",
                        padding=(0, 1)
                    )
                )
                
            self.live.refresh()
        except Exception:
            self.handleError(record)


# Global variable to track the current live display
_current_live = None


def set_current_live(live):
    """Set the current live display for global access."""
    global _current_live
    _current_live = live


def get_current_live():
    """Get the current live display."""
    return _current_live


async def log_operation(message: str, level: str = "info", region: str = None):
    """
    Logs an operation to the operation_logs queue for display in the console.
    
    Args:
        message: The message to log
        level: The log level (info, warn, error)
        region: Optional region context for the operation
    """
    global operation_logs
    
    # Format timestamp for the log
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Format the message with optional region and log level
    formatted_message = f"[dim]{timestamp}[/dim] "
    if region:
        formatted_message += f"[cyan]{region}:[/cyan] "
    
    if level == "error":
        formatted_message += f"[red bold]{message}[/red bold]"
    elif level == "warn":
        formatted_message += f"[yellow]{message}[/yellow]"
    else:  # default to info
        formatted_message += f"[green]{message}[/green]"
    
    # Add to the operation logs with thread-safe lock
    async with operation_logs_lock:
        operation_logs.append(formatted_message)
        # Keep only the most recent logs
        if len(operation_logs) > max_operation_logs:
            operation_logs = operation_logs[-max_operation_logs:]
        
    # Also log to the standard logger
    if level == "error":
        logger.error(message)
    elif level == "warn":
        logger.warning(message)
    else:
        logger.info(message)
    
    # If we have a live display, refresh it
    live = get_current_live()
    if live:
        try:
            live.refresh()
        except Exception as e:
            logger.error(f"Error refreshing live display: {e}")


async def update_display(live, progress: Progress):
    """Update the display with current instance status."""
    try:
        # Store live display for global access
        set_current_live(live)

        # Create a progress task
        task_id = progress.add_task("[cyan]Processing...", total=None)

        while not table_update_event.is_set():
            # Get a copy of current statuses
            async with status_lock:
                current_statuses = all_statuses.copy()

            # Get a copy of current operation logs
            async with operation_logs_lock:
                current_op_logs = operation_logs.copy()

            # Update progress
            progress.update(task_id, advance=1)

            # Update table
            table = make_progress_table()
            for instance_id, status in current_statuses.items():
                # Format public IP address if available
                ip_display = "pending"
                if "public_ip" in status:
                    ip_display = status["public_ip"]
                elif "private_ip" in status:
                    ip_display = f"private: {status['private_ip']}"
                
                # Format launch time if available
                launch_time = status.get("created_at", "unknown")
                if isinstance(launch_time, (int, float)):
                    launch_time = datetime.fromtimestamp(launch_time).strftime("%H:%M:%S")
                
                table.add_row(
                    instance_id,
                    status.get("region", "unknown"),
                    status.get("state", "unknown"),
                    ip_display,
                    launch_time,
                )

            # Update layout
            layout = create_layout(progress, table)
            
            # Update operations log panel
            if "operations" in layout:
                ops_content = "\n".join(current_op_logs) if current_op_logs else "[dim]No operations logged yet...[/dim]"
                layout["operations"].update(
                    Panel(
                        ops_content,
                        title="[bold]AWS Operations[/bold]",
                        border_style="yellow",
                        padding=(0, 1)
                    )
                )
            
            live.update(layout)

            # Wait before next update
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error in display update task: {e}", exc_info=True)
        raise
    finally:
        # Clear the global live display reference
        set_current_live(None)


def create_layout(progress: Progress, table: Table) -> Layout:
    """Create the layout for the rich console display."""
    # Create main layout
    layout = Layout(name="root")

    # Create header
    header = Layout(name="header", size=3)
    header.update(
        Panel(
            "[bold blue]AWS Spot Instance Manager[/bold blue]\n[dim]Managing EC2 spot instances across regions[/dim]",
            border_style="blue",
            title="[bold]Status[/bold]",
        )
    )

    # Create content area with progress and table
    content = Layout(name="content")
    content.split_column(
        Layout(
            Panel(progress, title="[bold]Progress[/bold]", border_style="green"), size=4
        ),
        Layout(
            Panel(table, title="[bold]Resources[/bold]", border_style="cyan"), ratio=2
        ),
    )

    # Create log area for general logs
    logs = Layout(name="logs", size=6)
    logs.update(
        Panel("", title="[bold]Logs[/bold]", border_style="blue", padding=(0, 1))
    )

    # Create operations log area for tracking AWS operations
    operations = Layout(name="operations", size=8)
    
    # Get the operations logs to display
    global operation_logs
    ops_content = "\n".join(operation_logs) if operation_logs else "[dim]No operations logged yet...[/dim]"
    
    operations.update(
        Panel(
            ops_content, 
            title="[bold]AWS Operations[/bold]", 
            border_style="yellow", 
            padding=(0, 1)
        )
    )

    # Combine all layouts
    layout.split_column(header, content, operations, logs)

    return layout


def make_progress_table() -> Table:
    """Create a table for displaying instance progress."""
    table = Table(
        title="Instance Status",
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        expand=True,
    )

    # Add columns
    table.add_column("Instance ID", style="cyan")
    table.add_column("Region", style="green")
    table.add_column("State", style="yellow")
    table.add_column("IP Address", style="blue")
    table.add_column("Launch Time", style="magenta")

    return table


async def perform_action():
    """Perform the requested action based on command line arguments."""
    try:
        if args.command == "create":
            # Log the operation initiation
            await log_operation(f"Starting 'create' operation", "info")
            
            # Get configuration values
            script_name, instance_type, region = get_config_values(args, config)
            
            if region == "all":
                await log_operation(f"Using multi-region deployment for script: {script_name}", "info")
            else:
                await log_operation(f"Using region: {region} for script: {script_name}", "info")
                if instance_type:
                    await log_operation(f"Instance type: {instance_type}", "info")

            # Create new instances
            await log_operation(f"Starting instance creation process", "info")
            result = await run_instances_in_region(
                region, args, script_name, script_name, ""
            )
            
            # Log completion
            if isinstance(result, dict) and result.get("success", False):
                await log_operation(f"Create operation completed successfully", "info")
            else:
                await log_operation(f"Create operation completed with errors", "warn")
                
            return {"success": True, "result_summary": result}

        elif args.command == "destroy":
            # Log the operation initiation
            await log_operation(f"Starting 'destroy' operation", "info")
            
            # Destroy instances based on filters
            result = await destroy_instances(args)
            
            # Log completion
            if result.get("success", False):
                terminated = result.get("result_summary", {}).get("instances_terminated", 0)
                regions = result.get("result_summary", {}).get("regions_affected", [])
                await log_operation(f"Destroyed {terminated} instance(s) in {len(regions)} region(s)", "info")
            else:
                await log_operation(f"Destroy operation completed with errors", "warn")
                
            return result

        elif args.command == "nuke":
            # Log the operation initiation
            await log_operation(f"Starting 'nuke' operation", "info")
            await log_operation(f"This will terminate ALL spot instances and resources", "warn")
            
            # Nuke all instances
            result = await nuke_all_instances(args)
            
            # Log completion
            if result.get("success", False):
                terminated = result.get("result_summary", {}).get("instances_terminated", 0)
                await log_operation(f"Nuked {terminated} instance(s) and associated resources", "info")
            else:
                await log_operation(f"Nuke operation completed with errors", "warn")
                
            return result

        else:
            logger.error(f"Unknown command: {args.command}")
            await log_operation(f"Unknown command: {args.command}", "error")
            return {"success": False, "error": f"Unknown command: {args.command}"}

    except Exception as e:
        logger.error(f"Error performing action: {str(e)}", exc_info=True)
        await log_operation(f"Error: {str(e)}", "error")
        return {"success": False, "error": str(e)}


async def main():
    """Main execution function"""
    handler = None  # Initialize handler to None
    display_task = None  # Initialize display_task to None
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    null_io = NullIO()

    try:
        args = parse_arguments()

        # Redirect stdout/stderr to prevent any direct printing
        sys.stdout = null_io
        sys.stderr = null_io

        # Only log to file, not to console unless verbose
        if args.verbose:
            logger.debug("Verbose logging enabled")
            logger.info(f"Starting command: {args.command}")

        if args.format == "json":
            logger.info("Using JSON output format")
            operation_result = await perform_action()
            # Machine updates in MACHINES.json are now handled within perform_action()

            # For JSON output, also show MACHINES.json contents if it exists
            machines_from_file = load_machines_from_json().get("machines", {})

            # Use direct stdout before rich console is initialized
            output = {
                "current_machines": {},  # We don't track statuses in JSON mode
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

                # Start display update task
                display_task = asyncio.create_task(update_display(live, progress))

                # Perform the requested action
                operation_result = await perform_action()

                # Signal display task to stop
                table_update_event.set()

                # Wait for display task to finish
                if display_task and not display_task.done():
                    try:
                        # Give the task a short time to finish gracefully
                        await asyncio.wait_for(display_task, timeout=2.0)
                    except asyncio.TimeoutError:
                        # If it doesn't finish in time, cancel it
                        display_task.cancel()
                        try:
                            await display_task
                        except asyncio.CancelledError:
                            pass  # This is expected
                    except Exception as e:
                        logger.error(f"Error in display task cleanup: {str(e)}")

                # Display summary after operation completes (if successful)
                if isinstance(operation_result, dict) and operation_result.get(
                    "success", False
                ):
                    # Create a nice summary table
                    summary_table = Table(
                        title=f"{args.command.capitalize()} Operation Summary",
                        show_header=True,
                        header_style="bold cyan",
                        box=box.ROUNDED,
                    )

                    # Add columns based on the command
                    if args.command == "create":
                        summary_table.add_column("Total Created", style="green")
                        summary_table.add_column("Regions", style="blue")
                        summary_table.add_column("Distribution", style="cyan")

                        # Get summary data
                        summary = operation_result.get("result_summary", {})
                        total = (
                            summary.get("instances_created", 0)
                            if isinstance(summary, dict)
                            else 0
                        )
                        by_region = (
                            summary.get("instances_by_region", {})
                            if isinstance(summary, dict)
                            else {}
                        )
                        all_ips = (
                            summary.get("all_received_ips", True)
                            if isinstance(summary, dict)
                            else True
                        )

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

                    elif args.command == "destroy":
                        summary_table.add_column("Instances Terminated", style="red")
                        summary_table.add_column("Regions Affected", style="cyan")
                        summary_table.add_column("Result", style="magenta")

                        # Get summary data
                        summary = operation_result.get("result_summary", {})
                        terminated = (
                            summary.get("instances_terminated", 0)
                            if isinstance(summary, dict)
                            else 0
                        )
                        regions = (
                            summary.get("regions_affected", [])
                            if isinstance(summary, dict)
                            else []
                        )

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
                        args.command == "create"
                        and operation_result.get("result_summary", {}).get(
                            "instances_created", 0
                        )
                        > 0
                    ):
                        console.print(
                            "[green]✓ Machine information saved to MACHINES.json[/green]"
                        )
                    elif (
                        args.command == "list"
                        and operation_result.get("result_summary", {}).get(
                            "total_instances", 0
                        )
                        > 0
                    ):
                        console.print(
                            "[green]✓ Machine information updated in MACHINES.json[/green]"
                        )
                    elif (
                        args.command == "destroy"
                        and operation_result.get("result_summary", {}).get(
                            "instances_terminated", 0
                        )
                        > 0
                    ):
                        console.print(
                            "[red]✓ Terminated machines removed from MACHINES.json[/red]"
                        )

                # Signal display task to stop and wait for completion
                table_update_event.set()

                # Print a clear summary of what was done
                if isinstance(operation_result, dict):
                    success = operation_result.get("success", False)
                    if success:
                        summary = operation_result.get("result_summary", {})
                        if args.command == "destroy":
                            terminated = (
                                summary.get("instances_terminated", 0)
                                if isinstance(summary, dict)
                                else 0
                            )
                            if terminated > 0:
                                console.print(
                                    f"\n[green]Successfully terminated {terminated} instance(s)[/green]"
                                )
                            else:
                                console.print(
                                    "\n[yellow]No instances found to terminate[/yellow]"
                                )
                else:
                    console.print(
                        "\n[red]Operation failed. Check debug.log for details[/red]"
                    )

                # For create command, make sure we keep the display up just long enough
                # to let users see the results but not block on full provisioning
                if args.command == "create":
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

                # Temporarily restore stdout/stderr for cleanup
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # Remove the rich console handler if it was added
                if handler is not None and handler in logger.handlers:
                    logger.removeHandler(handler)

                # Redirect back to null for outer finally block
                sys.stdout = null_io
                sys.stderr = null_io

    except Exception as e:
        logger.error(f"Fatal error occurred: {str(e)}", exc_info=True)
        console.print(f"\n[bold red]Fatal error:[/bold red] {str(e)}")
        raise
    finally:
        # Always restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


if __name__ == "__main__":
    # Store the original terminal settings to ensure we can properly display errors
    is_terminal_cleared = False
    args = parse_arguments()

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
        if args.verbose:
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
