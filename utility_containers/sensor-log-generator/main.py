#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "numpy",
#     "pyyaml",
#     "psutil",
# ]
# ///

import argparse
import json
import logging
import sys
from typing import Dict

import yaml

from src.simulator import SensorSimulator


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
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading identity file: {e}")
        raise


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

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)


def main():
    """Main entry point for the sensor simulator."""
    parser = argparse.ArgumentParser(description="Industrial Sensor Simulator")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--identity",
        type=str,
        default="node_identity.json",
        help="Path to node identity file (default: node_identity.json)",
    )
    parser.add_argument(
        "--exit",
        action="store_true",
        help="Exit after loading dependencies (for Docker build)",
    )
    args = parser.parse_args()

    # Exit early if --exit flag is provided (used during Docker build)
    if args.exit:
        print("Dependencies loaded successfully. Exiting as requested.")
        sys.exit(0)

    # Load configuration files
    config = load_config(args.config)
    identity = load_identity(args.identity)

    # Check if config file exists
    if not args.config:
        logging.warning("Config file not specified")
        logging.info("Using default configuration")

    # Set up logging based on config
    setup_logging(config)

    # Run the simulator
    simulator = SensorSimulator(config=config, identity=identity)

    # Start simulation
    logging.info("Starting sensor simulator")
    simulator.run()


if __name__ == "__main__":
    main()
