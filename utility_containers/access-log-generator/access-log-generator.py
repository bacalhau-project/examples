#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "faker==33.3.1",
#     "python-dateutil==2.9.0.post0",
#     "pytz==2024.2",
#     "pyyaml==6.0.2",
#     "setuptools==75.8.0",
#     "six==1.17.0",
#     "typing-extensions==4.12.2",
#     "wheel==0.45.1",
# ]
# ///

import argparse
import base64
import gzip
import logging
import logging.handlers
import os
import random
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import pytz
import yaml
from faker import Faker


# Add this after the imports, before load_config()
class SessionState:
    """State machine states for user sessions"""

    START = "START"
    LOGIN = "LOGIN"
    DIRECT_ACCESS = "DIRECT_ACCESS"
    BROWSING = "BROWSING"
    LOGOUT = "LOGOUT"
    ABANDON = "ABANDON"
    LEAVE = "LEAVE"
    ERROR = "ERROR"
    END = "END"


# Default configuration path
DEFAULT_CONFIG_PATH = Path("config/config.yaml")


def laughable_function_that_is_not_real():
    pass  # this is not a real function and you should not expect it to be called


def validate_config(config: dict) -> Tuple[bool, List[Tuple[str, str]]]:
    """Validate configuration structure and values. Returns (is_valid, messages_list)."""
    messages = []
    is_valid = True
    required_sections = [
        "output",
        "state_transitions",
        "navigation",
        "error_rates",
        "session",
        "traffic_patterns",
    ]

    # Check required sections exist
    missing_sections = [s for s in required_sections if s not in config]
    if missing_sections:
        messages.append(
            (
                "error",
                f"Missing required configuration sections: {', '.join(missing_sections)}",
            )
        )
        is_valid = False

    # Validate output settings
    output = config.get("output", {})
    if not isinstance(output.get("directory", ""), str):
        messages.append(("error", "Output directory must be a string"))
        is_valid = False
    if (
        not isinstance(output.get("rate", 0), (int, float))
        or output.get("rate", 0) <= 0
    ):
        messages.append(("error", "Rate must be a positive number"))
        is_valid = False

    # Validate state transitions
    for state, transitions in config.get("state_transitions", {}).items():
        if not isinstance(transitions, dict):
            messages.append(
                (
                    "error",
                    f"State transitions for {state} must be a dictionary",
                )
            )
            is_valid = False
            continue  # Skip sum validation if not a dict
        total = sum(transitions.values())
        if not (0.99 <= total <= 1.01):  # Allow for floating point imprecision
            messages.append(
                (
                    "error",
                    f"State transitions for {state} must sum to 1.0 (got {total})",
                )
            )
            is_valid = False

    # Validate traffic patterns
    for pattern in config.get("traffic_patterns", []):
        if "time" not in pattern or "multiplier" not in pattern:
            messages.append(
                (
                    "error",
                    "Traffic patterns must have 'time' and 'multiplier' keys",
                )
            )
            is_valid = False
            continue  # Skip further validation for this pattern
        try:
            start, end = map(int, pattern["time"].split("-"))
            if not (0 <= start <= 23) or not (0 <= end <= 23):
                messages.append(("error", f"Invalid time range: {pattern['time']}"))
                is_valid = False
        except ValueError:
            messages.append(("error", f"Invalid time format: {pattern['time']}"))
            is_valid = False

    if not messages and not is_valid:
        # Generic message if is_valid was set to False for a reason not producing a message
        messages.append(
            ("error", "Configuration validation failed due to an unspecified error.")
        )

    return is_valid, messages


def load_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Tuple[dict, List[Tuple[str, str]]]:
    """Load and validate configuration. Returns (config, messages_list)."""
    config = None
    messages_to_log = []

    # Try base64 encoded config first
    env_config_b64 = os.environ.get("LOG_GENERATOR_CONFIG_YAML_B64")
    if env_config_b64:
        try:
            decoded_config = base64.b64decode(env_config_b64).decode("utf-8")
            config = yaml.safe_load(decoded_config)
            messages_to_log.append(
                (
                    "info",
                    "Loaded configuration from LOG_GENERATOR_CONFIG_YAML_B64 environment variable",
                )
            )
        except base64.binascii.Error as e:
            msg = f"Failed to decode base64 configuration: {e}"
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)
        except yaml.YAMLError as e:
            msg = f"Failed to parse base64 decoded YAML: {e}"
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            msg = f"Error processing base64 configuration: {e}"
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)

    # If no base64 config, try plain YAML env var
    if config is None:
        env_config = os.environ.get("LOG_GENERATOR_CONFIG_YAML")
        if env_config:
            try:
                # Try parsing as direct YAML content first
                try:
                    config = yaml.safe_load(env_config)
                    messages_to_log.append(
                        (
                            "info",
                            "Loaded configuration from LOG_GENERATOR_CONFIG_YAML environment variable",
                        )
                    )
                except yaml.YAMLError:
                    # If parsing fails, try treating it as a file path
                    env_path = Path(env_config)
                    if env_path.exists():
                        with open(env_path) as f:
                            config = yaml.safe_load(f)
                        messages_to_log.append(
                            (
                                "info",
                                f"Loaded configuration from environment-specified path: {env_path}",
                            )
                        )
                    else:
                        msg = "LOG_GENERATOR_CONFIG_YAML contains invalid YAML and is not a valid file path"
                        messages_to_log.append(("error", msg))
                        print(f"❌ {msg}", file=sys.stderr)
                        sys.exit(1)
            except Exception as e:
                msg = f"Failed to load configuration from environment variable: {e}"
                messages_to_log.append(("error", msg))
                print(f"❌ {msg}", file=sys.stderr)
                sys.exit(1)

    # If no environment configs, use file config
    if config is None:
        if (
            config_path == Path("dummy_path")
            and not os.environ.get("LOG_GENERATOR_CONFIG_YAML_B64")
            and not os.environ.get("LOG_GENERATOR_CONFIG_YAML")
        ):
            # This case means we expected env vars but didn't find them, and args.config was None, so dummy_path was used.
            # main() would have already errored if args.config was required and None, so this specific check is for when
            # env vars were expected due to args.config being None, but the env vars are also missing/empty.
            msg = "Configuration via environment variables was attempted but no relevant environment variables were found."
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)
        elif not config_path.exists():
            msg = f"Configuration file not found: {config_path}"
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            messages_to_log.append(
                (
                    "info",
                    f"Loaded configuration from {config_path}",
                )
            )
        except yaml.YAMLError as e:
            msg = f"YAML parsing error in {config_path}: {e}"
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            msg = f"Failed to load configuration from {config_path}: {e}"
            messages_to_log.append(("error", msg))
            print(f"❌ {msg}", file=sys.stderr)
            sys.exit(1)

    if config is None:
        # This should ideally not be reached if all paths above sys.exit appropriately.
        msg = "Configuration could not be loaded from any source."
        messages_to_log.append(("error", msg))
        print(f"❌ {msg}", file=sys.stderr)
        sys.exit(1)

    # Validate configuration
    is_valid, validation_messages = validate_config(config)
    messages_to_log.extend(validation_messages)
    if not is_valid:
        messages_to_log.append(
            (
                "error",
                "Configuration validation failed. See previous messages for details.",
            )
        )
        # Print all validation messages to stderr before exiting
        for level, v_msg in validation_messages:
            print(f"❌ Validation {level}: {v_msg}", file=sys.stderr)
        print("❌ Configuration validation failed.", file=sys.stderr)
        sys.exit(1)

    # Add configuration summary to messages
    messages_to_log.append(
        (
            "info",
            "\n⚙️  Configuration Summary:",
        )
    )
    messages_to_log.append(
        (
            "info",
            f"  Output Directory: {config['output']['directory']}",
        )
    )
    messages_to_log.append(
        (
            "info",
            f"  Base Rate: {config['output']['rate']} logs/sec",
        )
    )
    messages_to_log.append(
        (
            "info",
            f"  Debug Mode: {config['output'].get('debug', False)}",
        )
    )
    messages_to_log.append(
        (
            "info",
            f"  Pre-warm: {config['output'].get('pre_warm', True)}",
        )
    )
    messages_to_log.append(
        (
            "info",
            f"  No Error Log: {config['output'].get('no_error_log', False)}",
        )
    )
    messages_to_log.append(
        (
            "info",
            f"  No System Log: {config['output'].get('no_system_log', False)}",
        )
    )
    messages_to_log.append(
        (
            "info",
            "\n  State Transitions:",
        )
    )
    for state, transitions in config["state_transitions"].items():
        messages_to_log.append(
            (
                "info",
                f"    {state}:",
            )
        )
        for action, prob in transitions.items():
            messages_to_log.append(
                (
                    "info",
                    f"      {action}: {prob:.2f}",
                )
            )
    messages_to_log.append(
        (
            "info",
            "\n  Traffic Patterns:",
        )
    )
    for pattern in config["traffic_patterns"]:
        messages_to_log.append(
            (
                "info",
                f"    {pattern['time']}: {pattern['multiplier']}x",
            )
        )
    messages_to_log.append(
        (
            "info",
            "\n✅ Configuration validated successfully\n",
        )
    )

    return config, messages_to_log


# Configure separate logging streams
def setup_logging(output_dir: Path, config: Dict = None) -> Dict[str, logging.Logger]:
    """Configure logging with rotation based on configuration"""
    try:
        # Create output directory with permissive permissions if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(output_dir, 0o755)  # rwxr-xr-x permissions

        # Reset all existing loggers to avoid interference
        for logger_name in logging.root.manager.loggerDict:
            logger_obj = logging.getLogger(logger_name)
            logger_obj.handlers = []
            logger_obj.propagate = False

        # Clear root logger handlers
        logging.root.handlers = []

        # Get rotation settings from config
        rotation_config = {}
        if config:
            rotation_config = config.get("output", {}).get("log_rotation", {})

        rotation_enabled = rotation_config.get("enabled", True)
        max_size_mb = rotation_config.get("max_size_mb", 1000)  # Default to 1 GB
        when = rotation_config.get("when", "h")  # Default to hourly
        interval = rotation_config.get("interval", 1)
        backup_count = rotation_config.get("backup_count", 5)
        compress = rotation_config.get("compress", True)

        # Convert max_size_mb to bytes
        max_bytes = max_size_mb * 1024 * 1024 if max_size_mb > 0 else 0

        # Check for disabled loggers
        output_config = config.get("output", {}) if config else {}
        no_error_log = output_config.get("no_error_log", False) or os.environ.get(
            "NO_ERROR_LOG", ""
        ).lower() in ("true", "1", "yes", "on")
        no_system_log = output_config.get("no_system_log", False) or os.environ.get(
            "NO_SYSTEM_LOG", ""
        ).lower() in ("true", "1", "yes", "on")

        # Determine which log files to create
        log_files_to_create = []
        if not no_error_log:
            log_files_to_create.append("error.log")
        if not no_system_log:
            log_files_to_create.append("system.log")
        # Always create access.log
        log_files_to_create.append("access.log")

        # Truncate log files on startup
        for log_file in log_files_to_create:
            file_path = output_dir / log_file
            # Truncate the file by opening it in write mode
            if file_path.exists():
                with open(file_path, "w") as f:
                    pass  # Just open and close to truncate

        # Set up loggers with appropriate handlers based on rotation settings
        loggers = {}
        for logger_name, file_name in [
            ("access", "access.log"),
            ("error", "error.log"),
            ("system", "system.log"),
        ]:
            logger = logging.getLogger(f"{logger_name}_log")
            logger.setLevel(logging.INFO if logger_name != "error" else logging.WARNING)
            logger.propagate = False

            # Skip creating file handler if logger is disabled
            should_create_handler = True
            if logger_name == "error" and no_error_log:
                should_create_handler = False
            elif logger_name == "system" and no_system_log:
                should_create_handler = False

            if should_create_handler:
                # Choose handler based on rotation settings
                if rotation_enabled:
                    if max_bytes > 0:
                        # Use size-based rotation
                        handler = logging.handlers.RotatingFileHandler(
                            filename=output_dir / file_name,
                            maxBytes=max_bytes,
                            backupCount=backup_count,
                            encoding="utf-8",
                        )
                    elif when:
                        # Use time-based rotation
                        handler = logging.handlers.TimedRotatingFileHandler(
                            filename=output_dir / file_name,
                            when=when,
                            interval=interval,
                            backupCount=backup_count,
                            encoding="utf-8",
                        )
                    else:
                        # Fallback to no rotation
                        handler = logging.FileHandler(
                            filename=output_dir / file_name,
                            encoding="utf-8",
                        )
                else:
                    # No rotation
                    handler = logging.FileHandler(
                        filename=output_dir / file_name,
                        encoding="utf-8",
                    )

                logger.addHandler(handler)

                # Set formatter
                formatter = logging.Formatter(
                    "%(message)s"
                    if logger_name == "access"
                    else "%(asctime)s - %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)

                # Add compression if enabled
                if (
                    compress
                    and rotation_enabled
                    and isinstance(
                        handler,
                        (
                            logging.handlers.RotatingFileHandler,
                            logging.handlers.TimedRotatingFileHandler,
                        ),
                    )
                ):
                    # Add compression to rotated logs
                    def namer(name):
                        return name + ".gz"

                    def rotator(source, dest):
                        with open(source, "rb") as f_in:
                            with gzip.open(dest + ".gz", "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(source)

                    handler.namer = namer
                    handler.rotator = rotator
            else:
                # Create a null handler if logger is disabled
                handler = logging.NullHandler()
                logger.addHandler(handler)

            loggers[logger_name] = logger

        # Configure root logger to use system logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        # Add system logger handlers to root logger (even if it's a NullHandler)
        for handler in loggers["system"].handlers:
            root_logger.addHandler(handler)

        # Ensure immediate flushing for access log
        for handler in loggers["access"].handlers:
            if hasattr(handler, "stream"):
                handler.stream.flush()
                if hasattr(handler.stream, "reconfigure"):
                    handler.stream.reconfigure(write_through=True)

        # Log initial message to system log
        loggers["system"].info("Logging initialized - all output directed to log files")

        # Log information about disabled loggers
        disabled_loggers = []
        if no_error_log:
            disabled_loggers.append("error.log")
        if no_system_log:
            disabled_loggers.append("system.log")

        if disabled_loggers:
            loggers["system"].info(f"Disabled log files: {', '.join(disabled_loggers)}")

        loggers["system"].info(f"Active log files: {', '.join(log_files_to_create)}")

        return loggers

    except Exception as e:
        print(f"Failed to set up logging: {e}", file=sys.stderr)
        sys.exit(1)


class AccessLogGenerator:
    def __init__(self, config: Dict, loggers: Dict[str, logging.Logger]):
        """Initialize generator with configuration and loggers"""
        self.config = config
        self.loggers = loggers  # Store the loggers dictionary
        self.output_dir = Path(config["output"]["directory"])
        self.log_file = self.output_dir / "access.log"
        self.rate = config["output"]["rate"]
        self.debug = config["output"].get("debug", False)
        self.pre_warm = config["output"].get("pre_warm", True)

        # Initialize Faker and user pool
        self.faker = Faker()
        self.user_pool = set()

        # Initialize transitions from config first
        transitions = config.get("state_transitions", {})
        self.START_TRANSITIONS = transitions.get(
            "START", {"LOGIN": 0.7, "DIRECT_ACCESS": 0.3}
        )
        self.LOGIN_TRANSITIONS = transitions.get(
            "LOGIN", {"BROWSING": 0.9, "ABANDON": 0.1}
        )
        self.DIRECT_ACCESS_TRANSITIONS = transitions.get(
            "DIRECT_ACCESS", {"BROWSING": 0.8, "LEAVE": 0.2}
        )
        self.BROWSING_TRANSITIONS = transitions.get(
            "BROWSING", {"LOGOUT": 0.4, "ABANDON": 0.3, "ERROR": 0.05, "BROWSING": 0.25}
        )

        # Then initialize state transitions
        self.state_transitions = self._initialize_state_transitions()

        # Initialize state handlers
        self.state_handlers = {
            SessionState.START: self._handle_start_state,
            SessionState.LOGIN: self._handle_login_state,
            SessionState.DIRECT_ACCESS: self._handle_direct_access_state,
            SessionState.BROWSING: self._handle_browsing_state,
            SessionState.LOGOUT: self._handle_logout_state,
            SessionState.ABANDON: self._handle_abandon_state,
            SessionState.ERROR: self._handle_error_state,
            SessionState.LEAVE: self._handle_leave_state,
        }

        # Cache error codes
        status_codes = self.config.get("status_codes", {})
        self.error_codes = [
            str(status_codes.get("not_found", 404)),
            str(status_codes.get("server_error", 500)),
            str(status_codes.get("forbidden", 403)),
            str(status_codes.get("unauthorized", 401)),
        ]

        # Initialize other settings
        self.HOME_NAVIGATION = config.get("navigation", {}).get(
            "HOME", {"/": 0.2, "/about": 0.3, "/products": 0.4, "/search": 0.1}
        )
        self.LOGOUT_NAVIGATION = config.get("navigation", {}).get(
            "LOGOUT", {"/": 0.2, "/about": 0.3, "/products": 0.4, "/search": 0.1}
        )
        self.ERROR_RATES = config.get("error_rates", {})
        self.PRODUCT_404_RATE = self.ERROR_RATES.get("product_404", 0.02)
        self.CHECKOUT_500_RATE = self.ERROR_RATES.get("checkout_500", 0.01)
        self.CART_ABANDON_RATE = self.ERROR_RATES.get("cart_abandon", 0.5)
        self.SESSION_PARAMS = config.get("session", {})
        self.MIN_BROWSING_DURATION = self.SESSION_PARAMS.get(
            "min_browsing_duration", 60
        )
        self.MAX_BROWSING_DURATION = self.SESSION_PARAMS.get(
            "max_browsing_duration", 600
        )
        self.PAGE_VIEW_INTERVAL = self.SESSION_PARAMS.get("page_view_interval", 5)

        self.TRAFFIC_PATTERNS = {}
        for pattern in config.get("traffic_patterns", []):
            time_range = tuple(map(int, pattern["time"].split("-")))
            self.TRAFFIC_PATTERNS[time_range] = pattern.get("multiplier", 0.1)

    def _log_configuration(self) -> None:
        """Log the configuration settings"""
        logger = self.loggers["system"]
        logger.info("Starting access log generator with configuration:")
        logger.info(f"  Output Directory: {self.output_dir}")
        logger.info(f"  Log file: {self.log_file}")
        logger.info(f"  Rate: {self.rate} logs/second")
        logger.info(f"  Debug mode: {'on' if self.debug else 'off'}")

    def _initialize_state_transitions(self) -> Dict:
        """Initialize the state machine transitions"""
        return {
            SessionState.START: self.START_TRANSITIONS,
            SessionState.LOGIN: self.LOGIN_TRANSITIONS,
            SessionState.DIRECT_ACCESS: self.DIRECT_ACCESS_TRANSITIONS,
            SessionState.BROWSING: self.BROWSING_TRANSITIONS,
        }

    def _generate_unique_username(self) -> str:
        """Generate a unique username not in the user pool"""
        username = self.faker.user_name()
        while username in self.user_pool:
            username = self.faker.user_name()
        return username

    def _create_log_entry(
        self,
        ip: str,
        user: str,
        method: str,
        path: str,
        status: str,
        referrer: str,
        user_agent: str,
        session_id: str,
    ) -> str:
        """Create a single log entry in NCSA Common Log Format"""
        # Ensure timezone is present by using UTC if needed
        now = datetime.now(pytz.UTC)
        # NCSA format: [dd/MMM/yyyy:HH:mm:ss ±HHMM]
        timestamp = now.strftime("%d/%b/%Y:%H:%M:%S %z")
        size = random.randint(100, 5000)

        if path == "/search" and "?" not in path:
            if random.random() < self.HOME_NAVIGATION["/search"]:
                search_terms = random.choice(
                    [
                        "shoes",
                        "laptop",
                        "phone",
                        "jacket",
                        "watch",
                        "headphones",
                        "camera",
                        "gaming",
                        "fitness",
                    ]
                )
                path += f"?q={search_terms}"
                if random.random() < 0.4:
                    path += f"&page={random.randint(1, 5)}"

        log_entry = (
            f'{ip} - {user} [{timestamp}] "{method} {path} HTTP/1.1" '
            f'{status} {size} "{referrer}" "{user_agent}"\n'
        )

        # Get status codes from config
        status_codes = self.config.get("status_codes", {})

        # Check for various error conditions
        # Get navigation paths from config
        nav_paths = self.config.get("navigation", {}).get("home", {})
        product_paths = [p for p in nav_paths.keys() if p.startswith("/products")]

        # Check if current path is a product path
        is_product_path = any(path.startswith(p) for p in product_paths)

        # Check for high error pages first
        high_error_pages = self.config.get("error_rates", {}).get(
            "high_error_pages", []
        )
        for error_page in high_error_pages:
            if path == error_page.get("path", "") and random.random() < error_page.get(
                "error_rate", 0
            ):
                log_entry = log_entry.replace(
                    str(status_codes.get("success", 200)),
                    str(status_codes.get("server_error", 500)),
                )
                return log_entry

        # Global 500 error chance
        if random.random() < self.config.get("error_rates", {}).get("global_500", 0.02):
            log_entry = log_entry.replace(
                str(status_codes.get("success", 200)),
                str(status_codes.get("server_error", 500)),
            )
            return log_entry

        # Product 404 error chance
        if is_product_path and random.random() < self.PRODUCT_404_RATE:
            log_entry = log_entry.replace(
                str(status_codes.get("success", 200)),
                str(status_codes.get("not_found", 404)),
            )
        elif random.random() < self.ERROR_RATES.get("redirect_301", 0.01):
            log_entry = log_entry.replace(
                str(status_codes.get("success", 200)),
                str(status_codes.get("redirect_permanent", 301)),
            )
        elif random.random() < self.ERROR_RATES.get("redirect_302", 0.02):
            log_entry = log_entry.replace(
                str(status_codes.get("success", 200)),
                str(status_codes.get("redirect_temporary", 302)),
            )
        elif path.startswith("/admin") and random.random() < self.ERROR_RATES.get(
            "forbidden_access", 0.005
        ):
            log_entry = log_entry.replace(
                str(status_codes.get("success", 200)),
                str(status_codes.get("forbidden", 403)),
            )
        elif path.startswith("/profile") and random.random() < self.ERROR_RATES.get(
            "auth_failure", 0.01
        ):
            log_entry = log_entry.replace(
                str(status_codes.get("success", 200)),
                str(status_codes.get("unauthorized", 401)),
            )

        return log_entry

    def _get_next_page(self, current_path: str) -> str:
        """Determine the next page based on current location"""
        # Get navigation paths from config
        nav_paths = self.config.get("navigation", {}).get("home", {})

        # Get weights for current path's possible transitions
        if current_path in nav_paths:
            next_paths = list(nav_paths.keys())
            weights = list(nav_paths.values())

            # Add special paths with their weights
            if current_path.startswith("/products"):
                next_paths.extend(["/cart", "/checkout"])
                weights.extend([0.3, 0.1])
            elif current_path == "/cart":
                next_paths.append("/checkout")
                weights.append(0.7)
            elif current_path == "/checkout":
                return "/thank-you"

            return random.choices(next_paths, weights=weights)[0]

        # Default to home if path not found
        return "/"

    def _add_query_params(self, path: str) -> str:
        """Add realistic query parameters to paths"""
        if path == "/products":
            if random.random() < 0.7:
                path += f"?categoryID={random.randint(1, 20)}"
                if random.random() < 0.3:
                    path += f"&sort={random.choice(['price', 'rating', 'popularity'])}"
        elif path.startswith("/products/"):
            if random.random() < 0.5:
                path += f"?variant={random.choice(['red', 'blue', 'large', 'small'])}"
        elif path == "/search":
            search_terms = random.choice(
                [
                    "shoes",
                    "laptop",
                    "phone",
                    "jacket",
                    "watch",
                    "headphones",
                    "camera",
                    "gaming",
                    "fitness",
                ]
            )
            path += f"?q={search_terms}"
            if random.random() < 0.4:
                path += f"&page={random.randint(1, 5)}"
        elif path == "/profile":
            if random.random() < 0.3:
                path += f"?tab={random.choice(['orders', 'settings', 'payment'])}"
        return path

    def _get_referrer(self, current_path: str) -> str:
        """Get a realistic referrer for the current path"""
        if current_path == "/" or random.random() < 0.3:
            return "-"

        # Get navigation paths from config
        nav_paths = self.config.get("navigation", {}).get("home", {})

        if any(
            current_path.startswith(p) for p in nav_paths if p.startswith("/products")
        ):
            return random.choices(
                ["/", "/search", "/products", "/cart"], weights=[0.3, 0.4, 0.2, 0.1]
            )[0]
        elif current_path == "/cart":
            return random.choices(
                ["/products", "/products?categoryID=*", "/search?q=*"],
                weights=[0.6, 0.3, 0.1],
            )[0]
        elif current_path == "/checkout":
            return "/cart"
        else:
            return random.choice(list(nav_paths.keys()))

    def _initialize_log_file(self) -> None:
        """Initialize log file with proper error handling"""
        try:
            # Check if we can write to the directory
            test_file = self.output_dir / ".write_test"
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except IOError as e:
                logger = self.loggers["system"]
                logger.error(f"Directory not writable: {e}")
                raise

            # Log initialization info to system log instead of access log
            logger = self.loggers["system"]
            logger.info(
                f"Access Log Generator started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(f"Output directory: {self.output_dir}")
            logger.info(f"Rate: {self.rate} logs/second")
            logger.info(f"Debug mode: {'on' if self.debug else 'off'}")
            logger.info(f"Pre-warm: {'yes' if self.pre_warm else 'no'}")

        except Exception as e:
            logger = self.loggers["system"]
            logger.critical(f"Initialization failed: {e}")
            sys.exit(1)

    def _write_log_entry(self, entry: str, max_retries: int = 3) -> bool:
        """Write a log entry with retry logic"""
        retry_delay = 1  # seconds

        access_logger = self.loggers["access"]
        system_logger = self.loggers["system"]

        for attempt in range(max_retries):
            try:
                # Write to access log
                if self.debug:
                    system_logger.debug(f"Writing log entry: {entry.strip()}")

                # Write the log entry to access log only
                access_logger.info(entry.strip())

                # Force immediate flush
                for handler in access_logger.handlers:
                    if hasattr(handler, "stream"):
                        handler.stream.flush()

                # No longer logging HTTP errors to error.log
                # They should only go to access.log

                return True
            except Exception as e:
                system_logger.warning(
                    f"Failed to write log entry (attempt {attempt + 1}/{max_retries}): {e}"
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

        return False

    def _handle_start_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the START state transitions"""
        possible_states = list(self.state_transitions[SessionState.START].keys())
        weights = [
            self.state_transitions[SessionState.START][s] for s in possible_states
        ]
        next_state = random.choices(possible_states, weights=weights)[0]
        # Convert to proper SessionState constant
        next_state = getattr(SessionState, next_state.upper())
        return next_state, []

    def _handle_login_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the LOGIN state and generate login entry"""
        username = self._generate_unique_username()
        self.user_pool.add(username)

        # Update session data with username
        session_data["username"] = username

        if self.debug:
            logger = self.loggers["system"]
            logger.debug(f"User logged in: {username}")

        log_entry = self._create_log_entry(
            ip=session_data["ip"],
            user=username,
            method="POST",
            path="/login",
            status=str(self.config.get("status_codes", {}).get("success", 200)),
            referrer="-",
            user_agent=session_data["user_agent"],
            session_id=session_data["session_id"],
        )

        possible_states = list(self.state_transitions[SessionState.LOGIN].keys())
        weights = [
            self.state_transitions[SessionState.LOGIN][s] for s in possible_states
        ]
        next_state = random.choices(possible_states, weights=weights)[0]

        if self.debug:
            logger = self.loggers["system"]
            logger.debug(f"Login -> {next_state}")

        return next_state, [log_entry]

    def _handle_browsing_state(
        self, session_data: Dict
    ) -> Generator[Tuple[str, List[str]], None, None]:
        """Handle the BROWSING state and generate browsing entries in real-time"""
        current_path = "/"
        browsing_duration = 0
        max_duration = random.randint(
            self.MIN_BROWSING_DURATION, self.MAX_BROWSING_DURATION
        )

        while browsing_duration < max_duration:
            path = self._get_next_page(current_path)
            path = self._add_query_params(path)
            current_path = path

            log_entry = self._create_log_entry(
                ip=session_data["ip"],
                user=session_data["username"],
                method="GET",
                path=path,
                status="200",
                referrer=self._get_referrer(path),
                user_agent=session_data["user_agent"],
                session_id=session_data["session_id"],
            )

            # Yield each entry with current state
            yield SessionState.BROWSING, [log_entry]

            # Sleep for a realistic page view interval
            view_time = random.uniform(
                self.PAGE_VIEW_INTERVAL * 0.5,  # Minimum time
                self.PAGE_VIEW_INTERVAL * 1.5,  # Maximum time
            )
            time.sleep(view_time)
            browsing_duration += view_time

        # Determine next state after browsing session ends
        possible_states = list(self.state_transitions[SessionState.BROWSING].keys())
        weights = [
            self.state_transitions[SessionState.BROWSING][s] for s in possible_states
        ]
        next_state = random.choices(possible_states, weights=weights)[0]

        # Yield final state transition
        yield next_state, []

    def _handle_logout_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the LOGOUT state and generate logout entry"""
        log_entry = self._create_log_entry(
            ip=session_data["ip"],
            user=session_data["username"],
            method="POST",
            path="/logout",
            status=str(self.config.get("status_codes", {}).get("success", 200)),
            referrer="-",
            user_agent=session_data["user_agent"],
            session_id=session_data["session_id"],
        )
        self.user_pool.discard(session_data["username"])
        return SessionState.END, [log_entry]

    def _handle_abandon_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the ABANDON state and generate abandon entry"""
        log_entries = []
        if random.random() < self.CART_ABANDON_RATE:
            log_entry = self._create_log_entry(
                ip=session_data["ip"],
                user=session_data["username"],
                method="GET",
                path="/cart",
                status="200",
                referrer=session_data["current_path"],
                user_agent=session_data["user_agent"],
                session_id=session_data["session_id"],
            )
            log_entries.append(log_entry)
        return SessionState.END, log_entries

    def _handle_error_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the ERROR state and generate error entry"""
        log_entry = self._create_log_entry(
            ip=session_data["ip"],
            user=session_data["username"],
            method="GET",
            path=session_data["current_path"],
            status=str(self.config.get("status_codes", {}).get("server_error", 500)),
            referrer=session_data["current_path"],
            user_agent=session_data["user_agent"],
            session_id=session_data["session_id"],
        )
        return SessionState.END, [log_entry]

    def _handle_direct_access_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the DIRECT_ACCESS state and generate direct access entry"""
        path = random.choice(["/products", "/search", "/about"])
        log_entry = self._create_log_entry(
            ip=session_data["ip"],
            user=session_data["username"],
            method="GET",
            path=path,
            status="200",
            referrer="-",
            user_agent=session_data["user_agent"],
            session_id=session_data["session_id"],
        )

        possible_states = list(
            self.state_transitions[SessionState.DIRECT_ACCESS].keys()
        )
        weights = [
            self.state_transitions[SessionState.DIRECT_ACCESS][s]
            for s in possible_states
        ]
        next_state = random.choices(possible_states, weights=weights)[0]

        return next_state, [log_entry]

    def _handle_leave_state(self, session_data: Dict) -> Tuple[str, List[str]]:
        """Handle the LEAVE state - user leaves without any action"""
        # Simply transition to END with no log entries
        return SessionState.END, []

    def _process_active_sessions(self, session_generators: List[Any]) -> List[Any]:
        """Process all active sessions and write their log entries"""
        active_sessions = []

        for gen in session_generators:
            try:
                next_state, log_entries = next(gen)

                for log_entry in log_entries:
                    if not self._write_log_entry(log_entry):
                        logger = self.loggers["system"]
                        logger.warning("Attempting to recover from write failure...")
                        time.sleep(5)
                        try:
                            self._initialize_log_file()
                        except Exception as e:
                            logger.critical(f"Failed to recover: {e}")
                            sys.exit(1)

                    if self.debug:
                        print(log_entry.strip())

                active_sessions.append(gen)
            except StopIteration:
                pass

        return active_sessions

    def _get_traffic_multiplier(self, hour: Optional[int] = None) -> float:
        """Calculate traffic multiplier based on time of day"""
        if hour is None:
            # Use current hour for live generation
            hour = datetime.now(pytz.timezone("US/Eastern")).hour

        for (start, end), multiplier in self.TRAFFIC_PATTERNS.items():
            if start <= hour < end or (start > end and (hour >= start or hour < end)):
                return multiplier
        return 0.2  # Default multiplier

    def _pre_warm_traffic(self) -> None:
        """Simulate 24 hours of traffic with error handling"""
        try:
            logger = self.loggers["system"]
            logger.info("Pre-warming with 24 hours of simulated traffic...")
            entries_buffer = []  # Buffer for batch writing
            BUFFER_SIZE = 1000  # Flush every 1000 entries

            # Generate full day at once
            for hour in range(24):
                traffic_mult = self._get_traffic_multiplier(hour)
                num_sessions = max(1, int(self.rate * 3600 * traffic_mult))  # Full hour
                logger.info(f"Generating {num_sessions} sessions for hour {hour}")

                for _ in range(num_sessions):
                    session_data = {
                        "ip": self.faker.ipv4(),
                        "user_agent": self.faker.user_agent(),
                        "session_id": str(uuid.uuid4()),
                        "username": "-",
                        "current_path": "/",
                    }

                    current_state = SessionState.START
                    while current_state != SessionState.END:
                        handler = self.state_handlers.get(current_state)
                        if handler:
                            next_state, log_entries = handler(session_data)
                            entries_buffer.extend(log_entries)

                            # Batch write when buffer is full
                            if len(entries_buffer) >= BUFFER_SIZE:
                                self._batch_write_entries(entries_buffer)
                                entries_buffer = []

                            current_state = next_state
                        else:
                            logger.error(f"No handler for state: {current_state}")
                            break

            # Write any remaining entries
            if entries_buffer:
                self._batch_write_entries(entries_buffer)

            logger.info("Pre-warm complete")

        except Exception as e:
            logger.error(f"Error during pre-warm: {e}")
            logger.exception("Full traceback:")

    def _batch_write_entries(self, entries: List[str]) -> None:
        """Write multiple log entries efficiently"""
        access_logger = self.loggers["access"]
        system_logger = self.loggers["system"]

        # Write all entries to access log only
        for entry in entries:
            access_logger.info(entry.strip())

        # Force flush after batch
        for handler in access_logger.handlers:
            if hasattr(handler, "stream"):
                handler.stream.flush()

    def generate_user_session(self) -> Generator[Tuple[str, List[str]], None, None]:
        """Generate a complete user session using state machine"""
        session_data = {
            "ip": self.faker.ipv4(),
            "user_agent": self.faker.user_agent(),
            "session_id": str(uuid.uuid4()),
            "username": "-",
            "current_path": "/",
        }

        current_state = SessionState.START

        while current_state != SessionState.END:
            handler = self.state_handlers.get(current_state)
            if handler:
                if current_state == SessionState.BROWSING:
                    # Handle browsing state specially for real-time generation
                    for next_state, log_entries in handler(session_data):
                        yield next_state, log_entries
                        if isinstance(next_state, str):
                            current_state = next_state
                            break
                else:
                    # Handle other states normally
                    next_state, log_entries = handler(session_data)
                    yield next_state, log_entries
                    current_state = next_state

    def run(self) -> None:
        """Run the log generator"""
        try:
            self._initialize_log_file()
            system_logger = self.loggers["system"]
            system_logger.info(
                f"Starting log generation. Logs will be written to: {self.log_file}"
            )

            # Start disk space monitoring
            self.monitor_disk_space(self.output_dir)

            if self.pre_warm:
                self._pre_warm_traffic()

            session_generators = []
            last_rate_check = time.time()
            tokens = 0.0  # Token bucket for rate control
            max_tokens = self.rate * 2  # Allow some burst capacity

            while True:
                now = time.time()
                time_elapsed = now - last_rate_check
                last_rate_check = now

                # Calculate current rate based on traffic patterns
                current_rate = self.rate * self._get_traffic_multiplier()

                # Add tokens based on elapsed time and current rate
                tokens = min(max_tokens, tokens + time_elapsed * current_rate)

                # Generate new sessions based on available tokens
                while tokens >= 1.0:
                    session_generators.append(self.generate_user_session())
                    tokens -= 1.0

                    # Log rate every 10 seconds
                    if int(now) % 10 == 0:
                        system_logger.info(
                            f"Current rate: {current_rate:.1f} logs/sec, "
                            f"Active sessions: {len(session_generators)}"
                        )

                # Process active sessions
                session_generators = self._process_active_sessions(session_generators)

                # Sleep to prevent CPU spinning while maintaining precision
                time.sleep(max(0, 1.0 / current_rate - 0.001))

        except KeyboardInterrupt:
            system_logger.info("Shutting down...")
        except Exception as e:
            system_logger.error(f"Error: {e}")
            system_logger.exception("Full traceback:")
            sys.exit(1)

    def monitor_disk_space(
        self, output_dir: Path, min_free_gb: float = 1.0, check_interval: int = 300
    ):
        """
        Monitor disk space and delete oldest log files if free space falls below threshold.

        Args:
            output_dir: Directory containing log files
            min_free_gb: Minimum free space in GB
            check_interval: Check interval in seconds (default: 300 = 5 minutes)
        """

        def _check_disk_space():
            while True:
                try:
                    # Get disk usage statistics
                    disk_usage = shutil.disk_usage(output_dir)
                    free_gb = disk_usage.free / (
                        1024 * 1024 * 1024
                    )  # Convert bytes to GB

                    # Log current disk space
                    logger = self.loggers["system"]
                    logger.info(f"Disk space monitor: {free_gb:.2f}GB free")

                    # If free space is below threshold, delete oldest log files
                    if free_gb < min_free_gb:
                        logger.warning(
                            f"Low disk space: {free_gb:.2f}GB free, need {min_free_gb}GB"
                        )

                        # Get all log files in the directory
                        log_files = []
                        for ext in [".log", ".log.*", ".gz"]:
                            log_files.extend(output_dir.glob(f"*{ext}"))

                        # Sort by modification time (oldest first)
                        log_files.sort(key=lambda x: x.stat().st_mtime)

                        # Delete oldest files until we have enough space or no more files
                        for log_file in log_files:
                            if free_gb >= min_free_gb:
                                break

                            file_size_gb = log_file.stat().st_size / (
                                1024 * 1024 * 1024
                            )
                            logger.warning(
                                f"Deleting old log file: {log_file} ({file_size_gb:.2f}GB)"
                            )

                            try:
                                log_file.unlink()
                                free_gb += file_size_gb
                            except Exception as e:
                                logger.error(f"Failed to delete {log_file}: {e}")

                        # Check if we've freed up enough space
                        disk_usage = shutil.disk_usage(output_dir)
                        free_gb = disk_usage.free / (1024 * 1024 * 1024)
                        logger.info(f"After cleanup: {free_gb:.2f}GB free")

                        if free_gb < min_free_gb:
                            logger.error(
                                f"Still low on disk space after cleanup: {free_gb:.2f}GB free"
                            )

                except Exception as e:
                    logger = self.loggers["system"]
                    logger.error(f"Error in disk space monitor: {e}")

                # Sleep for the specified interval
                time.sleep(check_interval)

        # Start the monitoring thread
        monitor_thread = threading.Thread(target=_check_disk_space, daemon=True)
        monitor_thread.start()
        system_logger = self.loggers["system"]
        system_logger.info(
            f"Disk space monitor started (min: {min_free_gb}GB, interval: {check_interval}s)"
        )
        return monitor_thread


def main():
    parser = argparse.ArgumentParser(description="Access Log Generator")
    parser.add_argument(
        "config",
        type=str,
        nargs="?",  # Make config optional
        help="Path to configuration file (optional if using environment variables)",
    )
    parser.add_argument(
        "--log-dir-override",
        type=str,
        help="Override the log directory specified in config",
    )

    parser.add_argument(
        "--exit",
        action="store_true",
        help="Exit immediately - used just for pre-caching dependencies",
    )

    args = parser.parse_args()

    # Temporary list for messages before logger is fully initialized
    # Some messages from load_config (like which file is used) are generated there.
    pre_log_messages = []

    if args.exit:
        # If exiting early, logger might not be set up, so print to stdout.
        print("Exiting after pre-caching dependencies...")
        return

    # Determine config_path based on args and env vars
    config_path_env = os.environ.get("LOG_GENERATOR_CONFIG_PATH")
    # Default to dummy_path if no CLI arg, to be resolved by load_config based on other env vars or default.
    config_path_cli = Path(args.config) if args.config else None

    if os.environ.get("LOG_GENERATOR_CONFIG_YAML_B64") or os.environ.get(
        "LOG_GENERATOR_CONFIG_YAML"
    ):
        # If direct YAML content is in env vars, use dummy_path, load_config will handle it.
        config_path = Path("dummy_path")
        if config_path_cli:
            pre_log_messages.append(
                (
                    "info",
                    f"Ignoring CLI config path '{config_path_cli}' because LOG_GENERATOR_CONFIG_YAML or LOG_GENERATOR_CONFIG_YAML_B64 is set.",
                )
            )
        elif config_path_env:
            pre_log_messages.append(
                (
                    "info",
                    f"Ignoring LOG_GENERATOR_CONFIG_PATH '{config_path_env}' because LOG_GENERATOR_CONFIG_YAML or LOG_GENERATOR_CONFIG_YAML_B64 is set.",
                )
            )
    elif config_path_env:
        config_path = Path(config_path_env)
        pre_log_messages.append(
            (
                "info",
                f"Using configuration from LOG_GENERATOR_CONFIG_PATH: {config_path}",
            )
        )
        if config_path_cli and config_path_cli != config_path:
            pre_log_messages.append(
                (
                    "info",
                    f"Ignoring CLI config path '{config_path_cli}' because LOG_GENERATOR_CONFIG_PATH is set.",
                )
            )
    elif config_path_cli:
        config_path = config_path_cli
        # This message will be logged by load_config itself: f"Loaded configuration from {config_path}"
    else:
        # No CLI, no LOG_GENERATOR_CONFIG_PATH, no direct YAML content. load_config will use DEFAULT_CONFIG_PATH or error.
        config_path = DEFAULT_CONFIG_PATH  # or Path("dummy_path") if we want load_config to default
        pre_log_messages.append(
            (
                "info",
                f"No config path specified, attempting to use default: {config_path}",
            )
        )

    config, messages_from_load_config = load_config(config_path)

    # Combine pre-log messages with those from load_config
    all_initial_messages = pre_log_messages + messages_from_load_config

    # Determine the log directory override
    log_dir_override_value = None
    override_source = None

    if args.log_dir_override:
        log_dir_override_value = args.log_dir_override
        override_source = "command-line argument"
    else:
        env_log_dir_override = os.environ.get("LOG_DIR_OVERRIDE")
        if env_log_dir_override:
            log_dir_override_value = env_log_dir_override
            override_source = "environment variable LOG_DIR_OVERRIDE"

    # Override log directory if specified by CLI or environment variable
    if log_dir_override_value:
        log_override_message = (
            "info",
            f"Overriding log directory with: {log_dir_override_value} (from {override_source})",
        )
        all_initial_messages.append(log_override_message)
        # Ensure 'output' key exists, though load_config should have created it or errored.
        if "output" not in config:
            config["output"] = {}
        config["output"]["directory"] = log_dir_override_value

    # Check for environment variable overrides
    env_overrides = []

    # Override rate if RATE_PER_SECOND is set
    rate_override = os.environ.get("RATE_PER_SECOND")
    if rate_override:
        try:
            rate_value = float(rate_override)
            if rate_value <= 0:
                all_initial_messages.append(
                    ("error", f"RATE_PER_SECOND must be positive, got: {rate_value}")
                )
                print(
                    f"❌ RATE_PER_SECOND must be positive, got: {rate_value}",
                    file=sys.stderr,
                )
                sys.exit(1)
            config["output"]["rate"] = rate_value
            env_overrides.append(f"rate={rate_value}")
        except ValueError:
            all_initial_messages.append(
                ("error", f"Invalid RATE_PER_SECOND value: {rate_override}")
            )
            print(f"❌ Invalid RATE_PER_SECOND value: {rate_override}", file=sys.stderr)
            sys.exit(1)

    # Override pre_warm if PRE_WARM is set
    pre_warm_override = os.environ.get("PRE_WARM")
    if pre_warm_override:
        pre_warm_value = pre_warm_override.lower() in ("true", "1", "yes", "on")
        config["output"]["pre_warm"] = pre_warm_value
        env_overrides.append(f"pre_warm={pre_warm_value}")

    # Override debug if DEBUG is set
    debug_override = os.environ.get("DEBUG")
    if debug_override:
        debug_value = debug_override.lower() in ("true", "1", "yes", "on")
        config["output"]["debug"] = debug_value
        env_overrides.append(f"debug={debug_value}")

    # Override no_error_log if NO_ERROR_LOG is set
    no_error_log_override = os.environ.get("NO_ERROR_LOG")
    if no_error_log_override:
        no_error_log_value = no_error_log_override.lower() in ("true", "1", "yes", "on")
        config["output"]["no_error_log"] = no_error_log_value
        env_overrides.append(f"no_error_log={no_error_log_value}")

    # Override no_system_log if NO_SYSTEM_LOG is set
    no_system_log_override = os.environ.get("NO_SYSTEM_LOG")
    if no_system_log_override:
        no_system_log_value = no_system_log_override.lower() in (
            "true",
            "1",
            "yes",
            "on",
        )
        config["output"]["no_system_log"] = no_system_log_value
        env_overrides.append(f"no_system_log={no_system_log_value}")

    if env_overrides:
        all_initial_messages.append(
            (
                "info",
                f"Environment variable overrides applied: {', '.join(env_overrides)}",
            )
        )

    # Initialize logging with possibly overridden directory and rotation settings
    loggers = setup_logging(Path(config["output"]["directory"]), config)
    system_logger = loggers["system"]

    # Log all collected initial messages
    for level, msg in all_initial_messages:
        if level == "info":
            system_logger.info(msg.strip("\n"))  # Strip newlines for cleaner log output
        elif level == "error":
            # Errors from load_config that didn't exit should be logged as errors.
            # Fatal errors in load_config already printed to stderr and exited.
            system_logger.error(msg.strip("\n"))

    # Pass loggers to the generator
    generator = AccessLogGenerator(config, loggers)
    generator.run()


if __name__ == "__main__":
    main()
