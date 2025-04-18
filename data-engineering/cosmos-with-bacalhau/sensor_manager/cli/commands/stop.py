"""
Stop command implementation.

This module implements the 'stop' command for the Sensor Manager CLI,
which stops all running containers.
"""

import os
from pathlib import Path

from sensor_manager.docker.compose import DockerComposeRunner
from sensor_manager.utils import logging as log


def get_project_name():
    """
    Get the project name from the .current-project-name file.
    
    Returns:
        Project name or None if not found
    """
    project_file = Path('.current-project-name')
    if project_file.exists():
        return project_file.read_text().strip()
    return None


def stop_command(args):
    """
    Implementation of the 'stop' command.
    
    Args:
        args: Command-line arguments
    """
    log.header("Stopping all containers")
    
    # Check if docker-compose.yml exists
    if not os.path.exists('docker-compose.yml'):
        log.error("docker-compose.yml not found. Nothing to stop.")
        return 1
    
    # Get project name if available
    project_name = get_project_name()
    
    if project_name:
        log.info(f"Using saved project name: {project_name}")
    else:
        log.warning("No project name found, using default docker-compose")
    
    # Stop all containers
    compose_runner = DockerComposeRunner('docker-compose.yml', project_name)
    
    try:
        if compose_runner.down():
            log.success("All containers stopped")
        else:
            log.error("Failed to stop containers")
            return 1
    except Exception as e:
        log.error(f"Error stopping containers: {e}")
        return 1
    
    # Ask if user wants to delete the project file, unless --no-prompt is used
    if not args.no_prompt:
        try:
            response = input("Remove project reference? (y/n): ").strip().lower()
            if response == 'y':
                try:
                    os.remove('.current-project-name')
                    log.info("Project reference removed")
                except Exception as e:
                    log.warning(f"Failed to remove project reference: {e}")
        except (KeyboardInterrupt, EOFError):
            log.info("\nKeeping project reference")
    
    return 0