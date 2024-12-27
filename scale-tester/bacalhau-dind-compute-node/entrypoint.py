#!/usr/bin/env python3

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="\033[0;34m[%(levelname)s]\033[0m %(message)s"
)
logger = logging.getLogger(__name__)


def read_cgroup_value(path: str, default: str = "unlimited") -> str:
    """Read a value from a cgroup file, returning default if not available."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except (IOError, OSError):
        return default


def read_bacalhau_config(config_path: str) -> Dict:
    """Read and parse the Bacalhau config file."""
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"No config file found at {config_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config file: {e}")
        sys.exit(1)


def read_node_info() -> Dict[str, str]:
    """Read additional labels from /etc/node-info if present."""
    node_info = {}
    try:
        with open("/etc/node-info", "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key and value:
                        node_info[key.strip()] = value.strip()
    except FileNotFoundError:
        logger.info("No /etc/node-info found, proceeding without node info labels.")
    return node_info


def gather_labels(config: Dict) -> List[str]:
    """Gather all labels from various sources."""
    labels = []

    # Get values from Bacalhau config
    if compute := config.get("Compute"):
        # Handle AllowListedLocalPaths
        if paths := compute.get("AllowListedLocalPaths"):
            for path in paths:
                labels.append(f"Compute.AllowListedLocalPaths={path}")

        # Handle Orchestrators
        if orchestrators := compute.get("Orchestrators"):
            for orchestrator in orchestrators:
                labels.append(f"Compute.Orchestrators={orchestrator}")

        # Handle Engine Resources
        if engine := compute.get("Engine"):
            if resources := engine.get("Resources"):
                if cpu := resources.get("CPU"):
                    labels.append(f"Compute.Engine.Resources.CPU={cpu}")
                if memory := resources.get("Memory"):
                    labels.append(f"Compute.Engine.Resources.Memory={memory}")

    # Handle JobAdmissionControl
    if job_control := config.get("JobAdmissionControl"):
        if networked := job_control.get("AcceptNetworkedJobs"):
            labels.append(
                f"JobAdmissionControl.AcceptNetworkedJobs={str(networked).lower()}"
            )

    # Add system resource information
    resource_info = {
        "memory_limit": read_cgroup_value(
            "/sys/fs/cgroup/memory/memory.limit_in_bytes"
        ),
        "cpu_quota": read_cgroup_value("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
        "cpu_period": read_cgroup_value("/sys/fs/cgroup/cpu/cpu.cfs_period_us"),
        "hostname": os.uname().nodename,
    }
    labels.extend([f"{k}={v}" for k, v in resource_info.items()])

    # Add node info labels
    node_info = read_node_info()
    labels.extend([f"{k}={v}" for k, v in node_info.items()])

    return labels


def main():
    # Get config file path from environment or use default
    config_path = os.getenv("BACALHAU_CONFIG_PATH", "/etc/bacalhau/config.yaml")

    # Read Bacalhau config
    config = read_bacalhau_config(config_path)

    # Gather all labels
    labels = gather_labels(config)
    labels_string = ",".join(labels)

    logger.info(f"Launching Bacalhau with labels: {labels_string}")

    # Construct and execute the bacalhau serve command
    cmd = [
        "bacalhau",
        "serve",
        "--config",
        config_path,
        "-c",
        "Logging.Level=info",
        "-c",
        f"Labels={labels_string}",
    ]

    try:
        # Execute bacalhau serve with the gathered configuration
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start Bacalhau server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
