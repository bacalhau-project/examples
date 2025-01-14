#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "rich",
#     "boto3",
#     "click",
#     "aiohttp",
#     "python-dotenv",
#     "python-json-logger",
# ]
# ///

import asyncio
import json
import logging
import os
import random
import re
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import boto3
import click
from click import Context
from pythonjsonlogger import jsonlogger
from rich.box import ROUNDED
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
    TimeRemainingColumn,
)
from rich.table import Table
from rich.theme import Theme

# Initialize Rich console with consistent theme
console = Console(
    theme=Theme(
        {
            "info": "bold blue",
            "warning": "bold yellow",
            "error": "bold red",
            "success": "bold green",
            "highlight": "bold cyan",
            "dim": "dim",
        }
    )
)

# Get the project root directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DEBUG_LOG = Path(os.getcwd()) / "debug.log"  # Use caller's directory for debug log


def write_debug(message: str) -> None:
    """Write debug information to debug.log in the caller's directory"""
    try:
        # 'a' mode is used to prevent multiple processes from truncating each other's output
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
    except Exception as e:
        # If we can't write to the debug log, fall back to stderr
        print(f"Failed to write to debug log: {str(e)}", file=sys.stderr)


# Truncate the debug log at startup
try:
    DEBUG_LOG.write_text("")
except Exception as e:
    print(f"Failed to truncate debug log: {str(e)}", file=sys.stderr)

# Initialize global layout with consistent sizing
layout = Layout()
layout.split_column(
    Layout(name="header", size=3, minimum_size=3),
    Layout(name="body", ratio=2),
    Layout(name="status", size=6, minimum_size=6),
    Layout(name="progress", size=4, minimum_size=4),
)

# Initialize global progress with more detailed columns and safer formatting
progress = Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(bar_width=None),
    TaskProgressColumn(),
    # Remove percentage for tasks that might not have a total
    TimeElapsedColumn(),
    TimeRemainingColumn(),
    expand=True,
    disable=False,
)


def safe_progress_update(task_id, **kwargs):
    """Safely update progress without template errors"""
    try:
        if "total" in kwargs and kwargs["total"] is None:
            # Don't show percentage for indeterminate progress
            kwargs["visible"] = True
            if "completed" in kwargs:
                del kwargs["completed"]
        progress.update(task_id, **kwargs)
    except Exception as e:
        # Fallback to basic progress display
        try:
            progress.update(task_id, description="Processing...", visible=True)
        except:
            pass  # Suppress any errors in the fallback


progress_task = None
layout["progress"].update(progress)

# Initialize global live display
live = Live(layout, refresh_per_second=4, auto_refresh=True)


def load_shell_env(env_path: Path) -> None:
    """Load environment variables from a shell script"""
    if not env_path.exists():
        console.print(f"[yellow]Warning: Environment file not found at {env_path}[/yellow]")
        return

    content = env_path.read_text()
    pattern = r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=["\']?([^"\'\n]*)["\']?$'

    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            match = re.match(pattern, line)
            if match:
                key, value = match.groups()
                os.environ[key] = value


class RateLimiter:
    """Rate limiter for AWS API calls"""

    def __init__(self, max_rate: float = 10, time_window: float = 1.0):
        self.max_rate = max_rate
        self.time_window = time_window
        self.timestamps = deque(maxlen=max_rate)
        self.lock = asyncio.Lock()

    async def wait(self):
        """Wait until we can make another API call"""
        async with self.lock:
            now = time.time()

            # Remove old timestamps
            while self.timestamps and now - self.timestamps[0] > self.time_window:
                self.timestamps.popleft()

            if len(self.timestamps) >= self.max_rate:
                # Calculate wait time
                oldest = self.timestamps[0]
                wait_time = self.time_window - (now - oldest)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.time()

            self.timestamps.append(now)


def rate_limited(max_rate: float = 10, time_window: float = 1.0):
    """Decorator to rate limit AWS API calls"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            await self.rate_limiter.wait()
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


class SpotManager:
    def __init__(self, debug: bool = False):
        self.debug = debug

        # Initialize logging first
        self._setup_logging()

        # Initialize AWS clients
        self.region = os.getenv("AWS_REGION", "us-west-2")
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.ec2_resource = boto3.resource("ec2", region_name=self.region)
        self._instance_type_cache = {}

        # Initialize rate limiter with conservative defaults
        self.rate_limiter = RateLimiter(max_rate=8, time_window=1.0)  # 8 requests per second

        # Initialize lifecycle tracking
        self.lifecycle_events = {}  # instance_id -> list of lifecycle events
        self.lifecycle_lock = asyncio.Lock()  # For thread-safe lifecycle updates

        # Health monitoring configuration
        self.health_check_interval = 60  # Seconds between health checks
        self.max_health_failures = 3  # Max consecutive failures before recovery
        self.health_metrics = {}  # instance_id -> health metrics
        self.health_lock = asyncio.Lock()  # For thread-safe health updates
        self.monitoring_tasks = set()  # Track active monitoring tasks
        self.health_thresholds = {
            "max_response_time": 5.0,  # Seconds
            "min_success_rate": 0.8,  # 80%
            "max_consecutive_failures": 3,
            "max_error_rate": 0.2,  # 20%
        }

        # Error recovery configuration
        self.max_retries = 5  # Max retries for recoverable errors
        self.retry_delay = 1.0  # Initial retry delay in seconds
        self.max_retry_delay = 30.0  # Max retry delay in seconds
        self.recovery_actions = {
            "InstanceLimitExceeded": self._handle_instance_limit_error,
            "InsufficientInstanceCapacity": self._handle_capacity_error,
            "SpotInstanceRequestLimitExceeded": self._handle_spot_limit_error,
            "RequestLimitExceeded": self._handle_rate_limit_error,
            "Unavailable": self._handle_service_unavailable,
            "InternalError": self._handle_internal_error,
        }
        # Load environment variables
        aws_env_path = PROJECT_ROOT / "aws" / "config" / "env.sh"
        load_shell_env(aws_env_path)

        # Initialize scaling limits from environment or defaults
        self.max_instances = int(os.getenv("MAX_INSTANCES", 1000))
        self.max_instances_per_launch = min(
            int(os.getenv("MAX_INSTANCES_PER_LAUNCH", 100)),
            100,  # AWS hard limit per launch request
        )
        self.min_instances = int(os.getenv("MIN_INSTANCES", 1))
        self.max_total_vcpus = int(os.getenv("MAX_TOTAL_VCPUS", 10000))
        self.max_total_memory = int(os.getenv("MAX_TOTAL_MEMORY", 100000))  # In GB

        # Track resource usage
        self.current_vcpus = 0
        self.current_memory = 0  # In GB
        self.region = os.getenv("AWS_REGION", "us-west-2")
        self.instance_type = os.getenv("INSTANCE_TYPE", "t3.micro")
        self.key_name = os.getenv("KEY_NAME")
        self.security_group_name = os.getenv("SECURITY_GROUP_NAME", "bacalhau-scale-test-sg")
        self.configured_ami_id = os.getenv("CONFIGURED_AMI_ID")

        # Validate all configuration parameters
        self._validate_configuration()
        self._cleanup_tasks = set()  # Track cleanup tasks
        self._cleanup_lock = asyncio.Lock()  # For thread-safe cleanup operations
        self._created_resources = {"instances": set(), "security_groups": set(), "key_pairs": set()}
        self.key_name = os.getenv("KEY_NAME")
        self.security_group_name = os.getenv("SECURITY_GROUP_NAME", "bacalhau-scale-test-sg")
        # Initialize tagging system
        self.default_tags = {
            "Name": os.getenv("INSTANCE_TAG_VALUE", "bacalhau-scale-test"),
            "Project": "BacalhauScaleTest",
            "Environment": "Test",
            "ManagedBy": "SpotManager",
            "CreationTime": datetime.now().isoformat(),
        }
        self.configured_ami_id = os.getenv("CONFIGURED_AMI_ID")

        # Instance state machine tracking
        self.instance_states = {}  # instance_id -> state info
        self.state_lock = asyncio.Lock()  # For thread-safe state updates
        self.state_transitions = {
            "pending": ["running", "terminated", "shutting-down"],
            "running": ["stopping", "shutting-down", "terminated"],
            "stopping": ["stopped", "terminated"],
            "stopped": ["terminated", "pending"],
            "shutting-down": ["terminated"],
            "terminated": [],
        }

        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.ec2_resource = boto3.resource("ec2", region_name=self.region)
        self._instance_type_cache = {}

        # Use global progress task
        global progress_task
        self.progress_task = progress_task

        self._setup_logging()
        self.log(
            "info",
            "SpotManager initialized",
            region=self.region,
            instance_type=self.instance_type,
            security_group=self.security_group_name,
        )

    def _validate_configuration(self) -> None:
        """Validate all configuration parameters"""
        required_env_vars = [
            "AWS_REGION",
            "KEY_NAME",
            "SECURITY_GROUP_NAME",
            "CONFIGURED_AMI_ID",
            "INSTANCE_TYPE",
        ]

        # Validate instance type
        if not self.validate_instance_type(self.instance_type):
            raise ValueError(
                f"Instance type {self.instance_type} is not supported or available. "
                f"Must support EBS optimization, HVM virtualization, and have at least 2 network interfaces"
            )

        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please check your aws/config/env.sh file"
            )

        # Validate instance type format
        if not re.match(r"^[a-z0-9]+\.\w+$", self.instance_type):
            raise ValueError(
                f"Invalid instance type format: {self.instance_type}. "
                f"Expected format like 't3.micro'"
            )

        # Validate AMI ID format
        if not re.match(r"^ami-[0-9a-f]{17}$", self.configured_ami_id):
            raise ValueError(
                f"Invalid AMI ID format: {self.configured_ami_id}. "
                f"Expected format like 'ami-0123456789abcdef0'"
            )

        # Validate security group name
        if not re.match(r"^[a-zA-Z0-9_\-]{1,255}$", self.security_group_name):
            raise ValueError(
                f"Invalid security group name: {self.security_group_name}. "
                f"Must be 1-255 alphanumeric characters, underscores or hyphens"
            )

        # Validate key pair name
        if not re.match(r"^[a-zA-Z0-9_\-]{1,255}$", self.key_name):
            raise ValueError(
                f"Invalid key pair name: {self.key_name}. "
                f"Must be 1-255 alphanumeric characters, underscores or hyphens"
            )

        # Validate region format
        if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", self.region):
            raise ValueError(
                f"Invalid AWS region format: {self.region}. Expected format like 'us-west-2'"
            )

    def _setup_logging(self):
        """Setup logging to write to debug.log"""
        self.logger = logging.getLogger("SpotManager")
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        # Remove any existing handlers
        self.logger.handlers = []

        # Create file handler that writes to debug.log
        file_handler = logging.FileHandler(DEBUG_LOG)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log(self, level: str, message: str, **kwargs):
        """Log structured messages with additional context"""
        log_method = getattr(self.logger, level, self.logger.info)
        log_data = {"message": message, **kwargs}
        log_method(log_data)

    def debug_log(self, message: str, **kwargs):
        """Log debug messages to debug.log"""
        if self.debug:
            write_debug(message)
            if kwargs:
                write_debug(f"Additional context: {json.dumps(kwargs, indent=2)}")

    async def check_node_health(
        self, ip_address: str, max_retries: int = 3, timeout: int = 5
    ) -> Dict[str, Any]:
        """Check if a Bacalhau node is healthy by querying its API with retries
        and collecting detailed metrics.

        Args:
            ip_address: IP address of node to check
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds for each attempt

        Returns:
            Dict containing health status and metrics:
            {
                "healthy": bool,
                "response_time": float,  # In seconds
                "status_code": int,
                "error": Optional[str],
                "timestamp": str
            }
        """
        url = f"http://{ip_address}:1234"
        retry_delay = 1  # Start with 1 second delay
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=timeout) as response:
                        response_time = time.time() - start_time

                        # Collect metrics
                        metrics = {
                            "healthy": response.status == 200,
                            "response_time": response_time,
                            "status_code": response.status,
                            "error": None,
                            "timestamp": datetime.now().isoformat(),
                        }

                        if response.status != 200:
                            self.debug_log(
                                f"Health check attempt {attempt + 1} failed for {ip_address}: "
                                f"Status {response.status}"
                            )
                            metrics["error"] = f"HTTP {response.status}"

                        return metrics
            except asyncio.TimeoutError:
                error_msg = f"Health check attempt {attempt + 1} timed out for {ip_address}"
                self.debug_log(error_msg)
                metrics = {
                    "healthy": False,
                    "response_time": time.time() - start_time,
                    "status_code": None,
                    "error": "Timeout",
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                error_msg = f"Health check attempt {attempt + 1} failed for {ip_address}: {str(e)}"
                self.debug_log(error_msg)
                metrics = {
                    "healthy": False,
                    "response_time": time.time() - start_time,
                    "status_code": None,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            # Exponential backoff between retries
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)  # Cap at 10 seconds

        return metrics

    async def start_health_monitoring(self) -> None:
        """Start continuous health monitoring for all instances"""
        while True:
            try:
                # Get all running instances
                instance_ids = await asyncio.get_event_loop().run_in_executor(
                    None, self.get_all_instance_ids
                )

                if not instance_ids:
                    await asyncio.sleep(self.health_check_interval)
                    continue

                # Get instance IPs
                instance_ips = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.get_instance_ips(instance_ids)
                )

                # Check health of all nodes
                health_results = await self.check_all_nodes_health(instance_ips)

                # Update health metrics
                async with self.health_lock:
                    for ip, metrics in health_results.items():
                        instance_id = next(
                            (
                                id
                                for id, ip_addr in zip(instance_ids, instance_ips)
                                if ip_addr == ip
                            ),
                            None,
                        )
                        if instance_id:
                            if instance_id not in self.health_metrics:
                                self.health_metrics[instance_id] = {
                                    "history": [],
                                    "consecutive_failures": 0,
                                    "last_healthy": None,
                                }

                            # Update metrics
                            self.health_metrics[instance_id]["history"].append(metrics)
                            if not metrics["healthy"]:
                                self.health_metrics[instance_id]["consecutive_failures"] += 1
                            else:
                                self.health_metrics[instance_id]["consecutive_failures"] = 0
                                self.health_metrics[instance_id]["last_healthy"] = datetime.now()

                            # Check if instance needs recovery
                            if (
                                self.health_metrics[instance_id]["consecutive_failures"]
                                >= self.health_thresholds["max_consecutive_failures"]
                            ):
                                await self.recover_instance(instance_id)

                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                self.log("error", "Health monitoring error", error=str(e))
                await asyncio.sleep(self.health_check_interval)

    async def recover_instance(self, instance_id: str) -> None:
        """Recover an unhealthy instance"""
        self.log("warning", "Recovering unhealthy instance", instance_id=instance_id)

        try:
            # Get instance details
            instance = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
                    "Instances"
                ][0],
            )

            # Terminate the unhealthy instance
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.ec2.terminate_instances(InstanceIds=[instance_id])
            )

            # Wait for termination to complete
            waiter = self.ec2.get_waiter("instance_terminated")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: waiter.wait(
                    InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 40}
                ),
            )

            # Launch replacement instance
            await self.launch_instances(1)

            # Cleanup health metrics
            async with self.health_lock:
                if instance_id in self.health_metrics:
                    del self.health_metrics[instance_id]

            self.log("info", "Instance recovery completed", instance_id=instance_id)

        except Exception as e:
            self.log("error", "Instance recovery failed", instance_id=instance_id, error=str(e))
            raise

    async def check_all_nodes_health(
        self, instance_ips: List[str], progress=None, timeout: int = 10
    ) -> Dict[str, Dict]:
        """Check health of all nodes in parallel with timeout and collect metrics

        Args:
            instance_ips: List of IP addresses to check
            progress: Progress tracker for UI updates
            timeout: Maximum time to wait for all checks

        Returns:
            Dict mapping IP addresses to health metrics:
            {
                "healthy": bool,
                "response_time": float,
                "status_code": Optional[int],
                "error": Optional[str],
                "timestamp": str
            }
        """
        try:
            # Create tasks with individual timeouts
            tasks = [
                asyncio.wait_for(self.check_node_health(ip), timeout=timeout) for ip in instance_ips
            ]

            # Run all checks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            health_status = {}
            for ip, result in zip(instance_ips, results):
                if isinstance(result, Exception):
                    self.debug_log(f"Health check failed for {ip}: {str(result)}")
                    health_status[ip] = False
                else:
                    health_status[ip] = result

            return health_status

        except asyncio.TimeoutError:
            self.debug_log(f"Health checks timed out after {timeout} seconds")
            return {ip: False for ip in instance_ips}
        except Exception as e:
            self.debug_log(f"Error checking node health: {str(e)}")
            return {ip: False for ip in instance_ips}

    def get_instance_ips(self, instance_ids: List[str]) -> List[str]:
        """Get public IPs for a list of instance IDs"""
        response = self.ec2.describe_instances(InstanceIds=instance_ids)
        return [
            instance["PublicIpAddress"]
            for reservation in response["Reservations"]
            for instance in reservation["Instances"]
            if "PublicIpAddress" in instance
        ]

    def ensure_security_group(self) -> str:
        """Ensure security group exists and has correct rules"""
        # Validate security group configuration before proceeding
        if not self.security_group_name:
            raise ValueError("Security group name is not configured")

        self.debug_log("Checking for existing security group...")

        try:
            response = self.ec2.describe_security_groups(
                Filters=[{"Name": "group-name", "Values": [self.security_group_name]}]
            )

            if response["SecurityGroups"]:
                group_id = response["SecurityGroups"][0]["GroupId"]
                self.debug_log(f"Found existing security group: {group_id}")
            else:
                response = self.ec2.create_security_group(
                    GroupName=self.security_group_name,
                    Description="Security group for Bacalhau scale testing",
                )
                group_id = response["GroupId"]
                self._created_resources["security_groups"].add(group_id)
                self.debug_log(f"Created new security group: {group_id}")

            self._update_security_group_rules(group_id)
            return group_id

        except Exception as e:
            console.print(f"[red]Error ensuring security group: {str(e)}[/red]")
            self._cleanup_resources()
            raise

    def _update_security_group_rules(self, group_id: str):
        """Update security group rules"""
        try:
            existing_rules = self.ec2.describe_security_group_rules(
                Filters=[{"Name": "group-id", "Values": [group_id]}]
            )

            for rule in existing_rules.get("SecurityGroupRules", []):
                if not rule.get("IsEgress", True):
                    try:
                        self.ec2.revoke_security_group_ingress(
                            GroupId=group_id,
                            SecurityGroupRuleIds=[rule["SecurityGroupRuleId"]],
                        )
                    except Exception as e:
                        self.debug_log(f"Error removing rule: {str(e)}")

            self.ec2.authorize_security_group_ingress(
                GroupId=group_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 4222,
                        "ToPort": 4222,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 1234,
                        "ToPort": 1234,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                ],
            )
        except Exception as e:
            self.debug_log(f"Error updating security group rules: {str(e)}")
            raise

    async def _cleanup_instances(self, instance_ids: List[str]) -> None:
        """Async cleanup handler for instances with improved state validation"""
        async with self._cleanup_lock:
            try:
                self.log("info", "Starting instance cleanup", instance_count=len(instance_ids))

                # Get current instance states
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.ec2.describe_instances(InstanceIds=instance_ids)
                )

                # Filter out instances that are already terminated or shutting-down
                active_instances = [
                    instance["InstanceId"]
                    for reservation in response["Reservations"]
                    for instance in reservation["Instances"]
                    if instance["State"]["Name"] not in ["terminated", "shutting-down"]
                ]

                if not active_instances:
                    self.log("info", "No active instances to terminate")
                    return

                # Calculate resources to release
                released_vcpus = 0
                released_memory = 0
                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        if instance["InstanceId"] in active_instances:
                            instance_type = instance["InstanceType"]
                            instance_info = self.get_instance_type_info(instance_type)
                            released_vcpus += int(instance_info["vcpus"])
                            released_memory += float(instance_info["memory"].replace("GB", ""))

                # Terminate active instances
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.ec2.terminate_instances(InstanceIds=active_instances)
                )
                self.log("info", "Instance termination requested", instance_ids=active_instances)

                # Wait for termination with state validation
                max_attempts = 40
                attempt = 0
                while attempt < max_attempts:
                    # Get current states
                    status_response = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.ec2.describe_instances(InstanceIds=active_instances)
                    )

                    # Check if all instances are terminated
                    terminated_count = sum(
                        1
                        for reservation in status_response["Reservations"]
                        for instance in reservation["Instances"]
                        if instance["State"]["Name"] in ["terminated", "shutting-down"]
                    )

                    if terminated_count == len(active_instances):
                        break

                    attempt += 1
                    await asyncio.sleep(5)

                if attempt >= max_attempts:
                    self.log(
                        "warning",
                        "Timeout waiting for instances to terminate",
                        instance_ids=active_instances,
                    )
                    raise RuntimeError(
                        f"Timeout waiting for instances to terminate. "
                        f"Current states: {', '.join(set(instance['State']['Name'] for reservation in status_response['Reservations'] for instance in reservation['Instances']))}"
                    )
                    # Update resource tracking
                    self.current_vcpus = max(0, self.current_vcpus - released_vcpus)
                    self.current_memory = max(0, self.current_memory - released_memory)

                    self.log(
                        "info",
                        "Instances terminated",
                        instance_ids=instance_ids,
                        released_vcpus=released_vcpus,
                        released_memory=f"{released_memory}GB",
                        remaining_vcpus=self.current_vcpus,
                        remaining_memory=f"{self.current_memory}GB",
                    )

            except Exception as e:
                self.log("error", "Error during instance cleanup", error=str(e))
                raise

    @rate_limited(max_rate=5, time_window=1.0)  # 5 requests per second for state updates
    async def update_instance_states(self, instance_ids: List[str]) -> Dict[str, Dict]:
        """Update and return current states for given instance IDs with state machine validation
        and detailed lifecycle tracking"""
        async with self.state_lock:
            try:
                # Get both instance details and status checks in parallel
                instance_response, status_response = await asyncio.gather(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.ec2.describe_instances(InstanceIds=instance_ids)
                    ),
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.ec2.describe_instance_status(
                            InstanceIds=instance_ids, IncludeAllInstances=True
                        ),
                    ),
                )

                # Create status mapping for quick lookup
                status_map = {
                    status["InstanceId"]: status
                    for status in status_response.get("InstanceStatuses", [])
                }

                # Update our state tracking
                for reservation in instance_response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        new_state = instance["State"]["Name"]

                        # Get current state if exists
                        current_state = self.instance_states.get(instance_id, {}).get(
                            "state", "pending"
                        )

                        # Validate state transition
                        if not self.validate_state_transition(instance_id, new_state):
                            self.log(
                                "warning",
                                "Invalid state transition attempted",
                                instance_id=instance_id,
                                current_state=current_state,
                                new_state=new_state,
                            )
                            continue

                        # Get system health status
                        system_status = "unknown"
                        instance_status = "unknown"
                        if instance_id in status_map:
                            status = status_map[instance_id]
                            system_status = status["SystemStatus"]["Status"]
                            instance_status = status["InstanceStatus"]["Status"]

                        # Record lifecycle event
                        # Get instance type info
                        instance_info = self.get_instance_type_info(instance["InstanceType"])

                        lifecycle_event = {
                            "timestamp": datetime.now().isoformat(),
                            "state": new_state,
                            "system_status": system_status,
                            "instance_status": instance_status,
                            "ip": instance.get("PublicIpAddress", ""),
                            "type": instance["InstanceType"],
                            "details": {
                                "cpu": instance_info["vcpus"],
                                "memory": instance_info["memory"],
                                "network": instance_info["network"],
                                "ebs_optimized": instance_info["ebs_optimized"],
                            },
                        }

                        async with self.lifecycle_lock:
                            if instance_id not in self.lifecycle_events:
                                self.lifecycle_events[instance_id] = []
                            self.lifecycle_events[instance_id].append(lifecycle_event)

                        # Update state tracking
                        self.instance_states[instance_id] = {
                            "state": new_state,
                            "ip": instance.get("PublicIpAddress", ""),
                            "type": instance["InstanceType"],
                            "launch_time": instance["LaunchTime"].isoformat(),
                            "system_status": system_status,
                            "instance_status": instance_status,
                            "state_history": self.instance_states.get(instance_id, {}).get(
                                "state_history", []
                            )
                            + [{"state": new_state, "timestamp": datetime.now().isoformat()}],
                            "lifecycle_events": self.lifecycle_events.get(instance_id, []),
                        }

                return self.instance_states

            except Exception as e:
                self.debug_log(f"Error updating instance states: {str(e)}")
                raise

    @rate_limited(max_rate=5, time_window=1.0)  # 5 requests per second for polling
    async def poll_instance_status(
        self,
        instance_ids: List[str],
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        progress_tracker: Progress = None,
        task: int = None,
    ) -> None:
        """Poll EC2 for the status of instances until all are running with exponential backoff"""
        global progress, progress_task, layout
        progress_task = progress.add_task(
            "Waiting for instances to start...", total=len(instance_ids)
        )

        current_delay = initial_delay
        max_attempts = 60
        attempt = 0

        while attempt < max_attempts:
            try:
                # Get current states
                states = await self.update_instance_states(instance_ids)

                running_count = sum(1 for state in states.values() if state["state"] == "running")

                terminated_count = sum(
                    1
                    for state in states.values()
                    if state["state"] in ["terminated", "shutting-down"]
                )

                if terminated_count > 0:
                    raise RuntimeError(
                        f"{terminated_count} instances were terminated while waiting for startup. This usually indicates insufficient spot capacity."
                    )

                if progress_tracker and task is not None:
                    progress_tracker.update(
                        task,
                        completed=running_count,
                        description=f"[yellow]Running: {running_count}/{len(instance_ids)}[/yellow]",
                    )
                    live.refresh()
                layout["progress"].update(progress)

                if running_count == len(instance_ids):
                    break

                # Exponential backoff with jitter
                await asyncio.sleep(current_delay)
                current_delay = min(max_delay, current_delay * 1.5) * (1 + random.random())
                attempt += 1

            except self.ec2.exceptions.ClientError as e:
                if "InvalidInstanceID.NotFound" in str(e):
                    raise RuntimeError(
                        "Some instances disappeared while waiting for startup. This usually indicates insufficient spot capacity."
                    )
                # Retry on throttling errors
                if "RequestLimitExceeded" in str(e):
                    await asyncio.sleep(current_delay)
                    current_delay = min(max_delay, current_delay * 1.5) * (1 + random.random())
                    attempt += 1
                    continue
                raise
            except Exception as e:
                # General error handling with retry
                self.debug_log(f"Polling error: {str(e)}")
                await asyncio.sleep(current_delay)
                current_delay = min(max_delay, current_delay * 1.5) * (1 + random.random())
                attempt += 1
                continue

        if attempt >= max_attempts:
            if progress_tracker and task is not None:
                progress_tracker.update(
                    task,
                    description="[red]Timeout waiting for instances[/red]",
                    completed=running_count,
                )
                live.refresh()
            raise RuntimeError(
                f"Timeout waiting for instances to start after {max_attempts} attempts"
            )

    def list_instances(self, filters: List[Dict] = None) -> None:
        """List all running instances with optional filters"""
        try:
            # Default filter for managed instances
            default_filters = [
                {
                    "Name": "tag:ManagedBy",
                    "Values": ["SpotManager"],
                },
                {"Name": "instance-state-name", "Values": ["pending", "running"]},
            ]

            # Merge with any additional filters
            if filters:
                default_filters.extend(filters)

            response = self.ec2.describe_instances(Filters=default_filters)

            instances = [
                instance
                for reservation in response["Reservations"]
                for instance in reservation["Instances"]
            ]

            # Update layout with consistent styling
            layout["header"].update(
                Panel(
                    "[bold blue]Bacalhau Spot Manager[/bold blue]\n"
                    f"[dim]Listing {len(instances)} instances[/dim]",
                    style="white on #28464B",
                    border_style="blue",
                )
            )

            # Create and display the table
            table = self.create_instance_table(instances)
            layout["body"].update(Panel(table, border_style="blue"))
            layout["status"].update(
                Panel(
                    "[green]✓ Instance list loaded successfully[/green]",
                    border_style="green",
                )
            )
            live.refresh()

        except Exception as e:
            console.print(f"[red]Error listing instances: {str(e)}[/red]")
            raise

    @rate_limited(max_rate=2, time_window=1.0)  # 2 requests per second for terminations
    async def terminate_instances(self, instance_ids: List[str], batch_size: int = 50) -> None:
        """Terminate specified instances in batches

        Args:
            instance_ids: List of instance IDs to terminate
            batch_size: Number of instances per batch (default: 50)
        """
        if not instance_ids:
            return

        global progress, progress_task, layout
        progress_task = progress.add_task("Terminating instances...", total=len(instance_ids))
        layout["progress"].update(progress)

        try:
            # Process instances in batches
            batches = (len(instance_ids) + batch_size - 1) // batch_size
            terminated_count = 0

            for batch_num in range(batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(instance_ids))
                batch_ids = instance_ids[start_idx:end_idx]

                # Update progress
                progress.update(
                    progress_task,
                    description=f"Terminating batch {batch_num + 1}/{batches} ({len(batch_ids)} instances)...",
                    completed=terminated_count,
                )
                layout["progress"].update(progress)
                live.refresh()

                try:
                    # Terminate batch
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.ec2.terminate_instances(InstanceIds=batch_ids)
                    )

                    # Wait for termination with async waiter
                    waiter = self.ec2.get_waiter("instance_terminated")
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: waiter.wait(
                            InstanceIds=batch_ids,
                            WaiterConfig={"Delay": 5, "MaxAttempts": 40},
                        ),
                    )

                    terminated_count += len(batch_ids)
                    progress.update(progress_task, completed=terminated_count)
                    layout["progress"].update(progress)
                    live.refresh()

                    # Update status after each batch
                    layout["status"].update(
                        Panel(
                            f"[green]Terminated {terminated_count}/{len(instance_ids)} instances[/green]",
                            border_style="green",
                        )
                    )

                except Exception as e:
                    layout["status"].update(
                        Panel(
                            f"[red]Error terminating batch {batch_num + 1}: {str(e)}[/red]",
                            border_style="red",
                        )
                    )
                    raise

                # Wait briefly between batches to avoid rate limits
                if batch_num < batches - 1:
                    await asyncio.sleep(2)

            progress.update(
                progress_task,
                description="All instances terminated",
                completed=len(instance_ids),
            )
            layout["progress"].update(progress)

        except Exception as e:
            console.print(f"[red]Error terminating instances: {str(e)}[/red]")
            raise

    @rate_limited(max_rate=2, time_window=1.0)  # 2 requests per second for launches
    async def launch_instances(self, count: int, batch_size: int = 50) -> List[str]:
        """Launch specified number of spot instances in batches with cleanup handler
        and automatic error recovery

        Args:
            count: Total number of instances to launch
            batch_size: Number of instances per batch (default: 50)

        Returns:
            List of launched instance IDs

        Raises:
            ValueError: If launch configuration is invalid
            RuntimeError: If launch fails
        """
        global progress, progress_task, layout, live

        # Create detailed progress tracking
        launch_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            expand=True,
        )

        # Create subtasks for each phase
        main_task = launch_progress.add_task("[cyan]Launching instances...", total=100)
        phase1 = launch_progress.add_task("[yellow]Validating configuration...", total=1)
        phase2 = launch_progress.add_task("[yellow]Requesting instances...", total=1)
        phase3 = launch_progress.add_task("[yellow]Waiting for instances...", total=1)

        # Update layout with detailed progress
        layout["progress"].update(
            Panel(launch_progress, title="Launch Progress", border_style="blue")
        )
        live.refresh()

        # Update progress for validation phase
        launch_progress.update(phase1, description="[green]Validating configuration...")
        live.refresh()

        # Validate launch configuration
        if not self.configured_ami_id:
            launch_progress.update(
                phase1, description="[red]Error: AMI ID not configured[/red]", completed=1
            )
            live.refresh()
            raise ValueError("AMI ID is not configured")
        if not self.key_name:
            raise ValueError("Key pair name is not configured")
        if not self.instance_type:
            raise ValueError("Instance type is not configured")

        # Validate instance count against various limits
        if count < self.min_instances:
            raise ValueError(
                f"Cannot launch fewer than {self.min_instances} instances. Requested: {count}"
            )

        if count > self.max_instances_per_launch:
            raise ValueError(
                f"Cannot launch more than {self.max_instances_per_launch} instances at once. "
                f"Requested: {count}"
            )

        # Check current instance count
        current_count = len(self.get_all_instance_ids())
        if current_count + count > self.max_instances:
            raise ValueError(
                f"Cannot launch {count} instances. Would exceed max limit of {self.max_instances}. "
                f"Current instances: {current_count}"
            )

        # Check resource limits
        instance_info = self.get_instance_type_info(self.instance_type)
        requested_vcpus = int(instance_info["vcpus"]) * count
        requested_memory = float(instance_info["memory"].replace("GB", "")) * count

        if self.current_vcpus + requested_vcpus > self.max_total_vcpus:
            raise ValueError(
                f"Cannot launch {count} instances. Would exceed vCPU limit of {self.max_total_vcpus}. "
                f"Current vCPUs: {self.current_vcpus}, Requested: {requested_vcpus}"
            )

        if self.current_memory + requested_memory > self.max_total_memory:
            raise ValueError(
                f"Cannot launch {count} instances. Would exceed memory limit of {self.max_total_memory}GB. "
                f"Current memory: {self.current_memory}GB, Requested: {requested_memory}GB"
            )

        if not self.configured_ami_id:
            raise ValueError("No AMI ID configured. Please run build-ami.sh first.")

        security_group_id = self.ensure_security_group()
        startup_script_path = PROJECT_ROOT / "fleet" / "scripts" / "startup.sh"

        if not startup_script_path.exists():
            raise FileNotFoundError(f"Startup script not found at {startup_script_path}")

        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # Update progress for request phase
                launch_progress.update(
                    phase2,
                    description=f"[green]Requesting instances (attempt {retry_count + 1}/{self.max_retries})...",
                )
                live.refresh()

                # Update resource tracking
                self.current_vcpus += requested_vcpus
                self.current_memory += requested_memory

                # Update main progress
                launch_progress.update(main_task, completed=25)

                # Update progress for instance creation
                launch_progress.update(phase2, description="[green]Creating instances...")
                live.refresh()

                # Calculate number of batches needed
                batches = (count + batch_size - 1) // batch_size
                instance_ids = []

                # Process batches sequentially with error handling
                for batch_num in range(batches):
                    batch_count = min(batch_size, count - (batch_num * batch_size))

                    # Update progress for batch
                    launch_progress.update(
                        phase2,
                        description=f"[green]Processing batch {batch_num + 1}/{batches} ({batch_count} instances)[/green]",
                    )
                    live.refresh()

                    # Track batch resources
                    batch_vcpus = int(instance_info["vcpus"]) * batch_count
                    batch_memory = float(instance_info["memory"].replace("GB", "")) * batch_count

                    # Try batch with retries
                    batch_retries = 3
                    for attempt in range(batch_retries):
                        try:
                            # Run batch asynchronously
                            response = await asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda: self.ec2.run_instances(
                                    ImageId=self.configured_ami_id,
                                    InstanceType=self.instance_type,
                                    KeyName=self.key_name,
                                    SecurityGroupIds=[security_group_id],
                                    TagSpecifications=[
                                        {
                                            "ResourceType": "instance",
                                            "Tags": [
                                                {"Key": key, "Value": value}
                                                for key, value in self.default_tags.items()
                                            ]
                                            + [
                                                {
                                                    "Key": "LaunchGroup",
                                                    "Value": f"scale-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                                                }
                                            ],
                                        }
                                    ],
                                    IamInstanceProfile={"Name": "BacalhauScaleTestRole"},
                                    UserData=startup_script_path.read_text(),
                                    InstanceMarketOptions={
                                        "MarketType": "spot",
                                        "SpotOptions": {
                                            "SpotInstanceType": "one-time",
                                            "InstanceInterruptionBehavior": "terminate",
                                        },
                                    },
                                    MinCount=batch_count,
                                    MaxCount=batch_count,
                                ),
                            )

                            # Collect instance IDs
                            batch_ids = [i["InstanceId"] for i in response["Instances"]]
                            instance_ids.extend(batch_ids)

                            # Update resource tracking
                            self.current_vcpus += batch_vcpus
                            self.current_memory += batch_memory

                            # Wait briefly between batches to avoid rate limits
                            if batch_num < batches - 1:
                                await asyncio.sleep(2)

                            break  # Success - exit retry loop

                        except Exception as e:
                            # Handle batch failure
                            self.log(
                                "warning",
                                "Batch launch failed",
                                batch_num=batch_num,
                                attempt=attempt + 1,
                                error=str(e),
                            )

                            # Rollback resource tracking
                            self.current_vcpus -= batch_vcpus
                            self.current_memory -= batch_memory

                            if attempt == batch_retries - 1:
                                raise RuntimeError(
                                    f"Failed to launch batch {batch_num + 1} after {batch_retries} attempts"
                                )

                            # Exponential backoff before retry
                            await asyncio.sleep(2**attempt)

                    self._created_resources["instances"].update(instance_ids)

                    # Update progress
                    launch_progress.update(
                        phase2,
                        description=f"[green]Created {len(instance_ids)} instances[/green]",
                        completed=1,
                    )
                    launch_progress.update(main_task, completed=50)
                    live.refresh()

                    # Create cleanup task
                    cleanup_task = asyncio.create_task(self._cleanup_instances(instance_ids))
                    self._cleanup_tasks.add(cleanup_task)
                    cleanup_task.add_done_callback(self._cleanup_tasks.discard)

                    try:
                        # Update progress for waiting phase
                        launch_progress.update(
                            phase3,
                            description="[yellow]Waiting for instances to start...",
                            total=len(instance_ids),
                        )
                        live.refresh()

                        # Poll for instance status with progress updates
                        await self.poll_instance_status(
                            instance_ids, progress=launch_progress, task=phase3
                        )

                        # Update main progress
                        launch_progress.update(main_task, completed=100)
                        launch_progress.update(
                            phase3,
                            description="[green]All instances running[/green]",
                            completed=len(instance_ids),
                        )
                        live.refresh()

                        return instance_ids
                    except Exception as e:
                        # If launch fails, ensure cleanup
                        await cleanup_task
                        raise

            except Exception as e:
                # Handle recoverable errors
                error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
                if error_code in self.recovery_actions:
                    recovery_action = self.recovery_actions[error_code]
                    await recovery_action(e, count, batch_size)

                    # Exponential backoff before retry
                    await asyncio.sleep(self.retry_delay)
                    self.retry_delay = min(self.retry_delay * 2, self.max_retry_delay)
                    retry_count += 1
                    continue

                # Non-recoverable error
                console.print(f"[red]Error launching instances: {str(e)}[/red]")
                raise

    def get_all_instance_ids(self, filters: List[Dict] = None) -> List[str]:
        """Get all running instance IDs with optional filters"""
        try:
            # Default filter for managed instances
            default_filters = [
                {
                    "Name": "tag:ManagedBy",
                    "Values": ["SpotManager"],
                },
                {"Name": "instance-state-name", "Values": ["pending", "running"]},
            ]

            # Merge with any additional filters
            if filters:
                default_filters.extend(filters)

            response = self.ec2.describe_instances(Filters=default_filters)

            return [
                instance["InstanceId"]
                for reservation in response["Reservations"]
                for instance in reservation["Instances"]
            ]

        except Exception as e:
            console.print(f"[red]Error getting instance IDs: {str(e)}[/red]")
            raise

    def wait_for_instances_running(self, instance_ids: List[str]) -> None:
        """Wait for instances to be in running state"""
        global progress, progress_task, layout
        progress_task = progress.add_task("Waiting for instances...", total=len(instance_ids))
        layout["progress"].update(progress)

        max_attempts = 60
        attempt = 0

        while attempt < max_attempts:
            try:
                response = self.ec2.describe_instances(InstanceIds=instance_ids)
                running_count = sum(
                    1
                    for reservation in response["Reservations"]
                    for instance in reservation["Instances"]
                    if instance["State"]["Name"] == "running"
                )
                terminated_count = sum(
                    1
                    for reservation in response["Reservations"]
                    for instance in reservation["Instances"]
                    if instance["State"]["Name"] in ["terminated", "shutting-down"]
                )

                if terminated_count > 0:
                    raise RuntimeError(
                        f"{terminated_count} instances were terminated while waiting for startup. This usually indicates insufficient spot capacity."
                    )

                progress.update(
                    progress_task,
                    completed=running_count,
                    description=f"Running: {running_count}/{len(instance_ids)}",
                )
                layout["progress"].update(progress)

                if running_count == len(instance_ids):
                    break

                time.sleep(5)
                attempt += 1

            except self.ec2.exceptions.ClientError as e:
                if "InvalidInstanceID.NotFound" in str(e):
                    raise RuntimeError(
                        "Some instances disappeared while waiting for startup. This usually indicates insufficient spot capacity."
                    )
                raise

        if attempt >= max_attempts:
            raise RuntimeError(
                f"Timeout waiting for instances to start. Current states: {', '.join(set(instance['State']['Name'] for reservation in response['Reservations'] for instance in reservation['Instances']))}"
            )

    def verify_bacalhau_access(self) -> None:
        """Verify that we can access Bacalhau CLI and have correct permissions"""
        try:
            result = subprocess.run(
                ["bacalhau", "node", "list", "--output", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            nodes = json.loads(result.stdout)

            if isinstance(nodes, dict):
                if "nodes" in nodes:
                    nodes = nodes["nodes"]
                elif "data" in nodes:
                    nodes = nodes["data"]
                else:
                    raise ValueError(f"Unexpected response structure: {list(nodes.keys())}")

            if not isinstance(nodes, list):
                raise ValueError(f"Unexpected nodes type: {type(nodes)}")

            self.debug_log(f"Successfully verified Bacalhau access. Found {len(nodes)} nodes.")

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Bacalhau node list output as JSON: {str(e)}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to run 'bacalhau node list'. Error: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "Bacalhau CLI not found. Please install Bacalhau CLI and ensure it's in your PATH."
            )

    async def check_bacalhau_node_status(
        self, instance_id: str, max_retries: int = 3, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Check if a Bacalhau node is healthy using bacalhau node list with retries

        Args:
            instance_id: Instance ID to check
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds for each attempt

        Returns:
            Tuple of (health status, status message)
        """
        retry_delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                # Run bacalhau node list command with timeout
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: subprocess.run(
                            ["bacalhau", "node", "list", "--output", "json"],
                            capture_output=True,
                            text=True,
                            check=True,
                        ),
                    ),
                    timeout=timeout,
                )

                # Parse JSON output
                try:
                    nodes = json.loads(result.stdout)
                    if self.debug:
                        self.debug_log(f"Node check response type: {type(nodes)}")
                        self.debug_log(f"Node check response count: {len(nodes)}")

                    # Ensure nodes is a list
                    if not isinstance(nodes, list):
                        return False, f"Invalid response type: {type(nodes)}"

                    # Iterate through each node to find a match
                    for node in nodes:
                        if not isinstance(node, dict):
                            continue

                        # Extract node info
                        info = node.get("Info", {})
                        if not isinstance(info, dict):
                            continue

                        # Extract labels and public IP
                        labels = info.get("Labels", {})
                        if not isinstance(labels, dict):
                            continue

                        found_instance_id = labels.get("INSTANCE_ID", "")
                        if not found_instance_id:
                            continue

                        # Check if the IP matches
                        if found_instance_id == instance_id:
                            # Extract connection state
                            connection_state = node.get("ConnectionState", {})
                            if not isinstance(connection_state, dict):
                                return False, "Invalid connection state format"

                            # Determine node health based on connection status
                            status = connection_state.get("Status", "UNKNOWN")
                            if status == "CONNECTED":
                                return True, "Connected"
                            else:
                                # Include last error if available
                                last_error = connection_state.get("LastError", "")
                                return False, f"Status: {status}" + (
                                    f" ({last_error})" if last_error else ""
                                )

                    return False, ""

                except json.JSONDecodeError as e:
                    if self.debug:
                        self.debug_log(f"Raw response: {result.stdout}")
                    return False, f"Invalid JSON response: {str(e)}"

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
                self.debug_log(f"Error running bacalhau node list: {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 10)  # Cap at 10 seconds
                    continue
                return False, f"Command failed: {error_msg}"
            except asyncio.TimeoutError:
                self.debug_log(f"Node status check timed out for {instance_id}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 10)  # Cap at 10 seconds
                    continue
                return False, "Timeout"
            except Exception as e:
                self.debug_log(f"Unexpected error checking node status: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 10)  # Cap at 10 seconds
                    continue
                return False, str(e)

    async def check_all_nodes_status(self, instance_ids: List[str]) -> Dict[str, Tuple[bool, str]]:
        """Check status of all Bacalhau nodes"""
        global progress, progress_task
        results = {}
        for instance_id in instance_ids:
            # Update the global progress task description
            progress.update(
                progress_task, description=f"Checking Bacalhau status of {instance_id}..."
            )
            status, message = await self.check_bacalhau_node_status(instance_id)
            results[instance_id] = (status, message)
        return results

    def validate_instance_type(self, instance_type: str) -> bool:
        """Validate if an instance type is supported and available"""
        try:
            # Check if instance type exists
            response = self.ec2.describe_instance_types(InstanceTypes=[instance_type])
            if not response["InstanceTypes"]:
                return False

            # Check instance type capabilities
            instance_info = response["InstanceTypes"][0]

            # Must support HVM virtualization
            if "hvm" not in instance_info.get("SupportedVirtualizationTypes", []):
                return False

            # Must support at least 1 network interface
            if instance_info.get("NetworkInfo", {}).get("MaximumNetworkInterfaces", 0) < 1:
                return False

            return True

        except Exception as e:
            self.debug_log(f"Error validating instance type: {str(e)}")
            return False

    def get_instance_type_info(self, instance_type: str) -> Dict[str, str]:
        """Get CPU and memory information for an instance type"""
        if instance_type not in self._instance_type_cache:
            try:
                if not self.validate_instance_type(instance_type):
                    raise ValueError(f"Instance type {instance_type} is not supported")

                response = self.ec2.describe_instance_types(InstanceTypes=[instance_type])
                info = response["InstanceTypes"][0]
                self._instance_type_cache[instance_type] = {
                    "vcpus": str(info["VCpuInfo"]["DefaultVCpus"]),
                    "memory": f"{info['MemoryInfo']['SizeInMiB'] / 1024:.1f}GB",
                    "type": instance_type,
                    "network": str(info["NetworkInfo"]["MaximumNetworkInterfaces"]),
                    "ebs_optimized": info["EbsInfo"]["EbsOptimizedSupport"] == "supported",
                    "supported_architectures": info["ProcessorInfo"]["SupportedArchitectures"],
                }
            except Exception as e:
                self.debug_log(f"Error getting instance type info: {str(e)}")
                self._instance_type_cache[instance_type] = {
                    "vcpus": "?",
                    "memory": "?",
                    "type": instance_type,
                    "network": "?",
                    "ebs_optimized": False,
                    "supported_architectures": [],
                }
        return self._instance_type_cache[instance_type]

    async def _handle_instance_limit_error(self, error, count, batch_size):
        """Handle instance limit exceeded errors"""
        self.log("warning", "Instance limit exceeded", error=str(error))

        # Reduce requested count and retry
        new_count = min(count, self.max_instances_per_launch // 2)
        if new_count < self.min_instances:
            raise RuntimeError("Cannot reduce instance count below minimum")

        self.log("info", f"Reducing instance count from {count} to {new_count}")
        return await self.launch_instances(new_count, batch_size)

    async def _handle_capacity_error(self, error, count, batch_size):
        """Handle insufficient capacity errors"""
        self.log("warning", "Insufficient instance capacity", error=str(error))

        # Try different instance type
        alt_instance_type = self._get_alternative_instance_type()
        if not alt_instance_type:
            raise RuntimeError("No alternative instance types available")

        self.log("info", f"Trying alternative instance type: {alt_instance_type}")
        original_type = self.instance_type
        self.instance_type = alt_instance_type
        try:
            return await self.launch_instances(count, batch_size)
        finally:
            self.instance_type = original_type

    async def _handle_spot_limit_error(self, error, count, batch_size):
        """Handle spot instance limit errors"""
        self.log("warning", "Spot instance limit exceeded", error=str(error))

        # Reduce batch size and retry
        new_batch_size = max(1, batch_size // 2)
        self.log("info", f"Reducing batch size from {batch_size} to {new_batch_size}")
        return await self.launch_instances(count, new_batch_size)

    async def _handle_rate_limit_error(self, error, count, batch_size):
        """Handle API rate limit errors"""
        self.log("warning", "API rate limit exceeded", error=str(error))

        # Wait and retry with reduced rate
        self.rate_limiter.max_rate = max(1, self.rate_limiter.max_rate // 2)
        self.log("info", f"Reduced API rate to {self.rate_limiter.max_rate} req/sec")
        await asyncio.sleep(self.retry_delay)
        return await self.launch_instances(count, batch_size)

    async def _handle_service_unavailable(self, error, count, batch_size):
        """Handle service unavailable errors"""
        self.log("warning", "Service unavailable", error=str(error))

        # Wait and retry
        await asyncio.sleep(self.retry_delay)
        return await self.launch_instances(count, batch_size)

    async def _handle_internal_error(self, error, count, batch_size):
        """Handle AWS internal errors"""
        self.log("warning", "AWS internal error", error=str(error))

        # Wait and retry
        await asyncio.sleep(self.retry_delay)
        return await self.launch_instances(count, batch_size)

    def _get_alternative_instance_type(self) -> Optional[str]:
        """Get alternative instance type with similar specs"""
        current_info = self.get_instance_type_info(self.instance_type)
        alternatives = [
            "t3.micro",
            "t3.small",
            "t3.medium",  # Burstable instances
            "m5.large",
            "m5.xlarge",  # General purpose
            "c5.large",
            "c5.xlarge",  # Compute optimized
        ]

        # Try to find similar instance type
        for alt_type in alternatives:
            if alt_type == self.instance_type:
                continue

            alt_info = self.get_instance_type_info(alt_type)
            if (
                alt_info["vcpus"] >= current_info["vcpus"]
                and alt_info["memory"] >= current_info["memory"]
            ):
                return alt_type

        return None

    def _cleanup_resources(self) -> None:
        """Cleanup all created resources"""
        self.log("info", "Starting resource cleanup")

        # Cleanup instances
        if self._created_resources["instances"]:
            try:
                self.ec2.terminate_instances(InstanceIds=list(self._created_resources["instances"]))
                self.log(
                    "info",
                    "Terminated instances",
                    instance_ids=list(self._created_resources["instances"]),
                )
            except Exception as e:
                self.log("error", "Error terminating instances", error=str(e))

        # Cleanup security groups
        if self._created_resources["security_groups"]:
            for group_id in self._created_resources["security_groups"]:
                try:
                    self.ec2.delete_security_group(GroupId=group_id)
                    self.log("info", "Deleted security group", group_id=group_id)
                except Exception as e:
                    self.log(
                        "error", "Error deleting security group", group_id=group_id, error=str(e)
                    )

        # Cleanup key pairs
        if self._created_resources["key_pairs"]:
            for key_name in self._created_resources["key_pairs"]:
                try:
                    self.ec2.delete_key_pair(KeyName=key_name)
                    self.log("info", "Deleted key pair", key_name=key_name)
                except Exception as e:
                    self.log("error", "Error deleting key pair", key_name=key_name, error=str(e))

        self._created_resources = {"instances": set(), "security_groups": set(), "key_pairs": set()}
        self.log("info", "Resource cleanup completed")

    async def _cleanup_all(self) -> None:
        """Cleanup all resources"""
        self.log("info", "Starting full cleanup")

        # Get all running instances
        instance_ids = await asyncio.get_event_loop().run_in_executor(
            None, self.get_all_instance_ids
        )

        # Cleanup instances
        if instance_ids:
            await self._cleanup_instances(instance_ids)

        # Cleanup other resources
        self._cleanup_resources()

        self.log("info", "Full cleanup completed")

    async def run_stress_test(
        self,
        min_nodes: int = 250,
        max_nodes: int = 750,
        iterations: int = 10,
        health_check_timeout: int = 300,
    ) -> None:
        """Run stress test with random node counts"""
        # Validate stress test parameters
        if min_nodes <= 0 or max_nodes <= 0:
            raise ValueError("Node counts must be greater than 0")

        if min_nodes > max_nodes:
            raise ValueError("min_nodes cannot be greater than max_nodes")

        if iterations <= 0:
            raise ValueError("Iterations must be greater than 0")

        if health_check_timeout <= 0:
            raise ValueError("Health check timeout must be greater than 0")

        # Check max nodes against instance limits
        if max_nodes > self.max_instances:
            raise ValueError(
                f"max_nodes ({max_nodes}) exceeds maximum instance limit ({self.max_instances})"
            )
        global progress, progress_task, layout, live

        # Initialize the status table with tighter column widths
        status_table = Table(
            show_header=True,
            header_style="bold magenta",
            title="Node Status",
            title_style="bold blue",
            expand=True,
        )
        status_table.add_column("ID", style="cyan", no_wrap=True, width=20)
        status_table.add_column("State", style="green", width=10)
        status_table.add_column("CPU", style="yellow", justify="right", width=6)
        status_table.add_column("Mem", style="yellow", justify="right", width=6)
        status_table.add_column("InstType", style="yellow", width=10)
        status_table.add_column("IP Address", style="blue", width=15)
        status_table.add_column("🐟", style="cyan", width=4)

        # Start progress tracking
        progress_task = progress.add_task("Waiting...", total=None)

        def update_layout_error(error_msg: str, details: str = ""):
            """Helper to update layout in error state"""
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            layout["header"].update(
                Panel(
                    f"[bold blue]Bacalhau Scale Test[/bold blue]\n"
                    f"[red]Error State[/red]\n"
                    f"Time: {current_time}",
                    style="white on red",
                )
            )
            layout["status"].update(
                Panel(
                    f"[red bold]Error:[/red bold] {error_msg}",
                    style="red",
                )
            )
            status_table.rows = []
            status_table.add_row("Error Type", "Failed", error_msg)
            if details:
                status_table.add_row("Details", "Info", details)
            status_table.add_row(
                "Recovery", "Action Required", "Please check AWS quotas and permissions"
            )
            layout["body"].update(status_table)

        def cleanup_instances():
            """Helper to cleanup instances on exit"""
            if "instance_ids" in locals():
                try:
                    progress.update(progress_task, description="Cleaning up instances...")
                    layout["progress"].update(progress)
                    status_table.add_row("Cleanup", "In Progress", "Terminating instances...")
                    layout["body"].update(status_table)
                    self.terminate_instances(instance_ids)
                    status_table.add_row(
                        "Cleanup", "[green]Complete[/green]", "All instances terminated"
                    )
                    layout["body"].update(status_table)
                except Exception as e:
                    status_table.add_row("Cleanup", "[red]Failed[/red]", f"Error: {str(e)}")
                    layout["body"].update(status_table)

        try:
            # Register cleanup handler for Ctrl+C
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self._cleanup_all()))

            # Verify Bacalhau access before starting
            try:
                progress.update(progress_task, description="Verifying Bacalhau access...")
                layout["progress"].update(progress)
                self.verify_bacalhau_access()
            except Exception as e:
                raise RuntimeError(f"Bacalhau verification failed: {str(e)}")

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            layout["header"].update(
                Panel(
                    f"[bold blue]Bacalhau Scale Test[/bold blue]\n"
                    f"Configuration: Nodes: {min_nodes}-{max_nodes} | Iterations: {iterations}\n"
                    f"Started: {current_time}",
                    style="white on #28464B",
                )
            )
            live.refresh()

            try:
                for iteration in range(iterations):
                    node_count = random.randint(min_nodes, max_nodes)
                    layout["status"].update(
                        Panel(
                            f"[bold]Iteration {iteration + 1}/{iterations}[/bold]\n"
                            f"Target Nodes: {node_count}\n"
                            f"Time: {datetime.now().strftime('%H:%M:%S')}",
                            style="yellow",
                        )
                    )

                    # Reset progress for new iteration
                    progress.update(progress_task, total=None, completed=0)
                    progress.update(
                        progress_task,
                        description=f"Launching {node_count} instances...",
                    )
                    layout["progress"].update(progress)
                    live.refresh()

                    try:
                        # Clear and initialize status table
                        status_table.rows = []
                        layout["body"].update(status_table)
                        live.refresh()

                        # Launch instances asynchronously
                        instance_ids = await self.launch_instances(node_count)

                        # Update progress for instance startup
                        progress.update(progress_task, total=len(instance_ids), completed=0)
                        progress.update(
                            progress_task,
                            description="Waiting for instances to start...",
                        )
                        layout["progress"].update(progress)
                        live.refresh()

                        # Wait for instances to start and join Bacalhau
                        running_count = 0
                        joined_count = 0
                        start_time = time.time()
                        node_states = {}  # Track node states and info

                        while running_count < len(instance_ids):
                            # Check if we've exceeded the timeout
                            if time.time() - start_time > 30:
                                raise RuntimeError(
                                    "Timeout waiting for nodes to start and join Bacalhau cluster"
                                )

                            # Get instance states from AWS
                            response = await asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda: self.ec2.describe_instances(InstanceIds=instance_ids),
                            )
                            running_count = 0
                            instance_rows = []

                            # Update instance states
                            for reservation in response["Reservations"]:
                                for instance in reservation["Instances"]:
                                    instance_id = instance["InstanceId"]
                                    state = instance["State"]["Name"]
                                    instance_type = instance["InstanceType"]
                                    specs = self.get_instance_type_info(instance_type)
                                    ip = instance.get("PublicIpAddress", "pending...")

                                    # Update node state tracking
                                    if instance_id not in node_states:
                                        node_states[instance_id] = {
                                            "state": state,
                                            "ip": ip,
                                            "specs": specs,
                                            "bacalhau_joined": False,
                                            "bacalhau_status": "❓",  # Default status
                                        }
                                    else:
                                        node_states[instance_id]["state"] = state
                                        if ip != "pending...":
                                            node_states[instance_id]["ip"] = ip

                                    if state == "running":
                                        running_count += 1

                            # Check Bacalhau status for running nodes
                            if running_count > 0:
                                running_ips = [
                                    state["ip"]
                                    for state in node_states.values()
                                    if state["state"] == "running" and state["ip"] != "pending..."
                                ]
                                node_results = await self.check_all_nodes_status(running_ips)

                                # Debug log Bacalhau API query
                                if self.debug:
                                    self.debug_log(
                                        f"Queried Bacalhau API. Nodes present: {len(node_results)}"
                                    )

                                # Update Bacalhau status
                                for instance_id, state in node_states.items():
                                    if state["ip"] in node_results:
                                        is_healthy, message = node_results[state["ip"]]
                                        if is_healthy:
                                            state["bacalhau_joined"] = True
                                            state["bacalhau_status"] = "✅"
                                        else:
                                            state["bacalhau_status"] = f"❌ ({message})"

                                # Build table rows with sort key
                                for instance_id, state in node_states.items():
                                    status = (
                                        "[green]running[/green]"
                                        if state["state"] == "running"
                                        else f"[yellow]{state['state']}[/yellow]"
                                    )

                                    # Sort key: pending first, then running not joined, then running and joined
                                    sort_key = (
                                        0
                                        if state["state"] != "running"
                                        else 1
                                        if not state["bacalhau_joined"]
                                        else 2
                                    )

                                    instance_rows.append(
                                        (
                                            sort_key,
                                            instance_id,
                                            status,
                                            f"{state['specs']['vcpus']}",
                                            state["specs"]["memory"],
                                            state["specs"]["type"],
                                            state["ip"],
                                            state["bacalhau_status"],  # Add Bacalhau status
                                        )
                                    )

                                # Sort and update table
                                instance_rows.sort(key=lambda x: x[0])
                                status_table.rows = []
                                for _, *row in instance_rows:
                                    status_table.add_row(*row)

                                # Update progress
                                joined_count = sum(
                                    1 for state in node_states.values() if state["bacalhau_joined"]
                                )
                                progress.update(
                                    progress_task,
                                    completed=joined_count,
                                    total=len(instance_ids),
                                    description=f"Running: {running_count}, Joined: {joined_count}/{len(instance_ids)}",
                                )

                                # Update layout
                                layout["body"].update(status_table)
                                layout["progress"].update(progress)
                                live.refresh()

                                # Check if all nodes are running and joined
                                if running_count == len(instance_ids):
                                    if joined_count == len(instance_ids):
                                        break
                                    # If all running but not all joined, wait a bit longer
                                    await asyncio.sleep(2)
                                else:
                                    await asyncio.sleep(5)

                            # Verify all nodes joined
                            if joined_count < len(instance_ids):
                                raise RuntimeError(
                                    f"Timeout waiting for nodes to join Bacalhau cluster. "
                                    f"Only {joined_count}/{len(instance_ids)} nodes joined."
                                )

                        # After all nodes are provisioned, continue to monitor Bacalhau status
                        while True:
                            # Check Bacalhau status for all running nodes
                            running_ips = [
                                state["ip"]
                                for state in node_states.values()
                                if state["state"] == "running" and state["ip"] != "pending..."
                            ]
                            node_results = await self.check_all_nodes_status(running_ips)

                            # Debug log Bacalhau API query
                            if self.debug:
                                self.debug_log(
                                    f"Queried Bacalhau API. Nodes present: {len(node_results)}"
                                )

                            # Update Bacalhau status
                            for instance_id, state in node_states.items():
                                if state["ip"] in node_results:
                                    is_healthy, message = node_results[state["ip"]]
                                    if is_healthy:
                                        state["bacalhau_joined"] = True
                                        state["bacalhau_status"] = "✅"
                                    else:
                                        state["bacalhau_status"] = f"❌ ({message})"

                            # Build table rows with sort key
                            instance_rows = []
                            for instance_id, state in node_states.items():
                                status = (
                                    "[green]running[/green]"
                                    if state["state"] == "running"
                                    else f"[yellow]{state['state']}[/yellow]"
                                )

                                # Sort key: pending first, then running not joined, then running and joined
                                sort_key = (
                                    0
                                    if state["state"] != "running"
                                    else 1
                                    if not state["bacalhau_joined"]
                                    else 2
                                )

                                instance_rows.append(
                                    (
                                        sort_key,
                                        instance_id,
                                        status,
                                        f"{state['specs']['vcpus']}",
                                        state["specs"]["memory"],
                                        state["specs"]["type"],
                                        state["ip"],
                                        state["bacalhau_status"],  # Add Bacalhau status
                                    )
                                )

                            # Sort and update table
                            instance_rows.sort(key=lambda x: x[0])
                            status_table.rows = []
                            for _, *row in instance_rows:
                                status_table.add_row(*row)

                            # Update progress
                            joined_count = sum(
                                1 for state in node_states.values() if state["bacalhau_joined"]
                            )
                            progress.update(
                                progress_task,
                                completed=joined_count,
                                total=len(instance_ids),
                                description=f"Running: {running_count}, Joined: {joined_count}/{len(instance_ids)}",
                            )

                            # Update layout
                            layout["body"].update(status_table)
                            layout["progress"].update(progress)
                            live.refresh()

                            # Check if all nodes are running and joined
                            if joined_count == len(instance_ids):
                                break

                            await asyncio.sleep(5)

                    except Exception as e:
                        error_msg = str(e)
                        if "MaxSpotInstanceCountExceeded" in error_msg:
                            details = (
                                "AWS Spot Instance quota exceeded.\n"
                                "Please request a quota increase in AWS Console:\n"
                                "EC2 > Limits > Spot Instance Requests"
                            )
                        else:
                            details = f"Error occurred during iteration {iteration + 1}"
                        update_layout_error(error_msg, details)
                        live.refresh()
                        break

                    finally:
                        cleanup_instances()
                        live.refresh()

                    if iteration < iterations - 1:
                        await asyncio.sleep(10)

            except KeyboardInterrupt:
                update_layout_error("Test interrupted by user", "Cleaning up resources...")
                live.refresh()
                cleanup_instances()
                live.refresh()

        except Exception as e:
            update_layout_error(str(e))
            live.refresh()

    def create_instance_table(self, instances: List[Dict[str, Any]]) -> Table:
        """Create and populate a table with detailed instance status information
        including lifecycle events."""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            border_style="blue",
            title="Instance Status",
            title_style="bold blue",
            caption="Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            caption_style="dim",
        )

        # Add columns with adjusted widths
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Type", style="green", width=10)
        table.add_column("State", style="yellow", width=8)
        table.add_column("Zone", style="blue", width=12)
        table.add_column("DNS", style="white", width=50)  # Wide enough for full DNS
        table.add_column("Age", style="green", width=8)

        for instance in instances:
            # Get basic instance info
            instance_id = instance.get("InstanceId", "N/A")
            instance_type = instance.get("InstanceType", "N/A")
            state = instance.get("State", {}).get("Name", "N/A")
            zone = instance.get("Placement", {}).get("AvailabilityZone", "N/A")
            public_dns = instance.get("PublicDnsName", "N/A")

            # Calculate instance age
            launch_time = instance.get("LaunchTime")
            age = "N/A"
            if launch_time:
                age_delta = datetime.now(launch_time.tzinfo) - launch_time
                hours = age_delta.total_seconds() / 3600
                if hours < 24:
                    age = f"{hours:.1f}h"
                else:
                    age = f"{hours / 24:.1f}d"

            table.add_row(
                instance_id,
                instance_type,
                state,
                zone,
                public_dns,
                age,
            )

        return table

    def terminate_all(self, ctx: Context) -> None:
        """Terminate all running instances"""
        if ctx is None:
            raise ValueError("Context cannot be None")

        global progress, progress_task, layout, live

        # Get instance IDs first
        instance_ids = self.get_all_instance_ids()
        if not instance_ids:
            layout["header"].update(Panel("[bold blue]Bacalhau Spot Manager[/bold blue]"))
            layout["body"].update(Panel("[yellow]No instances found[/yellow]"))
            layout["status"].update(Panel("[yellow]No instances to terminate[/yellow]"))
            layout["progress"].update(progress)
            return

        try:
            # Create main termination task
            progress_task = progress.add_task("Terminating instances...", total=len(instance_ids))
            layout["progress"].update(progress)

            # Update header
            layout["header"].update(
                Panel(
                    "[bold blue]Bacalhau Spot Manager[/bold blue]\n"
                    f"[dim]Terminating {len(instance_ids)} instances[/dim]",
                    style="white on #28464B",
                )
            )

            # Get instance details
            response = self.ec2.describe_instances(InstanceIds=instance_ids)
            instances = [
                instance
                for reservation in response["Reservations"]
                for instance in reservation["Instances"]
            ]

            # Create and display initial table
            table = self.create_instance_table(instances)
            layout["body"].update(Panel(table, border_style="blue"))
            layout["status"].update(
                Panel(
                    f"[yellow]Terminating {len(instances)} instances...[/yellow]",
                    border_style="yellow",
                )
            )

            # Run the async termination in an event loop
            asyncio.run(self.terminate_instances(instance_ids))

            # Final update
            layout["status"].update(
                Panel(
                    "[green]✓ All instances terminated successfully[/green]",
                    border_style="green",
                )
            )
            layout["body"].update(
                Panel(
                    "[green]All instances have been terminated[/green]",
                    border_style="green",
                )
            )

        except Exception as e:
            error_msg = f"Error during termination process: {str(e)}"
            write_debug(error_msg)
            layout["status"].update(Panel(f"[red]{error_msg}[/red]", border_style="red"))
            layout["body"].update(
                Panel("[red]Termination process failed[/red]", border_style="red")
            )
            raise

    def get_running_instances(self):
        """Get list of running instances"""
        response = self.ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running", "pending"]}]
        )

        instances = []
        for reservation in response["Reservations"]:
            instances.extend(reservation["Instances"])
        return instances


@click.group()
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable debug logging (must be specified before command)",
)
@click.pass_context
def cli(ctx: Context, debug: bool) -> None:
    """Manage AWS spot instances for Bacalhau scale testing

    Example usage:
        ./spot-manager --debug launch --count 5
        ./spot-manager --debug stress-test
        ./spot-manager --debug list
    """
    global live
    if ctx is None:
        raise ValueError("Context cannot be None")

    ctx.obj = SpotManager(debug=debug)
    # Start the live display before running commands
    live.start()


@cli.result_callback()
def cleanup(ctx: Context, debug: bool) -> None:
    """Cleanup after all commands are done"""
    global live, progress, progress_task, layout

    try:
        # Clear any progress display
        if progress_task is not None:
            try:
                progress.update(progress_task, visible=False)
                layout["progress"].update(progress)
            except Exception as e:
                write_debug(f"Error clearing progress: {str(e)}")

        # Clear the layout
        try:
            layout["header"].update("")
            layout["body"].update("")
            layout["status"].update("")
            layout["progress"].update("")
        except Exception as e:
            write_debug(f"Error clearing layout: {str(e)}")

        # Stop the live display first
        if live and live.is_started:
            try:
                live.stop()
            except Exception as e:
                write_debug(f"Error stopping live display: {str(e)}")

        # Then handle any remaining cleanup tasks
        if ctx is not None and hasattr(ctx, "obj") and ctx.obj is not None:
            manager = ctx.obj
            if manager._cleanup_tasks:
                try:
                    asyncio.run(asyncio.wait(manager._cleanup_tasks))
                except Exception as e:
                    write_debug(f"Error during task cleanup: {str(e)}")

    except Exception as e:
        write_debug(f"Error during cleanup: {str(e)}")


@cli.command()
@click.option("--count", default=1, help="Number of instances to launch")
@click.pass_obj
def launch(manager: SpotManager, count: int):
    """Launch spot instances"""
    global progress, progress_task, layout, live

    # Update header with consistent styling
    layout["header"].update(
        Panel(
            f"[bold blue]Bacalhau Spot Manager[/bold blue]\n[dim]Launching {count} instances[/dim]",
            style="white on #28464B",
            border_style="blue",
        )
    )

    progress_task = progress.add_task("Launching instances...", total=count)
    layout["progress"].update(progress)
    live.refresh()

    try:
        instance_ids = asyncio.run(manager.launch_instances(count))
        manager.wait_for_instances_running(instance_ids)

        # Fetch instance details
        response = manager.ec2.describe_instances(InstanceIds=instance_ids)
        instances = [
            instance
            for reservation in response["Reservations"]
            for instance in reservation["Instances"]
        ]

        # Create and display the table with consistent styling
        table = manager.create_instance_table(instances)
        layout["body"].update(Panel(table, border_style="blue"))
        layout["status"].update(
            Panel(
                f"[green]✓ Successfully launched {len(instance_ids)} instances[/green]",
                border_style="green",
            )
        )
        layout["progress"].update(progress)

        # Show the layout
        live.refresh()
        time.sleep(2)  # Give user time to see the final state

    except Exception as e:
        layout["status"].update(
            Panel(
                f"[red]✗ Error launching instances: {str(e)}[/red]",
                border_style="red",
            )
        )
        live.refresh()
        raise


@cli.command("list")
@click.option("--tag", multiple=True, help="Filter instances by tag (format: key=value)")
@click.pass_obj
def list_instances(manager: SpotManager, tag):
    """List running instances with optional tag filtering"""
    global progress, progress_task, layout, live

    try:
        # Parse tag filters
        filters = []
        if tag:
            for t in tag:
                if "=" in t:
                    key, value = t.split("=", 1)
                    filters.append({"Name": f"tag:{key}", "Values": [value]})
                else:
                    write_debug(f"Ignoring malformed tag filter: {t}")
                    console.print(
                        f"[yellow]Warning: Ignoring malformed tag filter '{t}' (expected key=value)[/yellow]"
                    )

        response = manager.ec2.describe_instances(Filters=filters)
        instances = [
            instance
            for reservation in response["Reservations"]
            for instance in reservation["Instances"]
        ]

        # Check if no instances were found - print simple message and return early
        if not instances:
            console.print("[yellow]No instances found[/yellow]")
            return

        # Create and update the table for instances that exist
        progress_task = progress.add_task(
            description="Listing instances...", total=None, visible=True
        )
        layout["progress"].update(progress)

        try:
            # Create and update the table
            table = manager.create_instance_table(instances)
            layout["body"].update(Panel(table, border_style="blue"))
            layout["status"].update(
                Panel(f"Found {len(instances)} running instances", style="green")
            )
            safe_progress_update(progress_task, description="Complete", visible=False)
            layout["progress"].update(progress)

        except Exception as e:
            write_debug(f"Error in table creation/display: {str(e)}")
            layout["body"].update(Panel("[red]Error creating table[/red]", border_style="red"))
            layout["status"].update(
                Panel("[red]Error displaying instance information[/red]", border_style="red")
            )

    except Exception as e:
        # Ensure we catch and properly display any errors
        error_msg = f"Error listing instances: {str(e)}"
        write_debug(error_msg)
        console.print(f"[red]{error_msg}[/red]")
        raise


@cli.command()
@click.argument("instance-id")
@click.pass_obj
def terminate(manager: SpotManager, instance_id: str):
    """Terminate a specific instance"""
    global progress, progress_task, layout, live
    progress_task = progress.add_task("Terminating instance...", total=1)
    layout["progress"].update(progress)

    # Run the async termination in an event loop
    asyncio.run(manager.terminate_instances([instance_id]))

    # Fetch instance details
    response = manager.ec2.describe_instances(InstanceIds=[instance_id])
    instances = [
        instance
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
    ]

    # Create and display the table
    table = manager.create_instance_table(instances)
    layout["body"].update(table)
    layout["status"].update(Panel(f"[green]Successfully terminated instance {instance_id}[/green]"))
    layout["progress"].update(progress)

    # Show the layout
    live.refresh()
    time.sleep(2)  # Give user time to see the final state


@cli.command()
@click.pass_obj
def terminate_all(manager: SpotManager):
    """Terminate all running instances"""
    global progress, progress_task, layout, live

    progress_task = progress.add_task("Finding instances...", total=None)
    layout["progress"].update(progress)
    live.refresh()

    try:
        instance_ids = manager.get_all_instance_ids()
        if not instance_ids:
            layout["header"].update(
                Panel("[bold blue]Bacalhau Spot Manager[/bold blue]", border_style="blue")
            )
            layout["body"].update(
                Panel("[yellow]No instances found[/yellow]", border_style="yellow")
            )
            layout["status"].update(
                Panel("[yellow]No instances to terminate[/yellow]", border_style="yellow")
            )
            layout["progress"].update(progress)
            live.refresh()
            return

        # Get initial instance details for comparison
        initial_response = manager.ec2.describe_instances(InstanceIds=instance_ids)
        initial_instances = [
            instance
            for reservation in initial_response["Reservations"]
            for instance in reservation["Instances"]
        ]

        # Show current instances
        table = manager.create_instance_table(initial_instances)
        layout["header"].update(
            Panel("[bold blue]Bacalhau Spot Manager[/bold blue]", border_style="blue")
        )
        layout["body"].update(Panel(table, border_style="blue"))
        layout["status"].update(
            Panel(
                f"[yellow]Terminating {len(initial_instances)} instances...[/yellow]",
                border_style="yellow",
            )
        )
        layout["progress"].update(progress)
        live.refresh()

        # Run the async termination in an event loop
        asyncio.run(manager.terminate_instances(instance_ids))

        # Create summary table
        summary_table = Table(
            show_header=True,
            header_style="bold magenta",
            title="Termination Summary",
            title_style="bold blue",
            box=ROUNDED,
        )
        summary_table.add_column("Instance ID", style="cyan")
        summary_table.add_column("Type", style="green")
        summary_table.add_column("Zone", style="blue")
        summary_table.add_column("Launch Time", style="yellow")
        summary_table.add_column("IP Address", style="white")
        summary_table.add_column("State", style="red")

        # Add rows for each terminated instance
        for instance in initial_instances:
            summary_table.add_row(
                instance.get("InstanceId", "N/A"),
                instance.get("InstanceType", "N/A"),
                instance.get("Placement", {}).get("AvailabilityZone", "N/A"),
                instance.get("LaunchTime", "N/A").strftime("%Y-%m-%d %H:%M:%S")
                if instance.get("LaunchTime")
                else "N/A",
                instance.get("PublicIpAddress", "N/A"),
                "[red]Terminated[/red]",
            )

        # Update layout with summary
        layout["header"].update(
            Panel(
                "[bold blue]Termination Complete[/bold blue]\n"
                f"[green]Successfully terminated {len(initial_instances)} instances[/green]",
                border_style="blue",
            )
        )
        layout["body"].update(Panel(summary_table, border_style="blue"))
        layout["status"].update(
            Panel(
                "[green]✓ All instances have been terminated[/green]\n"
                f"Total instances terminated: {len(initial_instances)}",
                border_style="green",
            )
        )
        layout["progress"].update(progress)
        live.refresh()
        time.sleep(3)  # Give user time to see the summary

    except Exception as e:
        error_msg = f"Error during termination: {str(e)}"
        write_debug(error_msg)
        layout["status"].update(Panel(f"[red]{error_msg}[/red]", border_style="red"))
        layout["body"].update(Panel("[red]Termination process failed[/red]", border_style="red"))
        live.refresh()
        raise


@cli.command()
@click.option("--min-nodes", default=250, help="Minimum number of nodes per iteration")
@click.option("--max-nodes", default=750, help="Maximum number of nodes per iteration")
@click.option("--iterations", default=10, help="Number of test iterations")
@click.option("--health-timeout", default=300, help="Timeout in seconds for health checks")
@click.pass_obj
def stress_test(
    manager: SpotManager,
    min_nodes: int,
    max_nodes: int,
    iterations: int,
    health_timeout: int,
):
    """Run stress test with random node counts

    Example usage:
        ./spot-manager --debug stress-test --min-nodes 5 --max-nodes 10
    """
    asyncio.run(
        manager.run_stress_test(
            min_nodes=min_nodes,
            max_nodes=max_nodes,
            iterations=iterations,
            health_check_timeout=health_timeout,
        )
    )


if __name__ == "__main__":
    cli(obj={})
