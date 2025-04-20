import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, Optional

import numpy as np
import psutil

from .anomaly import AnomalyGenerator
from .config import ConfigManager
from .database import SensorDatabase
from .enums import FirmwareVersion, Manufacturer, Model
from .location import LocationGenerator
from .monitor import MonitoringServer

# Set up global logger
logger = logging.getLogger(__name__)


class SensorSimulator:
    def __init__(self, config: Dict, identity: Dict):
        """Initialize the sensor simulator.

        Args:
            config: Configuration dictionary loaded from YAML
            identity: Identity dictionary loaded from JSON, including keys:
                'id', 'location', 'manufacturer', 'model', 'firmware_version'
        """
        # Store configuration and identity
        self.config = config
        self.identity = identity
        self.sensor_id = identity.get("id")
        self.location = identity.get("location")
        self.manufacturer = identity.get("manufacturer")
        self.model = identity.get("model")
        self.firmware_version = identity.get("firmware_version")
        self.running = False
        self.logger = logging.getLogger("SensorSimulator")

        # Set up database path for sensor in project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_dir = os.path.join(base_dir, "data", self.sensor_id)
        os.makedirs(db_dir, exist_ok=True)

        self.db_path = os.path.join(db_dir, f"{self.sensor_id}.db")
        self.log_path = os.path.join(db_dir, f"{self.sensor_id}.log")

        # Initialize database
        self.database = SensorDatabase(self.db_path)

        # Set up logging to file
        file_handler = logging.FileHandler(self.log_path)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        self.logger.addHandler(file_handler)

        # Validate sensor configuration
        try:
            self._validate_sensor_config()
        except ValueError as e:
            self.logger.error(str(e))
            raise

        # Get the base directory (where main.py is located)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Initialize location generator with the correct config section
        self.location_generator = LocationGenerator(
            self.config.get("random_location", {})
        )

        # Generate and store the location once at initialization
        self.sensor_location = self._get_initial_location()
        self.logger.info(f"Sensor initialized with location: {self.sensor_location}")

        # Get simulation parameters
        self.readings_per_second = self.config.get("simulation", {}).get(
            "readings_per_second", 1
        )
        self.run_time_seconds = self.config.get("simulation", {}).get(
            "run_time_seconds", 3600
        )

        # Get replica configuration
        self.replica_config = self.config.get("replicas", {})
        self.replica_count = self.replica_config.get("count", 1)
        self.replica_prefix = self.replica_config.get("prefix", "SENSOR")
        self.replica_start_index = self.replica_config.get("start_index", 1)

        try:
            # Load configuration
            self.config_manager = ConfigManager(None, None)
            self.config_manager.config = self.config
            self.config_manager.identity = self.identity
            logging_config = self.config_manager.get_logging_config()
            logging.getLogger().setLevel(
                getattr(logging, logging_config.get("level", "INFO"))
            )

            # Get sensor configuration
            self.sensor_config = self.config_manager.get_sensor_config()

            # Get normal parameters
            self.normal_params = self.config_manager.get_normal_parameters()

            # Initialize anomaly generator with sensor config
            anomaly_config = self.config_manager.get_anomaly_config()
            self.anomaly_generator = AnomalyGenerator(anomaly_config, self.identity)

            # Initialize state
            self.start_time = None
            self.readings_count = 0
            self.error_count = 0
            self.max_consecutive_errors = 10
            self.consecutive_errors = 0

            # Last config check time
            self.last_config_check = time.time()
            self.config_check_interval = 5  # Check for config updates every 5 seconds

            # Memory usage monitoring
            self.process = psutil.Process(os.getpid())
            self.memory_usage = {
                "initial_mb": self._get_memory_usage(),
                "current_mb": 0,
                "peak_mb": 0,
                "last_check_time": time.time(),
                "check_interval": 60,  # Check memory usage every 60 seconds
            }

            # Initialize monitoring server if enabled
            monitoring_config = self.config.get("monitoring", {})
            self.monitoring_enabled = monitoring_config.get("enabled", False)
            self.monitoring_server = None

            if self.monitoring_enabled:
                host = monitoring_config.get("host", "0.0.0.0")
                port = monitoring_config.get("port", 8080)
                self.monitoring_server = MonitoringServer(self, host, port)

            logger.info("Sensor simulator initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing simulator: {str(e)}")
            raise

    def _validate_sensor_config(self):
        """Validate the sensor configuration."""
        # Check for required location
        location = self.identity.get("location")
        if not location:
            raise ValueError("Location is required in identity configuration")

        # Check manufacturer, model, and firmware version
        try:
            manufacturer = Manufacturer(self.identity.get("manufacturer"))
        except ValueError:
            valid_manufacturers = [m.value for m in Manufacturer]
            raise ValueError(
                f"Invalid manufacturer: {self.identity.get('manufacturer')}. "
                f"Valid manufacturers are: {valid_manufacturers}"
            )

        try:
            model = Model(self.identity.get("model"))
        except ValueError:
            valid_models = [m.value for m in Model]
            raise ValueError(
                f"Invalid model: {self.identity.get('model')}. "
                f"Valid models are: {valid_models}"
            )

        try:
            firmware = FirmwareVersion(self.identity.get("firmware_version"))
        except ValueError:
            valid_versions = [v.value for v in FirmwareVersion]
            raise ValueError(
                f"Invalid firmware version: {self.identity.get('firmware_version')}. "
                f"Valid versions are: {valid_versions}"
            )

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

            # Generate value from normal distribution
            value = np.random.normal(mean, std_dev)

            # Apply daily pattern (e.g., temperature higher during the day)
            if param_name == "temperature":
                hour = datetime.now().hour
                # Add a sinusoidal pattern based on hour of day
                # Peak at 3 PM (hour 15), trough at 3 AM (hour 3)
                hour_factor = np.sin((hour - 3) * np.pi / 12)
                value += hour_factor * std_dev

            # Ensure value is within min/max bounds
            value = max(min_val, min(max_val, value))

            return value
        except Exception as e:
            logger.error(f"Error generating parameter value for {param_name}: {e}")
            # Return default values based on parameter type
            defaults = {"temperature": 65.0, "vibration": 2.5, "voltage": 12.0}
            return defaults.get(param_name, 0)

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

    def check_for_config_updates(self):
        """Check if configuration has been updated and apply changes.
        Note: Location will not be changed even if config is reloaded.

        Returns:
            Boolean indicating if configuration was updated
        """
        try:
            current_time = time.time()

            # Only check periodically to avoid overhead
            if current_time - self.last_config_check < self.config_check_interval:
                return False

            self.last_config_check = current_time

            # Check if config has changed (reload_config returns True if changes were applied)
            if not hasattr(self.config_manager, "reload_config"):
                return False

            if self.config_manager.reload_config():
                logger.info("Applying configuration changes to simulator")

                # Update configuration references
                self.config = self.config_manager.config
                self.identity = self.config_manager.identity

                # Update logging configuration
                logging_config = self.config_manager.get_logging_config()
                logging.getLogger().setLevel(
                    getattr(logging, logging_config.get("level", "INFO"))
                )

                # Update simulation parameters
                self.simulation_config = self.config_manager.get_simulation_config()
                self.readings_per_second = self.simulation_config.get(
                    "readings_per_second", 1
                )

                # Only update run_time if simulation hasn't started yet
                if self.start_time is None:
                    self.run_time_seconds = self.simulation_config.get(
                        "run_time_seconds", 3600
                    )

                # Update normal parameters
                self.normal_params = self.config_manager.get_normal_parameters()

                # Update sensor configuration
                old_sensor_id = self.sensor_id
                self.sensor_config = self.config_manager.get_sensor_config()
                self.sensor_id = self.sensor_config.get("id", "SENSOR001")

                if old_sensor_id != self.sensor_id:
                    logger.info(
                        f"Sensor ID changed from {old_sensor_id} to {self.sensor_id}"
                    )

                # Update anomaly generator with new configuration
                anomaly_config = self.config_manager.get_anomaly_config()
                self.anomaly_generator = AnomalyGenerator(anomaly_config, self.identity)

                # Update monitoring configuration
                monitoring_config = self.config.get("monitoring", {})
                monitoring_enabled = monitoring_config.get("enabled", False)

                # Start or stop monitoring server if needed
                if monitoring_enabled and not self.monitoring_enabled:
                    self.monitoring_enabled = True
                    host = monitoring_config.get("host", "0.0.0.0")
                    port = monitoring_config.get("port", 8080)
                    self.monitoring_server = MonitoringServer(self, host, port)
                    if self.running:
                        self.monitoring_server.start()
                elif not monitoring_enabled and self.monitoring_enabled:
                    self.monitoring_enabled = False
                    if self.monitoring_server and self.monitoring_server.running:
                        self.monitoring_server.stop()

                return True

            return False
        except Exception as e:
            logger.error(f"Error checking for configuration updates: {e}")
            return False

    def process_reading(self, reading: Dict) -> bool:
        """Process a single reading.

        Args:
            reading: Dictionary containing the reading data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check for missing data anomaly
            if reading is None:
                self.logger.info("Missing data anomaly detected")
                return True

            # Get current location
            location = self._get_location()
            self.logger.debug(f"Current location: {location}")

            # Add anomaly information
            anomaly_flag = reading.get("anomaly_flag", False)
            anomaly_type = reading.get("anomaly_type", None)

            # Add status code for anomalies
            if anomaly_flag:
                reading["status_code"] = 1  # 1 = anomaly

            # Store in database with sensor identity fields
            self.database.store_reading(
                reading["sensor_id"],
                reading["temperature"],
                reading["vibration"],
                reading["voltage"],
                reading["status_code"],
                anomaly_flag,
                anomaly_type,
                self.identity.get("firmware_version"),
                self.identity.get("model"),
                self.identity.get("manufacturer"),
                location,  # Use the current location
            )

            self.readings_count += 1
            self.consecutive_errors = 0  # Reset error counter on success

            # Log occasional status
            if self.readings_count % 100 == 0:
                self.logger.info(f"Generated {self.readings_count} readings")

            return True
        except Exception as e:
            self.error_count += 1
            self.consecutive_errors += 1
            self.logger.error(f"Error processing reading: {e}")

            # If too many consecutive errors, stop the simulator
            if self.consecutive_errors >= self.max_consecutive_errors:
                self.logger.critical(
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

            # Stop the config file watcher if it's running
            if hasattr(self.config_manager, "stop_file_watcher"):
                self.config_manager.stop_file_watcher()

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
            "firmware_version": self.identity.get("firmware_version"),
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
            sensor_id: ID of the sensor

        Returns:
            Dictionary containing the reading data
        """
        # Get normal parameters
        normal_params = self.config.get("normal_parameters", {})

        # Get current location
        location = self._get_location()
        self.logger.debug(f"Generating reading for location: {location}")

        # Generate base reading
        reading = {
            "timestamp": time.time(),
            "sensor_id": sensor_id,
            "temperature": self._generate_normal_value(
                normal_params.get("temperature", {})
            ),
            "vibration": self._generate_normal_value(
                normal_params.get("vibration", {})
            ),
            "voltage": self._generate_normal_value(normal_params.get("voltage", {})),
            "status_code": 0,
            "anomaly_flag": False,
            "anomaly_type": None,
            "firmware_version": self.identity.get("firmware_version", "1.4"),
            "model": self.identity.get("model", "TempVibe-2000"),
            "manufacturer": self.identity.get("manufacturer", "SensorTech"),
            "location": location,
            "synced": False,
        }

        # Check for anomalies
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

    def _get_initial_location(self) -> str:
        """Get the initial location for the sensor.
        If random_location is enabled in config, generate a random location.
        Otherwise, use the configured location.

        Returns:
            Location string
        """
        # Check if random location is enabled in config
        if self.config.get("random_location", {}).get("enabled", False):
            location_info = self.location_generator.generate_location()
            if location_info:
                city_name, lat, lon = location_info
                location_str = f"{city_name} ({lat:.6f}, {lon:.6f})"
                logger.info(f"Generated random location: {location_str}")
                return location_str
            else:
                logger.warning(
                    "Location generator returned None, using configured location"
                )

        # Use the configured location from identity
        location = self.identity.get("location")
        if not location:
            raise ValueError("Location is required")
        logger.info(f"Using configured location: {location}")
        return location

    def _get_location(self) -> str:
        """Get the current location for the sensor.
        This will always return the initial location, even if config is reloaded.

        Returns:
            Location string
        """
        return self.sensor_location
