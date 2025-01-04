import json
import os
import platform
import socket
from datetime import datetime

import psutil
import yaml


def bytes_to_human(bytes_value):
    """Convert bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def get_system_info():
    info = {
        "timestamp": datetime.now().isoformat(),
        # Basic System Info
        "hostname": socket.gethostname(),
        "container": {
            "python_version": platform.python_version(),
            "base_image": "cgr.dev/chainguard/python:latest",
        },
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
        },
        # CPU Info
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "total_cores": psutil.cpu_count(logical=True),
        },
        # Memory Info
        "memory": {
            "total": bytes_to_human(psutil.virtual_memory().total),
            "used": bytes_to_human(psutil.virtual_memory().used),
            "percentage": psutil.virtual_memory().percent,
        },
        # Disk Info
        "disk": {
            "total": bytes_to_human(psutil.disk_usage("/").total),
            "used": bytes_to_human(psutil.disk_usage("/").used),
            "percentage": psutil.disk_usage("/").percent,
        },
        # Network Info
        "network": {
            "ip_addresses": [
                addr.address
                for interface in psutil.net_if_addrs().values()
                for addr in interface
                if addr.family == socket.AF_INET
            ],
        },
        # Current Working Directory and Contents
        "cwd": os.getcwd(),
    }
    return info


def main():
    try:
        # Print welcome message
        with open("hello-world-message.txt", "r") as f:
            print(f.read())

        system_info = get_system_info()
        # Print formatted YAML output
        print(yaml.dump(system_info, default_flow_style=False, sort_keys=False))

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
