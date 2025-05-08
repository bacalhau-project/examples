import json
import logging
import os

# Removed: from threading import Event, Thread # No longer needed for file watching
import yaml


class ConfigManager:
    def __init__(self, config: dict, identity: dict):
        """Initialize the configuration manager with pre-loaded config and identity.

        Args:
            config: Pre-loaded configuration dictionary.
            identity: Pre-loaded identity dictionary.
        """
        # Removed: self.config_mtime = 0
        # Removed: self.identity_mtime = 0
        # Removed: self._stop_event = Event()
        # Removed: self._watcher_thread = None
        # Removed: self.config_path = None
        # Removed: self.identity_path = None
        # Removed: loaded_config_from_file = False
        # Removed: loaded_identity_from_file = False

        self.config = config
        logging.info("Configuration dictionary provided.")

        self.identity = identity
        logging.info("Node identity dictionary provided.")

        # Apply environment variable overrides (highest priority)
        self._apply_env_overrides()

        # Removed: Setup dynamic reloading logic as it's no longer ConfigManager's responsibility
        # Removed: self.auto_reload = False
        # Removed: logging.info(...) for dynamic reloading

    def get_sensor_config(self):
        """Get sensor configuration."""
        return self.config.get("sensor", {})

    def _apply_env_overrides(self):
        """Apply environment variable overrides to the configuration."""
        # Ensure identity is a dict before trying to update it
        if self.identity is None:  # Should be initialized to {} if None was passed
            self.identity = {}

        # Override sensor location if environment variable is set
        if "SENSOR_LOCATION" in os.environ:
            self.identity["location"] = os.environ["SENSOR_LOCATION"]
            logging.info(
                f"Overriding sensor location from environment variable: {self.identity['location']}"
            )

        # Override sensor ID if environment variable is set
        if "SENSOR_ID" in os.environ:
            self.identity["id"] = os.environ["SENSOR_ID"]
            logging.info(
                f"Overriding sensor ID from environment variable: {self.identity['id']}"
            )

    # Removed: load_config(self) method
    # Removed: load_node_identity(self) method
    # Removed: check_for_changes(self) method
    # Removed: reload_config(self) method
    # Removed: start_file_watcher(self) method
    # Removed: stop_file_watcher(self) method
    # Removed: _watch_files(self) method

    def get_simulation_config(self):
        """Get simulation configuration."""
        return self.config.get("simulation", {}) if self.config else {}

    def get_normal_parameters(self):
        """Get normal operating parameters."""
        return self.config.get("normal_parameters", {}) if self.config else {}

    def get_anomaly_config(self):
        """Get anomaly configuration."""
        return self.config.get("anomalies", {}) if self.config else {}

    def get_database_config(self):
        """Get database configuration."""
        return self.config.get("database", {}) if self.config else {}

    def get_logging_config(self):
        """Get logging configuration."""
        return self.config.get("logging", {}) if self.config else {}

    def get_valid_configurations(self):
        """Get valid configurations for validation."""
        return self.config.get("valid_configurations", {}) if self.config else {}

    def get_identity(self):
        """Get the current node identity."""
        return self.identity if self.identity else {}
