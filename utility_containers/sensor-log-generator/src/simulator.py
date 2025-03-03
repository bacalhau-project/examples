import logging
import os
import random
import time
from datetime import datetime

import numpy as np
import psutil

from .anomaly import AnomalyGenerator, AnomalyType
from .config import ConfigManager
from .database import SensorDatabase
from .monitor import MonitoringServer


class SensorSimulator:
    def __init__(self, config_path=None, identity_path=None):
        """Initialize the sensor simulator.

        Args:
            config_path: Path to configuration file
            identity_path: Path to node identity file
        """
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        try:
            # Load configuration
            self.config_manager = ConfigManager(config_path, identity_path)
            self.config = self.config_manager.config
            logging_config = self.config_manager.get_logging_config()
            logging.getLogger().setLevel(
                getattr(logging, logging_config.get("level", "INFO"))
            )

            # Initialize database
            db_config = self.config_manager.get_database_config()
            self.db = SensorDatabase(
                db_config.get("path", "sensor_data.db"),
                batch_size=db_config.get("batch_size", 100),
            )

            # Get sensor configuration
            self.sensor_config = self.config_manager.get_sensor_config()
            self.sensor_id = self.sensor_config.get("id", "SENSOR001")

            # Initialize anomaly generator with sensor config
            anomaly_config = self.config_manager.get_anomaly_config()
            self.anomaly_generator = AnomalyGenerator(
                anomaly_config, self.sensor_config
            )

            # Get simulation parameters
            self.simulation_config = self.config_manager.get_simulation_config()
            self.readings_per_second = self.simulation_config.get(
                "readings_per_second", 1
            )
            self.run_time_seconds = self.simulation_config.get("run_time_seconds", 3600)

            # Get normal parameters
            self.normal_params = self.config_manager.get_normal_parameters()

            # Initialize state
            self.running = False
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

            logging.info("Sensor simulator initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing simulator: {e}")
            raise

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
            logging.error(f"Error generating normal reading: {e}")
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
            logging.error(f"Error generating parameter value for {param_name}: {e}")
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
            logging.error(f"Error getting memory usage: {e}")
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
                logging.info(
                    f"Memory usage: {current_mb:.2f} MB (initial: {initial_mb:.2f} MB, "
                    f"growth: {growth_mb:.2f} MB, {growth_percent:.1f}%)"
                )

            # Add growth information to memory usage dict
            self.memory_usage["growth_mb"] = growth_mb
            self.memory_usage["growth_percent"] = growth_percent

            return self.memory_usage
        except Exception as e:
            logging.error(f"Error checking memory usage: {e}")
            return self.memory_usage

    def check_for_config_updates(self):
        """Check if configuration has been updated and apply changes.

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
                logging.info("Applying configuration changes to simulator")

                # Update configuration references
                self.config = self.config_manager.config

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
                    logging.info(
                        f"Sensor ID changed from {old_sensor_id} to {self.sensor_id}"
                    )

                # Update anomaly generator with new configuration
                anomaly_config = self.config_manager.get_anomaly_config()
                self.anomaly_generator = AnomalyGenerator(
                    anomaly_config, self.sensor_config
                )

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
            logging.error(f"Error checking for configuration updates: {e}")
            return False

    def process_reading(self):
        """Generate a reading, potentially apply anomalies, and store in database.

        Returns:
            Boolean indicating if the reading was processed successfully
        """
        try:
            # Check for configuration updates
            self.check_for_config_updates()

            # Periodically check memory usage
            self._check_memory_usage()

            # Generate normal reading
            reading = self.generate_normal_reading()

            # Check for anomalies
            anomaly_flag = False
            anomaly_type = None

            # Check if we should start a new anomaly
            if self.anomaly_generator.should_generate_anomaly():
                new_anomaly_type = self.anomaly_generator.select_anomaly_type()
                if new_anomaly_type:
                    self.anomaly_generator.start_anomaly(new_anomaly_type)

            # Check for active anomalies and apply them
            for anomaly_type_enum in AnomalyType:
                anomaly_type_str = anomaly_type_enum.value
                if self.anomaly_generator.is_anomaly_active(anomaly_type_str):
                    modified_reading, is_anomaly, applied_type = (
                        self.anomaly_generator.apply_anomaly(reading, anomaly_type_str)
                    )

                    if is_anomaly:
                        reading = modified_reading
                        anomaly_flag = True
                        anomaly_type = applied_type
                        break

            # If reading is None, it simulates missing data
            if reading is None:
                logging.info(f"Missing data anomaly - skipping database insert")
                return True

            # Add status code for anomalies
            if anomaly_flag:
                reading["status_code"] = 1  # 1 = anomaly

            # Store in database with sensor identity fields
            self.db.insert_reading(
                reading["sensor_id"],
                reading["temperature"],
                reading["vibration"],
                reading["voltage"],
                reading["status_code"],
                anomaly_flag,
                anomaly_type,
                self.sensor_config.get("firmware_version"),
                self.sensor_config.get("model"),
                self.sensor_config.get("manufacturer"),
                self.sensor_config.get("location"),
            )

            self.readings_count += 1
            self.consecutive_errors = 0  # Reset error counter on success

            # Log occasional status
            if self.readings_count % 100 == 0:
                logging.info(f"Generated {self.readings_count} readings")

            return True
        except Exception as e:
            self.error_count += 1
            self.consecutive_errors += 1
            logging.error(f"Error processing reading: {e}")

            # If too many consecutive errors, stop the simulator
            if self.consecutive_errors >= self.max_consecutive_errors:
                logging.critical(
                    f"Too many consecutive errors ({self.consecutive_errors}). Stopping simulator."
                )
                self.stop()

            return False

    def run(self):
        """Run the simulator for the configured duration."""
        self.running = True
        self.start_time = time.time()
        logging.info(f"Starting sensor simulator for {self.run_time_seconds} seconds")
        logging.info(f"Generating {self.readings_per_second} readings per second")

        # Start monitoring server if enabled
        if self.monitoring_enabled and self.monitoring_server:
            self.monitoring_server.start()

        try:
            while self.running:
                # Check if we've reached the end of the simulation
                elapsed = time.time() - self.start_time
                if elapsed >= self.run_time_seconds:
                    logging.info(f"Simulation complete after {elapsed:.2f} seconds")
                    break

                # Generate and process a reading
                self.process_reading()

                # Sleep to maintain the configured rate
                sleep_time = 1.0 / self.readings_per_second
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logging.info("Simulation stopped by user")
        except Exception as e:
            logging.error(f"Error during simulation: {e}")
        finally:
            # Stop the monitoring server if it's running
            if self.monitoring_server and self.monitoring_server.running:
                self.monitoring_server.stop()

            # Stop the config file watcher if it's running
            if hasattr(self.config_manager, "stop_file_watcher"):
                self.config_manager.stop_file_watcher()

            # Close database connection
            if hasattr(self, "db"):
                self.db.close()

            # Log summary
            success_rate = 0
            if self.readings_count > 0:
                success_rate = 100 - (self.error_count / self.readings_count * 100)

            # Log memory usage
            memory_usage = self._check_memory_usage()
            initial_mb = memory_usage.get("initial_mb", 0)
            current_mb = memory_usage.get("current_mb", 0)
            peak_mb = memory_usage.get("peak_mb", 0)

            logging.info(
                f"Simulation ended. Generated {self.readings_count} readings with "
                f"{self.error_count} errors ({success_rate:.2f}% success rate). "
                f"Memory usage: {current_mb:.2f} MB (peak: {peak_mb:.2f} MB, "
                f"initial: {initial_mb:.2f} MB)"
            )

            self.running = False

    def stop(self):
        """Stop the simulator."""
        if self.running:
            logging.info("Stopping simulator...")
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
            "firmware_version": self.sensor_config.get("firmware_version"),
            "database_healthy": self.db.is_healthy() if hasattr(self, "db") else False,
            "memory_usage_mb": memory_usage.get("current_mb", 0),
            "memory_peak_mb": memory_usage.get("peak_mb", 0),
            "memory_growth_percent": memory_usage.get("growth_percent", 0),
            "monitoring_enabled": self.monitoring_enabled,
            "monitoring_server_running": self.monitoring_server.running
            if self.monitoring_server
            else False,
        }
