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
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from src.config import ConfigManager
from src.database import SensorReadingSchema
from src.location import LocationGenerator
from src.simulator import SensorSimulator
from src.llm_docs import print_llm_documentation, save_llm_documentation

# Pydantic Models for Configuration (config.yaml)


# === Configuration Models (Simplified and Organized) ===

class ParameterRange(BaseModel):
    """Reusable model for parameter ranges."""
    min_val: Union[int, float] = Field(alias="min")
    max_val: Union[int, float] = Field(alias="max")


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    path: str
    backup_enabled: bool
    backup_interval_seconds: Union[int, float]
    max_backup_size_mb: Union[int, float]
    compression_enabled: bool
    
    @field_validator('backup_interval_seconds')
    def validate_backup_interval(cls, v):
        if v < 60:
            raise ValueError("backup_interval_seconds must be at least 60")
        return v
    
    @field_validator('max_backup_size_mb')
    def validate_max_backup_size(cls, v):
        if v <= 0:
            raise ValueError("max_backup_size_mb must be positive")
        return v


class SimulationSettings(BaseModel):
    """Simulation and runtime settings."""
    interval_seconds: Union[int, float]
    replicas_count: Optional[int] = 1
    
    # Location randomization
    random_location_enabled: bool = False
    latitude_range: Optional[List[Union[int, float]]] = None
    longitude_range: Optional[List[Union[int, float]]] = None
    location_update_interval: Optional[Union[int, float]] = None
    
    # Dynamic reloading
    dynamic_reload_enabled: bool = False
    reload_check_interval: Union[int, float] = 5
    
    @field_validator('interval_seconds')
    def validate_interval(cls, v):
        if v <= 0:
            raise ValueError("interval_seconds must be positive")
        return v
    
    @field_validator('replicas_count')
    def validate_replicas(cls, v):
        if v is not None and v < 1:
            raise ValueError("replicas_count must be at least 1")
        return v
    
    @field_validator('latitude_range')
    def validate_latitude(cls, v):
        if v is not None:
            if len(v) != 2:
                raise ValueError("latitude_range must have exactly 2 values")
            if not (-90 <= v[0] <= v[1] <= 90):
                raise ValueError("latitude_range must be within [-90, 90]")
        return v
    
    @field_validator('longitude_range')
    def validate_longitude(cls, v):
        if v is not None:
            if len(v) != 2:
                raise ValueError("longitude_range must have exactly 2 values")
            if not (-180 <= v[0] <= v[1] <= 180):
                raise ValueError("longitude_range must be within [-180, 180]")
        return v


class SensorParameters(BaseModel):
    """Sensor parameter configuration including normal ranges and anomalies."""
    # Normal parameter ranges
    temperature: ParameterRange
    vibration: ParameterRange
    humidity: ParameterRange
    pressure: ParameterRange
    voltage: ParameterRange
    
    # Anomaly settings
    anomalies_enabled: bool = False
    anomaly_probability: Union[int, float] = 0.1
    anomaly_types: Optional[Dict[str, Any]] = None


class AppConfig(BaseModel):
    """Main application configuration."""
    version: Optional[int] = 1
    
    # Core configurations
    database: DatabaseConfig
    simulation: SimulationSettings
    parameters: SensorParameters
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/sensor.log"
    
    # Monitoring
    monitoring_enabled: bool = False
    monitoring_host: str = "0.0.0.0"
    monitoring_port: int = 8080
    
    # Legacy/flexible fields
    sensor: Optional[Dict[str, Any]] = None
    
    model_config = {"extra": "forbid"}
    
    @field_validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log level must be one of {valid_levels}")
        return v.upper()
    
    @model_validator(mode='after')
    def validate_version_requirements(self):
        """Validate version-specific requirements."""
        if self.version >= 2:
            if not self.monitoring_enabled:
                logging.warning(f"Config version {self.version} expects monitoring to be enabled")
        return self


# Helper function to convert old config format to new format
def migrate_config_format(raw_config: Dict) -> Dict:
    """Migrate old config format to simplified format."""
    # Handle database config migration
    db_config = raw_config.get("database", {})
    if "backup_interval_hours" in db_config:
        db_config["backup_interval_seconds"] = db_config.pop("backup_interval_hours", 24) * 3600
    if "max_backup_size_mb" not in db_config:
        db_config["max_backup_size_mb"] = 100  # Default 100MB
    if "compression_enabled" not in db_config:
        db_config["compression_enabled"] = False  # Default no compression
        
    migrated = {
        "version": raw_config.get("version", 1),
        "database": db_config,
        "log_level": raw_config.get("logging", {}).get("level", "INFO"),
        "log_file": raw_config.get("logging", {}).get("file", "logs/sensor.log"),
    }
    
    # Migrate simulation settings
    sim_settings = {}
    if "simulation" in raw_config:
        # Keep readings_per_second if present (don't convert to interval_seconds)
        if "readings_per_second" in raw_config["simulation"]:
            sim_settings["interval_seconds"] = 1.0 / raw_config["simulation"]["readings_per_second"]
        else:
            sim_settings["interval_seconds"] = raw_config["simulation"].get("interval_seconds", 1)
    if "replicas" in raw_config:
        sim_settings["replicas_count"] = raw_config["replicas"].get("count", 1)
    
    # Migrate random location
    if "random_location" in raw_config:
        rl = raw_config["random_location"]
        sim_settings["random_location_enabled"] = rl.get("enabled", False)
        sim_settings["latitude_range"] = rl.get("latitude_range")
        sim_settings["longitude_range"] = rl.get("longitude_range")
        sim_settings["location_update_interval"] = rl.get("update_interval_seconds")
    
    # Migrate dynamic reloading
    if "dynamic_reloading" in raw_config:
        dr = raw_config["dynamic_reloading"]
        sim_settings["dynamic_reload_enabled"] = dr.get("enabled", False)
        sim_settings["reload_check_interval"] = dr.get("check_interval_seconds", 5)
    
    migrated["simulation"] = sim_settings
    
    # Migrate parameters
    params = {}
    if "normal_parameters" in raw_config:
        params.update(raw_config["normal_parameters"])
    if "anomalies" in raw_config:
        an = raw_config["anomalies"]
        params["anomalies_enabled"] = an.get("enabled", False)
        params["anomaly_probability"] = an.get("probability", 0.1)
        params["anomaly_types"] = an.get("types")
    
    # Set default parameters if not provided
    if "temperature" not in params:
        params["temperature"] = {"min": 20, "max": 30}
    if "humidity" not in params:
        params["humidity"] = {"min": 30, "max": 70}
    if "pressure" not in params:
        params["pressure"] = {"min": 1000, "max": 1020}
    if "vibration" not in params:
        params["vibration"] = {"min": 0, "max": 10}
    if "voltage" not in params:
        params["voltage"] = {"min": 3.2, "max": 3.4}
        
    migrated["parameters"] = params
    
    # Migrate monitoring
    if "monitoring" in raw_config:
        mon = raw_config["monitoring"]
        migrated["monitoring_enabled"] = mon.get("enabled", False)
        migrated["monitoring_host"] = mon.get("host", "0.0.0.0")
        migrated["monitoring_port"] = mon.get("port", 8080)
    
    # Keep sensor settings as-is
    if "sensor" in raw_config:
        migrated["sensor"] = raw_config["sensor"]
    
    return migrated


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
    """Load configuration from YAML file and validate its structure."""
    try:
        with open(config_path, "r") as f:
            raw_config_data = yaml.safe_load(f)
        if not isinstance(raw_config_data, dict):
            logging.error(f"Config file {config_path} content must be a dictionary.")
            raise ValueError("Config file content must be a dictionary.")

        # Check if this is old format that needs migration
        needs_migration = any(key in raw_config_data for key in [
            "logging", "random_location", "normal_parameters", 
            "anomalies", "monitoring", "dynamic_reloading", "replicas"
        ])
        
        if needs_migration:
            logging.info("Migrating old config format to new simplified format")
            
            # Store original simulation for later use
            original_simulation = raw_config_data.get("simulation", {})
            
            config_data = migrate_config_format(raw_config_data)
            
            # Add defaults for version 1 configs
            if config_data.get("version", 1) == 1:
                config_data.setdefault("monitoring_enabled", False)
                config_data.setdefault("monitoring_host", "0.0.0.0")
                config_data.setdefault("monitoring_port", 8080)
        else:
            config_data = raw_config_data
            original_simulation = raw_config_data.get("simulation", {})

        # Validate using new Pydantic model
        app_config = AppConfig(**config_data)
        
        # Convert back to dict format expected by rest of code
        result = app_config.model_dump(by_alias=True)
        
        # Restructure to match old format for backward compatibility
        # But keep original simulation settings
        restructured = {
            "version": result["version"],
            "database": result["database"],
            "logging": {
                "level": result["log_level"],
                "file": result["log_file"]
            },
            # Use original simulation config if available, otherwise reconstruct
            "simulation": original_simulation if original_simulation else {
                "interval_seconds": result["simulation"]["interval_seconds"]
            },
            "replicas": {
                "count": result["simulation"].get("replicas_count", 1)
            },
            "random_location": {
                "enabled": result["simulation"].get("random_location_enabled", False),
                "latitude_range": result["simulation"].get("latitude_range", [-90, 90]),
                "longitude_range": result["simulation"].get("longitude_range", [-180, 180]),
                "update_interval_seconds": result["simulation"].get("location_update_interval", 60)
            },
            "normal_parameters": {
                k: v for k, v in result["parameters"].items()
                if k in ["temperature", "humidity", "pressure", "vibration", "voltage"]
            },
            "anomalies": {
                "enabled": result["parameters"].get("anomalies_enabled", False),
                "probability": result["parameters"].get("anomaly_probability", 0.1),
                "types": result["parameters"].get("anomaly_types")
            },
            "monitoring": {
                "enabled": result["monitoring_enabled"],
                "host": result["monitoring_host"],
                "port": result["monitoring_port"]
            },
            "dynamic_reloading": {
                "enabled": result["simulation"].get("dynamic_reload_enabled", False),
                "check_interval_seconds": result["simulation"].get("reload_check_interval", 5)
            }
        }
        
        if result.get("sensor"):
            restructured["sensor"] = result["sensor"]
            
        return restructured

    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML from configuration file {config_path}: {e}")
        raise
    except ValidationError as e:
        logging.error(f"Invalid configuration in {config_path}:\n{e}")
        raise ValueError(f"Invalid configuration: {e}")
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

        # Use shorter intervals to be more responsive to shutdown
        wait_intervals = 10
        interval = check_interval / wait_intervals
        for _ in range(wait_intervals):
            if stop_event.wait(interval):
                break  # Stop event was set
    logger.info(f"File watcher: Thread for {file_path} is stopping.")


def main():
    """Main function to run the sensor simulator."""

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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable extremely verbose debug logging with periodic status updates.",
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
    # Enable debug mode if requested
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            force=True  # Force reconfiguration
        )
        # Set debug level for all loggers
        logging.getLogger().setLevel(logging.DEBUG)
        for name in ['src.simulator', 'src.database', 'src.anomaly', 'SensorDatabase']:
            logging.getLogger(name).setLevel(logging.DEBUG)
        
        logging.info("🔍 DEBUG MODE ENABLED - Extremely verbose logging active")
        logging.debug("Debug flag detected from command line")
        # Store debug flag globally
        os.environ['DEBUG_MODE'] = 'true'
    else:
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

    # Track signal count for forced exit
    signal_count = 0
    
    # Set up signal handler for graceful shutdown
    def signal_handler(signum, frame):
        nonlocal shutdown_requested, simulator, stop_watcher_event, signal_count
        
        signal_count += 1
        
        # Force exit on third signal
        if signal_count >= 3:
            logging.critical("Received 3 signals, forcing immediate exit")
            sys.exit(1)
        
        # Prevent multiple signal handling
        if shutdown_requested:
            logging.warning(f"Already shutting down (signal {signal_count}/3)")
            return
            
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else signum
        logging.info(f"Received {sig_name} signal, initiating graceful shutdown...")
        shutdown_requested = True
        
        # Stop components
        if simulator:
            try:
                simulator.stop()
            except Exception as e:
                logging.error(f"Error stopping simulator: {e}")
        
        if stop_watcher_event:
            try:
                stop_watcher_event.set()
            except Exception as e:
                logging.error(f"Error stopping watchers: {e}")
        
        # Raise KeyboardInterrupt to break out of blocking calls
        if signal_count == 1:
            raise KeyboardInterrupt("Signal received")
    
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

        # Perform startup health checks
        logging.info("Performing startup health checks...")
        
        # 1. Check database is writable
        try:
            reading_count = simulator.database.get_database_stats()["total_readings"]
            logging.info(f"✓ Database is accessible (contains {reading_count} readings)")
        except Exception as e:
            logging.error(f"✗ Database health check failed: {e}")
            raise RuntimeError(f"Database is not accessible: {e}")
        
        # 2. Check disk space availability
        try:
            import shutil
            db_path = config_manager.get_database_config().get("path", "data/sensor_data.db")
            db_dir = os.path.dirname(os.path.abspath(db_path))
            stat = shutil.disk_usage(db_dir)
            free_gb = stat.free / (1024**3)
            min_required_gb = 0.1  # Require at least 100MB free
            if free_gb < min_required_gb:
                raise RuntimeError(f"Insufficient disk space: {free_gb:.2f}GB free, need {min_required_gb}GB")
            logging.info(f"✓ Disk space available ({free_gb:.2f}GB free)")
        except Exception as e:
            if "Insufficient disk space" in str(e):
                logging.error(f"✗ {e}")
                raise
            logging.warning(f"⚠ Could not check disk space: {e}")
        
        # 3. Validate monitoring connectivity (if enabled)
        monitoring_config = config_manager.config.get("monitoring", {})
        if monitoring_config.get("enabled", False):
            try:
                import socket
                host = monitoring_config.get("host", "0.0.0.0")
                port = monitoring_config.get("port", 8080)
                # Just check if port is available (not in use)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("127.0.0.1" if host == "0.0.0.0" else host, port))
                sock.close()
                if result == 0:
                    logging.warning(f"⚠ Monitoring port {port} is already in use")
                else:
                    logging.info(f"✓ Monitoring port {port} is available")
            except Exception as e:
                logging.warning(f"⚠ Could not verify monitoring port: {e}")
        
        logging.info("Health checks completed. Starting simulation...")
        
        # Track start time for diagnostics
        start_time = time.time()
        logging.info(f"Starting simulation: run_time={simulator.run_time_seconds}s, readings_per_second={simulator.readings_per_second}")
        simulator.run()
        
        # Check if simulator stopped early
        elapsed = time.time() - start_time
        expected_runtime = simulator.run_time_seconds
        if elapsed < expected_runtime * 0.9:  # Allow 10% tolerance
            logging.warning(f"Simulation stopped early: expected {expected_runtime}s, ran for {elapsed:.1f}s")
            logging.info(f"Generated {simulator.readings_count} readings, {simulator.error_count} errors")
            if simulator.error_count > 0:
                logging.critical(f"Error rate: {simulator.error_count/max(simulator.readings_count, 1)*100:.2f}%")

    except (KeyboardInterrupt, SystemExit):
        logging.info("Main: Simulation interrupted by signal.")
        shutdown_requested = True
        if simulator:
            simulator.stop()  # Gracefully stop simulator
        if stop_watcher_event:
            stop_watcher_event.set()  # Stop file watchers
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}", exc_info=True)
    finally:
        logging.info("Main: Beginning shutdown sequence...")
        
        # Stop file watchers
        if stop_watcher_event:
            logging.info("Main: Signaling watcher threads to stop...")
            stop_watcher_event.set()
            
            # Give threads a short time to finish
            for thread in watcher_threads:
                if thread.is_alive():
                    logging.debug(f"Main: Waiting for watcher thread {thread.name}...")
                    thread.join(timeout=1.0)  # Short timeout for responsive shutdown
                    if thread.is_alive():
                        logging.debug(f"Main: Watcher thread {thread.name} still running, abandoning.")

        # Simulator's own cleanup (like DB close) happens in its run() finally block.
        logging.info("Main: Shutdown complete.")


if __name__ == "__main__":
    main()
