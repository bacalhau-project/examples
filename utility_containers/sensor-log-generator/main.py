#!/usr/bin/env python3

import argparse
import json
import logging
import math
import os
import random
import signal
import string
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, Union
from datetime import datetime

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from src.config import ConfigManager
from src.database import SensorReadingSchema
from src.location import LocationGenerator
from src.simulator import SensorSimulator
from src.llm_docs import print_llm_documentation, save_llm_documentation

# Pydantic Models for Configuration (config.yaml)


class DatabaseConfig(BaseModel):
    path: str


class LoggingConfig(BaseModel):
    level: str
    format: str
    file: Optional[str] = None
    console_output: bool


class RandomLocationConfig(BaseModel):
    enabled: bool = False
    cities_file: Optional[str] = None
    gps_variation: Optional[Union[int, float]] = None  # Added, in meters
    number_of_cities: Optional[int] = None  # Added based on user example


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
    version: Optional[int] = 1  # Config version, defaults to 1 if not specified
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

    model_config = {
        "extra": "forbid"
    }  # Forbid any extra fields not defined in the model
    
    @model_validator(mode='after')
    def validate_version_requirements(self):
        """Validate that required fields are present based on config version."""
        if self.version >= 2:
            # Version 2 and above requires monitoring section
            if self.monitoring is None:
                raise ValueError(
                    f"Config version {self.version} requires 'monitoring' section. "
                    "Please add a monitoring section or use version: 1 for backward compatibility."
                )
            # Version 2 and above requires dynamic_reloading section
            if self.dynamic_reloading is None:
                raise ValueError(
                    f"Config version {self.version} requires 'dynamic_reloading' section. "
                    "Please add a dynamic_reloading section or use version: 1 for backward compatibility."
                )
        return self


# Pydantic Models for Identity (node_identity.json)
class LocationData(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    coordinates: Optional[Dict[str, Union[int, float]]] = None
    timezone: Optional[str] = None
    address: Optional[str] = None

    @field_validator('coordinates')
    def validate_coordinates(cls, v):
        if v is not None:
            if 'latitude' not in v or 'longitude' not in v:
                raise ValueError("coordinates must contain 'latitude' and 'longitude'")
            lat = v['latitude']
            lon = v['longitude']
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                raise ValueError("latitude and longitude must be numeric")
            if not (-90 <= lat <= 90):
                raise ValueError("latitude must be between -90 and 90")
            if not (-180 <= lon <= 180):
                raise ValueError("longitude must be between -180 and 180")
        return v


class DeviceInfoData(BaseModel):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None
    manufacture_date: Optional[str] = None

    @field_validator('manufacture_date')
    def validate_manufacture_date(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError("manufacture_date must be in ISO format")
        return v


class DeploymentData(BaseModel):
    deployment_type: Optional[str] = None
    installation_date: Optional[str] = None
    height_meters: Optional[Union[int, float]] = None
    orientation_degrees: Optional[Union[int, float]] = None

    @field_validator('installation_date')
    def validate_installation_date(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError("installation_date must be in ISO format")
        return v

    @field_validator('orientation_degrees')
    def validate_orientation(cls, v):
        if v is not None and not (0 <= v <= 360):
            raise ValueError("orientation_degrees must be between 0 and 360")
        return v


class MetadataData(BaseModel):
    instance_id: Optional[str] = None
    identity_generation_timestamp: Optional[str] = None
    generation_seed: Optional[Union[int, str]] = None
    sensor_type: Optional[str] = None

    @field_validator('identity_generation_timestamp')
    def validate_timestamp(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError("identity_generation_timestamp must be in ISO format")
        return v


class IdentityData(BaseModel):
    sensor_id: Optional[str] = None
    location: Optional[Union[str, LocationData]] = None
    device_info: Optional[DeviceInfoData] = None
    deployment: Optional[DeploymentData] = None
    metadata: Optional[MetadataData] = None
    
    # Legacy fields for backward compatibility
    id: Optional[str] = None
    latitude: Optional[Union[int, float]] = None
    longitude: Optional[Union[int, float]] = None
    timezone: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None

    model_config = {"extra": "forbid"}  # Forbid any extra fields

    @model_validator(mode='after')
    def handle_legacy_fields(self):
        # If sensor_id is not set but id is, use id
        if self.sensor_id is None and self.id is not None:
            self.sensor_id = self.id
        
        # If location is a string (legacy), convert it
        if isinstance(self.location, str):
            coords = None
            if self.latitude is not None and self.longitude is not None:
                coords = {'latitude': self.latitude, 'longitude': self.longitude}
            self.location = LocationData(
                city=self.location,
                coordinates=coords,
                timezone=self.timezone
            )
        
        # If device_info is not set but legacy fields exist, create it
        if self.device_info is None and any([self.manufacturer, self.model, self.firmware_version]):
            self.device_info = DeviceInfoData(
                manufacturer=self.manufacturer,
                model=self.model,
                firmware_version=self.firmware_version
            )
        
        return self


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file and validate its structure using Pydantic."""
    try:
        with open(config_path, "r") as f:
            raw_config_data = yaml.safe_load(f)
        if not isinstance(raw_config_data, dict):
            logging.error(f"Config file {config_path} content must be a dictionary.")
            raise ValueError("Config file content must be a dictionary.")

        # Log config version for debugging
        config_version = raw_config_data.get("version", 1)
        logging.info(f"Loading config file version: {config_version}")
        
        # If version 1 (or missing), ensure monitoring and dynamic_reloading have defaults
        if config_version == 1:
            if "monitoring" not in raw_config_data:
                logging.info("Config version 1: Adding default monitoring section")
                raw_config_data["monitoring"] = {
                    "enabled": False,
                    "host": "0.0.0.0",
                    "port": 8080,
                    "metrics_interval_seconds": 60
                }
            if "dynamic_reloading" not in raw_config_data:
                logging.info("Config version 1: Adding default dynamic_reloading section")
                raw_config_data["dynamic_reloading"] = {
                    "enabled": False,
                    "check_interval_seconds": 5
                }

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
    # Handle both new nested structure and legacy format
    location_str = None
    
    # Check for nested location structure first
    location_data = identity.get("location")
    if isinstance(location_data, dict):
        location_str = location_data.get("city") or location_data.get("address")
    elif isinstance(location_data, str):
        location_str = location_data
    
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
    # Ensure gps_variation_meters is defined at a scope accessible by the fuzzing logic
    gps_variation_meters = random_location_config.get("gps_variation")

    # Check for presence and validity of location, latitude, longitude in identity_data
    # Handle both new nested structure and legacy format
    location_value = None
    latitude_value = None
    longitude_value = None
    
    location_data = working_identity.get("location")
    if isinstance(location_data, dict):
        # New nested structure
        location_value = location_data.get("city") or location_data.get("address")
        coords = location_data.get("coordinates", {})
        if isinstance(coords, dict):
            latitude_value = coords.get("latitude")
            longitude_value = coords.get("longitude")
    elif isinstance(location_data, str):
        # Legacy structure or already converted by model validator
        location_value = location_data
        latitude_value = working_identity.get("latitude")
        longitude_value = working_identity.get("longitude")
    
    # Location must be a non-empty string
    has_location = isinstance(location_value, str) and bool(location_value.strip())
    has_latitude = isinstance(latitude_value, (int, float))
    has_longitude = isinstance(longitude_value, (int, float))

    all_geo_fields_valid_and_present = has_location and has_latitude and has_longitude

    if all_geo_fields_valid_and_present:
        logger.info(
            f"Using location '{location_value}' (Lat: {latitude_value}, Lon: {longitude_value}) "
            "from identity file as base for geo-coordinates."
        )
        # Ensure flat values are set for backward compatibility
        working_identity["latitude"] = latitude_value
        working_identity["longitude"] = longitude_value
    elif random_location_enabled:
        logger.info(
            "Not all geo-fields (location, latitude, longitude) are valid or present in identity. "
            "'random_location.enabled' is true. Attempting to generate random location data."
        )

        location_generator = LocationGenerator(random_location_config)
        available_cities = location_generator.cities
        if not available_cities:
            logger.error(
                "City data is not available or empty. Cannot generate random location."
            )
            raise RuntimeError(
                "City data not available for random location generation."
            )

        random_city_name = random.choice(list(available_cities.keys()))
        random_city_data = available_cities[random_city_name]

        # Set base coordinates from the randomly chosen city
        # Update both nested and flat structure for compatibility
        if isinstance(working_identity.get("location"), dict):
            working_identity["location"]["city"] = random_city_name
            working_identity["location"]["coordinates"] = {
                "latitude": random_city_data["latitude"],
                "longitude": random_city_data["longitude"]
            }
        else:
            # Create new location structure if needed
            working_identity["location"] = {
                "city": random_city_name,
                "coordinates": {
                    "latitude": random_city_data["latitude"],
                    "longitude": random_city_data["longitude"]
                }
            }
        
        # Also set flat values for backward compatibility
        working_identity["latitude"] = random_city_data["latitude"]
        working_identity["longitude"] = random_city_data["longitude"]
        
        logger.info(
            f"Randomly selected base location: {random_city_name} "
            f"(Lat: {random_city_data['latitude']:.6f}, Lon: {random_city_data['longitude']:.6f})"
        )
        has_location = True  # Ensure this is set for ID generation logic
        location_value = random_city_name
        latitude_value = random_city_data["latitude"]
        longitude_value = random_city_data["longitude"]
        # The old fuzzing logic and log_suffix that were here are removed.
        # Fuzzing will be handled in a separate block later.
    else:
        # Not all geo fields are valid or present, and random_location is not enabled. This is an error.
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

    # --- Unified Fuzzing Logic ---
    # Apply fuzzing if random_location is enabled and gps_variation is configured positively,
    # using the coordinates currently in working_identity (either from file or random generation).
    if (
        random_location_enabled
        and gps_variation_meters
        and isinstance(gps_variation_meters, (int, float))
        and gps_variation_meters > 0
    ):
        current_lat = working_identity.get("latitude")
        current_lon = working_identity.get("longitude")

        if isinstance(current_lat, (int, float)) and isinstance(
            current_lon, (int, float)
        ):
            gps_variation_km = gps_variation_meters / 1000.0
            logger.info(
                f"Applying GPS fuzzing (up to {gps_variation_meters}m / {gps_variation_km:.2f}km) "
                f"to location: {working_identity.get('location')} "
                f"(Base Lat: {current_lat:.6f}, Base Lon: {current_lon:.6f})."
            )

            # Approximate conversion for fuzzing
            lat_variation_degrees = gps_variation_km / 111.0
            lon_variation_degrees = (
                gps_variation_km / (111.0 * math.cos(math.radians(current_lat)))
                if math.cos(math.radians(current_lat)) != 0
                else lat_variation_degrees
            )

            lat_offset = random.uniform(-lat_variation_degrees, lat_variation_degrees)
            lon_offset = random.uniform(-lon_variation_degrees, lon_variation_degrees)

            fuzzed_latitude = current_lat + lat_offset
            fuzzed_longitude = current_lon + lon_offset

            # Round to 5 decimal places (precision of ~1.11 meters)
            fuzzed_latitude = round(fuzzed_latitude, 5)
            fuzzed_longitude = round(fuzzed_longitude, 5)

            # Update both nested and flat structure
            if isinstance(working_identity.get("location"), dict) and "coordinates" in working_identity["location"]:
                working_identity["location"]["coordinates"]["latitude"] = fuzzed_latitude
                working_identity["location"]["coordinates"]["longitude"] = fuzzed_longitude
            
            # Always update flat values for backward compatibility
            working_identity["latitude"] = fuzzed_latitude
            working_identity["longitude"] = fuzzed_longitude
            
            location_name = location_value or working_identity.get('location')
            logger.info(
                f"Fuzzed coordinates for '{location_name}': "
                f"New Lat: {fuzzed_latitude:.5f}, New Lon: {fuzzed_longitude:.5f}"
            )
        else:
            logger.warning(
                f"GPS fuzzing enabled, but current latitude/longitude in working_identity are invalid. Skipping fuzzing. "
                f"Lat: {current_lat}, Lon: {current_lon}"
            )
    elif (
        random_location_enabled and gps_variation_meters
    ):  # gps_variation_meters is not None but not positive float/int
        logger.info(
            f"Random location enabled, but GPS variation value ({gps_variation_meters}) is not a positive number. "
            "Using exact coordinates."
        )
    elif random_location_enabled:  # gps_variation_meters is None
        logger.info(
            "Random location enabled, but GPS variation ('gps_variation') not configured or is null. "
            "Using exact coordinates."
        )
    # If random_location is not enabled, no fuzzing occurs, and no message about it is needed here.

    # Now, ensure an ID is generated if it's missing.
    # This relies on 'location' being present and valid in working_identity,
    # which should be guaranteed by the logic above if no error was raised.
    sensor_id = working_identity.get("sensor_id") or working_identity.get("id")
    if not sensor_id:
        # Check location again, as generate_sensor_id depends on it.
        # It should be set if we reached here (either from file or random generation).
        current_location = working_identity.get("location")
        if isinstance(current_location, dict):
            # For nested structure, create a string representation for generate_sensor_id
            location_str = current_location.get("city") or current_location.get("address")
        else:
            location_str = current_location
            
        if not (isinstance(location_str, str) and location_str.strip()):
            critical_error_msg = (
                "Critical internal error: 'location' is missing or invalid in identity data "
                "just before ID generation, despite prior checks. This should not happen."
            )
            logger.error(critical_error_msg)
            raise RuntimeError(critical_error_msg)

        logger.info(
            "Identity file does not contain an 'id' or 'sensor_id' key, or it is empty. Generating new sensor ID."
        )
        try:
            generated_id = generate_sensor_id(working_identity)
            # Set both fields for compatibility
            working_identity["sensor_id"] = generated_id
            working_identity["id"] = generated_id
            logger.info(f"Generated sensor ID: {generated_id}")
        except ValueError as e:
            # This could happen if generate_sensor_id raises an error (e.g. location becomes invalid unexpectedly)
            logger.error(f"Failed to generate sensor ID: {e}")
            raise  # Re-raise to be caught by main
    else:
        # Ensure both fields are set for compatibility
        working_identity["sensor_id"] = sensor_id
        working_identity["id"] = sensor_id

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


def signal_handler(signum, frame):
    """Handle termination signals."""
    sig_name = signal.Signals(signum).name if signum in signal.Signals._value2member_map_ else str(signum)
    logging.critical(f"RECEIVED SIGNAL: {sig_name} ({signum})")
    logging.critical("Process is being terminated by external signal")
    if signum == signal.SIGTERM:
        logging.critical("This is typically from 'docker stop' or container timeout")
    elif signum == signal.SIGINT:
        logging.critical("This is typically from Ctrl+C or user interruption")
    elif signum == signal.SIGHUP:
        logging.critical("Terminal disconnected or session ended")
    sys.exit(128 + signum)  # Exit with standard signal exit code

def main():
    """Main function to run the sensor simulator."""
    
    # Register signal handlers early
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    try:
        signal.signal(signal.SIGHUP, signal_handler)
    except:
        pass  # SIGHUP might not be available on all platforms

    # Argument parsing
    parser = argparse.ArgumentParser(description="Sensor Log Generator")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to the configuration file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--identity",
        type=str,
        default="config/identity.json",
        help="Path to the identity file (default: config/identity.json)",
    )
    parser.add_argument(
        "--output-schema",
        action="store_true",
        help="Output the database schema as JSON and exit.",
    )
    parser.add_argument(
        "--generate-identity",
        action="store_true",
        help="Generate a new format identity template with placeholder values and exit.",
    )
    parser.add_argument(
        "--llm-docs",
        action="store_true",
        help="Output comprehensive LLM documentation and exit.",
    )

    args = parser.parse_args()

    if args.output_schema:
        # Generate schema from Pydantic model
        schema_dict = SensorReadingSchema.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2)
        print(schema_json)
        sys.exit(0)
    
    if args.llm_docs:
        # Output LLM documentation
        print_llm_documentation()
        sys.exit(0)
    
    if args.generate_identity:
        # Generate a new format identity template
        from datetime import datetime
        import uuid
        
        template = {
            "sensor_id": "SENSOR_XX_YYY_ZZZZ",
            "location": {
                "city": "YourCity",
                "state": "XX",
                "coordinates": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "timezone": "America/New_York",
                "address": "YourCity, XX, USA"
            },
            "device_info": {
                "manufacturer": "SensorCorp",
                "model": "WeatherStation Pro",
                "firmware_version": "2.1.0",
                "serial_number": f"SENSOR-{uuid.uuid4().hex[:6].upper()}",
                "manufacture_date": datetime.now().strftime("%Y-%m-%d")
            },
            "deployment": {
                "deployment_type": "stationary_unit",
                "installation_date": datetime.now().strftime("%Y-%m-%d"),
                "height_meters": 2.5,
                "orientation_degrees": 0
            },
            "metadata": {
                "instance_id": f"i-{uuid.uuid4().hex[:16]}",
                "identity_generation_timestamp": datetime.now().isoformat(),
                "generation_seed": random.randint(10**20, 10**40),
                "sensor_type": "environmental_monitoring"
            }
        }
        
        print(json.dumps(template, indent=2))
        sys.exit(0)

    # Determine configuration file paths, prioritizing environment variables
    config_file_path = os.environ.get("CONFIG_FILE") or args.config
    identity_file_path = os.environ.get("IDENTITY_FILE") or args.identity

    # Set up basic logging first (before config is fully loaded)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not config_file_path:
        # This condition might be less likely to be hit if args.config has a default
        print(
            "Error: Configuration file path is not set via --config or CONFIG_FILE env var.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not identity_file_path:
        # This condition might be less likely to be hit if args.identity has a default
        print(
            "Error: Identity file path is not set via --identity or IDENTITY_FILE env var.",
            file=sys.stderr,
        )
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
    shutdown_requested = False

    # Set up signal handler for graceful shutdown
    def signal_handler(signum, frame):
        nonlocal shutdown_requested, simulator, stop_watcher_event
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else signum
        logging.info(f"Received {sig_name} signal, initiating graceful shutdown...")
        shutdown_requested = True
        if simulator:
            simulator.stop()
        if stop_watcher_event:
            stop_watcher_event.set()
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

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

        # Get sensor ID and location for logging
        identity = config_manager.get_identity()
        sensor_id = identity.get('sensor_id') or identity.get('id', 'Not Set')
        
        # Handle both old and new location formats
        location_value = identity.get('location')
        if isinstance(location_value, dict):
            location_display = location_value.get('city') or location_value.get('address', 'Not Set')
        else:
            location_display = location_value or 'Not Set'
        
        logging.info(f"Using sensor ID: {sensor_id}")
        logging.info(f"Sensor Location: {location_display}")

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

        # Track start time for diagnostics
        start_time = time.time()
        simulator.run()
        
        # Check if simulator stopped early
        elapsed = time.time() - start_time
        expected_runtime = simulator.run_time_seconds
        if elapsed < expected_runtime * 0.9:  # Allow 10% tolerance
            logging.critical(f"SIMULATOR STOPPED EARLY!")
            logging.critical(f"Expected runtime: {expected_runtime}s, Actual: {elapsed:.1f}s")
            logging.critical(f"Generated {simulator.readings_count} readings, {simulator.error_count} errors")
            if simulator.error_count > 0:
                logging.critical(f"Error rate: {simulator.error_count/max(simulator.readings_count, 1)*100:.2f}%")

    except (KeyboardInterrupt, SystemExit):
        logging.info("Main: Simulation interrupted.")
        if simulator:
            simulator.stop()  # Gracefully stop simulator if possible
    except Exception as e:
        logging.critical(f"Main: CRITICAL UNHANDLED EXCEPTION: {e}", exc_info=True)
        logging.critical("This should never happen - please report this issue!")
    finally:
        logging.info("Main: Beginning shutdown sequence...")
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
