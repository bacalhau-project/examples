"""
Docker Compose generation command implementation.

This module implements the 'compose' command for the Sensor Manager CLI,
which generates a Docker Compose file for sensor simulation.
"""

import os
import random
import string
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from sensor_manager.config.models import load_config
from sensor_manager.docker.compose import DockerComposeGenerator
from sensor_manager.utils import logging as log


def generate_random_code(length: int = 4) -> str:
    """
    Generate a random alphanumeric code.

    Args:
        length: Length of the code to generate

    Returns:
        Random alphanumeric code
    """
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def generate_unique_random_codes(keys: List[str], length: int = 4) -> Dict[str, str]:
    """
    Generate unique random codes for the specified keys.

    Args:
        keys: List of keys to generate codes for
        length: Length of each code

    Returns:
        Dictionary mapping keys to unique random codes
    """
    codes = {}
    used_codes = set()

    for key in keys:
        # Generate a unique code for this key
        while True:
            code = generate_random_code(length)
            if code not in used_codes:
                break

        codes[key] = code
        used_codes.add(code)

    return codes


def load_cities_from_config(config_path: Path) -> List[Dict]:
    """
    Load city information from the configuration file.

    Args:
        config_path: Path to the configuration file

    Returns:
        List of city information dictionaries
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if "cities" not in config:
            log.error(f"No cities section found in {config_path}")
            return []

        return config["cities"]
    except Exception as e:
        log.error(f"Error loading cities from {config_path}: {e}")
        return []


def compose_command(args):
    """
    Implementation of the 'compose' command.

    Args:
        args: Command-line arguments
    """
    log.header("Generating Docker Compose file")

    # Load cities from config
    log.info(f"Loading city information from {args.config}")
    cities = load_cities_from_config(Path(args.config))

    if not cities:
        log.error(
            "No cities found in configuration. Cannot generate Docker Compose file."
        )
        return 1

    log.info(f"Found {len(cities)} cities in configuration")

    # Generate random codes for each sensor
    city_sensor_keys = []
    for city in cities:
        for i in range(1, args.sensors_per_city + 1):
            # Use a more unique key format to ensure no duplicates
            city_sensor_keys.append(f"{city['name']}_{i}")

    log.info(f"Generating random codes for {len(city_sensor_keys)} sensors")
    random_codes = generate_unique_random_codes(city_sensor_keys)

    # Generate Docker Compose file
    generator = DockerComposeGenerator(args.output)

    # Load environment variables for Cosmos DB
    cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT", "")
    cosmos_key = os.environ.get("COSMOS_KEY", "")

    # Get the uploader image tag - this should be passed from start_command
    if not hasattr(args, "uploader_tag") or not args.uploader_tag:
        log.error("No uploader tag provided. This should be passed from start_command.")
        return 1

    uploader_tag = args.uploader_tag

    # Safety check - never allow "latest" tag
    if uploader_tag == "latest":
        log.error("DANGER: 'latest' tag was specified but is not allowed!")
        return 1

    # Output registry information
    registry_image = f"ghcr.io/bacalhau-project/cosmos-uploader:{uploader_tag}"
    log.info(f"Using image: {registry_image}")

    # Prepare context for template rendering
    context = {
        "cities": cities,
        "sensors_per_city": args.sensors_per_city,
        "readings_per_second": args.readings_per_second,
        "anomaly_probability": args.anomaly_probability,
        "upload_interval": args.upload_interval,
        "archive_format": args.archive_format,
        "config_file": args.compose_config,
        "sensor_config_file": args.sensor_config,
        "random_codes": random_codes,
        "uploader_image_tag": uploader_tag,
        "cosmos_endpoint": cosmos_endpoint,
        "cosmos_key": cosmos_key,
        "cosmos_database": os.environ.get("COSMOS_DATABASE", "SensorData"),
        "cosmos_container": os.environ.get("COSMOS_CONTAINER", "SensorReadings"),
    }

    # Generate the file using the template
    if generator.generate_from_template("docker-compose.yml.j2", context):
        log.success(f"Generated Docker Compose file at {args.output}")
        return 0
    else:
        log.error("Failed to generate Docker Compose file")
        return 1
