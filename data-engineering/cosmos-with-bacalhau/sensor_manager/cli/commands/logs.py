"""
Logs command implementation.

This module implements the 'logs' command for the Sensor Manager CLI,
which displays logs from Docker containers.
"""

import os
import subprocess
from pathlib import Path

from sensor_manager.utils import logging as log
from sensor_manager.docker.compose import DockerComposeRunner


def get_project_name():
    """
    Get the current project name from the .current-project-name file if it exists.
    
    Returns:
        str: Project name or empty string if file doesn't exist
    """
    project_file = Path('.current-project-name')
    if project_file.exists():
        return project_file.read_text().strip()
    return ""


def logs_command(args):
    """
    Implementation of the 'logs' command.
    
    Args:
        args: Command-line arguments containing service names to show logs for
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    log.header("Viewing container logs")
    
    # Check if we have current project name saved
    project_name = get_project_name()
    if project_name:
        log.info(f"Viewing logs for project: {project_name}")
        compose_runner = DockerComposeRunner('docker-compose.yml', project_name=project_name)
    else:
        log.info("No project name found, using default docker-compose")
        compose_runner = DockerComposeRunner('docker-compose.yml')
    
    log.info("Press Ctrl+C to exit")
    log.separator()
    
    # Get services from args
    services = []
    if hasattr(args, 'services') and args.services:
        services = args.services
    
    # Handle follow flag
    follow = not hasattr(args, 'no_follow') or not args.no_follow
    
    try:
        # Build the docker compose logs command with services
        cmd = ["docker", "compose"]
        
        # Add project name if available
        if project_name:
            cmd.extend(["-p", project_name])
        
        # Add logs command
        cmd.append("logs")
        
        # Add follow flag if needed
        if follow:
            cmd.append("-f")
        
        # Add any specified services
        if services:
            cmd.extend(services)
        
        # Run the command (this will block until exit with Ctrl+C)
        subprocess.run(cmd, check=True)
        
        return 0
    except subprocess.CalledProcessError as e:
        log.error(f"Error viewing logs: {e}")
        return 1
    except KeyboardInterrupt:
        log.info("\nLog viewing terminated")
        return 0