import json
import logging
import os
from threading import Event, Thread

import yaml


class ConfigManager:
    def __init__(
        self,
        config_path=None,
        identity_path=None,
        initial_config=None,
        initial_identity=None,
    ):
        """Initialize the configuration manager.

        Args:
            config_path: Path to configuration file. Used if initial_config is None.
                         Defaults to env var CONFIG_FILE or 'config.yaml'.
            identity_path: Path to node identity file. Used if initial_identity is None.
                           Defaults to env var IDENTITY_FILE or 'node_identity.json'.
            initial_config: Optional pre-loaded configuration dictionary.
            initial_identity: Optional pre-loaded identity dictionary.
        """
        self.config_mtime = 0
        self.identity_mtime = 0
        self._stop_event = Event()
        self._watcher_thread = None

        self.config_path = None
        self.identity_path = None

        loaded_config_from_file = False
        loaded_identity_from_file = False

        # Load configuration
        if initial_config is not None:
            self.config = initial_config
            logging.info("Configuration was injected directly.")
        else:
            self.config_path = os.path.abspath(
                config_path or os.environ.get("CONFIG_FILE", "config.yaml")
            )
            if not os.path.exists(self.config_path):
                logging.error(f"Configuration file not found: {self.config_path}")
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}"
                )
            self.config = self.load_config()  # Uses self.config_path
            if self.config is None:  # load_config might return None on error
                logging.error("Failed to load configuration from file.")
                # Consider raising an error or ensuring self.config is a dict
                self.config = {}  # Fallback to empty dict if load_config returns None
            loaded_config_from_file = True

        # Load node identity
        if initial_identity is not None:
            self.identity = initial_identity
            logging.info("Node identity was injected directly.")
        else:
            self.identity_path = os.path.abspath(
                identity_path or os.environ.get("IDENTITY_FILE", "node_identity.json")
            )
            if not os.path.exists(self.identity_path):
                logging.error(f"Node identity file not found: {self.identity_path}")
                raise FileNotFoundError(
                    f"Node identity file not found: {self.identity_path}"
                )
            self.identity = self.load_node_identity()  # Uses self.identity_path
            if self.identity is None:  # load_node_identity might return None
                logging.error("Failed to load node identity from file.")
                self.identity = {}  # Fallback to empty dict
            loaded_identity_from_file = True

        # Apply environment variable overrides (highest priority)
        self._apply_env_overrides()

        # Setup dynamic reloading only if config was loaded from files
        if (
            loaded_config_from_file and self.config_path
        ):  # Ensure config_path is valid for watching
            reload_settings = self.config.get("dynamic_reloading", {})
            self.auto_reload = reload_settings.get("enabled", False)
            self.reload_interval = reload_settings.get("check_interval_seconds", 5)
            if self.auto_reload:
                # File watcher should only start if identity also comes from a file or isn't needed for reload logic
                if (
                    loaded_identity_from_file or not self.identity_path
                ):  # Or if identity path not critical for reload decision
                    self.start_file_watcher()
                else:
                    logging.info(
                        "Dynamic reloading of config enabled, but identity was injected. File watcher for identity changes will not be active via this ConfigManager instance."
                    )
            else:
                self.auto_reload = False  # Explicitly set if not enabled
        else:
            self.auto_reload = False
            logging.info(
                "Dynamic reloading disabled as configuration/identity were injected or config_path not set."
            )

    def get_sensor_config(self):
        """Get sensor configuration."""
        return self.config.get("sensor", {})

    def _apply_env_overrides(self):
        """Apply environment variable overrides to the configuration."""
        # Ensure identity is a dict before trying to update it
        if self.identity is None:
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

    def load_config(self):
        """Load configuration from YAML file specified by self.config_path."""
        if not self.config_path:  # Should not happen if called appropriately
            logging.warning("load_config called without a config_path.")
            return {}  # Or None, or raise error
        try:
            # This check is already here from original, good.
            if not os.path.exists(self.config_path):
                logging.error(f"Configuration file not found: {self.config_path}")
                return {}  # Consistent with original behavior

            with open(self.config_path, "r") as file:
                config_data = yaml.safe_load(file)
                abs_path = os.path.abspath(self.config_path)
                logging.info(f"Configuration loaded from {abs_path}")

                self.config_mtime = os.path.getmtime(self.config_path)
                return config_data
        except Exception as e:
            logging.error(f"Error loading configuration from {self.config_path}: {e}")
            # The get_default_config() method was in the original snippet's except block.
            # If it's defined elsewhere and returns a dict, that's fine.
            # For now, returning empty dict to avoid NameError if it's not defined.
            # if hasattr(self, 'get_default_config'):
            #     logging.info("Using default configuration.")
            #     return self.get_default_config()
            logging.warning(
                f"Returning empty dictionary for config due to loading error from {self.config_path}."
            )
            return {}

    def load_node_identity(self):
        """Load node identity from JSON file specified by self.identity_path."""
        if not self.identity_path:  # Should not happen
            logging.warning("load_node_identity called without an identity_path.")
            return {}
        try:
            if not os.path.exists(self.identity_path):
                logging.error(f"Node identity file not found: {self.identity_path}")
                return {}

            with open(self.identity_path, "r") as file:
                identity_data = json.load(file)

            self.identity_mtime = os.path.getmtime(self.identity_path)
            abs_path = os.path.abspath(self.identity_path)
            logging.info(f"Node identity loaded from {abs_path}")
            return identity_data
        except Exception as e:
            logging.error(f"Error loading node identity from {self.identity_path}: {e}")
            logging.warning(
                f"Returning empty dictionary for identity due to loading error from {self.identity_path}."
            )
            return {}

    def check_for_changes(self):
        """Check if configuration files have changed. Only if paths are set."""
        config_changed = False
        identity_changed = False

        if self.config_path and os.path.exists(self.config_path):  # Check path exists
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.config_mtime:
                logging.info(f"Configuration file {self.config_path} has changed")
                config_changed = True

        if self.identity_path and os.path.exists(
            self.identity_path
        ):  # Check path exists
            current_mtime = os.path.getmtime(self.identity_path)
            if current_mtime > self.identity_mtime:
                logging.info(f"Identity file {self.identity_path} has changed")
                identity_changed = True

        return config_changed or identity_changed

    # reload_config, start_file_watcher, stop_file_watcher, _watch_files
    # should ideally only operate if self.auto_reload is True,
    # which is now conditional on whether config was loaded from files.
    # The existing guards (e.g., in start_file_watcher for thread already running) are fine.

    def reload_config(self):
        """Reload configuration if files have changed and auto_reload is enabled."""
        if not self.auto_reload:  # If not set to auto-reload (e.g. injected config)
            return False

        if self.check_for_changes():
            logging.info("Reloading configuration...")
            # ... (rest of the method is largely okay but ensure it handles cases where paths might be None,
            # although check_for_changes already implicitly handles this by using self.config_path/self.identity_path)

            # Save current auto-reload setting, important if the file changes this setting
            current_auto_reload_enabled = self.auto_reload
            current_reload_interval = self.reload_interval

            if self.config_path:  # Only reload config if it was originally from a file
                self.config = self.load_config()
                if self.config is None:
                    logging.error("Failed to reload configuration from file.")
                    # Potentially revert to old config or handle error state
                    return False

            if (
                self.identity_path
            ):  # Only reload identity if it was originally from a file
                self.identity = self.load_node_identity()
                # self.identity could be {} if loading failed, handle as needed

            self._apply_env_overrides()  # Re-apply env overrides after reload

            # Re-evaluate auto-reload settings from the newly loaded config
            if self.config:  # Ensure config is not None
                reload_settings = self.config.get("dynamic_reloading", {})
                self.auto_reload = reload_settings.get(
                    "enabled", current_auto_reload_enabled
                )  # Use previous if not in new
                self.reload_interval = reload_settings.get(
                    "check_interval_seconds", current_reload_interval
                )
            else:  # If config became None after reload attempt
                self.auto_reload = False  # Disable if config is broken

            logging.info("Configuration reloaded (or attempt finished).")
            return True
        return False

    def start_file_watcher(self):
        """Start a background thread to watch for configuration changes if auto_reload is enabled."""
        if not self.auto_reload:  # Do not start if auto_reload is false
            logging.info("Auto-reload is disabled; file watcher will not start.")
            return

        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            logging.warning("File watcher thread is already running.")
            return

        # Ensure paths are set if we are starting a watcher that depends on them
        if not (self.config_path or self.identity_path):
            logging.warning(
                "File watcher cannot start without config_path or identity_path for watching."
            )
            self.auto_reload = False  # Disable if paths are missing
            return

        self._stop_event.clear()
        self._watcher_thread = Thread(target=self._watch_files, daemon=True)
        self._watcher_thread.start()
        logging.info(
            f"Started configuration file watcher (interval: {self.reload_interval}s)."
        )

    def stop_file_watcher(self):
        """Stop the file watcher thread."""
        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            self._stop_event.set()
            self._watcher_thread.join(timeout=5)  # Add timeout
            if self._watcher_thread.is_alive():
                logging.warning("File watcher thread did not stop in time.")
            else:
                logging.info("Stopped configuration file watcher.")
            self._watcher_thread = None  # Clear the thread
        else:
            logging.info("File watcher thread was not running or already stopped.")

    def _watch_files(self):
        """Background thread function to watch for file changes."""
        while not self._stop_event.is_set():
            try:
                if (
                    self.auto_reload
                ):  # Double check, in case it was disabled during runtime
                    self.reload_config()
                else:  # If auto_reload got disabled, stop watching effectively
                    logging.info("Auto-reload disabled, stopping file watcher loop.")
                    break
            except Exception as e:  # Catch broad exceptions from reload_config
                logging.error(f"Error in file watcher during reload_config: {e}")

            # Wait for the next check interval or until stopped
            # self._stop_event.wait returns True if event set, False on timeout
            if self._stop_event.wait(self.reload_interval):
                break  # Event was set, exit loop

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
