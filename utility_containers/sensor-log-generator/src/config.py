import json
import logging
import os
from threading import Event, Thread

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

        # File modification timestamps
        self.config_mtime = 0
        self.identity_mtime = 0

        # Config reload settings
        self.auto_reload = False
        self.reload_interval = 5  # seconds - reduced to 5 for identity file watching
        self._stop_event = Event()
        self._watcher_thread = None

        # Load configuration
        self.config = self.load_config()
        if self.config is None:
            logging.error("Failed to load configuration")
            return False

        # Load node identity
        self.identity = self.load_node_identity()

        # Apply environment variable overrides (highest priority)
        self._apply_env_overrides()

        # Check if auto-reload is enabled in config
        reload_config = self.config.get("dynamic_reloading", {})
        self.auto_reload = reload_config.get("enabled", False)
        self.reload_interval = reload_config.get("check_interval_seconds", 5)

        # Start file watcher if auto-reload is enabled
        if self.auto_reload:
            self.start_file_watcher()

    def get_sensor_config(self):
        """Get sensor configuration."""
        return self.config.get("sensor", {})

    def _apply_env_overrides(self):
        """Apply environment variable overrides to the configuration."""
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

    def load_config(self):
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logging.error(f"Configuration file not found: {self.config_path}")
                return {}

            with open(self.config_path, "r") as file:
                config = yaml.safe_load(file)
                logging.info(f"Configuration loaded from {self.config_path}")

                # Update config file modification time
                self.config_mtime = os.path.getmtime(self.config_path)

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
                return {}

            with open(self.identity_path, "r") as file:
                identity = json.load(file)

            # Update identity file modification time
            self.identity_mtime = os.path.getmtime(self.identity_path)

            logging.info(f"Node identity loaded from {self.identity_path}")
            return identity
        except Exception as e:
            logging.error(f"Error loading node identity: {e}")
            return {}

    def check_for_changes(self):
        """Check if configuration files have changed."""
        config_changed = False
        identity_changed = False

        # Check if config file has changed
        if os.path.exists(self.config_path):
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.config_mtime:
                logging.info(f"Configuration file {self.config_path} has changed")
                config_changed = True

        # Check if identity file has changed
        if os.path.exists(self.identity_path):
            current_mtime = os.path.getmtime(self.identity_path)
            if current_mtime > self.identity_mtime:
                logging.info(f"Identity file {self.identity_path} has changed")
                identity_changed = True

        return config_changed or identity_changed

    def reload_config(self):
        """Reload configuration if files have changed."""
        if self.check_for_changes():
            logging.info("Reloading configuration...")

            # Save current auto-reload setting
            current_auto_reload = self.auto_reload
            current_interval = self.reload_interval

            # Reload configuration
            self.config = self.load_config()
            if self.config is None:
                logging.error("Failed to reload configuration")
                return False

            # Reload node identity
            self.identity = self.load_node_identity()
            self._apply_env_overrides()

            # Check if auto-reload settings have changed
            reload_config = self.config.get("dynamic_reloading", {})
            self.auto_reload = reload_config.get("enabled", current_auto_reload)
            self.reload_interval = reload_config.get(
                "check_interval_seconds", current_interval
            )

            logging.info("Configuration reloaded successfully")
            return True

        return False

    def start_file_watcher(self):
        """Start a background thread to watch for configuration changes."""
        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            logging.warning("File watcher thread is already running")
            return

        self._stop_event.clear()
        self._watcher_thread = Thread(target=self._watch_files, daemon=True)
        self._watcher_thread.start()
        logging.info(
            f"Started configuration file watcher (interval: {self.reload_interval}s)"
        )

    def stop_file_watcher(self):
        """Stop the file watcher thread."""
        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            self._stop_event.set()
            self._watcher_thread.join(timeout=5)
            logging.info("Stopped configuration file watcher")

    def _watch_files(self):
        """Background thread function to watch for file changes."""
        while not self._stop_event.is_set():
            try:
                self.reload_config()
            except Exception as e:
                logging.error(f"Error in file watcher: {e}")

            # Wait for the next check interval or until stopped
            self._stop_event.wait(self.reload_interval)

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

    def get_valid_configurations(self):
        """Get valid configurations for validation."""
        return self.config.get("valid_configurations", {})

    def get_identity(self):
        """Get the current node identity."""
        return self.identity
