"""
Start command implementation.

This module implements the 'start' command for the Sensor Manager CLI,
which starts the sensor simulation with configuration.
"""

import glob
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from sensor_manager.cli.commands.compose import compose_command
from sensor_manager.docker.compose import DockerComposeRunner
from sensor_manager.docker.manager import DockerManager
from sensor_manager.utils import logging as log


def delete_sqlite_databases():
    """Delete all SQLite databases and their parent directories in the data directory."""
    log.step("Deleting existing SQLite databases and directories...")
    data_dir = Path("./data")
    if data_dir.exists():
        # Find all .db files in the data directory and its subdirectories
        db_files = glob.glob(str(data_dir / "**" / "*.db"), recursive=True)
        # Get unique parent directories
        parent_dirs = {Path(db_file).parent for db_file in db_files}

        # Delete each parent directory
        for dir_path in parent_dirs:
            try:
                shutil.rmtree(dir_path)
                log.info(f"Deleted directory: {dir_path}")
            except Exception as e:
                log.warning(f"Failed to delete directory {dir_path}: {e}")

        log.success(
            f"Deleted {len(parent_dirs)} directories containing SQLite databases"
        )
    else:
        log.info("Data directory does not exist, nothing to delete")

    # Delete the entire archive directory structure
    archive_dir = Path("./archive")
    if archive_dir.exists():
        try:
            shutil.rmtree(archive_dir)
            log.success("Deleted entire archive directory structure")
        except Exception as e:
            log.warning(f"Failed to delete archive directory: {e}")


def create_data_directories():
    """Create data and archive directories."""
    # Create base data and archive directories
    os.makedirs("./data", exist_ok=True)
    os.makedirs("./archive", exist_ok=True)
    log.success("Data directories prepared for deployment")


def check_docker_running():
    """
    Check if Docker is running.

    Returns:
        True if Docker is running, False otherwise
    """
    docker_manager = DockerManager()
    if not docker_manager.is_docker_running():
        log.error("Docker is not running. Please start Docker and try again.")
        return False
    return True


def check_cosmos_credentials():
    """
    Check if Cosmos DB credentials are set.

    Returns:
        True if credentials are set, False otherwise
    """
    if not os.environ.get("COSMOS_ENDPOINT") or not os.environ.get("COSMOS_KEY"):
        log.error("COSMOS_ENDPOINT and COSMOS_KEY environment variables must be set.")
        log.error(
            "You can create a .env file with these variables or set them manually."
        )
        return False
    return True


def load_env_file():
    """
    Load environment variables from .env file if it exists.

    Returns:
        True if .env file was loaded, False otherwise
    """
    if os.path.exists(".env"):
        log.info("Loading configuration from .env file...")
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")
            return True
        except Exception as e:
            log.error(f"Error loading .env file: {e}")
    else:
        log.warning(
            "No .env file found. Using default values and environment variables."
        )

    return False


def build_uploader_image(args):
    """
    Build the uploader image.

    Args:
        args: Command-line arguments

    Returns:
        True if successful, False otherwise
    """
    log.step("Building Cosmos Uploader image...")

    try:
        # Use the new build command module directly rather than subprocess
        from sensor_manager.cli.commands.build import build_command

        # Call the build command with the same arguments
        result = build_command(args)

        if result == 0:
            return True
        else:
            log.error("Failed to build uploader image")
            return False
    except Exception as e:
        log.error(f"Error building uploader image: {e}")
        return False


def verify_config_file(config_file):
    """
    Verify that the configuration file exists.

    Args:
        config_file: Path to the configuration file

    Returns:
        True if the file exists, False otherwise
    """
    config_path = Path(config_file)
    if not config_path.exists():
        log.warning(f"Config file {config_file} does not exist!")
        return False

    log.success(f"Config file found at {config_file}")
    return True


def start_command(args):
    """
    Implementation of the 'start' command.

    Args:
        args: Command-line arguments
    """
    log.header("Starting sensor simulation")

    # Step 1: Delete existing SQLite databases
    delete_sqlite_databases()

    # Step 2: Clean up existing container state first
    log.step("Cleaning up existing containers...")
    try:
        from sensor_manager.cli.commands.cleanup import cleanup_command

        # Create minimal args object with just what cleanup needs
        cleanup_args = type("CleanupArgs", (), {})
        cleanup_command(cleanup_args)
    except Exception as e:
        log.warning(f"Error cleaning up containers: {e}")
        log.warning("Continuing with startup...")

    # Step 3: Stop any remaining containers with docker-compose if needed
    log.step("Stopping any remaining compose services...")
    try:
        from sensor_manager.cli.commands.stop import stop_command

        stop_args = type("StopArgs", (), {"no_prompt": True})
        stop_command(stop_args)
    except Exception as e:
        log.warning(f"Error stopping existing containers: {e}")
        log.warning("Continuing with startup...")

    # Step 4: Load environment variables
    load_env_file()

    # Step 5: Check Cosmos credentials
    if not check_cosmos_credentials():
        return 1

    # Step 6: Check if Docker is running
    if not check_docker_running():
        return 1

    # Step 7: Build the uploader image if needed
    if not args.no_rebuild:
        # Generate a timestamp-based tag if not provided
        if not hasattr(args, "uploader_tag") or not args.uploader_tag:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            args.uploader_tag = f"v{timestamp}"
            log.info(f"Generated uploader tag: {args.uploader_tag}")

        if not build_uploader_image(args):
            return 1
    else:
        log.info("Skipping rebuild as requested")

    # Step 8: Generate Docker Compose file
    log.step("Generating Docker Compose file...")

    # Use the tag from the build step - this should always exist after build_uploader_image
    if not hasattr(args, "uploader_tag") or not args.uploader_tag:
        log.error("No uploader tag found after build step. This should not happen.")
        return 1

    uploader_tag = args.uploader_tag

    # Safety check - never allow "latest" tag
    if uploader_tag == "latest":
        log.error("DANGER: 'latest' tag was specified but is not allowed!")
        return 1

    # Output registry information
    registry_image = f"ghcr.io/bacalhau-project/cosmos-uploader:{uploader_tag}"
    log.info(f"Using image: {registry_image}")

    # Use the compose_command with the arguments from start
    compose_args = type(
        "ComposeArgs",
        (),
        {
            "output": "docker-compose.yml",
            "config": args.config,
            "sensors_per_city": args.sensors_per_city,
            "readings_per_second": args.readings_per_second,
            "anomaly_probability": args.anomaly_probability,
            "upload_interval": args.upload_interval,
            "archive_format": args.archive_format,
            "sensor_config": args.sensor_config,
            "compose_config": args.compose_config,
            "uploader_tag": uploader_tag,
        },
    )

    if compose_command(compose_args) != 0:
        return 1

    # Step 9: Clean up existing data directories
    log.step("Setting up data directories...")
    create_data_directories()

    # Step 10: Verify Docker Compose configuration
    log.step("Verifying Docker Compose configuration...")
    config_file = f"config/{args.compose_config}"

    if not verify_config_file(config_file):
        # Just warn and continue
        log.warning("This may cause containers to fail on startup.")
        log.warning("Continuing anyway...")

    # Step 11: Generate project name if not provided
    if not args.project_name:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        project_name = f"cosmos-sensors-{timestamp}"
    else:
        project_name = args.project_name

    # Save project name for later use
    with open(".current-project-name", "w") as f:
        f.write(project_name)

    log.info(f"Using project name: {project_name}")

    # Step 12: Start the containers
    log.step("Starting containers...")
    compose_runner = DockerComposeRunner("docker-compose.yml", project_name)

    if not compose_runner.up(detach=True):
        return 1

    # Wait for containers to start up
    log.info("Waiting for containers to start up...")
    time.sleep(5)

    # Display status
    log.header("STARTUP COMPLETE")

    # City count (calculate from args)
    if hasattr(args, "max_cities"):
        city_count = min(
            args.max_cities, 10
        )  # Assuming cities.txt has at least 10 cities
    else:
        city_count = 5  # Default

    num_sensors = city_count * args.sensors_per_city

    log.success(f"Running {num_sensors} sensors across {city_count} cities")
    log.success(f"Project name: {project_name}")
    log.success(
        f"Each city has {args.sensors_per_city} sensors and 1 dedicated uploader"
    )

    log.info("\nUSEFUL COMMANDS:")
    log.info("* View logs: python -m sensor_manager logs [service-name...]")
    log.info("* Stop all: python -m sensor_manager stop")
    log.info("* Diagnostics: python -m sensor_manager diagnostics")
    log.info(
        "* Query SQLite: python -m sensor_manager query [--all | <city> [<sensor>]]"
    )
    log.info("* Monitor: python -m sensor_manager monitor [--plain]")

    log.info("\nDATA LOCATIONS:")
    log.info("- ./data/{city}/{sensor-code}/sensor_data.db")
    log.info("- ./archive/{city}/{region}_{sensor-id}_{timestamp}.parquet")

    # Run diagnostics if requested
    if not args.no_diagnostics:
        log.header("Running initial diagnostics...")
        time.sleep(10)  # Give containers a bit more time to initialize
        # This would call: run_diagnostics()
        # To be implemented in a future step

    return 0
