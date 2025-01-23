import argparse
import base64
import gzip
import logging
import logging.handlers
import os
import random
import shutil
import sys
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


def validate_config(config: dict) -> bool:
    """Validate configuration structure and values"""
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
        print(
            f"❌ Missing required configuration sections: {', '.join(missing_sections)}"
        )
        return False

    # Validate output settings
    output = config.get("output", {})
    if not isinstance(output.get("directory", ""), str):
        print("❌ Output directory must be a string")
        return False
    if not isinstance(output.get("rate", 0), (int, float)) or output["rate"] <= 0:
        print("❌ Rate must be a positive number")
        return False

    # Validate state transitions
    for state, transitions in config.get("state_transitions", {}).items():
        if not isinstance(transitions, dict):
            print(f"❌ State transitions for {state} must be a dictionary")
            return False
        total = sum(transitions.values())
        if not (0.99 <= total <= 1.01):  # Allow for floating point imprecision
            print(f"❌ State transitions for {state} must sum to 1.0 (got {total})")
            return False

    # Validate traffic patterns
    for pattern in config.get("traffic_patterns", []):
        if "time" not in pattern or "multiplier" not in pattern:
            print("❌ Traffic patterns must have 'time' and 'multiplier' keys")
            return False
        try:
            start, end = map(int, pattern["time"].split("-"))
            if not (0 <= start <= 23) or not (0 <= end <= 23):
                print(f"❌ Invalid time range: {pattern['time']}")
                return False
        except ValueError:
            print(f"❌ Invalid time format: {pattern['time']}")
            return False

    return True


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load and validate configuration from environment variables or file"""
    config = None

    # Try base64 encoded config first
    env_config_b64 = os.environ.get("LOG_GENERATOR_CONFIG_YAML_B64")
    if env_config_b64:
        try:
            decoded_config = base64.b64decode(env_config_b64).decode("utf-8")
            config = yaml.safe_load(decoded_config)
            print(
                "✅ Loaded configuration from LOG_GENERATOR_CONFIG_YAML_B64 environment variable"
            )
        except base64.binascii.Error as e:
            print(f"❌ Failed to decode base64 configuration: {e}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Failed to parse base64 decoded YAML: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error processing base64 configuration: {e}")
            sys.exit(1)

    # If no base64 config, try plain YAML env var
    if config is None:
        env_config = os.environ.get("LOG_GENERATOR_CONFIG_YAML")
        if env_config:
            try:
                # Try parsing as direct YAML content first
                try:
                    config = yaml.safe_load(env_config)
                    print(
                        "✅ Loaded configuration from LOG_GENERATOR_CONFIG_YAML environment variable"
                    )
                except yaml.YAMLError:
                    # If parsing fails, try treating it as a file path
                    env_path = Path(env_config)
                    if env_path.exists():
                        with open(env_path) as f:
                            config = yaml.safe_load(f)
                        print(
                            f"✅ Loaded configuration from environment-specified path: {env_path}"
                        )
                    else:
                        print(
                            "❌ LOG_GENERATOR_CONFIG_YAML contains invalid YAML and is not a valid file path"
                        )
                        sys.exit(1)
            except Exception as e:
                print(f"❌ Failed to load configuration from environment variable: {e}")
                sys.exit(1)

    # If no environment configs, use file config
    if config is None:
        if not config_path.exists():
            print(f"❌ Configuration file not found: {config_path}")
            sys.exit(1)

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                print(f"✅ Loaded configuration from {config_path}")
        except yaml.YAMLError as e:
            print(f"❌ YAML parsing error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            sys.exit(1)

    # Validate configuration
    if not validate_config(config):
        print("❌ Configuration validation failed")
        sys.exit(1)

    # Print configuration summary
    print("\n⚙️  Configuration Summary:")
    print(f"  Output Directory: {config['output']['directory']}")
    print(f"  Base Rate: {config['output']['rate']} logs/sec")
    print(f"  Debug Mode: {config['output'].get('debug', False)}")
    print(f"  Pre-warm: {config['output'].get('pre_warm', True)}")
    print("\n  State Transitions:")
    for state, transitions in config["state_transitions"].items():
        print(f"    {state}:")
        for action, prob in transitions.items():
            print(f"      {action}: {prob:.2f}")
    print("\n  Traffic Patterns:")
    for pattern in config["traffic_patterns"]:
        print(f"    {pattern['time']}: {pattern['multiplier']}x")
    print("\n✅ Configuration validated successfully\n")

    return config


# Configure separate logging streams
def setup_logging(output_dir: Path) -> logging.Logger:
    """Configure logging with separate streams for access and errors"""
    try:
        # Ensure parent directories exist with correct permissions
        parent_dir = output_dir.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                # Make parent directory world-writable for container environments
                os.chmod(parent_dir, 0o777)
            except Exception as e:
                print(f"❌ Failed to create parent directory {parent_dir}: {e}")
                sys.exit(1)

        # Create output directory with permissive permissions if it doesn't exist
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                os.chmod(output_dir, 0o777)  # Make world-writable
                print(f"✅ Created output directory: {output_dir}")
            except Exception as e:
                print(f"❌ Failed to create output directory {output_dir}: {e}")
                sys.exit(1)
        else:
            # If directory exists, ensure it's writable
            try:
                os.chmod(output_dir, 0o777)  # Make world-writable
                print(f"✅ Updated permissions for existing directory: {output_dir}")
            except Exception as e:
                print(f"❌ Failed to update permissions for {output_dir}: {e}")
                sys.exit(1)

        # Verify write access
        if not os.access(output_dir, os.W_OK):
            print(f"❌ Log directory not writable: {output_dir}")
            try:
                import subprocess

                # Show detailed directory information
                print("\nDirectory Details:")
                subprocess.run(["ls", "-la", str(output_dir)], check=True)
                print("\nParent Directory Details:")
                subprocess.run(["ls", "-la", str(output_dir.parent)], check=True)
                print("\nCurrent Process User/Group:")
                subprocess.run(["id"], check=True)

                # Try to detect if running in container
                if os.path.exists("/.dockerenv"):
                    print("\nRunning inside container")
                    # Show mount information
                    print("\nMount Information:")
                    subprocess.run(["mount"], check=True)

                # Show SELinux context if available
                try:
                    print("\nSELinux Context:")
                    subprocess.run(["ls", "-Z", str(output_dir)], check=True)
                except subprocess.CalledProcessError:
                    print("SELinux information not available")

            except Exception as e:
                print(f"Could not check detailed permissions: {e}")
            sys.exit(1)

        # Test write access with a temporary file
        test_file = output_dir / ".write_test"
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            print(f"✅ Successfully verified write access to {output_dir}")
        except Exception as e:
            print(f"❌ Failed write access test: {e}")
            sys.exit(1)

        # Main logger for system messages
        logger = logging.getLogger("access_log_generator")
        logger.setLevel(logging.INFO)

        # Clear any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Console handler for system messages
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler for system messages
        system_log = output_dir / "system.log"
        file_handler = CustomRotatingHandler(
            system_log,
            max_bytes=100 * 1024 * 1024,  # 100MB
            backup_count=7,
            compress=True,
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)

        # Access logger for NCSA compliant logs
        access_logger = logging.getLogger("access")
        access_logger.setLevel(logging.INFO)
        for handler in access_logger.handlers[:]:
            access_logger.removeHandler(handler)
        access_handler = CustomRotatingHandler(
            output_dir / "access.log",
            max_bytes=500 * 1024 * 1024,  # 500MB
            backup_count=7,
            compress=True,
        )
        access_handler.setFormatter(logging.Formatter("%(message)s"))
        access_logger.addHandler(access_handler)
        access_logger.propagate = False

        # Error logger for error logs
        error_logger = logging.getLogger("error")
        error_logger.setLevel(logging.ERROR)
        for handler in error_logger.handlers[:]:
            error_logger.removeHandler(handler)
        error_handler = CustomRotatingHandler(
            output_dir / "error.log",
            max_bytes=100 * 1024 * 1024,  # 100MB
            backup_count=7,
            compress=True,
        )
        error_handler.setFormatter(logging.Formatter("%(message)s"))
        error_logger.addHandler(error_handler)
        error_logger.propagate = False

        return logger

    except Exception as e:
        print(f"❌ Failed to setup logging: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


class CustomRotatingHandler(TimedRotatingFileHandler):
    """Custom log handler that combines time and size based rotation with compression"""

    def __init__(
        self,
        filename,
        mode="a",
        encoding="utf-8",
        delay=False,
        max_bytes=100 * 1024 * 1024,
        backup_count=7,
        compress=True,
    ):
        # Initialize with daily rotation
        super().__init__(
            filename,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay,
        )
        self.maxBytes = max_bytes
        self.compress = compress

        # Ensure directory exists with correct permissions
        log_dir = Path(filename).parent
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(log_dir, 0o777)

        # Set file permissions if file exists or after it's created
        if os.path.exists(filename):
            os.chmod(filename, 0o666)  # World readable/writable
        else:
            # Create file with correct permissions
            Path(filename).touch(mode=0o666)

    def _open(self):
        """Override _open to ensure correct permissions on new files"""
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o666)  # World readable/writable
        except Exception:
            pass  # Don't fail if we can't set permissions
        return stream

    def rotate(self, source, dest):
        """Rotate the file and compress if needed with correct permissions"""
        if os.path.exists(source):
            if self.compress:
                with open(source, "rb") as f_in:
                    with gzip.open(f"{dest}.gz", "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(source)
                # Set permissions on compressed file
                os.chmod(f"{dest}.gz", 0o666)
            else:
                shutil.move(source, dest)
                # Set permissions on rotated file
                os.chmod(dest, 0o666)


class AccessLogGenerator:
    def __init__(self, config: Dict):
        """Initialize generator with configuration"""
        self.config = config
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

        self._log_configuration()

    def _log_configuration(self) -> None:
        """Log the configuration settings"""
        logger.info("Starting access log generator with configuration:")
        logger.info(f"  Output directory: {self.output_dir}")
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
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
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
                logger.error(f"Directory not writable: {e}")
                raise

            # Log initialization info to system log instead of access log
            logger.info(
                f"Access Log Generator started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(f"Output directory: {self.output_dir}")
            logger.info(f"Rate: {self.rate} logs/second")
            logger.info(f"Debug mode: {'on' if self.debug else 'off'}")
            logger.info(f"Pre-warm: {'yes' if self.pre_warm else 'no'}")

        except Exception as e:
            logger.critical(f"Initialization failed: {e}")
            sys.exit(1)

    def _write_log_entry(self, entry: str) -> bool:
        """Write log entry with error handling and retries"""
        max_retries = 3
        retry_delay = 1  # seconds

        access_logger = logging.getLogger("access")
        error_logger = logging.getLogger("error")

        for attempt in range(max_retries):
            try:
                # Write to access log
                if self.debug:
                    logger.debug(f"Writing log entry: {entry.strip()}")

                access_logger.info(entry.strip())

                # Force flush the handlers
                for handler in access_logger.handlers:
                    handler.flush()

                # If entry contains an error status code, log to error log
                status_codes = self.config.get("status_codes", {})
                error_codes = [
                    str(status_codes.get("not_found", 404)),
                    str(status_codes.get("server_error", 500)),
                    str(status_codes.get("forbidden", 403)),
                    str(status_codes.get("unauthorized", 401)),
                ]
                if any(f" {code} " in entry for code in error_codes):
                    error_logger.error(entry.strip())
                    for handler in error_logger.handlers:
                        handler.flush()

                return True
            except Exception as e:
                logger.warning(
                    f"Failed to write log entry (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to write log entry after {max_retries} attempts"
                    )
                    return False
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
        access_logger = logging.getLogger("access")
        error_logger = logging.getLogger("error")

        # Write all entries at once
        access_logger.info("\n".join(e.strip() for e in entries))

        # Write error entries if any
        error_entries = [
            e for e in entries if any(f" {code} " in e for code in self.error_codes)
        ]
        if error_entries:
            error_logger.error("\n".join(e.strip() for e in error_entries))

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
        """Main generator loop with precise rate control"""
        try:
            self._initialize_log_file()
            logger.info(
                f"Starting log generation. Logs will be written to: {self.log_file}"
            )

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
                        logger.info(
                            f"Current rate: {current_rate:.1f} logs/sec, "
                            f"Active sessions: {len(session_generators)}"
                        )

                # Process active sessions
                session_generators = self._process_active_sessions(session_generators)

                # Sleep to prevent CPU spinning while maintaining precision
                time.sleep(max(0, 1.0 / current_rate - 0.001))

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.exception("Full traceback:")
            sys.exit(1)


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

    args = parser.parse_args()

    # Check if we have environment variables for config
    if (
        os.environ.get("LOG_GENERATOR_CONFIG_YAML_B64") is None
        and os.environ.get("LOG_GENERATOR_CONFIG_YAML") is None
    ):
        # If no environment variables, require config file
        if args.config is None:
            parser.error(
                "Configuration file is required when not using environment variables"
            )
        config_path = Path(args.config)
    else:
        # Use dummy path when using environment variables
        config_path = Path("dummy_path")

    config = load_config(config_path)

    # Override log directory if specified
    if args.log_dir_override:
        print(f"Overriding log directory with: {args.log_dir_override}")
        config["output"]["directory"] = args.log_dir_override

    # Initialize logging with possibly overridden directory
    global logger  # Make logger global
    logger = setup_logging(Path(config["output"]["directory"]))

    generator = AccessLogGenerator(config)
    generator.run()


if __name__ == "__main__":
    main()
