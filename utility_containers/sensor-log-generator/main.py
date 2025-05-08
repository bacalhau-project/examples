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
#     "tenacity",
# ]
# ///

import json
import logging
import os
import random
import string
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError

from src.config import ConfigManager
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
    temperature: ParameterDetail
    vibration: ParameterDetail
    humidity: ParameterDetail
    pressure: ParameterDetail
    voltage: ParameterDetail


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


def file_watcher_thread(
    file_path: str,
    load_function: Callable[[str], Dict],
    config_manager_instance: ConfigManager,
    update_type: str,  # "config" or "identity"
    simulator_instance: SensorSimulator,
    simulator_update_method_name: str,  # "handle_config_updated" or "handle_identity_updated"
    stop_event: threading.Event,
    check_interval: Union[int, float],
):
    """
    Monitors a file for changes and updates the ConfigManager and SensorSimulator.
    """
    logger = logging.getLogger(__name__)
    last_mtime = None
    if os.path.exists(file_path):
        last_mtime = os.path.getmtime(file_path)
    else:
        logger.warning(
            f"File watcher: Initial file not found at {file_path}. Will watch for creation."
        )

    while not stop_event.is_set():
        try:
            if not os.path.exists(file_path):
                if last_mtime is not None:  # File was deleted
                    logger.warning(
                        f"File watcher: Watched file {file_path} has been deleted."
                    )
                    last_mtime = None  # Reset mtime so recreation is detected
                # Wait and check again
                stop_event.wait(check_interval)
                continue

            current_mtime = os.path.getmtime(file_path)
            if last_mtime is None or current_mtime > last_mtime:
                if last_mtime is None:
                    logger.info(
                        f"File watcher: File {file_path} has been created/appeared."
                    )
                else:
                    logger.info(
                        f"File watcher: File {file_path} has changed. Reloading..."
                    )

                try:
                    new_data = load_function(file_path)
                    if update_type == "config":
                        config_manager_instance.config = new_data
                        # Potentially re-process identity if config affects it, e.g., random location settings
                        # For now, assuming direct update is sufficient for config.
                        # If identity processing logic in main needs to be rerun, that's more complex.
                        # The main config doesn't usually change identity structure, but identity file does.
                    elif update_type == "identity":
                        # When identity file changes, it might need re-processing (e.g. ID generation, location fixing)
                        # This requires the *current app_config* for process_identity_and_location
                        # It's safer to re-run the original processing logic from main.py for identity.
                        # However, process_identity_and_location takes app_config, not config_manager.config.
                        # For now, we'll assume `load_identity` gives the final, processed identity.
                        # A more robust solution would re-run `process_identity_and_location`.
                        # Let's keep it simple: just load and set.
                        # The `config_manager.identity` will be updated by the simulator's handler.

                        # We need to pass the *raw loaded data* to `process_identity_and_location`
                        # and the *current config dictionary* from ConfigManager.
                        current_app_config = config_manager_instance.config
                        processed_new_identity = process_identity_and_location(
                            new_data, current_app_config
                        )
                        config_manager_instance.identity = processed_new_identity
                    else:
                        logger.error(
                            f"File watcher: Unknown update type '{update_type}' for {file_path}"
                        )
                        last_mtime = (
                            current_mtime  # Update mtime to avoid reprocessing error
                        )
                        stop_event.wait(check_interval)
                        continue

                    logger.info(
                        f"File watcher: Successfully reloaded {file_path}. Notifying simulator."
                    )
                    update_method = getattr(
                        simulator_instance, simulator_update_method_name
                    )
                    update_method()  # Call handle_config_updated() or handle_identity_updated()

                    last_mtime = current_mtime
                except Exception as e:
                    logger.error(
                        f"File watcher: Error reloading {file_path}: {e}. Using previous configuration for this source."
                    )
                    # last_mtime should not be updated here, so it tries again next interval
                    # unless the file truly hasn't changed, in which case an mtime update is needed
                    if os.path.exists(file_path):  # If error was not file not found
                        last_mtime = os.path.getmtime(
                            file_path
                        )  # Avoid loop if file is bad but mtime same

        except Exception as e:
            logger.error(f"File watcher: Unexpected error for {file_path}: {e}")
            # Avoid tight loop on unexpected errors

        stop_event.wait(check_interval)
    logger.info(f"File watcher: Thread for {file_path} is stopping.")


def main():
    """Main entry point for the sensor simulator."""
    # If the --exit flag is provided, exit after the simulator is run
    # This is a simple check, consider proper argparse for CLI flags
    if "--exit" in sys.argv:
        # Logging isn't set up yet here.
        print("Received --exit flag. Exiting script early.")
        sys.exit(0)

    config_file_path = os.environ.get("CONFIG_FILE")
    identity_file_path = os.environ.get("IDENTITY_FILE")

    if not config_file_path:
        print("Error: CONFIG_FILE environment variable is not set", file=sys.stderr)
        sys.exit(1)

    if not identity_file_path:
        print("Error: IDENTITY_FILE environment variable is not set", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(config_file_path):
        print(f"Error: Config file not found at {config_file_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(identity_file_path):
        print(
            f"Error: Identity file not found at {identity_file_path}", file=sys.stderr
        )
        sys.exit(1)

    initial_config = {}
    initial_identity = {}
    config_manager = None
    simulator = None
    watcher_threads = []
    stop_watcher_event = None

    try:
        # Load initial configuration
        try:
            initial_config = load_config(config_file_path)
        except Exception as e:
            # load_config logs, but print for early exit before logger is fully set
            print(
                f"Critical: Failed to load initial configuration from {config_file_path}. Exiting. Error: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Set up logging as early as possible after getting config
        setup_logging(initial_config)  # Uses the loaded config

        # Load initial raw identity data
        try:
            raw_identity = load_identity(identity_file_path)
        except Exception as e:
            logging.error(
                f"Failed to load initial identity from {identity_file_path}. Exiting. Error: {e}"
            )
            sys.exit(1)

        # Process initial identity, handle location, and generate ID if needed
        try:
            initial_identity = process_identity_and_location(
                raw_identity, initial_config
            )
        except (ValueError, RuntimeError) as e:  # Catch errors from processing
            logging.error(
                f"Failed to process initial identity or generate ID. Exiting. Error: {e}"
            )
            sys.exit(1)

        # Create ConfigManager with initial data
        config_manager = ConfigManager(config=initial_config, identity=initial_identity)

        logging.info(
            f"Using sensor ID: {config_manager.get_identity().get('id', 'Not Set')}"
        )
        logging.info(
            f"Sensor Location: {config_manager.get_identity().get('location', 'Not Set')}"
        )

        # Create and run the simulator, passing the ConfigManager
        simulator = SensorSimulator(config_manager)

        # Setup and start file watcher threads if dynamic reloading is enabled
        dynamic_reload_settings = config_manager.config.get("dynamic_reloading", {})
        if dynamic_reload_settings.get("enabled", False):
            check_interval = dynamic_reload_settings.get("check_interval_seconds", 5)
            logging.info(
                f"Dynamic reloading enabled. Check interval: {check_interval}s."
            )
            stop_watcher_event = threading.Event()

            # Config file watcher
            config_watcher = threading.Thread(
                target=file_watcher_thread,
                args=(
                    config_file_path,
                    load_config,  # function to load config
                    config_manager,
                    "config",  # type of update
                    simulator,
                    "handle_config_updated",  # simulator's method
                    stop_watcher_event,
                    check_interval,
                ),
                daemon=True,
            )
            watcher_threads.append(config_watcher)
            config_watcher.start()

            # Identity file watcher
            identity_watcher = threading.Thread(
                target=file_watcher_thread,
                args=(
                    identity_file_path,
                    load_identity,  # function to load identity (raw)
                    config_manager,
                    "identity",  # type of update
                    simulator,
                    "handle_identity_updated",  # simulator's method
                    stop_watcher_event,
                    check_interval,
                ),
                daemon=True,
            )
            watcher_threads.append(identity_watcher)
            identity_watcher.start()
        else:
            logging.info("Dynamic reloading is disabled.")

        simulator.run()

    except KeyboardInterrupt:
        logging.info("Main: Simulation interrupted by user.")
        if simulator:
            simulator.stop()  # Gracefully stop simulator if possible
    except Exception as e:
        logging.critical(f"Main: Unhandled exception: {e}", exc_info=True)
    finally:
        logging.info("Main: Shutting down...")
        if stop_watcher_event:
            logging.info("Main: Signaling watcher threads to stop...")
            stop_watcher_event.set()
            for thread in watcher_threads:
                if thread.is_alive():
                    logging.info(
                        f"Main: Waiting for watcher thread {thread.name} to join..."
                    )
                    thread.join(timeout=5)  # Wait for threads to finish
                    if thread.is_alive():
                        logging.warning(
                            f"Main: Watcher thread {thread.name} did not join in time."
                        )

        # Simulator's own cleanup (like DB close) happens in its run() finally block.
        logging.info("Main: Shutdown complete.")


if __name__ == "__main__":
    main()
