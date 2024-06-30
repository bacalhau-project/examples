import argparse
import asyncio
import base64
import io
import json
import logging
import os
import subprocess
import tarfile
import time
import uuid
from datetime import datetime, timezone

import boto3
import botocore
import requests
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

console = Console()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# AWS regions to deploy in (expanded to 10)
AWS_REGIONS = [
    "us-west-2",
    "us-east-1",
    "eu-west-1",
    "ap-southeast-1",
    "sa-east-1",
    "eu-central-1",
    "ap-northeast-1",
    "ap-southeast-2",
    "ca-central-1",
    "eu-west-2",
]

UBUNTU_AMIS = {
    "us-west-2": "ami-03ab9db8dada95e36",
    "us-east-1": "ami-0111190769c4329ae",
    "eu-west-1": "ami-07e2abe41a3dd4483",
    "ap-southeast-1": "ami-0417ea7f58950ec35",
    "sa-east-1": "ami-07f5d4171b892af81",
    "eu-central-1": "ami-039258d4169293e75",
    "ap-northeast-1": "ami-07ac8e5b1fefaa9e5",
    "ap-southeast-2": "ami-0266d373beca3c7fa",
    "ca-central-1": "ami-000610b0cd573898f",
    "eu-west-2": "ami-0226b5ec3281d5d20",
}

TOTAL_INSTANCES = 30
INSTANCES_PER_REGION = TOTAL_INSTANCES // len(
    AWS_REGIONS
)  # Evenly distribute instances

MAX_NODES = 30  # Global limit for total nodes across all regions
KEY_PAIR_NAME = "david-aws-keypair"

# Change this part to read the public key instead of the private key
with open("david-aws-keypair.pub", "r") as public_key_file:
    public_key_material = public_key_file.read().strip()

SCRIPT_DIR = "spot_creation_scripts"


# Global dictionary to store statuses
all_statuses = {}  # Moved to global scope
global_node_count = 0

# Add this global flag
table_update_running = False
table_update_event = asyncio.Event()

task_name = "TASK NAME"
task_total = 10000
task_count = 0
events_to_progress = []


class RateLimiter:
    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.updated_at = time.monotonic()

    async def wait(self):
        while self.tokens < 1:
            self.add_new_tokens()
            await asyncio.sleep(0.1)
        self.tokens -= 1

    def add_new_tokens(self):
        now = time.monotonic()
        time_passed = now - self.updated_at
        new_tokens = time_passed * self.rate_limit
        if new_tokens > 1:
            self.tokens = min(self.tokens + new_tokens, self.rate_limit)
            self.updated_at = now


# Create a rate limiter for AWS API calls (adjust the rate as needed)
aws_rate_limiter = RateLimiter(10)  # 10 requests per second


async def aws_api_call(func, *args, **kwargs):
    max_retries = 5
    for attempt in range(max_retries):
        await aws_rate_limiter.wait()
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "RequestLimitExceeded":
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                else:
                    raise
            else:
                raise


class InstanceStatus:
    def __init__(self, region, zone):
        # Generate a unique ID for each instance - maximum 6 characters
        self.id = f"{region}-{zone}-{uuid.uuid4()}"[:6]
        self.region = region
        self.zone = zone
        self.status = "Initializing"
        self.detailed_status = "Initializing"
        self.elapsed_time = 0
        self.instance_id = None
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
    table = Table(show_header=True, header_style="bold magenta", show_lines=False)
    table.add_column("ID", width=8, style="cyan", no_wrap=True)
    table.add_column("Region", width=15, style="green", no_wrap=True)
    table.add_column("Zone", width=15, style="green", no_wrap=True)
    table.add_column("Status", width=20, style="yellow", no_wrap=True)
    table.add_column(
        "Elapsed Time", width=15, justify="center", style="magenta", no_wrap=True
    )
    table.add_column("Instance ID", width=20, style="blue", no_wrap=True)
    table.add_column("Public IP", width=15, style="blue", no_wrap=True)
    table.add_column("Private IP", width=15, style="blue", no_wrap=True)

    sorted_statuses = sorted(all_statuses.values(), key=lambda x: (x.region, x.zone))
    for status in sorted_statuses:
        table.add_row(
            status.id[:5] + "..." if len(status.id) > 8 else status.id,
            status.region[:12] + "..." if len(status.region) > 15 else status.region,
            status.zone[:12] + "..." if len(status.zone) > 15 else status.zone,
            status.combined_status()[:17] + "..."
            if len(status.combined_status()) > 20
            else status.combined_status(),
            format_elapsed_time(status.elapsed_time),
            (status.instance_id or "")[:17] + "..."
            if len(status.instance_id or "") > 20
            else (status.instance_id or ""),
            (status.public_ip or "")[:12] + "..."
            if len(status.public_ip or "") > 15
            else (status.public_ip or ""),
            (status.private_ip or "")[:12] + "..."
            if len(status.private_ip or "") > 15
            else (status.private_ip or ""),
        )
    return table


async def update_table():
    global table_update_running
    if table_update_running:
        logging.debug("Table update already running. Exiting.")
        return

    logging.debug("Starting table update.")

    try:
        table_update_running = True
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        task = progress.add_task(task_name, total=task_total)

        with Live(console=console, refresh_per_second=4) as live:
            while not table_update_event.is_set():
                while len(events_to_progress) > 0:
                    progress.update(task, completed=len(events_to_progress))
                    events_to_progress.pop(0)

                table = make_progress_table()

                # Create a layout
                layout = Layout()
                layout.split(
                    Layout(
                        Panel(
                            progress,
                            title="Progress",
                            border_style="green",
                            padding=(1, 1),
                        ),
                        size=3,
                    ),
                    Layout(table),
                )

                # Update the live display
                live.update(layout)

                await asyncio.sleep(0.25)

    except Exception as e:
        logging.error(f"Error in update_table: {str(e)}")
    finally:
        table_update_running = False
        logging.debug("Table update finished.")


def get_instance_metadata(metadata_url):
    response = requests.get(metadata_url)
    return response.text.strip()


def get_env_vars():
    # Get instance metadata
    instance_id = get_instance_metadata(
        "http://169.254.169.254/latest/meta-data/instance-id"
    )
    region = get_instance_metadata(
        "http://169.254.169.254/latest/meta-data/placement/region"
    )

    # Create EC2 client
    ec2 = boto3.client("ec2", region_name=region)

    # Get instance details
    response = ec2.describe_instances(InstanceIds=[instance_id])
    instance = response["Reservations"][0]["Instances"][0]

    # Get instance type details
    instance_type = instance["InstanceType"]
    instance_type_info = ec2.describe_instance_types(InstanceTypes=[instance_type])[
        "InstanceTypes"
    ][0]

    # Calculate disk size (assuming only one EBS volume)
    disk_size = sum(volume["Size"] for volume in instance["BlockDeviceMappings"])

    # Prepare environment variables
    env_vars = [
        {"Name": "EC2_INSTANCE_FAMILY", "Value": instance_type.split(".")[0]},
        {
            "Name": "EC2_VCPU_COUNT",
            "Value": str(instance_type_info["VCpuInfo"]["DefaultVCpus"]),
        },
        {
            "Name": "EC2_MEMORY_GB",
            "Value": str(instance_type_info["MemoryInfo"]["SizeInMiB"] / 1024),
        },
        {"Name": "EC2_DISK_GB", "Value": str(disk_size)},
    ]

    return env_vars


def get_ec2_client(region):
    return boto3.client("ec2", region_name=region)


async def ensure_key_pair_exists(ec2):
    try:
        await asyncio.to_thread(ec2.describe_key_pairs, KeyNames=[KEY_PAIR_NAME])
        logging.debug(f"Key pair '{KEY_PAIR_NAME}' already exists.")
    except ec2.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.NotFound":
            logging.debug(f"Key pair '{KEY_PAIR_NAME}' not found. Creating it...")
            await asyncio.to_thread(
                ec2.import_key_pair,
                KeyName=KEY_PAIR_NAME,
                PublicKeyMaterial=public_key_material,
            )
            logging.debug(f"Key pair '{KEY_PAIR_NAME}' created successfully.")
        else:
            raise


async def get_availability_zones(ec2):
    response = await asyncio.to_thread(
        ec2.describe_availability_zones,
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}],
    )
    return [zone["ZoneName"] for zone in response["AvailabilityZones"]][
        :1
    ]  # Get 1 AZ per region


def tar_and_encode_scripts():
    memory_file = io.BytesIO()
    with tarfile.open(fileobj=memory_file, mode="w:gz") as tar:
        for script_file in sorted(os.listdir(SCRIPT_DIR)):
            if script_file.endswith(".sh"):
                script_path = os.path.join(SCRIPT_DIR, script_file)
                tar.add(script_path, arcname=script_file)

    memory_file.seek(0)
    return base64.b64encode(memory_file.getvalue()).decode()


def get_user_data_script(orchestrators, encoded_tar):
    # If the orchestrators are empty, we are creating a new network
    if not orchestrators:
        # Orchestrators being empty means we need to stop creation and warn
        logging.error("Orchestrators are empty. Stopping creation.")
        return ""

    return f"""#!/bin/bash

# Export ORCHESTRATORS
export ORCHESTRATORS="{','.join(orchestrators)}"

# Create and populate /etc/node-config
create_node_config() {{
    cat << EOF > /etc/node-config
ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
EC2_INSTANCE_FAMILY=$(curl -s http://169.254.169.254/latest/meta-data/instance-type | cut -d. -f1)
EC2_VCPU_COUNT=$(nproc)
EC2_MEMORY_GB=$(free -g | awk '/^Mem:/{{print $2}}')
EC2_DISK_GB=$(df -BG --output=size / | tail -n 1 | tr -d ' G')
ORCHESTRATORS=$ORCHESTRATORS
EOF
    chmod 644 /etc/node-config
}}

# Create node config
create_node_config

# Decode and extract scripts
SCRIPT_DIR="/tmp/spot_scripts"
mkdir -p "$SCRIPT_DIR"
echo "{encoded_tar}" | base64 -d | tar -xzv -C "$SCRIPT_DIR"

# Run scripts in order
for script in $(ls -1 "$SCRIPT_DIR"/*.sh | sort); do
    echo "Running $script"
    bash "$script"
done

# Clean up
rm -rf "$SCRIPT_DIR"
"""


async def create_spot_instances_in_region(region, orchestrators):
    ec2 = get_ec2_client(region)

    try:
        await ensure_key_pair_exists(ec2)
        encoded_tar = tar_and_encode_scripts()
        user_data = get_user_data_script(orchestrators, encoded_tar)
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
        for i in range(INSTANCES_PER_REGION):
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

            thisInstanceStatusObject = InstanceStatus(region, zone)
            all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject
            start_time = time.time()
            launch_specification = {
                "ImageId": UBUNTU_AMIS[region],
                "InstanceType": "t2.medium",
                "KeyName": KEY_PAIR_NAME,
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
            all_statuses[thisInstanceStatusObject.id] = (
                thisInstanceStatusObject  # Update all_statuses
            )

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
                            {"Key": "ManagedBy", "Value": "SpotInstanceScript"},
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
            instance_ids.extend(zone_instance_ids)

            if zone_instance_ids:
                thisInstanceStatusObject.instance_id = zone_instance_ids[0]
                thisInstanceStatusObject.status = "Tagging"

                # Tag instances
                await asyncio.to_thread(
                    ec2.create_tags,
                    Resources=zone_instance_ids,
                    Tags=[
                        {"Key": "ManagedBy", "Value": "SpotInstanceScript"},
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
                all_statuses[thisInstanceStatusObject.id] = thisInstanceStatusObject

    except Exception as e:
        logging.error(f"An error occurred in {region}: {str(e)}", exc_info=True)
        return [], {}

    return instance_ids, all_statuses


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


async def create_subnet(ec2, vpc_id, zone, cidr_block):
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
            cidrBlock = cidr_base_prefix + str(i) + cidr_base_suffix
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
                # Found the main route table, return its ID
                return rt["RouteTableId"]

    # If no route table exists, create a new one
    route_table = await asyncio.to_thread(ec2.create_route_table, VpcId=vpc_id)
    route_table_id = route_table["RouteTable"]["RouteTableId"]
    await asyncio.to_thread(
        ec2.create_route,
        RouteTableId=route_table_id,
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=igw_id,
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


async def create_spot_instances(orchestrators):
    if not orchestrators:
        print("Error: No orchestrators specified.")
        return []

    global task_name
    task_name = "Creating Spot Instances"
    global task_total
    task_total = MAX_NODES

    logging.debug(
        f"Starting to create spot instances with orchestrators: {orchestrators}"
    )

    async def create_in_region(region):
        global global_node_count
        available_slots = MAX_NODES - global_node_count
        if available_slots <= 0:
            logging.warning(f"Reached maximum nodes. Skipping region: {region}")
            return [], {}
        instances_to_create = min(INSTANCES_PER_REGION, available_slots)
        if instances_to_create == 0:
            return [], {}

        logging.debug(
            f"Creating {instances_to_create} spot instances in region: {region}"
        )

        instance_ids = await create_spot_instances_in_region(
            region,
            orchestrators,
        )
        global_node_count += len(instance_ids)
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
                        {"Name": "key-name", "Values": [KEY_PAIR_NAME]},
                    ],
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        thisInstanceStatusObject = InstanceStatus(region, az)
                        thisInstanceStatusObject.instance_id = instance_id
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
                        all_statuses[f"{region}-{az}-{instance_id}"] = (
                            thisInstanceStatusObject
                        )

                        events_to_progress.append(instance_id)
                        task_total += 1  # Increment total for each instance found

            logging.debug(f"Found {len(all_statuses)} instances in region {region}")

        except Exception as e:
            logging.error(
                f"An error occurred while listing instances in {region}: {str(e)}"
            )

    logging.debug("Finished listing spot instances")

    return all_statuses


async def destroy_instances():
    instance_region_map = {}

    global task_name
    task_name = "Terminating Spot Instances"
    global task_total

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
                    {"Name": "key-name", "Values": [KEY_PAIR_NAME]},
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

    print(f"\nFound {len(all_statuses)} instances to terminate.")

    async def terminate_instances_in_region(region, region_instances):
        ec2 = get_ec2_client(region)
        try:
            await asyncio.to_thread(
                ec2.terminate_instances, InstanceIds=region_instances
            )
            waiter = ec2.get_waiter("instance_terminated")
            events_to_progress.append(len(region_instances))
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
                        all_statuses[instance_id].elapsed_time = elapsed_time
                        all_statuses[
                            instance_id
                        ].detailed_status = f"Terminating ({elapsed_time:.0f}s)"
                    await asyncio.sleep(10)

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
    instances_by_region = {}
    for instance_id, info in instance_region_map.items():
        region = info["region"]
        if region not in instances_by_region:
            instances_by_region[region] = []
        instances_by_region[region].append(instance_id)
        task_total += 1

    await asyncio.gather(
        *[
            terminate_instances_in_region(region, region_instances)
            for region, region_instances in instances_by_region.items()
        ]
    )


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


async def main():
    global table_update_running
    table_update_running = False

    # Start update_table in the background
    table_task = asyncio.create_task(update_table())

    parser = argparse.ArgumentParser(
        description="Manage spot instances across multiple AWS regions."
    )
    parser.add_argument(
        "action",
        choices=["create", "destroy", "list", "delete_disconnected_aws_nodes"],
        help="Action to perform",
    )
    parser.add_argument(
        "--orchestrators",
        help="Comma-separated list of orchestrator addresses",
        default="",
    )
    args = parser.parse_args()

    orchestrators = args.orchestrators.split(",")

    try:
        if args.action == "create":
            await create_spot_instances(orchestrators)
        elif args.action == "list":
            await list_spot_instances()
        elif args.action == "destroy":
            await destroy_instances()
        elif args.action == "delete_disconnected_aws_nodes":
            await delete_disconnected_aws_nodes()
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
    finally:
        table_update_event.set()
        await table_task


if __name__ == "__main__":
    asyncio.run(main())
