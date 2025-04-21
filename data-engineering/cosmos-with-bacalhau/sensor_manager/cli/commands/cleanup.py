"""
Cleanup command implementation.

This module implements the 'cleanup' command for the Sensor Manager CLI,
which forcibly removes all sensor and uploader containers.
"""

import os
from pathlib import Path

from sensor_manager.docker.manager import DockerManager
from sensor_manager.utils import logging as log


def cleanup_command(args):
    """
    Implementation of the 'cleanup' command.
    
    Args:
        args: Command-line arguments
    """
    log.header("Force removing all sensor and uploader containers")
    
    # Create Docker manager
    docker_manager = DockerManager()
    
    # Define name patterns to match
    name_filters = ["sensor", "uploader"]
    
    # Remove containers matching the patterns
    removed_count = docker_manager.cleanup_containers(name_filters)
    
    if removed_count > 0:
        log.success(f"Removed {removed_count} containers")
    else:
        log.info("No containers found to remove")
    
    # Remove any old project references
    for file_path in ['.current-project-name', '.swarm-mode']:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                log.info(f"Removed {file_path}")
        except Exception as e:
            log.warning(f"Failed to remove {file_path}: {e}")
    
    log.success("Cleanup complete!")
    log.info("You can now run 'python -m sensor_manager start' to start fresh containers")
    
    return 0