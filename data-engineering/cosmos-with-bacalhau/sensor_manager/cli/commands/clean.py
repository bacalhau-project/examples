"""
Clean command implementation.

This module implements the 'clean' command for the Sensor Manager CLI,
which deletes all data from Cosmos DB.
"""

import os
import subprocess
import sys
from pathlib import Path

from sensor_manager.utils import logging as log


def load_env_file():
    """
    Load environment variables from a .env file if it exists.
    
    Returns:
        bool: True if .env file was loaded, False otherwise
    """
    env_file = Path('.env')
    if env_file.exists():
        log.info("Loading configuration from .env file...")
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")
            return True
        except Exception as e:
            log.warning(f"Error loading .env file: {e}")
    else:
        log.warning("No .env file found. Using default values and environment variables.")
    return False


def check_cosmos_credentials():
    """
    Check if the required Cosmos DB credentials are available.
    
    Returns:
        bool: True if credentials are available, False otherwise
    """
    if not os.environ.get('COSMOS_ENDPOINT') or not os.environ.get('COSMOS_KEY'):
        log.error("Error: COSMOS_ENDPOINT and COSMOS_KEY environment variables must be set.")
        log.info("You can create a .env file with these variables or set them manually.")
        return False
    return True


def run_bulk_delete_script(config_path, dry_run=False):
    """
    Run the bulk delete script to clean Cosmos DB data.
    
    Args:
        config_path: Path to the configuration file
        dry_run: Whether to perform a dry run (no actual deletion)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Build command options
    cmd_options = []
    
    if dry_run:
        cmd_options.append("--dry-run")
    
    # Always pass the config file
    cmd_options.extend(["--config", config_path])
    
    log.info(f"Executing: utility_scripts/bulk_delete_cosmos.py {' '.join(cmd_options)}")
    
    try:
        # Check if bulk_delete_cosmos.py exists and is executable
        script_path = Path("utility_scripts/bulk_delete_cosmos.py")
        if not script_path.exists():
            log.error("Error: bulk_delete_cosmos.py script not found.")
            return False
        
        # Make the script executable if it's not already
        script_path.chmod(script_path.stat().st_mode | 0o755)
        
        # Run the Python bulk delete script
        cmd = [str(script_path.absolute())]
        cmd.extend(cmd_options)
        
        # Use subprocess.PIPE to capture output but allow it to be displayed
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Stream output in real-time
        for line in process.stdout:
            print(line.rstrip())
        
        # Wait for the process to complete
        process.wait()
        
        # Check return code
        if process.returncode != 0:
            for line in process.stderr:
                print(line.rstrip())
            log.error(f"Bulk delete script failed with return code {process.returncode}")
            return False
        
        return True
    except Exception as e:
        log.error(f"Error running bulk delete script: {str(e)}")
        return False


def clean_command(args):
    """
    Implementation of the 'clean' command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    log.header("Starting Cosmos DB data cleanup")
    
    # Load environment variables
    load_env_file()
    
    # Check Cosmos credentials
    if not check_cosmos_credentials():
        return 1
    
    # Set default configuration
    database = os.environ.get('COSMOS_DATABASE', 'SensorData')
    container = os.environ.get('COSMOS_CONTAINER', 'SensorReadings')
    config_path = args.config if hasattr(args, 'config') and args.config else "config/config.yaml"
    dry_run = hasattr(args, 'dry_run') and args.dry_run
    
    log.info(f"Will clean data from database '{database}' and container '{container}'")
    
    # Check if config file exists
    config_file = Path(config_path)
    if not config_file.exists():
        log.error(f"Config file not found at {config_path}")
        return 1
    
    # Confirm unless --yes was provided
    if not (hasattr(args, 'yes') and args.yes):
        log.warning("This will DELETE ALL DATA in the specified container.")
        if dry_run:
            log.info("(Dry run mode - no data will actually be deleted)")
        
        try:
            response = input("Are you sure you want to continue? (y/n) ")
            if not response.lower().startswith('y'):
                log.info("Canceling cleanup operation.")
                return 0
        except KeyboardInterrupt:
            log.info("\nOperation cancelled by user.")
            return 0
    
    # Run the bulk delete script
    success = run_bulk_delete_script(config_path, dry_run)
    
    if success:
        log.separator()
        if dry_run:
            log.success("Dry run completed successfully! No data was deleted.")
            log.info("Run without --dry-run to perform the actual deletion.")
        else:
            log.success("Bulk deletion completed! The container has been emptied but preserved.")
            log.info("New data will be uploaded as sensors continue to run.")
        return 0
    else:
        log.error("Failed to clean Cosmos DB data.")
        log.info("Make sure the Azure Cosmos SDK is installed:")
        log.info("uv pip install azure-cosmos pyyaml")
        return 1