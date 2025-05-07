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
#     "pydantic",
# ]
# ///

import argparse
import json
import logging
import os
import random
import string
import sys
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError

from src.location import LocationGenerator
from src.simulator import SensorSimulator

# Pydantic Models for Configuration (config.yaml)


class DatabaseConfig(BaseModel):
    path: str


class LoggingConfig(BaseModel):
    level: str
    format: str
    file: Optional[str] = None
    console_output: bool


class RandomLocationConfig(BaseModel):
    enabled: bool
    cities_file: Optional[str] = None
    gps_variation_km: Optional[Union[int, float]] = None


class SimulationConfig(BaseModel):
    readings_per_second: Union[int, float]
    run_time_seconds: Union[int, float]


class ReplicasConfig(BaseModel):
    count: int
    prefix: str
    start_index: int


class ParameterDetail(BaseModel):
    mean: Union[int, float]
    std_dev: Union[int, float]
    min_val: Union[int, float] = Field(alias="min")  # Allow 'min' in YAML
    max_val: Union[int, float] = Field(alias="max")  # Allow 'max' in YAML


class NormalParametersConfig(BaseModel):
    temperature: Optional[ParameterDetail] = None
    vibration: Optional[ParameterDetail] = None
    humidity: Optional[ParameterDetail] = None
    pressure: Optional[ParameterDetail] = None
    voltage: Optional[ParameterDetail] = None


class AnomaliesConfig(BaseModel):
    enabled: bool
    probability: Union[int, float]
    types: Optional[Dict[str, Any]] = None  # Keeping types flexible as before


class MonitoringConfig(BaseModel):
    enabled: bool
    host: str
    port: int


class DynamicReloadingConfig(BaseModel):
    enabled: bool
    check_interval_seconds: Union[int, float]


class AppConfig(BaseModel):
    database: DatabaseConfig
    logging: LoggingConfig
    random_location: RandomLocationConfig
    simulation: Optional[SimulationConfig] = None
    replicas: Optional[ReplicasConfig] = None
    sensor: Optional[Dict[str, Any]] = None  # Keeping sensor flexible
    normal_parameters: Optional[NormalParametersConfig] = None
    anomalies: Optional[AnomaliesConfig] = None
    monitoring: Optional[MonitoringConfig] = None
    dynamic_reloading: Optional[DynamicReloadingConfig] = None
    # If 'valid_configurations' is a legitimate field, add it here.
    # For now, assuming it's not, Pydantic will error if it's present.

    class Config:
        extra = "forbid"  # Forbid any extra fields not defined in the model


# Pydantic Model for Identity (node_identity.json)
class IdentityData(BaseModel):
    id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[Union[int, float]] = None
    longitude: Optional[Union[int, float]] = None
    timezone: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None

    class Config:
        extra = "forbid"  # Forbid any extra fields


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
    """Load configuration from YAML file and validate its structure using Pydantic."""
    try:
        with open(config_path, "r") as f:
            raw_config_data = yaml.safe_load(f)
        if not isinstance(raw_config_data, dict):
            logging.error(f"Config file {config_path} content must be a dictionary.")
            raise ValueError("Config file content must be a dictionary.")

        # Validate and parse using Pydantic model
        app_config = AppConfig(**raw_config_data)
        return app_config.model_dump(by_alias=True)  # Convert Pydantic model to dict

    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML from configuration file {config_path}: {e}")
        raise
    except ValidationError as e:
        # Pydantic's ValidationError provides detailed error messages
        logging.error(f"Invalid configuration in {config_path}:\n{e}")
        raise ValueError(
            f"Invalid configuration: {e}"
        )  # Re-raise as ValueError to match previous behavior if needed
    except Exception as e:
        logging.error(f"Error loading configuration file {config_path}: {str(e)}")
        raise


def load_identity(identity_path: str) -> Dict:
    """Load sensor identity from JSON file and validate its structure using Pydantic."""
    try:
        with open(identity_path, "r") as f:
            raw_identity_data = json.load(f)
        if not isinstance(raw_identity_data, dict):
            logging.error(
                f"Identity file {identity_path} content must be a dictionary."
            )
            raise ValueError("Identity file content must be a dictionary.")

        # Validate and parse using Pydantic model
        identity_data_model = IdentityData(**raw_identity_data)
        return identity_data_model.model_dump()  # Convert Pydantic model to dict

    except FileNotFoundError:
        logging.error(f"Identity file not found: {identity_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from identity file {identity_path}: {e}")
        raise
    except ValidationError as e:
        logging.error(f"Invalid identity data in {identity_path}:\n{e}")
        raise ValueError(f"Invalid identity data: {e}")
    except Exception as e:
        logging.error(f"Error loading identity file {identity_path}: {e}")
        raise


def generate_sensor_id(identity: Dict) -> str:
    """Generate a new sensor ID in the format CITY_XXXXXX."""
    location_str = identity.get("location")
    if not location_str:  # Check if location_str is None or empty
        # This function expects location to be present in the identity dict
        raise ValueError(
            "Location is required in identity data to generate a sensor ID"
        )

    uppercity_no_special_chars = "".join(c.upper() for c in location_str if c.isalpha())

    # Get the first 4 letters of the location (was 3, but ID format implies 4, e.g. CITY)
    location_prefix = uppercity_no_special_chars[:4]
    if not location_prefix:
        # This would happen if location_str had no alpha characters
        raise ValueError(
            "Valid location with alphabetic characters is required to generate a sensor ID"
        )
    # Ensure it's padded or truncated to 4 chars if needed, or make it variable
    # For now, assume it must result in a prefix.
    # If location is "Ny", prefix is "NY". If "A", prefix "A".

    vowels = "aeiou"
    consonants = "".join(c.upper() for c in string.ascii_letters if c not in vowels)
    random_suffix = "".join(random.choice(consonants + string.digits) for _ in range(6))
    return f"{location_prefix.upper()}_{random_suffix}"


def process_identity_and_location(identity_data: Dict, app_config: Dict) -> Dict:
    """
    Processes the identity data, generating or validating location information.

    Args:
        identity_data: The raw identity data from the identity file.
        app_config: The application configuration.

    Returns:
        The processed identity data with location information.

    Raises:
        RuntimeError: If location generation fails when required.
    """
    working_identity = identity_data.copy()
    logger = logging.getLogger(__name__)  # Use a local logger

    # Get random_location settings from app_config
    random_location_config = app_config.get("random_location", {})
    random_location_enabled = random_location_config.get("enabled", False)

    # Check for presence and validity of location, latitude, longitude in identity_data
    location_value = working_identity.get("location")
    # Location must be a non-empty string
    has_location = isinstance(location_value, str) and bool(location_value.strip())

    latitude_value = working_identity.get("latitude")
    has_latitude = isinstance(latitude_value, (int, float))

    longitude_value = working_identity.get("longitude")
    has_longitude = isinstance(longitude_value, (int, float))

    all_geo_fields_valid_and_present = has_location and has_latitude and has_longitude

    if all_geo_fields_valid_and_present:
        logger.info("Using location, latitude, and longitude from identity file.")
    else:
        # Not all geo fields are valid or present
        if random_location_enabled:
            logger.info(
                "Not all geo-fields (location, latitude, longitude) are valid or present in identity. "
                "'random_location.enabled' is true. Attempting to use/generate random location data."
            )

            # Instantiate LocationGenerator to load/access city data
            location_generator = LocationGenerator(random_location_config)

            # The LocationGenerator's __init__ calls _load_cities if enabled.
            # The cities are stored in location_generator.cities
            available_cities = location_generator.cities

            if not available_cities:
                logger.error(
                    "City data is not available or empty after attempting to load via LocationGenerator. "
                    "Cannot generate random location."
                )
                raise RuntimeError(
                    "City data not available for random location generation via LocationGenerator."
                )

            random_city_name = random.choice(list(available_cities.keys()))
            random_city_data = available_cities[random_city_name]

            working_identity["location"] = random_city_name
            working_identity["latitude"] = random_city_data["latitude"]
            working_identity["longitude"] = random_city_data["longitude"]
            logger.info(
                f"Using randomly selected location: {random_city_name} "
                f"(Lat: {working_identity['latitude']:.6f}, Lon: {working_identity['longitude']:.6f})"
            )
            # Update has_location for subsequent ID generation logic, as it's now set
            has_location = True
        else:
            # random_location is not enabled, and some geo fields are missing or invalid. This is an error.
            missing_fields = []
            if not has_location:
                missing_fields.append("'location' (must be a non-empty string)")
            if not has_latitude:
                missing_fields.append("'latitude' (must be a number)")
            if not has_longitude:
                missing_fields.append("'longitude' (must be a number)")

            error_msg = (
                f"Required geo-fields ({', '.join(missing_fields)}) are missing or invalid in the identity file, "
                "and 'random_location.enabled' is false. "
                "Please provide valid 'location', 'latitude', and 'longitude' in the identity file, "
                "or enable 'random_location.enabled=true' in the configuration."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    # Now, ensure an ID is generated if it's missing.
    # This relies on 'location' being present and valid in working_identity,
    # which should be guaranteed by the logic above if no error was raised.
    if not working_identity.get("id"):
        # Check location again, as generate_sensor_id depends on it.
        # It should be set if we reached here (either from file or random generation).
        current_location = working_identity.get("location")
        if not (isinstance(current_location, str) and current_location.strip()):
            critical_error_msg = (
                "Critical internal error: 'location' is missing or invalid in identity data "
                "just before ID generation, despite prior checks. This should not happen."
            )
            logger.error(critical_error_msg)
            raise RuntimeError(critical_error_msg)

        logger.info(
            "Identity file does not contain an 'id' key, or 'id' is empty. Generating new sensor ID."
        )
        try:
            working_identity["id"] = generate_sensor_id(working_identity)
            logger.info(f"Generated sensor ID: {working_identity['id']}")
        except ValueError as e:
            # This could happen if generate_sensor_id raises an error (e.g. location becomes invalid unexpectedly)
            logger.error(f"Failed to generate sensor ID: {e}")
            raise  # Re-raise to be caught by main

    return working_identity


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
    # This is a simple check, consider proper argparse for CLI flags
    if "--exit" in sys.argv:
        logging.info("Received --exit flag. Exiting script after setup (if any).")
        sys.exit(0)

    # Check for required environment variables
    check_required_env_vars()

    config_path = os.getenv("CONFIG_FILE")
    identity_path = os.getenv("IDENTITY_FILE")

    # Load configuration
    try:
        config = load_config(config_path)
    except Exception as e:
        # load_config already logs, but we add context for exiting
        logging.error(
            f"Failed to load configuration from {config_path}. Exiting. Error: {e}"
        )
        sys.exit(1)

    # Set up logging as early as possible after getting config
    setup_logging(config)  # Uses the loaded config

    # Load raw identity data
    try:
        raw_identity = load_identity(identity_path)
    except Exception as e:
        logging.error(
            f"Failed to load identity from {identity_path}. Exiting. Error: {e}"
        )
        sys.exit(1)

    # Process identity, handle location, and generate ID if needed
    try:
        identity = process_identity_and_location(raw_identity, config)
    except (ValueError, RuntimeError) as e:  # Catch errors from processing
        logging.error(f"Failed to process identity or generate ID. Exiting. Error: {e}")
        sys.exit(1)

    logging.info(f"Using sensor ID: {identity.get('id', 'Not Set')}")
    logging.info(f"Sensor Location: {identity.get('location', 'Not Set')}")

    # Get data directory path from config
    data_dir_config = config.get("database", {})
    data_dir = data_dir_config.get("path", "data")
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
