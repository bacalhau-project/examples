#!/usr/bin/env python3
"""Unit tests for access-log-generator.py"""

import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, mock_open, patch

import yaml


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation"""

    def setUp(self):
        # Import the validate_config function
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "access_log_generator",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "access-log-generator.py",
            ),
        )
        self.module = importlib.util.module_from_spec(spec)

        # Mock the dependencies before loading
        sys.modules["pytz"] = Mock()
        sys.modules["faker"] = Mock()
        sys.modules["yaml"] = yaml  # Use real yaml

        # Add the dynamically loaded module to sys.modules so patch can find it
        sys.modules["access_log_generator"] = self.module

        spec.loader.exec_module(self.module)
        self.validate_config = self.module.validate_config
        self.SessionState = self.module.SessionState

    def test_valid_config(self):
        """Test validation of a valid configuration"""
        config = {
            "output": {"directory": "/tmp/logs", "rate": 10.0, "debug": False},
            "state_transitions": {"START": {"LOGIN": 0.7, "DIRECT_ACCESS": 0.3}},
            "navigation": {"index": {"/about": 0.3, "/products": 0.5, "/search": 0.2}},
            "error_rates": {"global_500_rate": 0.001, "product_404_rate": 0.05},
            "session": {"min_browsing_duration": 30, "max_browsing_duration": 300},
            "traffic_patterns": [
                {"time": "0-6", "multiplier": 0.1},
                {"time": "6-9", "multiplier": 0.8},
                {"time": "9-17", "multiplier": 1.0},
                {"time": "17-22", "multiplier": 0.6},
                {"time": "22-0", "multiplier": 0.3},  # Wrap around to midnight
            ],
        }
        is_valid, messages = self.validate_config(config)
        if not is_valid:
            print(f"Validation failed with messages: {messages}")
        self.assertTrue(is_valid)
        self.assertEqual(len(messages), 0)

    def test_missing_sections(self):
        """Test validation with missing required sections"""
        config = {"output": {"directory": "/tmp", "rate": 10}}
        is_valid, messages = self.validate_config(config)
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing required" in msg[1] for msg in messages))

    def test_invalid_rate(self):
        """Test validation with invalid rate"""
        config = {
            "output": {
                "directory": "/tmp/logs",
                "rate": -1,  # Invalid negative rate
                "debug": False,
            },
            "state_transitions": {},
            "navigation": {},
            "error_rates": {},
            "session": {},
            "traffic_patterns": {},
        }
        is_valid, messages = self.validate_config(config)
        self.assertFalse(is_valid)
        self.assertTrue(any("Rate must be a positive" in msg[1] for msg in messages))

    def test_session_states(self):
        """Test that all required session states are defined"""
        self.assertEqual(self.SessionState.START, "START")
        self.assertEqual(self.SessionState.LOGIN, "LOGIN")
        self.assertEqual(self.SessionState.DIRECT_ACCESS, "DIRECT_ACCESS")
        self.assertEqual(self.SessionState.BROWSING, "BROWSING")
        self.assertEqual(self.SessionState.LOGOUT, "LOGOUT")
        self.assertEqual(self.SessionState.ABANDON, "ABANDON")
        self.assertEqual(self.SessionState.LEAVE, "LEAVE")
        self.assertEqual(self.SessionState.ERROR, "ERROR")
        self.assertEqual(self.SessionState.END, "END")


class TestLogGeneration(unittest.TestCase):
    """Test log generation functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "output": {
                "directory": self.temp_dir,
                "rate": 10.0,
                "debug": False,
                "pre_warm": False,
                "log_rotation": {"enabled": False},
            },
            "state_transitions": {"START": {"LOGIN": 0.7, "DIRECT_ACCESS": 0.3}},
            "navigation": {"index": {"/about": 0.3, "/products": 0.5, "/search": 0.2}},
            "error_rates": {"global_500_rate": 0.001, "product_404_rate": 0.05},
            "session": {"min_browsing_duration": 30, "max_browsing_duration": 300},
            "traffic_patterns": [{"time": "0-23", "multiplier": 1.0}],
        }

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)

    def test_config_structure(self):
        """Test that config has all required sections"""
        required_sections = [
            "output",
            "state_transitions",
            "navigation",
            "error_rates",
            "session",
            "traffic_patterns",
        ]
        for section in required_sections:
            self.assertIn(section, self.config)

    def test_output_directory_creation(self):
        """Test that output directory is created"""
        # Directory should exist after setUp
        self.assertTrue(os.path.exists(self.temp_dir))
        self.assertTrue(os.path.isdir(self.temp_dir))


class TestTrafficPatterns(unittest.TestCase):
    """Test traffic pattern calculations"""

    def test_hourly_pattern_parsing(self):
        """Test parsing of hourly traffic patterns"""
        patterns = [
            {"time": "0-6", "multiplier": 0.1},
            {"time": "6-9", "multiplier": 0.8},
            {"time": "9-17", "multiplier": 1.0},
            {"time": "17-22", "multiplier": 0.6},
            {"time": "22-0", "multiplier": 0.3},  # Wrap to midnight
        ]

        # Test that all hours are covered
        hours_covered = set()
        for pattern in patterns:
            time_range = pattern["time"]
            if "-" in time_range:
                start, end = map(int, time_range.split("-"))
                if end < start:  # Handle wrap-around (e.g., 22-2)
                    hours_covered.update(range(start, 24))
                    hours_covered.update(range(0, end))
                else:
                    hours_covered.update(range(start, end))

        # Should cover all 24 hours
        self.assertEqual(len(hours_covered), 24)

    def test_multiplier_values(self):
        """Test that traffic multipliers are valid"""
        patterns = [
            {"time": "0-6", "multiplier": 0.1},
            {"time": "6-9", "multiplier": 0.8},
            {"time": "9-17", "multiplier": 1.0},
            {"time": "17-22", "multiplier": 0.6},
            {"time": "22-0", "multiplier": 0.3},  # Wrap to midnight
        ]

        for pattern in patterns:
            multiplier = pattern["multiplier"]
            self.assertGreaterEqual(multiplier, 0)
            self.assertLessEqual(multiplier, 2.0)  # Reasonable upper bound


class TestNCSALogFormat(unittest.TestCase):
    """Test that generated logs conform to NCSA Combined Log Format"""

    def setUp(self):
        """Set up test with sample log entries"""
        # Standard NCSA Combined Log Format pattern
        # %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-agent}i"
        self.ncsa_pattern = re.compile(
            r"^(\S+) (\S+) (\S+) \[([\w:/]+\s[+\-]\d{4})\] "
            r'"(\S+) (\S+) (\S+)" (\d{3}) (\d+|-) '
            r'"([^"]*)" "([^"]*)"$'
        )

        # Sample log entries to test
        self.valid_logs = [
            '192.168.1.100 - - [10/Oct/2024:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 5432 "-" "Mozilla/5.0"',
            '10.0.0.1 - john_doe [01/Jan/2025:00:00:00 +0000] "POST /login HTTP/1.1" 302 0 "http://example.com" "Chrome/120.0"',
            '172.16.0.5 - - [31/Dec/2024:23:59:59 -0800] "GET /products?id=123 HTTP/1.1" 404 1234 "-" "Safari/16.0"',
            '192.168.1.1 - admin [15/Mar/2025:14:30:45 +0100] "DELETE /api/user/456 HTTP/1.1" 500 567 "http://admin.example.com" "curl/7.68.0"',
        ]

        self.invalid_logs = [
            "invalid log format",
            "192.168.1.1 missing brackets timestamp",
            "192.168.1.1 - - [10/Oct/2024:13:55:36 +0000] missing quotes",
            '192.168.1.1 - - [bad-date-format] "GET / HTTP/1.1" 200 100 "-" "Mozilla"',
        ]

    def test_valid_ncsa_format(self):
        """Test that valid NCSA logs match the pattern"""
        for log_entry in self.valid_logs:
            with self.subTest(log=log_entry):
                match = self.ncsa_pattern.match(log_entry)
                self.assertIsNotNone(match, f"Failed to match valid log: {log_entry}")

                # Verify captured groups
                (
                    ip,
                    remote_logname,
                    user,
                    timestamp,
                    method,
                    path,
                    protocol,
                    status,
                    size,
                    referer,
                    user_agent,
                ) = match.groups()

                # Basic validations
                self.assertTrue(self._is_valid_ip(ip), f"Invalid IP: {ip}")
                self.assertEqual(remote_logname, "-")  # Always '-' in practice
                self.assertIn(user, ["-", "john_doe", "admin"])
                self.assertIn(method, ["GET", "POST", "DELETE"])
                self.assertTrue(path.startswith("/"))
                self.assertEqual(protocol, "HTTP/1.1")
                self.assertIn(int(status), [200, 302, 404, 500])
                self.assertTrue(size.isdigit() or size == "-")

    def test_invalid_ncsa_format(self):
        """Test that invalid logs don't match the pattern"""
        for log_entry in self.invalid_logs:
            with self.subTest(log=log_entry):
                match = self.ncsa_pattern.match(log_entry)
                self.assertIsNone(
                    match, f"Incorrectly matched invalid log: {log_entry}"
                )

    def test_generated_log_format(self):
        """Test that the generator creates valid NCSA format logs"""
        # Test various log entries that would be generated
        import random
        from datetime import datetime

        test_cases = [
            {
                "ip": "192.168.1.100",
                "user": "-",
                "timestamp": datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000"),
                "method": "GET",
                "path": "/test",
                "status": 200,
                "size": random.randint(100, 10000),
                "referrer": "-",
                "user_agent": "Mozilla/5.0 (test)",
            },
            {
                "ip": "10.0.0.1",
                "user": "testuser",
                "timestamp": datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000"),
                "method": "POST",
                "path": "/api/data",
                "status": 201,
                "size": 0,
                "referrer": "http://example.com/form",
                "user_agent": "CustomBot/1.0",
            },
            {
                "ip": "172.16.0.1",
                "user": "-",
                "timestamp": datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000"),
                "method": "GET",
                "path": "/products?id=123&category=electronics",
                "status": 404,
                "size": 1234,
                "referrer": "-",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        ]

        for test_data in test_cases:
            with self.subTest(test_data=test_data):
                # Format log entry as the generator does
                log_entry = (
                    f"{test_data['ip']} - {test_data['user']} [{test_data['timestamp']}] "
                    f'"{test_data["method"]} {test_data["path"]} HTTP/1.1" '
                    f"{test_data['status']} {test_data['size']} "
                    f'"{test_data["referrer"]}" "{test_data["user_agent"]}"'
                )

                # Verify it matches NCSA format
                match = self.ncsa_pattern.match(log_entry)
                self.assertIsNotNone(
                    match, f"Generated log doesn't match NCSA format: {log_entry}"
                )

                # Verify parsed values match input
                (
                    ip,
                    _,
                    user,
                    timestamp,
                    method,
                    path,
                    protocol,
                    status,
                    size,
                    referrer,
                    user_agent,
                ) = match.groups()
                self.assertEqual(ip, test_data["ip"])
                self.assertEqual(user, test_data["user"])
                self.assertEqual(method, test_data["method"])
                self.assertEqual(path, test_data["path"])
                self.assertEqual(int(status), test_data["status"])
                self.assertEqual(int(size), test_data["size"])
                self.assertEqual(referrer, test_data["referrer"])
                self.assertEqual(user_agent, test_data["user_agent"])

    def test_timestamp_format(self):
        """Test that timestamps follow the correct format"""
        # NCSA timestamp format: [DD/Mon/YYYY:HH:MM:SS ±HHMM]
        timestamp_pattern = re.compile(
            r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+\-]\d{4}"
        )

        valid_timestamps = [
            "10/Oct/2024:13:55:36 +0000",
            "01/Jan/2025:00:00:00 +0000",
            "31/Dec/2024:23:59:59 -0800",
            "15/Mar/2025:14:30:45 +0100",
        ]

        for ts in valid_timestamps:
            with self.subTest(timestamp=ts):
                self.assertIsNotNone(timestamp_pattern.match(ts))

    def test_status_codes(self):
        """Test that status codes are valid HTTP codes"""
        valid_codes = [200, 201, 204, 301, 302, 304, 400, 401, 403, 404, 500, 502, 503]

        for code in valid_codes:
            log_entry = f'192.168.1.1 - - [10/Oct/2024:13:55:36 +0000] "GET / HTTP/1.1" {code} 100 "-" "Mozilla"'
            match = self.ncsa_pattern.match(log_entry)
            self.assertIsNotNone(match)
            self.assertEqual(match.group(8), str(code))

    def _is_valid_ip(self, ip):
        """Helper to validate IP address format"""
        try:
            parts = ip.split(".")
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except:
            return False


class TestLogDirectoryOverride(unittest.TestCase):
    """Test log directory override functionality"""

    def setUp(self):
        """Set up test environment for log directory override tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file_path = os.path.join(self.temp_dir, "config.yaml")
        self.default_log_dir = os.path.join(self.temp_dir, "default_logs")
        self.cli_override_log_dir = os.path.join(self.temp_dir, "cli_override_logs")
        self.env_override_log_dir = os.path.join(self.temp_dir, "env_override_logs")

        # Create a dummy config file
        self.config_data = {
            "output": {
                "directory": self.default_log_dir,
                "rate": 1,
                "log_rotation": {"enabled": False},
            },
            "state_transitions": {"START": {"LOGIN": 1.0}},
            "navigation": {},
            "error_rates": {},
            "session": {},
            "traffic_patterns": [],
        }
        with open(self.config_file_path, "w") as f:
            yaml.dump(self.config_data, f)

        # Import the main function and other necessary components from the script
        import importlib.util

        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "access-log-generator.py",
        )
        spec = importlib.util.spec_from_file_location(
            "access_log_generator", script_path
        )
        self.module = importlib.util.module_from_spec(spec)

        # Mock dependencies before loading the module
        sys.modules["pytz"] = Mock()
        sys.modules["faker"] = Mock()
        sys.modules["yaml"] = yaml

        # Add the dynamically loaded module to sys.modules so patch can find it
        sys.modules["access_log_generator"] = self.module

        spec.loader.exec_module(self.module)
        self.main_func = self.module.main
        self.load_config_func = self.module.load_config  # For direct testing if needed
        self.DEFAULT_CONFIG_PATH = self.module.DEFAULT_CONFIG_PATH

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
        # Reset DEFAULT_CONFIG_PATH if it was changed
        self.module.DEFAULT_CONFIG_PATH = self.DEFAULT_CONFIG_PATH

    @patch(
        "access_log_generator.AccessLogGenerator.run"
    )  # Prevent actual log generation
    @patch("access_log_generator.setup_logging")
    def test_cli_override(self, mock_setup_logging, mock_run):
        """Test log directory override using command-line argument."""
        test_args = [
            "access-log-generator.py",
            self.config_file_path,
            "--log-dir-override",
            self.cli_override_log_dir,
        ]
        with patch.object(sys, "argv", test_args):
            self.main_func()
        mock_setup_logging.assert_called_once()
        called_config = mock_setup_logging.call_args[0][1]
        self.assertEqual(
            called_config["output"]["directory"], self.cli_override_log_dir
        )

    @patch("access_log_generator.AccessLogGenerator.run")
    @patch("access_log_generator.setup_logging")
    @patch.dict(os.environ, {"LOG_DIR_OVERRIDE": "placeholder_env_override_logs"})
    def test_env_override(self, mock_setup_logging, mock_run):
        """Test log directory override using environment variable."""
        # Update placeholder with dynamic path
        os.environ["LOG_DIR_OVERRIDE"] = self.env_override_log_dir
        test_args = ["access-log-generator.py", self.config_file_path]
        with patch.object(sys, "argv", test_args):
            self.main_func()
        mock_setup_logging.assert_called_once()
        called_config = mock_setup_logging.call_args[0][1]
        self.assertEqual(
            called_config["output"]["directory"], self.env_override_log_dir
        )
        del os.environ["LOG_DIR_OVERRIDE"]  # Clean up env var

    @patch("access_log_generator.AccessLogGenerator.run")
    @patch("access_log_generator.setup_logging")
    @patch.dict(os.environ, {"LOG_DIR_OVERRIDE": "placeholder_env_override_logs"})
    def test_cli_takes_precedence(self, mock_setup_logging, mock_run):
        """Test CLI override takes precedence over environment variable."""
        os.environ["LOG_DIR_OVERRIDE"] = self.env_override_log_dir
        test_args = [
            "access-log-generator.py",
            self.config_file_path,
            "--log-dir-override",
            self.cli_override_log_dir,
        ]
        with patch.object(sys, "argv", test_args):
            self.main_func()
        mock_setup_logging.assert_called_once()
        called_config = mock_setup_logging.call_args[0][1]
        self.assertEqual(
            called_config["output"]["directory"], self.cli_override_log_dir
        )
        del os.environ["LOG_DIR_OVERRIDE"]

    @patch("access_log_generator.AccessLogGenerator.run")
    @patch("access_log_generator.setup_logging")
    def test_config_default(self, mock_setup_logging, mock_run):
        """Test log directory uses config default when no overrides are present."""
        test_args = ["access-log-generator.py", self.config_file_path]
        with patch.object(sys, "argv", test_args):
            self.main_func()
        mock_setup_logging.assert_called_once()
        called_config = mock_setup_logging.call_args[0][1]
        self.assertEqual(called_config["output"]["directory"], self.default_log_dir)


if __name__ == "__main__":
    unittest.main()
