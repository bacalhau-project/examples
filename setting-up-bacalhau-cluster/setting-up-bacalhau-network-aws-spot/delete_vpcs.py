#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "botocore",
#     "pyyaml",
#     "rich",
#     "tenacity",
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

import boto3
import botocore
from rich import box
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
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


# Custom exception for authentication errors
class AuthenticationError(Exception):
    """Exception raised when AWS authentication fails."""

    pass


# Configure console and logging
console = Console()

# Configure logging handlers
debug_handler = logging.FileHandler("debug_delete_vpcs.log")
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
    )
)

# Configure rich console handler
rich_handler = RichHandler(
    rich_tracebacks=False,
    console=console,
    show_time=False,
    show_path=False,
    markup=True,
    level=logging.WARNING,
)

# Set up root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Set root logger to DEBUG to capture all levels
root_logger.addHandler(debug_handler)
root_logger.addHandler(rich_handler)

# Set up our module's logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = True  # Allow propagation to root logger

# Configure AWS logging
for aws_logger in ["boto3", "botocore", "urllib3"]:
    logging.getLogger(aws_logger).setLevel(logging.ERROR)


class AwsActivityTracker:
    def __init__(self):
        self.last_activity = ""
        self.total_calls = 0
        self.call_history = []

    def update(self, service: str, operation: str, region: str):
        """Update AWS activity with latest call information."""
        self.total_calls += 1
        timestamp = time.strftime("%H:%M:%S")
        activity = f"[{timestamp}] {service.upper()}.{operation} → {region}"
        self.last_activity = f"{activity} (Total calls: {self.total_calls})"
        self.call_history.append(activity)

    def get_activity_summary(self) -> str:
        """Get a summary of all AWS API calls."""
        if not self.call_history:
            return "No AWS API calls made"

        summary = [
            f"Total AWS API Calls: {self.total_calls}",
            "Recent API Calls:",
            *self.call_history[-10:],  # Show last 10 calls
        ]
        return "\n".join(summary)


class AwsVpcCleaner:
    def __init__(
        self,
        dry_run: bool,
        region_filter: Optional[List[str]],
        skip_credential_check: bool,
    ):
        self.dry_run = dry_run
        self.region_filter = region_filter
        self.skip_credential_check = skip_credential_check
        self.region_stats = {}  # Track statistics per region

        # Set up AWS session
        self.session = boto3.Session()

        # Set up API concurrency control
        self.api_semaphore = asyncio.Semaphore(
            10
        )  # Allow up to 10 concurrent API calls

        # Set up AWS activity tracking
        self.aws_tracker = AwsActivityTracker()
        self.aws_activity_text = Text(self.aws_tracker.last_activity, style="cyan")

        # Set up UI components
        self._setup_ui_components()

    def _setup_ui_components(self):
        """Set up UI components for the cleaner."""
        # Progress tracking
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            expand=True,
        )
        self.region_tasks = {}

        # Calculate column widths based on terminal
        terminal_width = console.width
        self.details_table = Table(
            box=box.ROUNDED,
            expand=True,
            show_lines=False,
            highlight=True,
        )
        self.details_table.add_column(
            "VPC ID", style="green", width=min(32, int(terminal_width * 0.20))
        )
        self.details_table.add_column(
            "Region", style="cyan", width=min(20, int(terminal_width * 0.15))
        )
        self.details_table.add_column(
            "Status", style="yellow", width=min(30, int(terminal_width * 0.25))
        )
        self.details_table.add_column(
            "Resources", style="magenta", width=min(30, int(terminal_width * 0.30))
        )

        # Create layout
        self.layout = Layout()
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="status_section", size=5),
            Layout(name="mode_banner", size=3),
        )
        self.layout["main"].split_row(
            Layout(name="progress", ratio=2),
            Layout(name="details", ratio=3),
        )
        self.layout["status_section"].split_row(
            Layout(name="aws_activity", ratio=1),
            Layout(name="init_status", ratio=1),
        )

        # Create header and mode banner
        title = "AWS VPC Cleanup Tool"
        if self.dry_run:
            title += " [SCAN-ONLY MODE - NO DELETION WILL OCCUR]"
            self.header_panel = Panel(
                Text(title, style="bold white on yellow", justify="center"),
                box=box.ROUNDED,
            )
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
            self.mode_banner = Panel(
                Text("! LIVE MODE: RESOURCES ARE BEING DELETED !", justify="center"),
                style="red bold on white",
                box=box.HEAVY,
            )

    @retry(
        retry=retry_if_exception_type(botocore.exceptions.ClientError),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(3),
    )
    async def execute_aws_api(self, func, *args, **kwargs):
        """Execute AWS API calls with rate limiting and retries."""
        async with self.api_semaphore:
            loop = asyncio.get_event_loop()

            # Extract service and operation name from the function
            service = func.__self__.meta.service_model.service_name
            operation = func.__name__
            region = func.__self__.meta.region_name

            # Update activity before making the call
            self.aws_tracker.update(service, operation, region)
            self.aws_activity_text = Text(self.aws_tracker.last_activity, style="cyan")

            # Update the live display with latest AWS activity
            if hasattr(self, "live"):
                self.layout["aws_activity"].update(Panel(self.aws_activity_text))
                self.live.refresh()

            try:
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            except Exception as e:
                logger.error(f"AWS API call failed: {str(e)}")
                raise

    async def verify_aws_credentials(self) -> bool:
        """Verify AWS credentials are valid."""
        try:
            sts = self.session.client("sts")
            await self.execute_aws_api(sts.get_caller_identity)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["ExpiredToken", "InvalidClientTokenId"]:
                console.print(
                    "\n[yellow]AWS SSO token has expired. Please run 'aws sso login'[/yellow]"
                )
            else:
                console.print(f"\n[yellow]AWS credentials error: {str(e)}[/yellow]")
            return False

    async def get_available_regions(self) -> List[str]:
        """Get available AWS regions."""
        try:
            ec2 = self.session.client("ec2")
            response = await self.execute_aws_api(ec2.describe_regions)
            regions = [region["RegionName"] for region in response["Regions"]]
            return [
                r for r in regions if not self.region_filter or r in self.region_filter
            ]
        except botocore.exceptions.ClientError as e:
            logger.error(f"Failed to get AWS regions: {str(e)}")
            raise

    async def delete_vpc_dependencies(self, ec2, vpc_id: str) -> bool:
        """Delete VPC dependencies in the correct order."""
        try:
            # Get VPC dependencies
            vpc = (await self.execute_aws_api(ec2.describe_vpcs, VpcIds=[vpc_id]))[
                "Vpcs"
            ][0]

            # First, terminate any EC2 instances in the VPC
            instances = (
                await self.execute_aws_api(
                    ec2.describe_instances,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
            )["Reservations"]

            instance_ids = []
            instance_names = []
            for reservation in instances:
                for instance in reservation["Instances"]:
                    if instance["State"]["Name"] not in ["terminated", "shutting-down"]:
                        instance_ids.append(instance["InstanceId"])
                        # Get instance name from tags if available
                        for tag in instance.get("Tags", []):
                            if tag["Key"] == "Name":
                                instance_names.append(tag["Value"])
                                break
                        else:
                            instance_names.append(instance["InstanceId"])

            if instance_ids:
                # Update status to show we're terminating instances
                self._update_vpc_row(
                    vpc_id,
                    ec2.meta.region_name,
                    "[yellow]Terminating Instances[/yellow]",
                    f"Instances: {', '.join(instance_names)}",
                )

                await self.execute_aws_api(
                    ec2.terminate_instances, InstanceIds=instance_ids
                )
                # Wait for instances to start terminating
                await asyncio.sleep(5)

            # Get all network interfaces in the VPC
            network_interfaces = (
                await self.execute_aws_api(
                    ec2.describe_network_interfaces,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
            )["NetworkInterfaces"]

            # First pass: Release all Elastic IPs
            for eni in network_interfaces:
                if eni.get("Association") and eni["Association"].get("PublicIp"):
                    try:
                        # Update status to show we're releasing Elastic IPs
                        self._update_vpc_row(
                            vpc_id,
                            ec2.meta.region_name,
                            "[yellow]Releasing Elastic IPs[/yellow]",
                            f"IP: {eni['Association']['PublicIp']}",
                        )
                        if eni["Association"].get("AssociationId"):
                            await self.execute_aws_api(
                                ec2.disassociate_address,
                                AssociationId=eni["Association"]["AssociationId"],
                            )
                        if eni["Association"].get("AllocationId"):
                            await self.execute_aws_api(
                                ec2.release_address,
                                AllocationId=eni["Association"]["AllocationId"],
                            )
                    except botocore.exceptions.ClientError as e:
                        if "does not exist" not in str(e).lower():
                            logger.error(f"Error releasing Elastic IP: {str(e)}")

            # Wait a moment for Elastic IP operations to complete
            await asyncio.sleep(2)

            # Second pass: Handle network interfaces
            for eni in network_interfaces:
                if eni["Status"] not in ["deleting", "deleted"]:
                    try:
                        # Skip detachment if this is the primary network interface
                        if eni.get("Attachment"):
                            if eni["Attachment"].get("DeviceIndex", 0) == 0:
                                logger.debug(
                                    f"Skipping detachment of primary network interface {eni['NetworkInterfaceId']}"
                                )
                                continue

                            try:
                                await self.execute_aws_api(
                                    ec2.detach_network_interface,
                                    AttachmentId=eni["Attachment"]["AttachmentId"],
                                    Force=True,
                                )
                                # Small delay after detachment
                                await asyncio.sleep(1)
                            except botocore.exceptions.ClientError as e:
                                error_code = e.response.get("Error", {}).get("Code", "")
                                if error_code in [
                                    "OperationNotPermitted",
                                    "UnsupportedOperation",
                                ]:
                                    logger.debug(
                                        f"Skipping network interface detachment due to {error_code}: {eni['NetworkInterfaceId']}"
                                    )
                                    continue
                                raise

                        # Try to delete the network interface
                        try:
                            await self.execute_aws_api(
                                ec2.delete_network_interface,
                                NetworkInterfaceId=eni["NetworkInterfaceId"],
                            )
                        except botocore.exceptions.ClientError as e:
                            if "does not exist" not in str(e).lower():
                                logger.error(
                                    f"Error deleting network interface {eni['NetworkInterfaceId']}: {str(e)}"
                                )
                    except botocore.exceptions.ClientError as e:
                        if "does not exist" not in str(e).lower():
                            logger.error(
                                f"Error handling network interface {eni['NetworkInterfaceId']}: {str(e)}"
                            )

            # Wait for network interface operations to complete
            await asyncio.sleep(2)

            # Delete NAT Gateways
            nat_gateways = (
                await self.execute_aws_api(
                    ec2.describe_nat_gateways,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
            )["NatGateways"]

            for nat in nat_gateways:
                if nat["State"] not in ["deleted", "deleting"]:
                    await self.execute_aws_api(
                        ec2.delete_nat_gateway, NatGatewayId=nat["NatGatewayId"]
                    )

            # Delete Internet Gateways
            igws = (
                await self.execute_aws_api(
                    ec2.describe_internet_gateways,
                    Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
                )
            )["InternetGateways"]

            for igw in igws:
                await self.execute_aws_api(
                    ec2.detach_internet_gateway,
                    InternetGatewayId=igw["InternetGatewayId"],
                    VpcId=vpc_id,
                )
                await self.execute_aws_api(
                    ec2.delete_internet_gateway,
                    InternetGatewayId=igw["InternetGatewayId"],
                )

            # Delete Subnets
            subnets = (
                await self.execute_aws_api(
                    ec2.describe_subnets,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
            )["Subnets"]

            for subnet in subnets:
                await self.execute_aws_api(
                    ec2.delete_subnet, SubnetId=subnet["SubnetId"]
                )

            # Delete Route Tables
            route_tables = (
                await self.execute_aws_api(
                    ec2.describe_route_tables,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
            )["RouteTables"]

            for rt in route_tables:
                if not rt.get("Associations", []) or not rt["Associations"][0].get(
                    "Main", False
                ):
                    await self.execute_aws_api(
                        ec2.delete_route_table, RouteTableId=rt["RouteTableId"]
                    )

            # Delete Security Groups
            security_groups = (
                await self.execute_aws_api(
                    ec2.describe_security_groups,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
            )["SecurityGroups"]

            for sg in security_groups:
                if sg["GroupName"] != "default":
                    await self.execute_aws_api(
                        ec2.delete_security_group, GroupId=sg["GroupId"]
                    )

            # Finally delete the VPC itself
            await self.execute_aws_api(ec2.delete_vpc, VpcId=vpc_id)
            return True

        except botocore.exceptions.ClientError as e:
            if "does not exist" in str(e).lower():
                # If resource doesn't exist, it's already deleted or being deleted
                return True
            logger.error(f"Failed to delete VPC dependencies: {str(e)}")
            return False

    async def get_vpc_ids(self, region: str) -> List[str]:
        """Get VPC IDs created by the DeploySpot script in a region."""
        try:
            ec2 = self.session.client(
                "ec2",
                region_name=region,
                config=botocore.config.Config(
                    connect_timeout=10, read_timeout=15, retries={"max_attempts": 3}
                ),
            )

            response = await self.execute_aws_api(
                ec2.describe_vpcs,
                Filters=[
                    {
                        "Name": "tag:Name",
                        "Values": ["SpotInstance-*", "SpotInstanceVPC"],
                    }
                ],
            )
            return [vpc["VpcId"] for vpc in response.get("Vpcs", [])]

        except botocore.exceptions.ClientError as e:
            if "ExpiredToken" in str(e):
                raise AuthenticationError("AWS SSO Token Expired") from e
            raise

    async def _process_single_region(
        self, region: str, results: Dict[str, Any]
    ) -> None:
        """Process a single AWS region."""
        task_id = self.region_tasks[region]
        self.progress.start_task(task_id)
        ec2 = self.session.client("ec2", region_name=region)

        # Initialize region stats
        self.region_stats[region] = {
            "instances_found": 0,
            "instances_deleted": 0,
            "vpcs_found": 0,
            "vpcs_deleted": 0,
        }

        try:
            # Scan for VPCs
            self.progress.update(
                task_id, advance=20, description=f"[cyan]Scanning {region}"
            )
            vpc_ids = await self.get_vpc_ids(region)

            if vpc_ids:
                self.progress.update(
                    task_id,
                    advance=30,
                    description=f"[yellow]Found {len(vpc_ids)} VPCs in {region}",
                )
                results["vpcs_found"].update(vpc_ids)
                self.region_stats[region]["vpcs_found"] = len(vpc_ids)

                for vpc_id in vpc_ids:
                    status = (
                        "[blue]Found[/blue]"
                        if self.dry_run
                        else "[yellow]DEL Started[/yellow]"
                    )
                    self._update_vpc_row(vpc_id, region, status, "Starting...")

                if not self.dry_run:
                    for vpc_id in vpc_ids:
                        try:
                            # Count instances before deletion
                            instances = (
                                await self.execute_aws_api(
                                    ec2.describe_instances,
                                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                                )
                            )["Reservations"]

                            instance_count = sum(
                                1
                                for r in instances
                                for i in r["Instances"]
                                if i["State"]["Name"]
                                not in ["terminated", "shutting-down"]
                            )
                            self.region_stats[region]["instances_found"] += (
                                instance_count
                            )

                            # Delete VPC dependencies
                            if await self.delete_vpc_dependencies(ec2, vpc_id):
                                results["vpcs_deleted"] += 1
                                self.region_stats[region]["vpcs_deleted"] += 1
                                self.region_stats[region]["instances_deleted"] += (
                                    instance_count
                                )
                                # Update row with new status
                                self._update_vpc_row(
                                    vpc_id,
                                    region,
                                    "[green]Deletion Started[/green]",
                                    "Removing dependencies...",
                                )
                        except Exception as e:
                            logger.error(f"Failed to delete VPC {vpc_id}: {str(e)}")
                            results["vpcs_failed"] += 1
                            # Update row with error status
                            self._update_vpc_row(
                                vpc_id,
                                region,
                                "[red]Failed[/red]",
                                f"Error: {str(e)[:50]}",
                            )

            # Mark region as complete
            self.progress.update(
                task_id, completed=100, description=f"[green]Completed {region}"
            )
            self.progress.stop_task(task_id)

        except Exception as e:
            logger.error(f"Error in region {region}: {str(e)}")
            self.progress.update(
                task_id, description=f"[red]Failed {region}: {str(e)[:30]}..."
            )
            raise

    async def _process_regions(self, max_concurrency: int) -> Dict[str, Any]:
        """Process all AWS regions to find and clean up VPCs."""
        results = {"vpcs_found": set(), "vpcs_deleted": 0, "vpcs_failed": 0}
        tasks = []

        try:
            regions = await self.get_available_regions()
            if not regions:
                console.print("[yellow]No AWS regions available[/yellow]")
                return results

            for region in regions:
                self.region_tasks[region] = self.progress.add_task(
                    f"[cyan]Scanning {region}...", total=100, start=False
                )

            # Create all tasks but don't await them yet
            async with asyncio.TaskGroup() as tg:
                for region in regions:
                    tasks.append(
                        tg.create_task(self._process_single_region(region, results))
                    )

            # All tasks are now complete
            return results

        except* AuthenticationError:
            logger.error("Authentication error during processing")
            raise
        except* Exception as e:
            logger.error(f"Error processing regions: {str(e)}")
            raise

    def _update_vpc_row(self, vpc_id: str, region: str, status: str, message: str):
        """Update the VPC row in the table."""

        # Look for the row in the details_table based on the first column
        vpc_column = self.details_table.columns[0]
        for row_index, row_text in enumerate(vpc_column._cells):
            if row_text == vpc_id:
                # Update each cell individually
                self.details_table.columns[0]._cells[row_index] = vpc_id
                self.details_table.columns[1]._cells[row_index] = region
                self.details_table.columns[2]._cells[row_index] = status
                self.details_table.columns[3]._cells[row_index] = message
                return

        # If the row is not found, add it
        self.details_table.add_row(vpc_id, region, status, message)

    async def run(self, max_concurrency: int = 5) -> None:
        """Main entry point for the VPC cleaner."""
        try:
            if (
                not self.skip_credential_check
                and not await self.verify_aws_credentials()
            ):
                return

            with Live(
                self.layout, console=console, screen=True, refresh_per_second=4
            ) as live:
                self.layout["header"].update(self.header_panel)
                self.layout["progress"].update(self.progress)
                self.layout["details"].update(self.details_table)
                self.layout["aws_activity"].update(Panel(self.aws_activity_text))
                self.layout["mode_banner"].update(self.mode_banner)
                self.live = live

                results = await self._process_regions(max_concurrency)

                # Wait for all progress bars to show 100%
                await asyncio.sleep(2)

            # After Live context exits, print final static summary
            console.print("\n[bold]Final Status:[/bold]")
            console.print(self.details_table)

            # Print region statistics
            stats_table = Table(
                title="Region Statistics",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )
            stats_table.add_column("Region", style="cyan")
            stats_table.add_column("Instances Found", justify="right")
            stats_table.add_column("Instances Deleted", justify="right")
            stats_table.add_column("VPCs Found", justify="right")
            stats_table.add_column("VPCs Deleted", justify="right")

            for region, stats in sorted(self.region_stats.items()):
                stats_table.add_row(
                    region,
                    str(stats["instances_found"]),
                    str(stats["instances_deleted"]),
                    str(stats["vpcs_found"]),
                    str(stats["vpcs_deleted"]),
                )

            console.print("\n[bold]Region Statistics:[/bold]")
            console.print(stats_table)

            total_vpcs = len(results["vpcs_found"])
            if self.dry_run:
                summary = Text(
                    f"\nScan Complete: Found {total_vpcs} DeploySpot VPCs (Dry Run - no deletions performed)",
                    style="yellow",
                )
            else:
                summary = Text(
                    f"\nCleanup Complete: Found {total_vpcs} VPCs, Deletion started for {results['vpcs_deleted']}, Failed to initiate deletion for {results['vpcs_failed']}",
                    style="green",
                )
            console.print(summary)

            # Print final AWS activity with full history
            console.print(
                Text(
                    f"AWS API Total Calls: {self.aws_tracker.total_calls}",
                    style="cyan",
                ),
            )

        except Exception as e:
            logger.error(f"Error during execution: {str(e)}")
            console.print(f"\n[bold red]Error: {str(e)[:200]}")


def check_aws_sso_token() -> bool:
    """Check if AWS SSO token is valid."""
    try:
        logger.info("Checking AWS SSO token")
        logger.debug("Inside of check_aws_sso_token")
        result = boto3.client("sts").get_caller_identity()
        logger.debug(f"Result of get_caller_identity: {result}")
        return True
    except Exception as e:
        logger.error(f"Error checking AWS SSO token: {str(e)}")
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ["ExpiredToken", "InvalidClientTokenId"]:
            console.print(
                "\n[yellow]AWS SSO token has expired. Please run 'aws sso login'[/yellow]"
            )
        else:
            console.print(f"\n[yellow]AWS authentication error: {str(e)}[/yellow]")
        return False


def main():
    logger.debug("Inside of main")
    if not check_aws_sso_token():
        sys.exit(1)

    parser = argparse.ArgumentParser(description="AWS VPC Cleanup Tool")
    parser.add_argument(
        "--dry-run", action="store_true", help="Perform a dry run (no deletions)"
    )
    parser.add_argument("--region", type=str, help="Filter by specific AWS region")
    parser.add_argument(
        "--skip-credential-check",
        action="store_true",
        help="Skip AWS credentials verification",
    )
    args = parser.parse_args()

    cleaner = AwsVpcCleaner(
        dry_run=args.dry_run,
        region_filter=[args.region] if args.region else None,
        skip_credential_check=args.skip_credential_check,
    )
    asyncio.run(cleaner.run())


if __name__ == "__main__":
    main()
