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
import logging
import os
import sys

from src.simulator import SensorSimulator


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
    parser = argparse.ArgumentParser(description="Industrial Sensor Simulator")
    parser.add_argument(
        "--config", type=str, default="config.yaml", help="Path to configuration file"
    )
    parser.add_argument("--identity", type=str, help="Path to node identity file")
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

    # Check if config file exists
    if not os.path.exists(args.config):
        logging.warning(f"Config file not found: {args.config}")
        logging.info("Using default configuration")

    # Run the simulator
    simulator = SensorSimulator(config_path=args.config, identity_path=args.identity)

    # Set up logging based on config
    setup_logging(simulator.config_manager.config)

    # Start simulation
    logging.info(f"Starting sensor simulator")
    simulator.run()


if __name__ == "__main__":
    main()
