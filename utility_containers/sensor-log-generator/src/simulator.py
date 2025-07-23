import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import psutil
from pydantic import ValidationError

from .anomaly import AnomalyGenerator
from .config import ConfigManager
from .database import SensorDatabase, SensorReadingSchema
from .monitor import MonitoringServer

# Set up global logger
logger = logging.getLogger(__name__)


class SensorSimulator:
    def __init__(self, config_manager: ConfigManager):
        """Initialize the sensor simulator.

        Args:
            config_manager: An instance of ConfigManager providing configuration and identity.
        """
        self.config_manager = config_manager
        self.identity = self.config_manager.get_identity()  # Get initial identity

        # Handle both old and new identity formats
        self.sensor_id = self.identity.get("sensor_id") or self.identity.get("id")
        # Manufacturer, model, and firmware_version will be set by _validate_sensor_config
        self.running = False

        # Initialize location properties including timezone
        # Extract location data based on format (nested or flat)
        location_data = self.identity.get("location")
        if isinstance(location_data, dict):
            # New nested format
            self.city_name = location_data.get("city") or location_data.get("address")
            coords = location_data.get("coordinates", {})
            self.latitude = coords.get("latitude", self.identity.get("latitude"))
            self.longitude = coords.get("longitude", self.identity.get("longitude"))
            self.timezone = location_data.get("timezone", self.identity.get("timezone", "UTC"))
        else:
            # Legacy flat format
            self.city_name = location_data
            self.latitude = self.identity.get("latitude")
            self.longitude = self.identity.get("longitude")
            self.timezone = self.identity.get("timezone", "UTC")
        try:
            # Validate IANA timezone and get offset string upon initialization
            self.timezone_offset_str = self._get_offset_str(time.time(), self.timezone)
            logger.info(
                f"SensorSimulator initialized with IANA timezone: '{self.timezone}' (Offset: '{self.timezone_offset_str}')"
            )
        except ZoneInfoNotFoundError:  # Catch if IANA name is invalid
            logger.error(
                f"Invalid IANA timezone name provided in identity: '{self.timezone}'. Exiting."
            )
            sys.exit(1)

        # Get database path from config
        db_path = self.config_manager.get_database_config().get("path")
        if not db_path:
            raise ValueError("Database path not specified in config.yaml")

        # Ensure the database directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Initialize database
        self.database = SensorDatabase(db_path)

        # Set up logging to file (using config from ConfigManager)
        log_file = self.config_manager.get_logging_config().get("file")
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            logger.addHandler(file_handler)

        # Validate sensor configuration (uses self.identity, which is from config_manager)
        try:
            self._validate_sensor_config()
        except ValueError as e:
            logger.error(str(e))
            raise

        # Generate and store the location once at initialization (validates and logs)
        self._get_initial_location()

        # Get simulation parameters
        sim_config = self.config_manager.get_simulation_config()
        self.readings_per_second = sim_config.get("readings_per_second", 1)
        self.run_time_seconds = sim_config.get("run_time_seconds", 3600)

        # Get replica configuration
        self.replica_config = self.config_manager.config.get("replicas") or {}
        self.replica_count = self.replica_config.get("count", 1)
        self.replica_prefix = self.replica_config.get("prefix", "SENSOR")
        self.replica_start_index = self.replica_config.get("start_index", 1)

        try:
            # ConfigManager is now passed in, no internal initialization.

            logging_config = self.config_manager.get_logging_config()
            logging.getLogger().setLevel(
                getattr(logging, logging_config.get("level", "INFO"))
            )

            self.sensor_config = self.config_manager.get_sensor_config()
            self.normal_params = self.config_manager.get_normal_parameters() or {}

            # Anomaly generator initialized with config and current identity
            anomaly_cfg = self.config_manager.get_anomaly_config() or {}
            self.anomaly_generator = AnomalyGenerator(anomaly_cfg, self.identity)

            # Initialize state
            self.start_time = None
            self.readings_count = 0
            self.error_count = 0
            self.max_consecutive_errors = 10
            self.consecutive_errors = 0

            # Memory usage monitoring
            self.process = psutil.Process(os.getpid())
            self.memory_usage = {
                "initial_mb": self._get_memory_usage(),
                "current_mb": 0,
                "peak_mb": 0,
                "last_check_time": time.time(),
                "check_interval": 60,
            }

            # Initialize monitoring server if enabled
            try:
                monitoring_cfg = self.config_manager.config.get("monitoring") or {}
                self.monitoring_enabled = monitoring_cfg.get("enabled", False) if monitoring_cfg else False
                self.monitoring_server = None
            except Exception as e:
                logger.warning(f"Failed to get monitoring config: {e}. Disabling monitoring.")
                monitoring_cfg = {}
                self.monitoring_enabled = False
                self.monitoring_server = None

            if self.monitoring_enabled:
                host = monitoring_cfg.get("host", "0.0.0.0")
                port = monitoring_cfg.get("port", 8080)
                self.monitoring_server = MonitoringServer(self, host, port)

            logger.info("Sensor simulator initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing simulator: {str(e)}")
            raise

    def _validate_sensor_config(self):
        """Validate the sensor configuration using self.identity and assign enum attributes."""
        current_identity = self.identity
        
        # Check if location exists (handle both formats)
        location = current_identity.get("location")
        if not location:
            raise ValueError("Location is required in identity configuration")
        
        # Extract device info based on format
        device_info = current_identity.get("device_info", {})
        
        # Manufacturer - check nested first, then flat
        manufacturer_val = device_info.get("manufacturer") or current_identity.get("manufacturer")
        if manufacturer_val is None:
            raise ValueError("Manufacturer is required in identity configuration")
        # Accept any string as manufacturer
        self.manufacturer = manufacturer_val

        # Model - check nested first, then flat
        model_val = device_info.get("model") or current_identity.get("model")
        if model_val is None:
            raise ValueError("Model is required in identity configuration")
        # Accept any string as model
        self.model = model_val

        # Firmware Version - check nested first, then flat
        firmware_val = device_info.get("firmware_version") or current_identity.get("firmware_version")
        if firmware_val is None:
            raise ValueError("Firmware version is required in identity configuration")
        # Validate SemVer format
        if not self._is_valid_semver(firmware_val):
            raise ValueError(
                f"Invalid firmware version '{firmware_val}'. "
                f"Must be a valid semantic version (e.g., 1.0.0, 2.1.3-beta, 1.0.0+build123)"
            )
        self.firmware_version = firmware_val
        
        # Store additional device info if available
        self.serial_number = device_info.get("serial_number") if device_info else None
        self.manufacture_date = device_info.get("manufacture_date") if device_info else None
        
        # Store deployment info if available
        deployment = current_identity.get("deployment") or {}
        self.deployment_type = deployment.get("deployment_type") if deployment else None
        self.installation_date = deployment.get("installation_date") if deployment else None
        self.height_meters = deployment.get("height_meters") if deployment else None
        self.orientation_degrees = deployment.get("orientation_degrees") if deployment else None
        
        # Store metadata if available
        metadata = current_identity.get("metadata") or {}
        self.instance_id = metadata.get("instance_id") if metadata else None
        self.sensor_type = metadata.get("sensor_type") if metadata else None

    def generate_normal_reading(self):
        """Generate a normal sensor reading based on configured parameters.

        Returns:
            Dictionary containing sensor reading values
        """
        try:
            reading = {
                "sensor_id": self.sensor_id,
                "temperature": self._generate_parameter_value("temperature"),
                "vibration": self._generate_parameter_value("vibration"),
                "voltage": self._generate_parameter_value("voltage"),
                "status_code": 0,  # 0 = normal operation
            }
            return reading
        except Exception as e:
            logger.error(f"Error generating normal reading: {e}")
            # Return a fallback reading with default values
            return {
                "sensor_id": self.sensor_id,
                "temperature": 65.0,
                "vibration": 2.5,
                "voltage": 12.0,
                "status_code": 0,
            }

    def _generate_parameter_value(self, param_name):
        """Generate a value for a specific parameter based on its configuration.

        Args:
            param_name: Name of the parameter to generate a value for

        Returns:
            Generated parameter value
        """
        try:
            param_config = self.normal_params.get(param_name, {})
            mean = param_config.get("mean", 0)
            std_dev = param_config.get("std_dev", 1)
            min_val = param_config.get("min", float("-inf"))
            max_val = param_config.get("max", float("inf"))

            # Generate base value with normal distribution
            value = random.gauss(mean, std_dev)

            # Seasonal variation based on hour of the day (UTC)
            hour = datetime.now(timezone.utc).hour
            seasonal_factor = (
                np.sin(2 * np.pi * (hour - 6) / 24) * std_dev * 0.1
            )  # Peak around midday
            value += seasonal_factor

            # Clamp value within min/max range
            value = max(min_val, min(value, max_val))

            return value
        except Exception as e:
            logger.error(f"Error generating value for {param_name}: {e}")
            # Return mean value as fallback
            return self.normal_params.get(param_name, {}).get("mean", 0)

    def _get_memory_usage(self):
        """Get current memory usage in MB.

        Returns:
            Current memory usage in MB
        """
        try:
            # Get memory info in bytes and convert to MB
            memory_info = self.process.memory_info()
            return memory_info.rss / (1024 * 1024)
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return 0

    def _check_memory_usage(self):
        """Check and log memory usage periodically.

        Returns:
            Dictionary with memory usage information
        """
        current_time = time.time()
        if (
            current_time - self.memory_usage["last_check_time"]
            < self.memory_usage["check_interval"]
        ):
            return self.memory_usage

        try:
            current_mb = self._get_memory_usage()
            self.memory_usage["current_mb"] = current_mb
            self.memory_usage["peak_mb"] = max(self.memory_usage["peak_mb"], current_mb)
            self.memory_usage["last_check_time"] = current_time

            # Calculate memory growth
            initial_mb = self.memory_usage["initial_mb"]
            growth_mb = current_mb - initial_mb
            growth_percent = (growth_mb / initial_mb * 100) if initial_mb > 0 else 0

            # Log memory usage if it has grown significantly
            if growth_percent > 10:  # Log if memory usage has grown by more than 10%
                logger.info(
                    f"Memory usage: {current_mb:.2f} MB (initial: {initial_mb:.2f} MB, "
                    f"growth: {growth_mb:.2f} MB, {growth_percent:.1f}%)"
                )

            # Add growth information to memory usage dict
            self.memory_usage["growth_mb"] = growth_mb
            self.memory_usage["growth_percent"] = growth_percent

            return self.memory_usage
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
            return self.memory_usage

    def handle_config_updated(self):
        """Apply changes after the main configuration (config.yaml) has been updated."""
        logger.info(
            "Applying configuration changes to simulator (triggered externally)"
        )

        # Update logging configuration
        logging_config = self.config_manager.get_logging_config()
        logging.getLogger().setLevel(
            getattr(logging, logging_config.get("level", "INFO"))
        )

        # Update simulation parameters
        simulation_config = self.config_manager.get_simulation_config()
        self.readings_per_second = simulation_config.get(
            "readings_per_second", self.readings_per_second
        )
        # Note: run_time_seconds is typically set at init and not changed mid-simulation.

        # Update normal parameters
        self.normal_params = self.config_manager.get_normal_parameters() or {}

        # Update sensor configuration (from config.yaml's "sensor" section if used for this)
        self.sensor_config = self.config_manager.get_sensor_config()
        # If sensor_id could be overridden by general config, handle here.
        # For now, assuming sensor_id is primarily from identity.

        # Update anomaly generator with new configuration (it uses current identity)
        anomaly_config = self.config_manager.get_anomaly_config() or {}
        self.anomaly_generator = AnomalyGenerator(anomaly_config, self.identity)

        # Update monitoring configuration
        monitoring_config = self.config_manager.config.get("monitoring", {})
        monitoring_enabled = monitoring_config.get("enabled", False)
        current_monitoring_host = (
            self.monitoring_server.host if self.monitoring_server else None
        )
        current_monitoring_port = (
            self.monitoring_server.port if self.monitoring_server else None
        )

        if monitoring_enabled:
            new_host = monitoring_config.get("host", "0.0.0.0")
            new_port = monitoring_config.get("port", 8080)
            if not self.monitoring_enabled or (
                self.monitoring_server
                and (
                    current_monitoring_host != new_host
                    or current_monitoring_port != new_port
                )
            ):
                logger.info(
                    f"Monitoring server config changed or being enabled. Host: {new_host}, Port: {new_port}"
                )
                if self.monitoring_server and self.monitoring_server.running:
                    self.monitoring_server.stop()
                self.monitoring_server = MonitoringServer(self, new_host, new_port)
                if self.running:
                    self.monitoring_server.start()
            self.monitoring_enabled = True
        elif not monitoring_enabled and self.monitoring_enabled:
            logger.info("Disabling monitoring server.")
            if self.monitoring_server and self.monitoring_server.running:
                self.monitoring_server.stop()
            self.monitoring_server = None
            self.monitoring_enabled = False

        logger.info("Configuration update processed.")

    def handle_identity_updated(self):
        """Handle updates to the sensor's identity if configuration changes."""
        try:
            new_identity = self.config_manager.get_identity()
            if new_identity != self.identity:
                logger.info(
                    f"Identity updated. Old: {self.identity}, New: {new_identity}"
                )
                old_iana_timezone = self.timezone
                self.identity = new_identity
                # Re-fetch identity-dependent attributes
                self.sensor_id = self.identity.get("sensor_id") or self.identity.get("id")
                
                # Extract location data based on format
                location_data = self.identity.get("location")
                if isinstance(location_data, dict):
                    # New nested format
                    self.city_name = location_data.get("city") or location_data.get("address")
                    coords = location_data.get("coordinates", {})
                    self.latitude = coords.get("latitude", self.identity.get("latitude"))
                    self.longitude = coords.get("longitude", self.identity.get("longitude"))
                    self.timezone = location_data.get("timezone", self.identity.get("timezone", "UTC"))
                else:
                    # Legacy flat format
                    self.city_name = location_data
                    self.latitude = self.identity.get("latitude")
                    self.longitude = self.identity.get("longitude")
                    self.timezone = self.identity.get("timezone", "UTC")

                try:
                    # Update timezone_offset_str based on new IANA timezone
                    self.timezone_offset_str = self._get_offset_str(
                        time.time(), self.timezone
                    )
                    logger.info(
                        f"IANA Timezone updated via handle_identity_updated to: '{self.timezone}' (New Offset: '{self.timezone_offset_str}')"
                    )
                except ZoneInfoNotFoundError:
                    logger.error(
                        f"Invalid IANA timezone name provided in updated identity: '{self.timezone}'. Using previous offset: '{self.timezone_offset_str}'."
                    )
                    # Optionally, revert self.timezone to old_iana_timezone or handle error more gracefully
                    self.timezone = old_iana_timezone  # Revert to last valid IANA name
                    # The self.timezone_offset_str will retain its old value in this error case if not re-assigned

                # Re-validate and update components that depend on identity
                self._validate_sensor_config()
                self._get_initial_location()  # May need to re-fetch/re-validate location dependent data
                if self.anomaly_generator:
                    self.anomaly_generator.update_identity(self.identity)
                logger.info(
                    "Sensor identity and dependent components updated successfully."
                )
            else:
                logger.debug("Identity checked, no changes detected.")
        except Exception as e:
            logger.error(f"Error handling identity update: {e}")

    def process_reading(self, reading: Dict) -> bool:
        """Process a single reading.

        Args:
            reading: Dictionary containing the reading data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current location
            location = self._get_location()
            logger.debug(f"Current location: {location}")

            # Add anomaly information
            anomaly_flag = reading.get("anomaly_flag", False)
            anomaly_type = reading.get("anomaly_type", None)

            # Get the current timestamp and the IANA timezone from the simulator's identity
            current_timestamp_unix = time.time()
            # Convert Unix timestamp to ISO 8601 format for Pydantic model
            iso_timestamp = datetime.fromtimestamp(
                current_timestamp_unix, tz=timezone.utc
            ).isoformat(timespec="milliseconds")

            # Extract device info and other metadata based on identity format
            device_info = self.identity.get("device_info", {})
            
            # Prepare data for Pydantic model
            reading_data_for_schema = {
                "timestamp": iso_timestamp,
                "sensor_id": reading["sensor_id"],
                "temperature": reading.get("temperature"),
                "humidity": reading.get("humidity"),
                "pressure": reading.get("pressure"),
                "vibration": reading.get("vibration"),
                "voltage": reading.get("voltage"),
                "status_code": reading.get("status_code", 0 if not anomaly_flag else 1),
                "anomaly_flag": anomaly_flag,
                "anomaly_type": anomaly_type,
                "firmware_version": device_info.get("firmware_version") or self.identity.get("firmware_version"),
                "model": device_info.get("model") or self.identity.get("model"),
                "manufacturer": device_info.get("manufacturer") or self.identity.get("manufacturer"),
                "location": self.city_name,  # Pass city name
                "latitude": self.latitude,
                "longitude": self.longitude,
                "original_timezone": self.timezone_offset_str,  # Pass the stored offset string
                "synced": False,  # Default value for new readings
                # New fields from enhanced identity
                "serial_number": getattr(self, 'serial_number', None),
                "manufacture_date": getattr(self, 'manufacture_date', None),
                "deployment_type": getattr(self, 'deployment_type', None),
                "installation_date": getattr(self, 'installation_date', None),
                "height_meters": getattr(self, 'height_meters', None),
                "orientation_degrees": getattr(self, 'orientation_degrees', None),
                "instance_id": getattr(self, 'instance_id', None),
                "sensor_type": getattr(self, 'sensor_type', None),
            }

            # Create and validate the reading with Pydantic model
            try:
                sensor_reading_instance = SensorReadingSchema(**reading_data_for_schema)
            except ValidationError as ve:
                logger.error(
                    f"Pydantic validation error while processing reading: {ve}"
                )
                # Optionally, handle this error more gracefully, e.g., by storing
                # the raw data in a separate "error" table or logging more details.
                self.error_count += 1
                self.consecutive_errors += 1
                # Check for max consecutive errors even for validation failures
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.critical(
                        f"Too many consecutive Pydantic validation errors ({self.consecutive_errors}). Stopping simulator."
                    )
                    return False  # Stop the simulator
                return False  # Indicate failure for this reading

            # Store in database using the Pydantic model instance
            self.database.store_reading(sensor_reading_instance)

            logger.debug(
                f"Storing reading with timezone_offset_str: '{self.timezone_offset_str}' via Pydantic model"
            )

            self.readings_count += 1
            self.consecutive_errors = 0  # Reset error counter on success

            # Log occasional status
            if self.readings_count % 100 == 0:
                logger.info(f"Generated {self.readings_count} readings")

            return True
        except Exception as e:
            self.error_count += 1
            self.consecutive_errors += 1
            logger.error(f"Error processing reading: {e}")

            # If too many consecutive errors, stop the simulator
            if self.consecutive_errors >= self.max_consecutive_errors:
                logger.critical(
                    f"Too many consecutive errors ({self.consecutive_errors}). Stopping simulator."
                )
                return False

            return False

    def run(self):
        """Run the simulator for the configured duration."""
        self.running = True
        self.start_time = time.time()
        logger.info(f"Starting sensor simulator for {self.run_time_seconds} seconds")
        logger.info(f"Generating {self.readings_per_second} readings per second")

        # Start monitoring server if enabled
        if self.monitoring_enabled and self.monitoring_server:
            self.monitoring_server.start()

        try:
            while self.running:
                # Check if we've reached the end of the simulation
                elapsed = time.time() - self.start_time
                if elapsed >= self.run_time_seconds:
                    logger.info(f"Simulation complete after {elapsed:.2f} seconds")
                    break

                # Generate and process a reading
                reading = self.generate_reading(self.sensor_id)
                if not self.process_reading(reading):
                    logger.error("Failed to process reading")
                    break

                # Sleep to maintain the configured rate
                sleep_time = 1.0 / self.readings_per_second
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Simulation stopped by user")
        except Exception as e:
            logger.error(f"Error during simulation: {e}")
        finally:
            # Stop the monitoring server if it's running
            if self.monitoring_server and self.monitoring_server.running:
                self.monitoring_server.stop()

            # Close database connection
            if hasattr(self, "database"):
                self.database.close()

            # Log summary
            success_rate = 0
            if self.readings_count > 0:
                success_rate = 100 - (self.error_count / self.readings_count * 100)

            # Log memory usage
            memory_usage = self._check_memory_usage()
            initial_mb = memory_usage.get("initial_mb", 0)
            current_mb = memory_usage.get("current_mb", 0)
            peak_mb = memory_usage.get("peak_mb", 0)

            logger.info(
                f"Simulation ended. Generated {self.readings_count} readings with "
                f"{self.error_count} errors ({success_rate:.2f}% success rate). "
                f"Memory usage: {current_mb:.2f} MB (peak: {peak_mb:.2f} MB, "
                f"initial: {initial_mb:.2f} MB)"
            )

            self.running = False

    def stop(self):
        """Stop the simulator."""
        if self.running:
            logger.info("Stopping simulator...")
            self.running = False

    def get_status(self):
        """Get the current status of the simulator.

        Returns:
            Dictionary containing simulator status information
        """
        elapsed = 0
        if self.start_time:
            elapsed = time.time() - self.start_time

        remaining = max(0, self.run_time_seconds - elapsed)

        # Get current memory usage
        memory_usage = self._check_memory_usage()

        return {
            "running": self.running,
            "readings_count": self.readings_count,
            "error_count": self.error_count,
            "elapsed_seconds": elapsed,
            "remaining_seconds": remaining,
            "readings_per_second": self.readings_per_second,
            "sensor_id": self.sensor_id,
            "location": {  # Added location dictionary
                "city": self.city_name,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "timezone": self.timezone,
                "timezone_offset": self.timezone_offset_str,
            },
            "firmware_version": self.firmware_version,  # Return enum member
            "model": self.model,  # Return enum member
            "manufacturer": self.manufacturer,  # Return enum member
            "database_healthy": self.database.is_healthy()
            if hasattr(self, "database")
            else False,
            "memory_usage_mb": memory_usage.get("current_mb", 0),
            "memory_peak_mb": memory_usage.get("peak_mb", 0),
            "memory_growth_percent": memory_usage.get("growth_percent", 0),
            "monitoring_enabled": self.monitoring_enabled,
            "monitoring_server_running": self.monitoring_server.running
            if self.monitoring_server
            else False,
        }

    def generate_reading(self, sensor_id: str) -> Dict:
        """Generate a single sensor reading.

        Args:
            sensor_id: ID of the sensor (note: self.sensor_id is the primary one)

        Returns:
            Dictionary containing the reading data
        """
        # Get normal parameters from ConfigManager
        normal_params = self.config_manager.get_normal_parameters()

        # Generate base reading
        reading = {
            "timestamp": time.time(),
            "sensor_id": sensor_id,  # Use provided sensor_id, usually self.sensor_id
            "temperature": self._generate_normal_value(
                normal_params.get("temperature", {})
            ),
            "vibration": self._generate_normal_value(
                normal_params.get("vibration", {})
            ),
            "humidity": self._generate_normal_value(normal_params.get("humidity", {})),
            "pressure": self._generate_normal_value(normal_params.get("pressure", {})),
            "voltage": self._generate_normal_value(normal_params.get("voltage", {})),
            "status_code": 0,
            "anomaly_flag": False,
            "anomaly_type": None,
            # Use current identity for these fields
            "firmware_version": self.identity.get("firmware_version"),
            "model": self.identity.get("model"),
            "manufacturer": self.identity.get("manufacturer"),
            "location": self.city_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "synced": False,
        }

        # Check for anomalies (AnomalyGenerator uses current config and identity)
        if self.anomaly_generator.should_generate_anomaly():
            anomaly_type = self.anomaly_generator.select_anomaly_type()
            if anomaly_type:
                self.anomaly_generator.start_anomaly(anomaly_type)
                modified_reading, is_anomaly, anomaly_type = (
                    self.anomaly_generator.apply_anomaly(reading, anomaly_type)
                )
                if modified_reading:
                    reading = modified_reading
                    reading["anomaly_flag"] = is_anomaly
                    reading["anomaly_type"] = anomaly_type
                    reading["status_code"] = 1

        return reading

    def _generate_normal_value(self, params: Dict) -> float:
        """Generate a value from a normal distribution with bounds.

        Args:
            params: Dictionary containing mean, std_dev, min, and max

        Returns:
            Generated value
        """
        mean = params.get("mean", 0)
        std_dev = params.get("std_dev", 1)
        min_val = params.get("min", float("-inf"))
        max_val = params.get("max", float("inf"))

        while True:
            value = random.gauss(mean, std_dev)
            if min_val <= value <= max_val:
                return value

    def _get_initial_location(self) -> None:
        """Get and validate the initial location for the sensor from self.identity.
        self.identity is expected to have complete and valid location information
        as processed by main.py and passed via ConfigManager.

        Sets the location properties (city_name, latitude, longitude) on the instance.
        Raises ValueError if self.identity has incomplete location information.
        """
        # self.identity is already set from config_manager in __init__
        # This method now primarily validates and logs the location from self.identity.
        current_identity_data = self.identity

        # Extract location data based on format (already done in __init__, but re-validate here)
        location_data = current_identity_data.get("location")
        if isinstance(location_data, dict):
            # New nested format
            self.city_name = location_data.get("city") or location_data.get("address")
            coords = location_data.get("coordinates", {})
            self.latitude = coords.get("latitude", current_identity_data.get("latitude"))
            self.longitude = coords.get("longitude", current_identity_data.get("longitude"))
        else:
            # Legacy flat format
            self.city_name = location_data
            self.latitude = current_identity_data.get("latitude")
            self.longitude = current_identity_data.get("longitude")
        # self.timezone is already set in __init__ from self.identity

        if not (
            isinstance(self.city_name, str)
            and self.city_name.strip()
            and isinstance(self.latitude, (int, float))
            and isinstance(self.longitude, (int, float))
        ):
            missing_fields = []
            if not (isinstance(self.city_name, str) and self.city_name.strip()):
                missing_fields.append("'location' (non-empty string)")
            if not isinstance(self.latitude, (int, float)):
                missing_fields.append("'latitude' (number)")
            if not isinstance(self.longitude, (int, float)):
                missing_fields.append("'longitude' (number)")

            error_msg = (
                f"SensorSimulator received identity with incomplete location information. "
                f"Missing/invalid fields: {', '.join(missing_fields)}. "
                "This should have been resolved by main.py before simulator initialization."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"SensorSimulator using location from processed identity: {self.city_name} "
            f"(Lat: {self.latitude:.6f}, Lon: {self.longitude:.6f})"
        )

    def _get_location(self) -> str:
        """Get the current location for the sensor.
        This will always return the initial location, even if config is reloaded.

        Returns:
            Location string (just the city name)
        """
        return self.city_name

    def _is_valid_semver(self, version: str) -> bool:
        """Validate if a string is a valid semantic version.
        
        Args:
            version: Version string to validate
            
        Returns:
            True if valid SemVer, False otherwise
        """
        # SemVer regex pattern
        # Matches: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
        semver_pattern = r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'
        return bool(re.match(semver_pattern, version))

    def _get_offset_str(self, unix_timestamp: float, iana_timezone_name: str) -> str:
        """
        Calculates the UTC offset string (e.g., '-04:00') for a given Unix timestamp
        and IANA timezone name.
        """
        if not iana_timezone_name:
            logger.warning(
                "No IANA timezone name provided to _get_offset_str, defaulting to UTC offset +00:00."
            )
            return "+00:00"

        try:
            # Create a datetime object from the Unix timestamp, making it timezone-aware (UTC)
            # then convert to the target timezone to get the correct offset for that moment.
            dt_utc = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
            target_tz = ZoneInfo(iana_timezone_name)
            dt_target = dt_utc.astimezone(target_tz)

            offset = dt_target.utcoffset()
            if offset is not None:
                total_seconds = offset.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                return f"{hours:+03d}:{minutes:02d}"  # Format: +HH:MM or -HH:MM
            else:  # Should not happen if ZoneInfo object is valid
                logger.warning(
                    f"Could not determine offset for {iana_timezone_name} at {unix_timestamp}, using +00:00."
                )
                return "+00:00"

        except ZoneInfoNotFoundError:
            logger.warning(
                f"Timezone '{iana_timezone_name}' not found using zoneinfo. Defaulting to UTC offset +00:00."
            )
            return "+00:00"
        except Exception as e:
            logger.error(
                f"Error calculating offset for timezone '{iana_timezone_name}': {e}. Defaulting to +00:00."
            )
            return "+00:00"
