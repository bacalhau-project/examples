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
import concurrent.futures
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Custom exception for authentication errors
class AuthenticationError(Exception):
    """Exception raised when AWS authentication fails."""
    pass

import boto3
import botocore
from rich import box

# Rich library for better UI
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

# Configure console and logging
console = Console()

# Configure a file handler for detailed logging
log_file = "delete_vpcs.log"
debug_log_file = "debug_delete_vpcs.log"  # More detailed debug log

# Regular log file
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

# Debug log file with very detailed information
debug_handler = logging.FileHandler(debug_log_file)
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
    )
)

# Configure rich console handler with minimal output to keep UI clean
rich_handler = RichHandler(
    rich_tracebacks=True,
    console=console,
    show_time=False,
    show_path=False,
    markup=True,
    level=logging.WARNING,  # Only show warnings and errors in the UI
)

# Set up logging to write detailed logs to file but minimal to console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[file_handler, debug_handler, rich_handler],
)

# Configure boto3 and botocore to log debug information
logging.getLogger("boto3").setLevel(logging.DEBUG)
logging.getLogger("botocore").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.INFO)  # Too verbose at DEBUG

logger = logging.getLogger(__name__)


class AwsActivityTracker:
    def __init__(self):
        self.last_activity = ""
        self.total_calls = 0

    def update(self, service: str, operation: str, region: str):
        """Update AWS activity with latest call information."""
        self.total_calls += 1
        timestamp = time.strftime("%H:%M:%S")
        self.last_activity = f"[{timestamp}] {service.upper()}.{operation} → {region} (Total calls: {self.total_calls})"


class AwsVpcCleaner:
    def __init__(
        self,
        skip_credential_check: bool = False,
        debug: bool = False,
        region_filter: Optional[List[str]] = None,
        dry_run: bool = False,
        api_concurrency: int = 10,
    ):
        self.skip_credential_check = skip_credential_check
        self.dry_run = dry_run
        self.region_filter = region_filter
        
        # Set API concurrency - controls how many AWS API calls can run in parallel
        self.api_concurrency = api_concurrency
        self.api_semaphore = asyncio.Semaphore(api_concurrency)

        # AWS activity tracking
        self.aws_activity = {
            "last_request_time": time.time(),
            "request_count": 0,
            "last_service": "AWS",
            "last_action": "Initializing",
            "last_region": "global",
        }
        
        # VPC row tracking for table management
        self.vpc_row_map = {}
        
        # Locks for thread safety
        self._refresh_lock = asyncio.Lock()
        self._table_lock = asyncio.Lock()
        self._activity_lock = asyncio.Lock()
        
        # Flag to track if we should continue status printing
        self.should_print_status = True

        # Set logging level based on debug flag
        if debug:
            logger.setLevel(logging.DEBUG)
            logging.getLogger("botocore").setLevel(logging.INFO)
            logging.getLogger("boto3").setLevel(logging.INFO)
            logging.getLogger("urllib3").setLevel(logging.INFO)

        # Default AWS session
        self.session = boto3.Session()

        # Progress tracking component
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            expand=True,
        )

        # Region tasks dictionary to track progress
        self.region_tasks = {}

        # Get terminal width to calculate column widths
        terminal_width = console.width
        vpc_col_width = min(32, int(terminal_width * 0.20))
        region_col_width = min(20, int(terminal_width * 0.15))
        status_col_width = min(30, int(terminal_width * 0.25))
        resources_col_width = min(30, int(terminal_width * 0.30))

        # Details table for showing status
        self.details_table = Table(
            box=box.ROUNDED,
            expand=True,
            show_lines=False,
            collapse_padding=True,
            highlight=True,
        )
        self.details_table.add_column(
            "VPC ID", style="green", width=vpc_col_width, no_wrap=True
        )
        self.details_table.add_column(
            "Region", style="cyan", width=region_col_width, no_wrap=True
        )
        self.details_table.add_column(
            "Status", style="yellow", width=status_col_width, no_wrap=True
        )
        self.details_table.add_column(
            "Resources", style="magenta", width=resources_col_width, no_wrap=True
        )

        # Header panel with title
        title = "AWS VPC Cleanup Tool"
        if self.dry_run:
            title += " [SCAN-ONLY MODE - NO DELETION WILL OCCUR]"
            self.header_panel = Panel(
                Text(title, style="bold white on yellow", justify="center"),
                box=box.ROUNDED,
            )
            # Create the mode banner for dry-run/scan-only mode
            self.mode_banner = Panel(
                Text(
                    "! SCAN-ONLY MODE: NO RESOURCES WILL BE DELETED !", justify="center"
                ),
                style="yellow bold",
                box=box.HEAVY,
            )
        else:
            self.header_panel = Panel(
                Text(title, style="bold white on blue", justify="center"),
                box=box.ROUNDED,
            )
            # Create the mode banner for live mode
            self.mode_banner = Panel(
                Text("! LIVE MODE: RESOURCES ARE BEING DELETED !", justify="center"),
                style="red bold on white",
                box=box.HEAVY,
            )

        # Create a layout that includes a warning/mode banner at the bottom
        # as well as AWS activity panel and status messages
        self.layout = Layout()
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="status_section", size=5),  # Section for status displays
            Layout(name="mode_banner", size=3),  # Add mode banner at bottom
        )

        # Split main section for progress and details
        self.layout["main"].split_row(
            Layout(name="progress", ratio=2), Layout(name="details", ratio=3)
        )

        # Split status section for AWS activity and initialization status
        self.layout["status_section"].split_row(
            Layout(name="aws_activity", ratio=1), Layout(name="init_status", ratio=1)
        )

        # Create the mode banner with appropriate style
        if self.dry_run:
            # Yellow warning for dry-run/scan-only mode
            mode_banner = Panel(
                Text(
                    "! SCAN-ONLY MODE: NO RESOURCES WILL BE DELETED !", justify="center"
                ),
                style="yellow bold",
                box=box.HEAVY,
            )
        else:
            # Red warning for live mode
            mode_banner = Panel(
                Text("! LIVE MODE: RESOURCES ARE BEING DELETED !", justify="center"),
                style="red bold on white",
                box=box.HEAVY,
            )

        # Create the AWS activity panel with simpler text
        aws_activity_text = Text("Initializing AWS client...", style="cyan")
        aws_activity_panel = Panel(
            aws_activity_text,
            title=f"AWS API Activity (Max Concurrency: {self.api_concurrency})",
            border_style="cyan",
            title_align="left",
        )
        self.aws_activity_text = aws_activity_text
        
        # Initialize status text for initialization steps
        self.init_status_text = Text("Starting up...", style="blue")
        init_status_panel = Panel(
            self.init_status_text,
            title="Initialization Status",
            border_style="blue",
            title_align="left",
        )
        
        # Define initialization steps for display
        self.init_steps = [
            "Verifying AWS credentials",
            "Discovering available regions",
            "Preparing VPC scan",
            "Checking for VPC dependencies"
        ]
        self.init_step_index = 0
        
        # Update status section
        self.layout["init_status"].update(init_status_panel)
        self.layout["aws_activity"].update(aws_activity_panel)

        # Initialize the Live display with our layout
        self.live = Live(
            self.layout, console=console, screen=True, refresh_per_second=4
        )
        
        # Start AWS activity processing task
        self.activity_task = None

    def get_ec2_client(self, region: str):
        """Get EC2 client with activity tracking."""
        client = self.session.client(
            "ec2",
            region_name=region,
            config=botocore.config.Config(
                connect_timeout=10, read_timeout=15, retries={"max_attempts": 3}
            ),
        )

        # Create a wrapper for client methods to track activity
        def track_call(func_name):
            original_func = getattr(client, func_name)

            def wrapper(*args, **kwargs):
                # Just update the tracker, UI update happens in separate task
                self.aws_tracker.update("ec2", func_name, region)
                return original_func(*args, **kwargs)

            return wrapper

        # Wrap common EC2 operations
        common_operations = [
            "describe_vpcs",
            "describe_instances",
            "terminate_instances",
            "describe_security_groups",
            "describe_subnets",
            "describe_route_tables",
            "describe_internet_gateways",
            "describe_nat_gateways",
            "describe_network_interfaces",
            "delete_vpc",
        ]

        for operation in common_operations:
            if hasattr(client, operation):
                setattr(client, operation, track_call(operation))

        return client

    async def verify_aws_credentials(self) -> bool:
        """Verify that AWS credentials are valid."""
        logger.info("Verifying AWS credentials...")

        try:
            sts = self.session.client("sts")
            sts.get_caller_identity()
            logger.info("AWS credentials verified successfully.")
            return True
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            
            # Instead of raising errors, show informative warnings
            console.print("\n[bold yellow]AWS Credentials Issue Detected[/bold yellow]")
            
            if "Token" in error_message and "expired" in error_message:
                console.print("[yellow]Your AWS SSO token has expired.[/yellow]")
                console.print("[yellow]Please run one of the following commands to refresh your credentials:[/yellow]")
                console.print("  aws sso login")
                console.print("  aws configure sso")
                console.print("[yellow]Then try running this script again.[/yellow]")
            elif "AccessDenied" in error_message or "NotAuthorized" in error_message:
                console.print("[yellow]You don't have sufficient permissions to access AWS resources.[/yellow]")
                console.print("[yellow]Please check that your AWS credentials have the required permissions.[/yellow]")
            else:
                console.print(f"[yellow]AWS credentials error: {error_message}[/yellow]")
            
            # Log the error quietly but don't show error-level messages to the user
            logger.debug(f"AWS credentials verification failed: {error_message}")
            return False

    async def get_available_regions(self) -> List[str]:
        """Get all available AWS regions."""
        logger.info("Retrieving available AWS regions...")

        try:
            ec2 = self.session.client("ec2")
            response = ec2.describe_regions()
            regions = [region["RegionName"] for region in response["Regions"]]

            # Apply region filter if provided
            if self.region_filter:
                regions = [r for r in regions if r in self.region_filter]

            return regions
        except botocore.exceptions.ClientError as e:
            error_message = str(e)
            
            # Handle credential errors gracefully
            if "Token" in error_message and "expired" in error_message:
                console.print("\n[bold yellow]AWS SSO Token Has Expired[/bold yellow]")
                console.print("[yellow]Please run 'aws sso login' to refresh your credentials,[/yellow]")
                console.print("[yellow]then try running this script again.[/yellow]")
            elif "AccessDenied" in error_message or "NotAuthorized" in error_message:
                console.print("\n[bold yellow]AWS Access Denied[/bold yellow]")
                console.print("[yellow]You don't have sufficient permissions to list AWS regions.[/yellow]")
                console.print("[yellow]Please check your AWS credentials and permissions.[/yellow]")
            else:
                console.print(f"\n[bold yellow]AWS API Error[/bold yellow]")
                console.print(f"[yellow]Failed to retrieve AWS regions: {error_message}[/yellow]")
            
            # Log at debug level instead of error to avoid alarming red error messages
            logger.debug(f"AWS API error: {error_message}")
            return []

    async def get_vpc_ids(self, region: str) -> List[str]:
        """Get VPC IDs created by the DeploySpot script in a region."""
        logger.debug(f"Starting scan of region: {region}")

        # Create the EC2 client for this region with a timeout
        ec2 = self.session.client(
            "ec2",
            region_name=region,
            config=botocore.config.Config(
                connect_timeout=10, read_timeout=15, retries={"max_attempts": 3}
            ),
        )

        # Log that we're about to make the API call
        logger.debug(
            f"Calling describe_vpcs for region {region} with SpotInstance filters"
        )

        # Find VPCs that match our deploy_spot.py naming patterns and tags
        # Use our execute_aws_api method to run this call with concurrency control
        response = await self.execute_aws_api(
            ec2.describe_vpcs,
            Filters=[
                # Match VPCs with our specific name patterns
                {
                    "Name": "tag:Name",
                    "Values": ["SpotInstance-*", "SpotInstanceVPC"],
                },
                # Additional filter to ensure it's created by deploy_spot.py
                # If available - uncomment if your deploy_spot.py adds this tag
                # {
                #     "Name": "tag:CreatedBy",
                #     "Values": ["DeploySpot", "deploy_spot.py"],
                # }
            ]
        )

        # Log the raw response for debugging
        logger.debug(
            f"Raw VPC response for {region}: {json.dumps(response, default=str)}"
        )

        # Extract VPC IDs and verify they match our pattern
        vpc_ids = []
        for vpc in response.get("Vpcs", []):
            vpc_id = vpc["VpcId"]
            # Additional verification that this is from deploy_spot.py
            # based on naming pattern or tags
            name_tag = ""
            for tag in vpc.get("Tags", []):
                if tag["Key"] == "Name":
                    name_tag = tag["Value"]
                    break

            # Only include VPCs with appropriate name patterns
            if (
                name_tag.startswith("SpotInstance-")
                or name_tag == "SpotInstanceVPC"
            ):
                vpc_ids.append(vpc_id)
                logger.info(
                    f"Found DeploySpot VPC: {vpc_id} - {name_tag} in region {region}"
                )

                # Add to the details table immediately when found - only if not already there
                await self.update_region_status(
                    region, "Found - will process", vpc_id, f"Name: {name_tag}"
                )

        if vpc_ids:
            logger.info(
                f"Found {len(vpc_ids)} matching DeploySpot VPCs in region {region}"
            )
        else:
            # This is normal and expected for many regions
            logger.info(
                f"No DeploySpot VPCs found in region {region} - this is normal"
            )

        return vpc_ids

    async def terminate_vpc_instances(self, vpc_id: str, region: str) -> None:
        """Terminate all instances in a VPC."""
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would terminate instances in VPC: {vpc_id} (Region: {region})"
            )
            return

        logger.info(f"Terminating instances in VPC: {vpc_id} (Region: {region})")

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Find all instances in the VPC
            response = await self.execute_aws_api(
                ec2.describe_instances,
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {
                        "Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping", "stopped"],
                    },
                ]
            )

            instance_ids = []
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_ids.append(instance["InstanceId"])

            if instance_ids:
                logger.info(f"Found instances to terminate: {instance_ids}")
                
                # Terminate instances using our async API executor
                await self.execute_aws_api(
                    ec2.terminate_instances,
                    InstanceIds=instance_ids
                )

                logger.info("Waiting for instances to terminate...")
                # Waiters are blocking, so we need to run them in a separate thread
                waiter = ec2.get_waiter("instance_terminated")
                
                # We need to wrap the waiter.wait call in a lambda to pass it to execute_aws_api
                await self.execute_aws_api(
                    lambda: waiter.wait(InstanceIds=instance_ids)
                )
            else:
                logger.debug(f"No instances found in VPC {vpc_id}")

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error terminating instances in VPC {vpc_id}: {e}")

    async def list_vpc_dependencies(self, vpc_id: str, region: str) -> None:
        """List all dependencies of a VPC for visibility."""
        logger.info(f"Listing dependencies for VPC: {vpc_id} (Region: {region})")

        ec2 = self.session.client("ec2", region_name=region)

        # Create a list of async tasks for each dependency type
        tasks = [
            self._list_instances(ec2, vpc_id),
            self._list_nat_gateways(ec2, vpc_id),
            self._list_network_interfaces(ec2, vpc_id),
            self._list_subnets(ec2, vpc_id),
            self._list_route_tables(ec2, vpc_id),
            self._list_security_groups(ec2, vpc_id),
            self._list_load_balancers(region, vpc_id),
            self._list_transit_gateways(ec2, vpc_id),
            self._list_vpc_endpoints(ec2, vpc_id),
            self._list_vpc_peering(ec2, vpc_id),
            self._list_vpn_gateways(ec2, vpc_id),
        ]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    async def _list_instances(self, ec2, vpc_id: str) -> None:
        try:
            response = await self.execute_aws_api(
                ec2.describe_instances,
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("Instances:")
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    state = instance["State"]["Name"]
                    instance_type = instance.get("InstanceType", "N/A")
                    subnet_id = instance.get("SubnetId", "N/A")

                    # Get Name tag if available
                    name = "N/A"
                    for tag in instance.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    logger.info(
                        f"  {instance_id} | {state} | {instance_type} | {subnet_id} | {name}"
                    )
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing instances: {e}")

    async def _list_nat_gateways(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_nat_gateways(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("NAT Gateways:")
            for natgw in response.get("NatGateways", []):
                natgw_id = natgw["NatGatewayId"]
                state = natgw["State"]
                subnet_id = natgw.get("SubnetId", "N/A")
                alloc_id = "N/A"
                if (
                    natgw.get("NatGatewayAddresses")
                    and len(natgw["NatGatewayAddresses"]) > 0
                ):
                    alloc_id = natgw["NatGatewayAddresses"][0].get(
                        "AllocationId", "N/A"
                    )

                logger.info(f"  {natgw_id} | {state} | {subnet_id} | {alloc_id}")
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing NAT gateways: {e}")

    async def _list_network_interfaces(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_network_interfaces(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("Network Interfaces (ENIs):")
            for eni in response.get("NetworkInterfaces", []):
                eni_id = eni["NetworkInterfaceId"]
                status = eni["Status"]
                description = eni.get("Description", "N/A")
                subnet_id = eni.get("SubnetId", "N/A")
                owner_id = eni.get("OwnerId", "N/A")
                requester_managed = str(eni.get("RequesterManaged", "N/A"))
                interface_type = eni.get("InterfaceType", "N/A")

                logger.info(
                    f"  {eni_id} | {status} | {description} | {subnet_id} | {owner_id} | {requester_managed} | {interface_type}"
                )
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing network interfaces: {e}")

    async def _list_subnets(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("Subnets:")
            for subnet in response.get("Subnets", []):
                subnet_id = subnet["SubnetId"]
                cidr_block = subnet["CidrBlock"]
                az = subnet["AvailabilityZone"]
                public_ip = str(subnet.get("MapPublicIpOnLaunch", "N/A"))

                logger.info(f"  {subnet_id} | {cidr_block} | {az} | {public_ip}")
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing subnets: {e}")

    async def _list_route_tables(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_route_tables(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("Route Tables and Associations:")
            for rt in response.get("RouteTables", []):
                rt_id = rt["RouteTableId"]
                associations = []

                for assoc in rt.get("Associations", []):
                    subnet_id = assoc.get("SubnetId", "N/A")
                    main = str(assoc.get("Main", False))
                    associations.append(f"{subnet_id} (Main: {main})")

                logger.info(
                    f"  {rt_id} | Associations: {', '.join(associations) if associations else 'None'}"
                )
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing route tables: {e}")

    async def _list_security_groups(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_security_groups(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("Security Groups:")
            for sg in response.get("SecurityGroups", []):
                sg_id = sg["GroupId"]
                sg_name = sg["GroupName"]
                description = sg.get("Description", "N/A")

                logger.info(f"  {sg_id} | {sg_name} | {description}")
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing security groups: {e}")

    async def _list_load_balancers(self, region: str, vpc_id: str) -> None:
        try:
            elbv2 = self.session.client("elbv2", region_name=region)
            response = elbv2.describe_load_balancers()

            logger.info("Load Balancers:")
            for lb in response.get("LoadBalancers", []):
                if lb.get("VpcId") == vpc_id:
                    lb_arn = lb["LoadBalancerArn"]
                    dns_name = lb.get("DNSName", "N/A")
                    state = lb.get("State", {}).get("Code", "N/A")
                    lb_type = lb.get("Type", "N/A")

                    logger.info(f"  {lb_arn} | {dns_name} | {state} | {lb_type}")
        except botocore.exceptions.ClientError as e:
            if "AccessDenied" not in str(e):
                logger.error(f"Error listing load balancers: {e}")

    async def _list_transit_gateways(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_transit_gateway_vpc_attachments(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("Transit Gateway Attachments:")
            for tgw in response.get("TransitGatewayVpcAttachments", []):
                tgw_id = tgw["TransitGatewayAttachmentId"]
                state = tgw["State"]
                transit_gateway_id = tgw.get("TransitGatewayId", "N/A")

                logger.info(f"  {tgw_id} | {state} | {transit_gateway_id}")
        except botocore.exceptions.ClientError as e:
            if "AccessDenied" not in str(e):
                logger.error(f"Error listing transit gateways: {e}")

    async def _list_vpc_endpoints(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_vpc_endpoints(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            logger.info("VPC Endpoints:")
            for endpoint in response.get("VpcEndpoints", []):
                endpoint_id = endpoint["VpcEndpointId"]
                endpoint_type = endpoint["VpcEndpointType"]
                state = endpoint["State"]
                service_name = endpoint["ServiceName"]

                logger.info(
                    f"  {endpoint_id} | {endpoint_type} | {state} | {service_name}"
                )
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing VPC endpoints: {e}")

    async def _list_vpc_peering(self, ec2, vpc_id: str) -> None:
        try:
            # Check both requester and accepter sides
            response = ec2.describe_vpc_peering_connections(
                Filters=[
                    {"Name": "requester-vpc-info.vpc-id", "Values": [vpc_id]},
                    {"Name": "accepter-vpc-info.vpc-id", "Values": [vpc_id]},
                ]
            )

            logger.info("VPC Peering Connections:")
            for peering in response.get("VpcPeeringConnections", []):
                peering_id = peering["VpcPeeringConnectionId"]
                status = peering.get("Status", {}).get("Code", "N/A")
                requester_vpc = peering.get("RequesterVpcInfo", {}).get("VpcId", "N/A")
                accepter_vpc = peering.get("AccepterVpcInfo", {}).get("VpcId", "N/A")

                logger.info(
                    f"  {peering_id} | {status} | Requester: {requester_vpc} | Accepter: {accepter_vpc}"
                )
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing VPC peering connections: {e}")

    async def _list_vpn_gateways(self, ec2, vpc_id: str) -> None:
        try:
            response = ec2.describe_vpn_gateways(
                Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
            )

            logger.info("VPN Gateways:")
            for vpn in response.get("VpnGateways", []):
                vpn_id = vpn["VpnGatewayId"]
                state = vpn["State"]
                vpn_type = vpn["Type"]

                logger.info(f"  {vpn_id} | {state} | {vpn_type}")
        except botocore.exceptions.ClientError as e:
            logger.error(f"Error listing VPN gateways: {e}")

    async def cleanup_security_group_rules(self, vpc_id: str, region: str) -> None:
        """Clean up all security group rules in a VPC."""
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would clean up security group rules for VPC: {vpc_id}"
            )
            return

        logger.info(f"Cleaning up security group rules for VPC: {vpc_id}")

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all security groups in the VPC
            response = ec2.describe_security_groups(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            security_groups = response.get("SecurityGroups", [])
            for sg in security_groups:
                sg_id = sg["GroupId"]
                logger.info(f"Cleaning rules for security group: {sg_id}")

                # Try to use the newer API first for ingress rules
                try:
                    ingress_rules_response = ec2.describe_security_group_rules(
                        Filters=[
                            {"Name": "group-id", "Values": [sg_id]},
                            {"Name": "is-egress", "Values": ["false"]},
                        ]
                    )

                    ingress_rules = ingress_rules_response.get("SecurityGroupRules", [])
                    if ingress_rules:
                        logger.info(
                            f"Removing {len(ingress_rules)} ingress rules for security group: {sg_id}"
                        )
                        for rule in ingress_rules:
                            rule_id = rule["SecurityGroupRuleId"]
                            try:
                                ec2.revoke_security_group_rules(
                                    GroupId=sg_id, SecurityGroupRuleIds=[rule_id]
                                )
                                logger.debug(f"Removed ingress rule: {rule_id}")
                            except botocore.exceptions.ClientError as e:
                                logger.warning(
                                    f"Error removing ingress rule {rule_id}: {e}"
                                )
                except botocore.exceptions.ClientError:
                    # Fall back to the older method
                    logger.info(
                        f"Using legacy method to remove ingress rules for security group: {sg_id}"
                    )
                    try:
                        ip_permissions = sg.get("IpPermissions", [])
                        if ip_permissions:
                            ec2.revoke_security_group_ingress(
                                GroupId=sg_id, IpPermissions=ip_permissions
                            )
                    except botocore.exceptions.ClientError as e:
                        logger.warning(
                            f"Error removing ingress rules using legacy method: {e}"
                        )

                # Try to use the newer API first for egress rules
                try:
                    egress_rules_response = ec2.describe_security_group_rules(
                        Filters=[
                            {"Name": "group-id", "Values": [sg_id]},
                            {"Name": "is-egress", "Values": ["true"]},
                        ]
                    )

                    egress_rules = egress_rules_response.get("SecurityGroupRules", [])
                    if egress_rules:
                        logger.info(
                            f"Removing {len(egress_rules)} egress rules for security group: {sg_id}"
                        )
                        for rule in egress_rules:
                            rule_id = rule["SecurityGroupRuleId"]
                            try:
                                ec2.revoke_security_group_rules(
                                    GroupId=sg_id, SecurityGroupRuleIds=[rule_id]
                                )
                                logger.debug(f"Removed egress rule: {rule_id}")
                            except botocore.exceptions.ClientError as e:
                                logger.warning(
                                    f"Error removing egress rule {rule_id}: {e}"
                                )
                except botocore.exceptions.ClientError:
                    # Fall back to the older method
                    logger.info(
                        f"Using legacy method to remove egress rules for security group: {sg_id}"
                    )
                    try:
                        ip_permissions_egress = sg.get("IpPermissionsEgress", [])
                        if ip_permissions_egress:
                            ec2.revoke_security_group_egress(
                                GroupId=sg_id, IpPermissions=ip_permissions_egress
                            )
                    except botocore.exceptions.ClientError as e:
                        logger.warning(
                            f"Error removing egress rules using legacy method: {e}"
                        )

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error cleaning up security group rules: {e}")

    async def delete_load_balancers(self, vpc_id: str, region: str) -> None:
        """Delete all load balancers in the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete load balancers in VPC: {vpc_id}")
            return

        try:
            elbv2 = self.session.client("elbv2", region_name=region)

            # Get all load balancers
            response = elbv2.describe_load_balancers()

            # Filter for this VPC
            for lb in response.get("LoadBalancers", []):
                if lb.get("VpcId") == vpc_id:
                    lb_arn = lb["LoadBalancerArn"]
                    logger.info(f"Deleting Load Balancer: {lb_arn}")
                    try:
                        elbv2.delete_load_balancer(LoadBalancerArn=lb_arn)
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error deleting load balancer {lb_arn}: {e}")

        except botocore.exceptions.ClientError as e:
            if "AccessDenied" not in str(e):
                logger.error(f"Error handling load balancers: {e}")

    async def delete_transit_gateway_attachments(
        self, vpc_id: str, region: str
    ) -> None:
        """Delete all transit gateway attachments in the VPC."""
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would delete transit gateway attachments in VPC: {vpc_id}"
            )
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all transit gateway attachments
            response = ec2.describe_transit_gateway_vpc_attachments(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            for tgw in response.get("TransitGatewayVpcAttachments", []):
                tgw_id = tgw["TransitGatewayAttachmentId"]
                logger.info(f"Deleting Transit Gateway Attachment: {tgw_id}")
                try:
                    ec2.delete_transit_gateway_vpc_attachment(
                        TransitGatewayAttachmentId=tgw_id, Force=True
                    )
                except botocore.exceptions.ClientError as e:
                    logger.warning(
                        f"Error deleting transit gateway attachment {tgw_id}: {e}"
                    )

        except botocore.exceptions.ClientError as e:
            if "AccessDenied" not in str(e):
                logger.error(f"Error handling transit gateway attachments: {e}")

    async def delete_vpc_endpoints(self, vpc_id: str, region: str) -> None:
        """Delete all VPC endpoints in the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete VPC endpoints in VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all VPC endpoints
            response = ec2.describe_vpc_endpoints(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            endpoint_ids = [
                ep["VpcEndpointId"] for ep in response.get("VpcEndpoints", [])
            ]

            if endpoint_ids:
                logger.info(f"Deleting VPC Endpoints: {endpoint_ids}")
                try:
                    ec2.delete_vpc_endpoints(VpcEndpointIds=endpoint_ids)
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error deleting VPC endpoints: {e}")

                    # Try one by one if batch deletion fails
                    for endpoint_id in endpoint_ids:
                        try:
                            logger.info(
                                f"Retrying deletion of VPC Endpoint: {endpoint_id}"
                            )
                            ec2.delete_vpc_endpoints(VpcEndpointIds=[endpoint_id])
                        except botocore.exceptions.ClientError as e2:
                            logger.warning(
                                f"Error deleting VPC endpoint {endpoint_id}: {e2}"
                            )

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling VPC endpoints: {e}")

    async def delete_nat_gateways(self, vpc_id: str, region: str) -> None:
        """Delete all NAT gateways in the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete NAT gateways in VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all NAT gateways
            response = ec2.describe_nat_gateways(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            nat_gateways = [
                ng["NatGatewayId"]
                for ng in response.get("NatGateways", [])
                if ng["State"] != "deleted"
            ]

            if nat_gateways:
                logger.info(f"Deleting NAT Gateways: {nat_gateways}")
                for nat_id in nat_gateways:
                    try:
                        ec2.delete_nat_gateway(NatGatewayId=nat_id)
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error deleting NAT gateway {nat_id}: {e}")

                logger.info("Waiting for NAT Gateways to delete...")
                await asyncio.sleep(
                    30
                )  # Give some time for NAT Gateway deletion to start

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling NAT gateways: {e}")

    async def delete_network_interfaces(self, vpc_id: str, region: str) -> None:
        """Delete all network interfaces in the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete network interfaces in VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all network interfaces
            response = ec2.describe_network_interfaces(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            for eni in response.get("NetworkInterfaces", []):
                eni_id = eni["NetworkInterfaceId"]
                logger.info(f"Deleting network interface: {eni_id}")

                # Try to detach first if attached
                if eni.get("Attachment"):
                    attachment_id = eni["Attachment"].get("AttachmentId")
                    if attachment_id:
                        try:
                            logger.debug(f"Detaching network interface: {eni_id}")
                            ec2.detach_network_interface(
                                AttachmentId=attachment_id, Force=True
                            )
                            await asyncio.sleep(5)  # Give it time to detach
                        except botocore.exceptions.ClientError as e:
                            logger.warning(
                                f"Error detaching network interface {eni_id}: {e}"
                            )

                # Now try to delete
                try:
                    ec2.delete_network_interface(NetworkInterfaceId=eni_id)
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error deleting network interface {eni_id}: {e}")

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling network interfaces: {e}")

    async def delete_internet_gateways(self, vpc_id: str, region: str) -> None:
        """Delete all internet gateways attached to the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete internet gateways for VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all internet gateways
            response = ec2.describe_internet_gateways(
                Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
            )

            for igw in response.get("InternetGateways", []):
                igw_id = igw["InternetGatewayId"]
                logger.info(f"Detaching and deleting internet gateway: {igw_id}")

                try:
                    ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error detaching internet gateway {igw_id}: {e}")

                try:
                    ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error deleting internet gateway {igw_id}: {e}")

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling internet gateways: {e}")

    async def delete_security_groups(self, vpc_id: str, region: str) -> None:
        """Delete all non-default security groups in the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete security groups in VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all non-default security groups
            response = ec2.describe_security_groups(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "group-name", "Values": ["*"]},
                ]
            )

            # Filter out the default security group which cannot be deleted
            security_groups = [
                sg["GroupId"]
                for sg in response.get("SecurityGroups", [])
                if sg["GroupName"] != "default"
            ]

            for sg_id in security_groups:
                logger.info(f"Deleting security group: {sg_id}")

                # Try up to 3 times to delete the security group
                max_retries = 3
                for i in range(max_retries):
                    try:
                        ec2.delete_security_group(GroupId=sg_id)
                        logger.info(f"Successfully deleted security group: {sg_id}")
                        break
                    except botocore.exceptions.ClientError as e:
                        logger.warning(
                            f"Retry {i + 1}: Failed to delete security group: {sg_id} - {e}"
                        )

                        # Double-check there are really no rules left
                        try:
                            # Try to remove any remaining rules
                            ec2.revoke_security_group_ingress(
                                GroupId=sg_id,
                                IpPermissions=[
                                    {
                                        "IpProtocol": "-1",
                                        "FromPort": -1,
                                        "ToPort": -1,
                                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                                    }
                                ],
                            )
                        except botocore.exceptions.ClientError:
                            pass

                        try:
                            ec2.revoke_security_group_egress(
                                GroupId=sg_id,
                                IpPermissions=[
                                    {
                                        "IpProtocol": "-1",
                                        "FromPort": -1,
                                        "ToPort": -1,
                                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                                    }
                                ],
                            )
                        except botocore.exceptions.ClientError:
                            pass

                        if i == max_retries - 1:
                            logger.warning(
                                f"WARNING: Failed to delete security group after {max_retries} attempts: {sg_id}"
                            )
                        else:
                            await asyncio.sleep(5)

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling security groups: {e}")

    async def wait_for_nat_gateway_deletion(self, vpc_id: str, region: str) -> None:
        """Wait for all NAT gateways in the VPC to be deleted."""
        if self.dry_run:
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Check if there are any NAT gateways still being deleted
            response = ec2.describe_nat_gateways(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            pending_nats = [
                ng["NatGatewayId"]
                for ng in response.get("NatGateways", [])
                if ng["State"] != "deleted"
            ]

            if pending_nats:
                logger.info("Waiting for NAT Gateways to be deleted...")

                max_wait_time = 300  # seconds
                wait_interval = 10
                waited_time = 0

                while waited_time < max_wait_time:
                    response = ec2.describe_nat_gateways(
                        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
                    )

                    pending_nats = [
                        ng["NatGatewayId"]
                        for ng in response.get("NatGateways", [])
                        if ng["State"] != "deleted"
                    ]

                    if not pending_nats:
                        logger.info("All NAT Gateways have been deleted.")
                        break

                    logger.info(
                        f"Still waiting for NAT Gateways to be deleted: {pending_nats}"
                    )
                    await asyncio.sleep(wait_interval)
                    waited_time += wait_interval

                if waited_time >= max_wait_time:
                    logger.warning(
                        f"Timed out waiting for NAT Gateways to be deleted: {pending_nats}"
                    )

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error waiting for NAT gateway deletion: {e}")

    async def delete_route_tables(self, vpc_id: str, region: str) -> None:
        """Delete all route tables in the VPC except the main one."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete route tables in VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all route tables
            response = ec2.describe_route_tables(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            for rt in response.get("RouteTables", []):
                rt_id = rt["RouteTableId"]

                # Check if it's the main route table
                is_main = any(
                    assoc.get("Main", False) for assoc in rt.get("Associations", [])
                )

                logger.info(f"Processing route table: {rt_id} (Main: {is_main})")

                # First, delete all non-local routes
                routes_to_delete = []
                ipv6_routes_to_delete = []

                for route in rt.get("Routes", []):
                    if route.get("GatewayId") != "local":
                        if "DestinationCidrBlock" in route:
                            routes_to_delete.append(route["DestinationCidrBlock"])
                        elif "DestinationIpv6CidrBlock" in route:
                            ipv6_routes_to_delete.append(
                                route["DestinationIpv6CidrBlock"]
                            )

                # Delete IPv4 routes
                for route_cidr in routes_to_delete:
                    logger.info(
                        f"Deleting IPv4 route to {route_cidr} from route table {rt_id}"
                    )
                    try:
                        ec2.delete_route(
                            RouteTableId=rt_id, DestinationCidrBlock=route_cidr
                        )
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error deleting IPv4 route {route_cidr}: {e}")

                # Delete IPv6 routes
                for route_cidr in ipv6_routes_to_delete:
                    logger.info(
                        f"Deleting IPv6 route to {route_cidr} from route table {rt_id}"
                    )
                    try:
                        ec2.delete_route(
                            RouteTableId=rt_id, DestinationIpv6CidrBlock=route_cidr
                        )
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error deleting IPv6 route {route_cidr}: {e}")

                # Handle route table associations
                for assoc in rt.get("Associations", []):
                    assoc_id = assoc.get("RouteTableAssociationId")
                    if assoc_id and not assoc.get("Main", False):
                        logger.info(
                            f"Disassociating route table association: {assoc_id}"
                        )
                        try:
                            ec2.disassociate_route_table(AssociationId=assoc_id)
                        except botocore.exceptions.ClientError as e:
                            logger.warning(
                                f"Error disassociating route table {assoc_id}: {e}"
                            )

                # Only try to delete non-main route tables
                if not is_main:
                    logger.info(f"Deleting route table: {rt_id}")
                    try:
                        ec2.delete_route_table(RouteTableId=rt_id)
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error deleting route table {rt_id}: {e}")
                else:
                    logger.info(
                        f"Skipping deletion of main route table {rt_id} (will be deleted with VPC)"
                    )

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling route tables: {e}")

    async def delete_subnets(self, vpc_id: str, region: str) -> None:
        """Delete all subnets in the VPC."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete subnets in VPC: {vpc_id}")
            return

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Get all subnets
            response = ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            for subnet in response.get("Subnets", []):
                subnet_id = subnet["SubnetId"]
                logger.info(f"Deleting subnet: {subnet_id}")
                try:
                    ec2.delete_subnet(SubnetId=subnet_id)
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error deleting subnet {subnet_id}: {e}")

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error handling subnets: {e}")

    async def check_remaining_dependencies(
        self, vpc_id: str, region: str
    ) -> Dict[str, List[str]]:
        """Check for any remaining dependencies in the VPC."""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            dependencies = {}

            # Check for instances
            response = ec2.describe_instances(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {
                        "Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping", "stopped"],
                    },
                ]
            )

            instances = []
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instances.append(instance["InstanceId"])

            if instances:
                dependencies["instances"] = instances

            # Check for NAT gateways
            response = ec2.describe_nat_gateways(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            nat_gateways = [
                ng["NatGatewayId"]
                for ng in response.get("NatGateways", [])
                if ng["State"] != "deleted"
            ]

            if nat_gateways:
                dependencies["nat_gateways"] = nat_gateways

            # Check for network interfaces
            response = ec2.describe_network_interfaces(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            network_interfaces = [
                eni["NetworkInterfaceId"]
                for eni in response.get("NetworkInterfaces", [])
            ]

            if network_interfaces:
                dependencies["network_interfaces"] = network_interfaces

            return dependencies

        except botocore.exceptions.ClientError as e:
            logger.error(f"Error checking remaining dependencies: {e}")
            return {}

    async def force_cleanup_remaining_resources(
        self, vpc_id: str, region: str, dependencies: Dict[str, List[str]]
    ) -> None:
        """Force cleanup of any remaining resources that prevent VPC deletion."""
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would force cleanup remaining resources in VPC: {vpc_id}"
            )
            return

        logger.info(
            f"Attempting to force cleanup of remaining resources in VPC: {vpc_id}"
        )

        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Force terminate any instances
            if "instances" in dependencies and dependencies["instances"]:
                instances = dependencies["instances"]
                logger.info(f"Force terminating instances: {instances}")
                try:
                    ec2.terminate_instances(InstanceIds=instances)
                    await asyncio.sleep(10)
                except botocore.exceptions.ClientError as e:
                    logger.warning(f"Error force terminating instances: {e}")

            # Force delete network interfaces
            if (
                "network_interfaces" in dependencies
                and dependencies["network_interfaces"]
            ):
                for eni in dependencies["network_interfaces"]:
                    logger.info(f"Force detaching network interface: {eni}")

                    try:
                        # Get attachment if exists
                        response = ec2.describe_network_interfaces(
                            NetworkInterfaceIds=[eni]
                        )

                        if response.get("NetworkInterfaces") and response[
                            "NetworkInterfaces"
                        ][0].get("Attachment"):
                            attachment_id = response["NetworkInterfaces"][0][
                                "Attachment"
                            ]["AttachmentId"]
                            ec2.detach_network_interface(
                                AttachmentId=attachment_id, Force=True
                            )
                            await asyncio.sleep(2)
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error detaching network interface {eni}: {e}")

                    logger.info(f"Force deleting network interface: {eni}")
                    try:
                        ec2.delete_network_interface(NetworkInterfaceId=eni)
                    except botocore.exceptions.ClientError as e:
                        logger.warning(f"Error deleting network interface {eni}: {e}")

            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"Error in force cleanup: {e}")

    async def delete_vpc(self, vpc_id: str, region: str, wait_for_deletion: bool = True) -> bool:
        """Delete a VPC after cleaning up all its resources.
        
        Args:
            vpc_id: The ID of the VPC to delete
            region: The AWS region where the VPC is located
            wait_for_deletion: If True, wait and retry until VPC is completely deleted.
                               If False, return True as soon as deletion has been initiated.
        
        Returns:
            bool: True if VPC deletion succeeded or was initiated, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete VPC: {vpc_id} in region {region}")
            return True

        logger.info(f"Deleting VPC: {vpc_id} in region {region}")

        # Try to delete with multiple retries
        max_retries = 3 if wait_for_deletion else 1
        vpc_deleted = False
        deletion_initiated = False

        for retry in range(max_retries):
            try:
                # Check for remaining dependencies
                dependencies = await self.check_remaining_dependencies(vpc_id, region)

                if dependencies:
                    logger.info(f"Found remaining dependencies in VPC {vpc_id}:")
                    for dep_type, resources in dependencies.items():
                        logger.info(f" - {dep_type}: {resources}")

                    # Try to force clean up remaining resources
                    await self.force_cleanup_remaining_resources(
                        vpc_id, region, dependencies
                    )

                # Try to delete the VPC
                logger.info(f"Attempt {retry + 1} to delete VPC: {vpc_id}")

                ec2 = self.session.client("ec2", region_name=region)
                # Execute VPC deletion using our async API executor
                await self.execute_aws_api(
                    ec2.delete_vpc,
                    VpcId=vpc_id
                )
                
                # Mark that we've at least initiated deletion
                deletion_initiated = True

                if wait_for_deletion:
                    logger.info(f"Successfully deleted VPC: {vpc_id} in region {region}")
                    vpc_deleted = True
                    break
                else:
                    # If not waiting for complete deletion, consider initiated deletion a success
                    logger.info(f"Initiated deletion of VPC: {vpc_id} in region {region}")
                    return True

            except botocore.exceptions.ClientError as e:
                if "does not exist" in str(e).lower():
                    # VPC doesn't exist anymore - consider this a success
                    logger.info(f"VPC {vpc_id} no longer exists - deletion was successful")
                    return True
                    
                logger.warning(
                    f"Failed to delete VPC {vpc_id} on attempt {retry + 1}: {e}"
                )
                if retry < max_retries - 1 and wait_for_deletion:
                    logger.info(f"Retrying in 10 seconds...")
                    await asyncio.sleep(10)

        if not wait_for_deletion:
            # When not waiting for complete deletion, return status of deletion initiation
            return deletion_initiated
            
        if not vpc_deleted and wait_for_deletion:
            logger.warning(
                f"WARNING: Failed to delete VPC {vpc_id} in region {region} after {max_retries} attempts."
            )
            logger.warning(
                "You may need to manually check for remaining dependencies in the AWS Console."
            )

        return vpc_deleted

    def truncate_str(self, text: str, max_width: int) -> str:
        """Truncate text to fit within column width, adding ellipsis if needed."""
        if not text:
            return ""

        # Convert to string if not already
        text = str(text)

        # Account for ellipsis if we need to truncate
        if len(text) > max_width:
            # Allow room for the ellipsis "..."
            return text[: max(0, max_width - 3)] + "..."
        return text

    def _setup_aws_call_tracking(self):
        """Set up event handlers to track AWS API calls."""
        try:
            events = self.session._session.get_component("event_emitter")
            events.register("before-call.*.*", self._track_aws_call)
            logger.debug("AWS API call tracking enabled")
        except Exception as e:
            logger.warning(f"Could not set up AWS API call tracking: {e}")
            
    async def execute_aws_api(self, func, *args, **kwargs):
        """Execute an AWS API call with concurrency control.
        
        This wrapper ensures we don't exceed AWS API rate limits by
        using a semaphore to control the number of concurrent calls.
        Also handles AWS credential errors gracefully.
        
        Args:
            func: The AWS API function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the API call
        """
        async with self.api_semaphore:
            try:
                # Use asyncio.to_thread to run the blocking AWS API call in a separate thread
                # This prevents blocking the event loop while making the AWS API call
                return await asyncio.to_thread(func, *args, **kwargs)
            except botocore.exceptions.ClientError as e:
                error_message = str(e)
                
                # Handle specific AWS credential errors gracefully
                if "ExpiredToken" in error_message or "expired" in error_message.lower():
                    # Don't log as error - just debug to avoid red error messages
                    logger.debug(f"AWS token expired: {error_message}")
                    
                    # Show a yellow warning instead of red error
                    console.print("\n[bold yellow]AWS Token Expired[/bold yellow]")
                    console.print("[yellow]Your AWS SSO token has expired during operation.[/yellow]")
                    console.print("[yellow]Please run 'aws sso login' to refresh your credentials,[/yellow]")
                    console.print("[yellow]then try running this script again.[/yellow]")
                    
                    # Signal to the caller that an authentication error occurred
                    raise AuthenticationError("AWS token expired") from e
                
                # Re-raise the original exception for other types of errors
                raise

    def _track_aws_call(self, params, model, **kwargs):
        """Track AWS API calls to show in the UI."""
        try:
            # Extract service and operation information
            service = model.service_model.service_name
            operation = model.name
            region = params.get('context', {}).get('client_region', 'unknown')
            
            # Update activity tracking info (non-async context)
            self.aws_activity["last_request_time"] = time.time()
            self.aws_activity["request_count"] += 1
            self.aws_activity["last_service"] = service
            self.aws_activity["last_action"] = operation
            self.aws_activity["last_region"] = region
            
            # Create a formatted activity message
            msg = f"{service.upper()}.{operation} → Region: {region}"
            
            # Update the UI text (will be displayed on next refresh)
            # Using a simple string concatenation approach here
            # This avoids async issues since this is called from a non-async context
            try:
                if hasattr(self, 'aws_activity_text'):
                    timestamp = time.strftime("%H:%M:%S")
                    self.aws_activity_text.plain = f"[{timestamp}] {msg} (API Calls: {self.aws_activity['request_count']})"
            except Exception as ex:
                logger.debug(f"Could not update AWS activity display: {ex}")
            
            # Log to debug log
            logger.debug(f"AWS API Call: {msg}")
        except Exception as e:
            logger.debug(f"Error tracking AWS call: {e}")

    async def _update_aws_activity_display(self):
        """Update the AWS activity display in the UI."""
        try:
            if hasattr(self, 'aws_activity_text'):
                activity = self.aws_activity
                elapsed = int(time.time() - activity["last_request_time"])
                timestamp = time.strftime("%H:%M:%S")
                
                # Calculate current active API calls by checking semaphore value
                # The _value attribute gives us the current count of available permits
                active_calls = self.api_concurrency - self.api_semaphore._value
                if active_calls < 0:  # Safeguard against potential race conditions
                    active_calls = 0
                
                if elapsed < 10:  # Recent activity
                    msg = f"[{timestamp}] {activity['last_service'].upper()}.{activity['last_action']} → {activity['last_region']}"
                    self.aws_activity_text.plain = (
                        f"{msg}\n"
                        f"Total calls: {activity['request_count']} | "
                        f"Active calls: {active_calls}/{self.api_concurrency}"
                    )
                else:  # No recent activity
                    self.aws_activity_text.plain = (
                        f"[{timestamp}] Last API call {elapsed}s ago\n"
                        f"Total calls: {activity['request_count']} | "
                        f"Active calls: {active_calls}/{self.api_concurrency}"
                    )
        except Exception as e:
            logger.debug(f"Error updating AWS activity display: {e}")

    async def _update_init_status(self):
        """Update the initialization status display in the UI."""
        try:
            if hasattr(self, "init_status_text") and hasattr(self, "init_steps"):
                # Update the current step index
                self.init_step_index = (self.init_step_index + 1) % len(self.init_steps)

                # Format the status lines with the current step highlighted
                status_lines = []
                for i in range(len(self.init_steps)):
                    # Mark current step with bullet, completed steps with checkmark, future steps with empty box
                    if i == self.init_step_index:
                        marker = "[•]"  # Current step
                    elif i < self.init_step_index:
                        marker = "[✓]"  # Completed step
                    else:
                        marker = "[ ]"  # Future step

                    status_lines.append(f"{marker} {self.init_steps[i]}")

                # Update the text widget
                self.init_status_text.plain = "\n".join(status_lines)

                # When we've gone through all steps, add a "completed" message
                if self.init_step_index == len(self.init_steps) - 1:
                    self.init_status_text.plain += "\n\n[✓] Initialization complete!"

        except Exception as e:
            logger.debug(f"Error updating initialization status display: {e}")

    async def _print_periodic_status(self):
        """Periodically print status to console as a backup in case the UI freezes."""
        try:
            init_update_counter = 0
            while self.should_print_status:
                await asyncio.sleep(5)  # Check more frequently (5 seconds)

                # Update AWS activity display every cycle
                await self._update_aws_activity_display()

                # Update initialization status every 3 cycles (15 seconds)
                init_update_counter += 1
                if init_update_counter >= 3:
                    await self._update_init_status()
                    init_update_counter = 0

                # Always refresh UI after updates using the full refresh method
                try:
                    await self._refresh_ui()
                except Exception as e:
                    logger.debug(f"Periodic UI refresh error: {e}")

                # Every 20 seconds, do the full status update for logging
                if int(time.time()) % 20 == 0:
                    try:
                        # Use logger to avoid interfering with Rich UI
                        logger.info(f"STATUS UPDATE Time: {time.strftime('%H:%M:%S')}")

                        # Count VPCs by status
                        statuses = {}
                        for i, row in enumerate(self.details_table.rows):
                            try:
                                vpc_id = str(row.cells[0].renderable)
                                region = str(row.cells[1].renderable)
                                status_text = str(row.cells[2].renderable)

                                if status_text not in statuses:
                                    statuses[status_text] = 0
                                statuses[status_text] += 1

                                # Log the last 3 VPCs being processed
                                if i >= len(self.details_table.rows) - 3:
                                    logger.info(
                                        f"VPC: {vpc_id} | Region: {region} | Status: {status_text}"
                                    )
                            except Exception as e:
                                pass

                        # Log status counts
                        logger.info("Status Summary:")
                        for status, count in statuses.items():
                            logger.info(f"  {status}: {count}")
                    except Exception as e:
                        logger.error(f"Error in status printer: {e}")

        except Exception as e:
            logger.error(f"Error in status printer: {e}")
        finally:
            logger.debug("Status printer stopped")

    async def update_region_status(
        self, region: str, status: str, vpc_id: str = "", resources: str = ""
    ):
        """Update the status of a region in the details table."""
        # Log what we're updating so it's visible in logs even if UI freezes
        logger.info(
            f"Status update: Region={region}, VPC={vpc_id}, Status={status}, Resources={resources}"
        )

        # Get terminal width for dynamic truncation
        terminal_width = console.width
        
        # Calculate column widths based on current terminal size
        vpc_col_width = min(32, int(terminal_width * 0.20))
        region_col_width = min(20, int(terminal_width * 0.15))
        status_col_width = min(30, int(terminal_width * 0.25))
        resources_col_width = min(30, int(terminal_width * 0.30))
        
        # Truncate values to fit in table using truncate_str
        vpc_id_truncated = self.truncate_str(vpc_id, vpc_col_width)
        region_truncated = self.truncate_str(region, region_col_width)
        status_truncated = self.truncate_str(status, status_col_width)
        resources_truncated = self.truncate_str(resources, resources_col_width)

        # Use a lock to prevent concurrent table updates which can cause errors
        async with self._table_lock:
            # Initialize vpc_row_map if it doesn't exist yet
            if not hasattr(self, "vpc_row_map"):
                self.vpc_row_map = {}
                
            # Special handling: if this is a 'No VPCs found' status, clean up any 'Scanning' rows
            if "No " in status and "VPC" in status and not vpc_id:
                # Look for scanning entry for this region and remove it
                scan_key = f"region:{region}"
                if scan_key in self.vpc_row_map:
                    row_index = self.vpc_row_map[scan_key]
                    try:
                        # Only delete if the row actually contains 'Scanning'
                        row = self.details_table.rows[row_index]
                        if "Scanning" in str(row.cells[2].renderable):
                            # Delete the scanning row
                            del self.details_table.rows[row_index]
                            # Update indices for all items with higher row indices
                            for k, idx in list(self.vpc_row_map.items()):
                                if idx > row_index:
                                    self.vpc_row_map[k] = idx - 1
                            # Remove this region from tracking
                            del self.vpc_row_map[scan_key]
                    except (IndexError, KeyError):
                        pass

                # If this is a "No VPCs" message, we can skip adding it to the UI
                if "No DeploySpot VPCs" in status:
                    return
                    
            # Check if this is the first real entry - if so, remove the placeholder row
            if len(self.details_table.rows) == 1:
                first_row = self.details_table.rows[0]
                try:
                    first_status = str(first_row.cells[2].renderable)
                    # If the only row is our placeholder, remove it before adding real content
                    if "Waiting for regions" in first_status:
                        del self.details_table.rows[0]
                        # Clear tracking dictionary since we're starting fresh
                        self.vpc_row_map = {}
                except (IndexError, AttributeError, TypeError):
                    pass
            
            # Create a key for this VPC or region
            if vpc_id:
                # Use vpc_id AND region as the compound key
                key = f"vpc:{vpc_id}:{region}"
            else:
                key = f"region:{region}"
            
            # If this entry already has a row, update it instead of adding a new one
            if key in self.vpc_row_map:
                try:
                    # Get the row index from our tracking map
                    row_index = self.vpc_row_map[key]
                    
                    # If row index is valid
                    if row_index < len(self.details_table.rows):
                        # Update row content
                        row = self.details_table.rows[row_index]
                        row.cells[0].renderable = vpc_id_truncated
                        row.cells[1].renderable = region_truncated
                        row.cells[2].renderable = status_truncated
                        row.cells[3].renderable = resources_truncated
                        logger.debug(f"Updated existing row for key {key}")
                        return
                except Exception as e:
                    logger.debug(f"Error updating row: {e}, will add a new row instead")
            
            # Add a new row and remember its index
            self.details_table.add_row(vpc_id_truncated, region_truncated, status_truncated, resources_truncated)
            self.vpc_row_map[key] = len(self.details_table.rows) - 1
            logger.debug(f"Added new row for key {key} at index {self.vpc_row_map[key]}")

    async def _refresh_ui(self):
        """Simple UI refresh that includes AWS activity and removal of deleted VPC rows."""
        try:
            if not self._refresh_lock.locked():
                async with self._refresh_lock:
                    # Process any VPC rows marked for removal
                    if hasattr(self, "vpc_row_map"):
                        # Get keys for rows marked for removal
                        keys_to_remove = [k for k, v in self.vpc_row_map.items() if v == "remove"]
                        
                        # Create a new table without the removed rows
                        if keys_to_remove:
                            logger.debug(f"Removing {len(keys_to_remove)} VPC rows from table during refresh")
                            
                            # Create new table with same structure
                            new_table = Table(
                                box=box.ROUNDED,
                                expand=True,
                                show_lines=False,
                                collapse_padding=True,
                                highlight=True,
                            )
                            
                            # Copy column structure
                            for column in self.details_table.columns:
                                new_table.add_column(
                                    column.header, 
                                    style=column.style, 
                                    width=column.width, 
                                    no_wrap=column.no_wrap
                                )
                            
                            # Rebuild the vpc_row_map and transfer rows that aren't removed
                            new_vpc_row_map = {}
                            row_index = 0
                            
                            for i, row in enumerate(self.details_table.rows):
                                # Extract vpc_id and region from this row
                                vpc_id = str(row.cells[0].renderable)
                                region = str(row.cells[1].renderable)
                                key = f"{vpc_id}:{region}" if vpc_id and region else None
                                
                                # If not marked for removal and has a key, add to new table
                                if key and key in self.vpc_row_map and self.vpc_row_map[key] == "remove":
                                    # Skip this row - it's marked for removal
                                    continue
                                
                                # Add this row to the new table
                                cells = [cell.renderable for cell in row.cells]
                                new_table.add_row(*cells)
                                
                                # Update the row map if it's a tracked row
                                if key and key in self.vpc_row_map:
                                    new_vpc_row_map[key] = row_index
                                
                                # Increment for next row
                                row_index += 1
                            
                            # Replace the old table and map
                            self.details_table = new_table
                            self.vpc_row_map = new_vpc_row_map
                            
                            # Update the layout with the new table
                            self.layout["details"].update(self.details_table)
                    
                    # Refresh the UI
                    self.live.refresh()
        except Exception as e:
            logger.debug(f"UI refresh error: {e}")

    async def _process_regions(self, max_concurrency: int):
        """Process all regions with progress tracking."""
        # Get all available regions
        regions = await self.get_available_regions()

        if not regions:
            logger.error("Failed to retrieve AWS regions")
            return {"vpcs_found": [], "vpcs_deleted": 0, "vpcs_failed": 0}

        # Create region tasks in progress bar
        region_progress_task = self.progress.add_task(
            "[bold blue]Region Scanning", total=len(regions)
        )

        for region in regions:
            self.region_tasks[region] = self.progress.add_task(
                f"[cyan]{region}", total=100, visible=True
            )

        # Use a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrency)

        async def process_region_with_semaphore(region):
            try:
                async with semaphore:
                    logger.debug(f"Starting scan of region {region}")
                    result = await asyncio.wait_for(
                        self.process_region_with_progress(region),
                        timeout=300,  # 5 minute timeout per region
                    )
                    logger.debug(f"Completed scan of region {region}")
                    return result
            except asyncio.TimeoutError:
                logger.error(f"Timeout processing region {region}")
                await self.update_region_status(
                    region, "Timeout", "", "Processing timed out"
                )
                return {"vpcs_found": [], "vpcs_deleted": 0, "vpcs_failed": 0}
            except AuthenticationError as e:
                # Handle authentication errors gracefully - already logged by execute_aws_api
                logger.debug(f"Authentication error in region {region}: {e}")
                await self.update_region_status(
                    region, "Auth Error", "", "Token expired"
                )
                # Signal to the parent that authentication failed
                return {"vpcs_found": [], "vpcs_deleted": 0, "vpcs_failed": 0, "auth_error": True}
            except Exception as e:
                logger.error(f"Error processing region {region}: {e}")
                await self.update_region_status(
                    region, "Error", "", f"Error: {str(e)[:40]}"
                )
                return {"vpcs_found": [], "vpcs_deleted": 0, "vpcs_failed": 0}

        # Create tasks for each region
        tasks = []
        for region in regions:
            task = asyncio.create_task(process_region_with_semaphore(region))
            task.region = region
            tasks.append(task)

        # Wait for all tasks to complete
        total_results = {"vpcs_found": [], "vpcs_deleted": 0, "vpcs_failed": 0}

        try:
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            auth_error_detected = False
            for result in results:
                if isinstance(result, dict):  # Successful result
                    # Check if this region encountered an auth error
                    if result.get("auth_error", False):
                        auth_error_detected = True
                        continue
                        
                    total_results["vpcs_found"].extend(result.get("vpcs_found", []))
                    total_results["vpcs_deleted"] += result.get("vpcs_deleted", 0)
                    total_results["vpcs_failed"] += result.get("vpcs_failed", 0)
                else:  # Exception occurred
                    logger.error(f"Error in region processing: {result}")
            
            # If any region had an auth error, report it in the results
            if auth_error_detected:
                total_results["auth_error"] = True

            # Update final progress
            self.progress.update(region_progress_task, completed=len(regions))

            return total_results

        except Exception as e:
            logger.error(f"Error waiting for region processing tasks: {e}")
            return total_results

    async def run(self, max_concurrency: int = 5) -> None:
        """Main entry point for the VPC cleaner."""
        logger.debug(f"Starting VPC cleanup with max concurrency of {max_concurrency}")

        try:
            # Start periodic UI refresh task
            self.should_print_status = True
            refresh_task = asyncio.create_task(self._refresh_ui_periodic())
            
            # Create status monitoring task
            status_task = asyncio.create_task(self._print_periodic_status())
            
            with self.live:
                # Update all layout sections
                self.layout["header"].update(self.header_panel)
                self.layout["progress"].update(self.progress)
                self.layout["details"].update(self.details_table)
                self.layout["aws_activity"].update(Panel(self.aws_activity_text))
                self.layout["mode_banner"].update(self.mode_banner)  # Add mode banner
                self.live.update(self.layout)

                # Process regions and wait for completion
                results = await self._process_regions(max_concurrency)

                # Check if we encountered an authentication error
                if results.get("auth_error", False):
                    console.print("\n[bold yellow]Operation aborted due to authentication errors[/bold yellow]")
                    console.print("[yellow]Please run 'aws sso login' to refresh your credentials and try again.[/yellow]")
                    return

                # Show final summary
                total_vpcs = len(results["vpcs_found"])
                deleted = results["vpcs_deleted"]
                failed = results["vpcs_failed"]

                if self.dry_run:
                    summary = f"\n[yellow]Scan Complete: Found {total_vpcs} DeploySpot VPCs (Dry Run - no deletions performed)"
                else:
                    summary = f"\n[green]Cleanup Complete: Found {total_vpcs} VPCs, Successfully deleted {deleted}, Failed to delete {failed}"

                console.print(summary)
                
            # Clean up tasks
            self.should_print_status = False
            refresh_task.cancel()
            status_task.cancel()
            
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
                
            try:
                await status_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(f"Error during execution: {str(e)}", exc_info=True)
            console.print(f"\n[bold red]Error: {str(e)[:200]}")

    async def process_region_with_progress(self, region: str) -> dict:
        """Process a single region with progress updates."""
        result_stats = {"vpcs_found": [], "vpcs_deleted": 0, "vpcs_failed": 0}
        logger.debug(f"Starting to process region {region}")

        # Get the task for this region
        region_task = self.region_tasks[region]
        self.progress.update(
            region_task, advance=10, description=f"[cyan]{region}: Scanning"
        )

        try:
            # Get VPCs in region with timeout
            logger.debug(f"Getting VPC IDs for region {region}")
            logger.info(f"Scanning region {region} for DeploySpot VPCs...")
            vpc_ids = await asyncio.wait_for(
                self.get_vpc_ids(region),
                timeout=60,  # 1 minute timeout for this API call
            )

            # Store found VPCs in our result stats
            result_stats["vpcs_found"] = vpc_ids[:]

            if not vpc_ids:
                logger.debug(f"No VPCs found in {region} - completing task")
                self.progress.update(
                    region_task,
                    advance=90,
                    description=f"[cyan]{region}: No DeploySpot VPCs",
                )
                return result_stats

        except asyncio.TimeoutError:
            logger.warning(f"Timeout while getting VPCs for region {region}")
            self.progress.update(
                region_task, advance=90, description=f"[red]{region}: API Timeout"
            )
            await self.update_region_status(
                region, "API Timeout", "", "EC2 API call timed out"
            )
            return result_stats
            
        except AuthenticationError as e:
            # Handle authentication errors gracefully
            logger.debug(f"Authentication error in region {region}: {e}")
            self.progress.update(
                region_task, advance=90, description=f"[yellow]{region}: Auth Error"
            )
            await self.update_region_status(
                region, "Auth Error", "", "Token expired"
            )
            # Signal to the parent that an auth error occurred
            result_stats["auth_error"] = True
            return result_stats

        except Exception as e:
            logger.error(f"Error in region {region} VPC discovery: {e}", exc_info=True)
            self.progress.update(
                region_task, advance=90, description=f"[red]{region}: Error"
            )
            await self.update_region_status(
                region, "Error", "", f"Error: {str(e)[:40]}"
            )
            return result_stats

        # Process each VPC in the region
        vpc_count = len(vpc_ids)
        progress_per_vpc = 90 / vpc_count  # Remaining 90% divided by VPC count

        for idx, vpc_id in enumerate(vpc_ids):
            vpc_step = idx + 1
            self.progress.update(
                region_task,
                description=f"[cyan]{region}: Processing VPC {vpc_step}/{vpc_count}",
            )

            status_prefix = "[SCAN] " if self.dry_run else ""
            resources_text = (
                "Scan only - no deletion" if self.dry_run else "Identifying resources"
            )

            await self.update_region_status(
                region,
                f"{status_prefix}Processing VPC {vpc_step}/{vpc_count}",
                vpc_id,
                resources_text,
            )

            if self.dry_run:
                logger.info(
                    f"[SCAN ONLY] Processing VPC {vpc_id} in {region} ({vpc_step}/{vpc_count}) - NO DELETION WILL OCCUR"
                )
            else:
                logger.info(
                    f"Processing VPC {vpc_id} in {region} ({vpc_step}/{vpc_count})"
                )

            try:
                # Delete resources inside the VPC with timeout
                try:
                    await asyncio.wait_for(
                        self.delete_vpc_resources_with_progress(vpc_id, region),
                        timeout=300,  # 5 minute timeout per VPC
                    )
                    self.progress.update(region_task, advance=progress_per_vpc * 0.7)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"VPC resource cleanup timed out after 300s: {vpc_id}"
                    )
                    # Continue with VPC deletion anyway

                # Delete the VPC itself
                await self.update_region_status(
                    region,
                    f"Deleting VPC {vpc_step}/{vpc_count}",
                    vpc_id,
                    "Final cleanup",
                )

                # Try to delete the VPC, but don't wait for full completion
                try:
                    # Start the deletion but don't wait for complete removal
                    started_deletion = await asyncio.wait_for(
                        self.delete_vpc(vpc_id, region, wait_for_deletion=False),
                        timeout=60,  # 1 minute timeout for VPC deletion initiation
                    )
                    
                    if started_deletion:
                        # Consider it a success if deletion has begun
                        await self.update_region_status(
                            region,
                            f"Completed {vpc_step}/{vpc_count}",
                            vpc_id,
                            "Deletion in progress",
                        )
                        logger.info(f"Started VPC deletion for {vpc_id} in {region}")
                        result_stats["vpcs_deleted"] += 1
                        
                        # Mark the entry for removal once deletion has begun
                        await self.update_region_status(
                            region,
                            f"Successfully deleted",
                            vpc_id,
                            "VPC deletion initiated",
                        )
                    else:
                        await self.update_region_status(
                            region,
                            f"Failed {vpc_step}/{vpc_count}",
                            vpc_id,
                            "Cleanup failed",
                        )
                        logger.warning(f"Failed to initiate deletion for VPC {vpc_id} in {region}")
                        result_stats["vpcs_failed"] += 1
                        
                except asyncio.TimeoutError:
                    logger.warning(f"VPC deletion initiation timed out: {vpc_id}")
                    await self.update_region_status(
                        region,
                        f"Timeout {vpc_step}/{vpc_count}",
                        vpc_id,
                        "VPC deletion timed out",
                    )
                    result_stats["vpcs_failed"] += 1

            except asyncio.TimeoutError:
                logger.error(f"Timeout processing VPC {vpc_id} in {region}")
                await self.update_region_status(
                    region,
                    f"Timeout {vpc_step}/{vpc_count}",
                    vpc_id,
                    "Processing timed out",
                )
                result_stats["vpcs_failed"] += 1
            except Exception as e:
                logger.error(f"Error processing VPC {vpc_id} in {region}: {e}")
                await self.update_region_status(
                    region,
                    f"Error {vpc_step}/{vpc_count}",
                    vpc_id,
                    f"Error: {str(e)[:40]}",
                )
                result_stats["vpcs_failed"] += 1

            # Update progress
            self.progress.update(region_task, advance=progress_per_vpc * 0.3)

        # Update final status for region
        self.progress.update(
            region_task,
            description=f"[green]{region}: Completed ({vpc_count} VPCs)",
            completed=100,
        )

        return result_stats

    async def delete_vpc_resources_with_progress(
        self, vpc_id: str, region: str
    ) -> None:
        """Delete all resources in a VPC with progress updates."""
        await self.update_region_status(
            region, "Listing dependencies", vpc_id, "Analyzing"
        )

        # List dependencies
        await self.list_vpc_dependencies(vpc_id, region)

        # Delete resources in steps with status updates
        resource_steps = [
            ("Cleaning security groups", self.cleanup_security_group_rules),
            ("Terminating instances", self.terminate_vpc_instances),
            ("Removing load balancers", self.delete_load_balancers),
            ("Removing transit gateways", self.delete_transit_gateway_attachments),
            ("Removing VPC endpoints", self.delete_vpc_endpoints),
            ("Removing NAT gateways", self.delete_nat_gateways),
            ("Removing network interfaces", self.delete_network_interfaces),
            ("Removing internet gateways", self.delete_internet_gateways),
            ("Removing security groups", self.delete_security_groups),
            ("Waiting for NAT gateways", self.wait_for_nat_gateway_deletion),
            ("Removing route tables", self.delete_route_tables),
            ("Removing subnets", self.delete_subnets),
        ]

        for idx, (description, function) in enumerate(resource_steps):
            step = idx + 1
            total_steps = len(resource_steps)

            await self.update_region_status(
                region,
                f"Cleaning up resources ({step}/{total_steps})",
                vpc_id,
                description,
            )

            # Execute the function for this step
            await function(vpc_id, region)

    async def _refresh_ui_periodic(self):
        """Periodically refresh the UI without blocking."""
        while True:
            try:
                # Use the full refresh method to handle row removal
                await self._refresh_ui()
            except Exception as e:
                logger.debug(f"Periodic UI refresh error: {e}")
            await asyncio.sleep(0.5)


async def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="AWS VPC Cleanup Tool - Finds and deletes SpotInstance VPCs across all regions"
    )
    parser.add_argument(
        "--skip-credential-check",
        action="store_true",
        help="Skip AWS credential verification",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--region",
        action="append",
        dest="regions",
        help="Specific AWS region(s) to process (can specify multiple times)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't actually delete resources",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=5,
        help="Maximum number of regions to process in parallel (default: 5)",
    )
    parser.add_argument(
        "--api-concurrency",
        type=int,
        default=10,
        help="Maximum number of AWS API calls to make in parallel (default: 10)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip actual cleanup, just scan and report VPCs found",
    )

    args = parser.parse_args()

    # Log the startup options
    if args.dry_run or args.no_cleanup:
        mode = "DRY RUN" if args.dry_run else "SCAN-ONLY"
        logger.info(f"*** {mode} MODE - Resources will be scanned but NOT DELETED ***")
        # Print very clear message to console
        console.print()
        console.print("=" * 80, style="yellow")
        console.print(f"  {'WARNING:':^76}", style="yellow bold")
        console.print(
            f"  {f'RUNNING IN {mode} MODE - NO RESOURCES WILL BE DELETED':^76}",
            style="yellow bold",
        )
        console.print("=" * 80, style="yellow")
        console.print()

    if args.max_concurrency:
        logger.info(
            f"Maximum region concurrency set to {args.max_concurrency} regions in parallel"
        )
        
    if args.api_concurrency:
        logger.info(
            f"Maximum API concurrency set to {args.api_concurrency} API calls in parallel"
        )
        console.print(f"[cyan]AWS API calls will be parallelized with up to {args.api_concurrency} concurrent calls")

    if args.regions:
        region_list = ", ".join(args.regions)
        logger.info(f"Filtering to specific regions: {region_list}")
        console.print(f"[cyan]Processing only these regions: {region_list}")

    # Initialize the VPC cleaner
    vpc_cleaner = AwsVpcCleaner(
        skip_credential_check=args.skip_credential_check,
        debug=args.debug,
        region_filter=args.regions,
        dry_run=args.dry_run or args.no_cleanup,  # Treat no-cleanup as dry-run
        api_concurrency=args.api_concurrency,  # Control parallel AWS API calls
    )

    # Add timing info
    start_time = time.time()

    try:
        # Run with timeout for overall execution
        await asyncio.wait_for(
            vpc_cleaner.run(max_concurrency=args.max_concurrency),
            timeout=1800,  # 30 minute overall timeout
        )
    except asyncio.TimeoutError:
        logger.error("Overall execution timed out after 30 minutes")
        console.print(
            "[bold red]Script timed out after 30 minutes - check logs for details"
        )
    except KeyboardInterrupt:
        logger.info("Operation canceled by user")
        console.print("[yellow]Operation canceled by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        console.print(f"[bold red]An error occurred: {str(e)}")
    finally:
        # Stop the periodic status printer
        vpc_cleaner.should_print_status = False

        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Script finished in {duration:.2f} seconds")

        # Create summary table
        summary_table = Table(
            title="VPC Cleanup Summary",
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED,
        )
        summary_table.add_column("Region", style="cyan")
        summary_table.add_column("VPCs Found", justify="right", style="green")
        summary_table.add_column("VPCs Deleted", justify="right", style="blue")
        summary_table.add_column("Resources", style="yellow")

        # Extract data from the details table
        region_summary = {}
        if hasattr(vpc_cleaner, "details_table"):
            for row in vpc_cleaner.details_table.rows:
                region = str(row.cells[1].renderable)
                vpc_id = str(row.cells[0].renderable)
                status = str(row.cells[2].renderable)
                resources = str(row.cells[3].renderable)

                if region not in region_summary:
                    region_summary[region] = {
                        "vpcs_found": set(),
                        "vpcs_deleted": set(),
                        "resources": set(),
                    }

                if vpc_id:
                    region_summary[region]["vpcs_found"].add(vpc_id)
                    if "Successfully deleted" in status:
                        region_summary[region]["vpcs_deleted"].add(vpc_id)
                if resources:
                    region_summary[region]["resources"].add(resources)

        # Add rows to summary table
        for region, data in sorted(region_summary.items()):
            if region.strip():  # Skip empty region names
                vpcs_found = len(data["vpcs_found"])
                vpcs_deleted = len(data["vpcs_deleted"])
                # Always show "0" for scanned regions with no VPCs
                summary_table.add_row(
                    region,
                    str(vpcs_found) if vpcs_found > 0 else "0",
                    str(vpcs_deleted) if vpcs_deleted > 0 else "0",
                    ", ".join(sorted(data["resources"]))[:50]
                    if data["resources"]
                    else "None",  # Show "None" if no resources
                )

        # Print the summary table
        console.print("\n[bold]Cleanup Summary:[/bold]")
        console.print(summary_table)

        console.print(f"[blue]Total execution time: {duration:.2f} seconds")
        console.print(f"[blue]Detailed logs written to: {debug_log_file}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Operation canceled by user.")
        sys.exit(1)
