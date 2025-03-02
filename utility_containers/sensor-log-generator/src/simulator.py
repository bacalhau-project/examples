import logging
import random
import time
from datetime import datetime

import numpy as np

from .anomaly import AnomalyGenerator, AnomalyType
from .config import ConfigManager
from .database import SensorDatabase


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

        # Load configuration
        self.config_manager = ConfigManager(config_path, identity_path)
        self.config = self.config_manager.config
        logging_config = self.config_manager.get_logging_config()
        logging.getLogger().setLevel(
            getattr(logging, logging_config.get("level", "INFO"))
        )

        # Initialize database
        db_config = self.config_manager.get_database_config()
        self.db = SensorDatabase(db_config.get("path", "sensor_data.db"))

        # Get sensor configuration
        self.sensor_config = self.config_manager.get_sensor_config()
        self.sensor_id = self.sensor_config.get("id", "SENSOR001")

        # Initialize anomaly generator with sensor config
        anomaly_config = self.config_manager.get_anomaly_config()
        self.anomaly_generator = AnomalyGenerator(anomaly_config, self.sensor_config)

        # Get simulation parameters
        self.simulation_config = self.config_manager.get_simulation_config()
        self.readings_per_second = self.simulation_config.get("readings_per_second", 1)
        self.run_time_seconds = self.simulation_config.get("run_time_seconds", 3600)

        # Get normal parameters
        self.normal_params = self.config_manager.get_normal_parameters()

        # Initialize state
        self.running = False
        self.start_time = None
        self.readings_count = 0

    def generate_normal_reading(self):
        """Generate a normal sensor reading based on configured parameters."""
        reading = {
            "sensor_id": self.sensor_id,
            "temperature": self._generate_parameter_value("temperature"),
            "vibration": self._generate_parameter_value("vibration"),
            "voltage": self._generate_parameter_value("voltage"),
            "status_code": 0,  # 0 = normal operation
        }
        return reading

    def _generate_parameter_value(self, param_name):
        """Generate a value for a specific parameter based on its configuration."""
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

    def process_reading(self):
        """Generate a reading, potentially apply anomalies, and store in database."""
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
            return

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

        # Log occasional status
        if self.readings_count % 100 == 0:
            logging.info(f"Generated {self.readings_count} readings")

    def run(self):
        """Run the simulator for the configured duration."""
        self.running = True
        self.start_time = time.time()
        logging.info(f"Starting sensor simulator for {self.run_time_seconds} seconds")
        logging.info(f"Generating {self.readings_per_second} readings per second")

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
            self.db.close()
            logging.info(f"Simulation ended. Generated {self.readings_count} readings")

    def stop(self):
        """Stop the simulator."""
        self.running = False
