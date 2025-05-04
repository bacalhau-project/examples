#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "numpy",
#     "pyyaml",
#     "psutil",
#     "pytz",
#     "numpy",
#     "psutil",
#     "requests",
# ]
# ///

import argparse
import json
import logging
import os
import random
import string
import sys
from typing import Dict

import yaml

from src.simulator import SensorSimulator


def check_required_env_vars():
    """Check for required environment variables and exit if any are missing."""
    required_vars = {
        "CONFIG_FILE": "Path to the configuration file",
        "IDENTITY_FILE": "Path to the identity file",
    }

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logging.error("Missing required environment variables:")
        for var in missing_vars:
            logging.error(f"- {var}: {required_vars[var]}")
        sys.exit(1)


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the configuration file

    Returns:
        Dictionary containing the configuration
    """
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading configuration file: {e}")
        raise


def load_identity(identity_path: str) -> Dict:
    """Load sensor identity from JSON file.

    Args:
        identity_path: Path to the identity file

    Returns:
        Dictionary containing the sensor identity
    """
    try:
        with open(identity_path, "r") as f:
            identity = json.load(f)
            if not identity.get("id"):
                logging.info(
                    "Identity file does not contain an 'id' key, generating..."
                )
                identity["id"] = generate_sensor_id(identity)
            return identity
    except Exception as e:
        logging.error(f"Error loading identity file: {e}")
        raise


def generate_sensor_id(identity: Dict) -> str:
    """Generate a new sensor ID in the format CITY_XXXXXX."""
    uppercity_no_special_chars = "".join(
        c.upper() for c in identity.get("location") if c.isalpha()
    )

    # Get the first 3 letters of the location
    location_prefix = uppercity_no_special_chars[:4]
    if not location_prefix:
        raise ValueError("Location is required to generate a sensor ID")

    # Generate a random 6-digit string of characters and numbers, no vowels, no special characters
    vowels = "aeiou"
    consonants = "".join(c.upper() for c in string.ascii_letters if c not in vowels)
    random_number = "".join(random.choice(consonants + string.digits) for _ in range(6))
    return f"{location_prefix}_{random_number}"


def setup_logging(config):
    """Set up logging based on configuration."""
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO"))
    log_format = log_config.get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_file = log_config.get("file")
    console_output = log_config.get("console_output", True)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add console handler if enabled
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console_handler)

    # Add file handler if log file is specified
    if log_file:
        # Ensure the log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)


def main():
    """Main entry point for the sensor simulator."""
    # If the --exit flag is provided, exit after the simulator is run
    if "--exit" in sys.argv:
        sys.exit(0)

    # Check for required environment variables
    check_required_env_vars()

    # Load configuration and identity
    try:
        config = load_config(os.getenv("CONFIG_FILE"))
    except Exception as e:
        logging.error(f"Failed to load configuration file: {e}")
        sys.exit(1)

    try:
        identity = load_identity(os.getenv("IDENTITY_FILE"))
    except Exception as e:
        logging.error(f"Failed to load identity file: {e}")
        sys.exit(1)

    # Set up logging
    setup_logging(config)

    # Get data directory path from config
    data_dir = config.get("database", {}).get("path", "data")
    if not data_dir:
        logging.error("Data directory path not specified in config.yaml")
        sys.exit(1)

    # Ensure the data directory exists
    try:
        os.makedirs(os.path.dirname(data_dir), exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to create data directory: {e}")
        sys.exit(1)

    # Create and run the simulator
    simulator = SensorSimulator(config, identity)
    simulator.run()


if __name__ == "__main__":
    main()
