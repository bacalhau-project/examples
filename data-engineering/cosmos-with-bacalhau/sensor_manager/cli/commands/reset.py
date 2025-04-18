"""
Reset command implementation.

This module implements the 'reset' command for the Sensor Manager CLI,
which resets services with fixed configuration.
"""

import os
import subprocess
import time
from pathlib import Path

from sensor_manager.cli.commands.stop import stop_command
from sensor_manager.cli.commands.build import build_command, backup_entrypoint
from sensor_manager.cli.commands.compose import compose_command
from sensor_manager.docker.compose import DockerComposeRunner
from sensor_manager.utils import logging as log


def regenerate_compose_file(args):
    """
    Regenerate the Docker Compose file using the compose command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        bool: True if successful, False otherwise
    """
    log.step("Regenerating Docker Compose file...")
    
    # Create a new set of arguments for the compose command
    compose_args = type('ComposeArgs', (), {
        'output': 'docker-compose.yml',
        'config': args.config if hasattr(args, 'config') else 'config/config.yaml',
        'sensors_per_city': args.sensors_per_city if hasattr(args, 'sensors_per_city') else 5,
        'readings_per_second': args.readings_per_second if hasattr(args, 'readings_per_second') else 1,
        'anomaly_probability': args.anomaly_probability if hasattr(args, 'anomaly_probability') else 0.05,
        'upload_interval': args.upload_interval if hasattr(args, 'upload_interval') else 30,
        'archive_format': args.archive_format if hasattr(args, 'archive_format') else 'Parquet',
        'sensor_config': args.sensor_config if hasattr(args, 'sensor_config') else 'config/sensor-config.yaml',
        'compose_config': args.compose_config if hasattr(args, 'compose_config') else 'config.yaml'
    })
    
    # Call the compose command
    result = compose_command(compose_args)
    return result == 0


def reset_command(args):
    """
    Implementation of the 'reset' command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    log.header("Resetting services with configuration")
    
    # Step 1: Stop all services
    log.step("Stopping all services...")
    stop_args = type('StopArgs', (), {
        'no_prompt': True
    })
    stop_result = stop_command(stop_args)
    
    if stop_result != 0:
        log.warning("Some issues occurred while stopping services. Continuing anyway...")
    
    # Step 2: Ensure entrypoint has a backup
    log.step("Ensuring entrypoint.sh has a backup...")
    if not backup_entrypoint():
        log.warning("Could not create entrypoint backup. Continuing anyway...")
    
    # Step 3: Rebuild the image
    log.step("Rebuilding the Docker image...")
    build_args = type('BuildArgs', (), {
        'no_tag': True
    })
    build_result = build_command(build_args)
    
    if build_result != 0:
        log.error("Failed to build the Docker image.")
        return 1
    
    # Step 4: Check if the sensor config file exists
    sensor_config_file = args.sensor_config if hasattr(args, 'sensor_config') else "config/sensor-config.yaml"
    if not Path(sensor_config_file).exists():
        log.warning(f"Sensor configuration file not found at {sensor_config_file}")
        log.warning("Using default configuration instead.")
    else:
        log.success(f"Using sensor configuration from {sensor_config_file}")
        # Set environment variable for use in other scripts
        os.environ["SENSOR_CONFIG_FILE"] = sensor_config_file
    
    # Step 5: Regenerate Docker Compose file
    log.step("Recreating Docker Compose file...")
    if not regenerate_compose_file(args):
        log.error("Failed to generate Docker Compose file.")
        return 1
    
    log.warning("Using TEST configuration with multiple regions - not for production use")
    
    # Step 6: Start all services
    log.step("Starting all services with configuration...")
    compose_runner = DockerComposeRunner('docker-compose.yml')
    if not compose_runner.up(detach=True):
        log.error("Failed to start services.")
        return 1
    
    log.success("Services reset complete.")
    log.info("Check their status with: docker compose ps")
    
    # Step 7: Run diagnostics if requested
    if not (hasattr(args, 'no_diagnostics') and args.no_diagnostics):
        log.step("Running diagnostics...")
        time.sleep(10)  # Give containers a bit more time to initialize
        
        # Import here to avoid circular imports
        try:
            from sensor_manager.cli.commands.diagnostics import diagnostics_command
            diagnostics_command(args)
        except ImportError:
            log.warning("Diagnostics command not available. Skipping diagnostics.")
            log.info("You can run diagnostics manually with: sensor_manager.py diagnostics")
    
    return 0