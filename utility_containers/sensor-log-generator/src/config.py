import json
import logging
import os
import sys

import yaml


class ConfigManager:
    def __init__(self, config_path=None, identity_path=None):
        """Initialize the configuration manager.

        Args:
            config_path: Path to configuration file. If None, will try to get from
                         environment variable SENSOR_CONFIG or use default 'config.yaml'.
            identity_path: Path to node identity file. If None, will try to get from
                          environment variable SENSOR_IDENTITY_FILE or use default 'node_identity.json'.
        """
        # Priority: 1. Passed argument, 2. Environment variable, 3. Default
        self.config_path = config_path or os.environ.get("SENSOR_CONFIG", "config.yaml")
        self.identity_path = identity_path or os.environ.get(
            "SENSOR_IDENTITY_FILE", "node_identity.json"
        )

        # Load configuration
        self.config = self.load_config()

        # Load node identity
        self.load_node_identity()

        # Apply environment variable overrides (highest priority)
        self._apply_env_overrides()

    def _apply_env_overrides(self):
        """Apply environment variable overrides to the configuration."""
        # Ensure sensor config exists
        if "sensor" not in self.config:
            self.config["sensor"] = {}

        # Override sensor location if environment variable is set
        if "SENSOR_LOCATION" in os.environ:
            self.config["sensor"]["location"] = os.environ["SENSOR_LOCATION"]
            logging.info(
                f"Overriding sensor location from environment variable: {self.config['sensor']['location']}"
            )

        # Override sensor ID if environment variable is set
        if "SENSOR_ID" in os.environ:
            self.config["sensor"]["id"] = os.environ["SENSOR_ID"]
            logging.info(
                f"Overriding sensor ID from environment variable: {self.config['sensor']['id']}"
            )

    def load_config(self):
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logging.warning(f"Config file not found: {self.config_path}")
                return self.get_default_config()

            with open(self.config_path, "r") as file:
                config = yaml.safe_load(file)
                logging.info(f"Configuration loaded from {self.config_path}")
                return config
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
            logging.info("Using default configuration")
            return self.get_default_config()

    def load_node_identity(self):
        """Load node identity from JSON file."""
        try:
            if not os.path.exists(self.identity_path):
                logging.warning(f"Node identity file not found: {self.identity_path}")
                return

            with open(self.identity_path, "r") as file:
                identity = json.load(file)

            # Ensure sensor config exists
            if "sensor" not in self.config:
                self.config["sensor"] = {}

            # Apply identity values to sensor config
            for key, value in identity.items():
                self.config["sensor"][key] = value

            logging.info(f"Node identity loaded from {self.identity_path}")
        except Exception as e:
            logging.error(f"Error loading node identity: {e}")

    def get_default_config(self):
        """Return default configuration if no config file is found."""
        return {
            "sensor": {
                "id": "TEMP001",
                "type": "temperature_vibration",
                "location": "Factory A - Machine 1",
                "manufacturer": "SensorTech",
                "model": "TempVibe-2000",
                "firmware_version": "1.3",
            },
            "simulation": {
                "readings_per_second": 1,
                "run_time_seconds": 3600,  # 1 hour
            },
            "normal_parameters": {
                "temperature": {
                    "mean": 65.0,  # Celsius
                    "std_dev": 2.0,
                    "min": 50.0,
                    "max": 80.0,
                },
                "vibration": {
                    "mean": 2.5,  # mm/s²
                    "std_dev": 0.5,
                    "min": 0.1,
                    "max": 10.0,
                },
                "voltage": {
                    "mean": 12.0,  # Volts
                    "std_dev": 0.1,
                    "min": 11.5,
                    "max": 12.5,
                },
            },
            "anomalies": {
                "enabled": True,
                "probability": 0.05,  # 5% chance of anomaly per reading
                "types": {
                    "spike": {"enabled": True, "weight": 0.4},
                    "trend": {
                        "enabled": True,
                        "weight": 0.2,
                        "duration_seconds": 300,  # 5 minutes
                    },
                    "pattern": {
                        "enabled": True,
                        "weight": 0.1,
                        "duration_seconds": 600,  # 10 minutes
                    },
                    "missing_data": {
                        "enabled": True,
                        "weight": 0.1,
                        "duration_seconds": 30,  # 30 seconds
                    },
                    "noise": {
                        "enabled": True,
                        "weight": 0.2,
                        "duration_seconds": 180,  # 3 minutes
                    },
                },
            },
            "database": {"path": "sensor_data.db"},
            "logging": {"level": "INFO", "file": "sensor_simulator.log"},
        }

    def get_sensor_config(self):
        """Get sensor configuration."""
        return self.config.get("sensor", {})

    def get_simulation_config(self):
        """Get simulation configuration."""
        return self.config.get("simulation", {})

    def get_normal_parameters(self):
        """Get normal operating parameters."""
        return self.config.get("normal_parameters", {})

    def get_anomaly_config(self):
        """Get anomaly configuration."""
        return self.config.get("anomalies", {})

    def get_database_config(self):
        """Get database configuration."""
        return self.config.get("database", {})

    def get_logging_config(self):
        """Get logging configuration."""
        return self.config.get("logging", {})
