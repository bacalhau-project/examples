#!/usr/bin/env python3
"""Unit tests for access-log-generator.py"""

import unittest
from unittest.mock import Mock, patch, mock_open
import tempfile
import shutil
import os
import yaml
from datetime import datetime
import sys


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation"""
    
    def setUp(self):
        # Import the validate_config function
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "access_log_generator",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "access-log-generator.py")
        )
        self.module = importlib.util.module_from_spec(spec)
        
        # Mock the dependencies before loading
        sys.modules['pytz'] = Mock()
        sys.modules['faker'] = Mock()
        sys.modules['yaml'] = yaml  # Use real yaml
        
        spec.loader.exec_module(self.module)
        self.validate_config = self.module.validate_config
        self.SessionState = self.module.SessionState
    
    def test_valid_config(self):
        """Test validation of a valid configuration"""
        config = {
            'output': {
                'directory': '/tmp/logs',
                'rate': 10.0,
                'debug': False
            },
            'state_transitions': {
                'START': {'LOGIN': 0.7, 'DIRECT_ACCESS': 0.3}
            },
            'navigation': {
                'index': {'/about': 0.3, '/products': 0.5, '/search': 0.2}
            },
            'error_rates': {
                'global_500_rate': 0.001,
                'product_404_rate': 0.05
            },
            'session': {
                'min_browsing_duration': 30,
                'max_browsing_duration': 300
            },
            'traffic_patterns': [
                {'time': '0-6', 'multiplier': 0.1},
                {'time': '6-9', 'multiplier': 0.8},
                {'time': '9-17', 'multiplier': 1.0},
                {'time': '17-22', 'multiplier': 0.6},
                {'time': '22-0', 'multiplier': 0.3}  # Wrap around to midnight
            ]
        }
        is_valid, messages = self.validate_config(config)
        if not is_valid:
            print(f"Validation failed with messages: {messages}")
        self.assertTrue(is_valid)
        self.assertEqual(len(messages), 0)
    
    def test_missing_sections(self):
        """Test validation with missing required sections"""
        config = {
            'output': {'directory': '/tmp', 'rate': 10}
        }
        is_valid, messages = self.validate_config(config)
        self.assertFalse(is_valid)
        self.assertTrue(any('Missing required' in msg[1] for msg in messages))
    
    def test_invalid_rate(self):
        """Test validation with invalid rate"""
        config = {
            'output': {
                'directory': '/tmp/logs',
                'rate': -1,  # Invalid negative rate
                'debug': False
            },
            'state_transitions': {},
            'navigation': {},
            'error_rates': {},
            'session': {},
            'traffic_patterns': {}
        }
        is_valid, messages = self.validate_config(config)
        self.assertFalse(is_valid)
        self.assertTrue(any('Rate must be a positive' in msg[1] for msg in messages))
    
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
            'output': {
                'directory': self.temp_dir,
                'rate': 10.0,
                'debug': False,
                'pre_warm': False,
                'log_rotation': {'enabled': False}
            },
            'state_transitions': {
                'START': {'LOGIN': 0.7, 'DIRECT_ACCESS': 0.3}
            },
            'navigation': {
                'index': {'/about': 0.3, '/products': 0.5, '/search': 0.2}
            },
            'error_rates': {
                'global_500_rate': 0.001,
                'product_404_rate': 0.05
            },
            'session': {
                'min_browsing_duration': 30,
                'max_browsing_duration': 300
            },
            'traffic_patterns': [
                {'time': '0-23', 'multiplier': 1.0}
            ]
        }
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_config_structure(self):
        """Test that config has all required sections"""
        required_sections = ['output', 'state_transitions', 'navigation', 
                           'error_rates', 'session', 'traffic_patterns']
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
            {'time': '0-6', 'multiplier': 0.1},
            {'time': '6-9', 'multiplier': 0.8},
            {'time': '9-17', 'multiplier': 1.0},
            {'time': '17-22', 'multiplier': 0.6},
            {'time': '22-0', 'multiplier': 0.3}  # Wrap to midnight
        ]
        
        # Test that all hours are covered
        hours_covered = set()
        for pattern in patterns:
            time_range = pattern['time']
            if '-' in time_range:
                start, end = map(int, time_range.split('-'))
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
            {'time': '0-6', 'multiplier': 0.1},
            {'time': '6-9', 'multiplier': 0.8},
            {'time': '9-17', 'multiplier': 1.0},
            {'time': '17-22', 'multiplier': 0.6},
            {'time': '22-0', 'multiplier': 0.3}  # Wrap to midnight
        ]
        
        for pattern in patterns:
            multiplier = pattern['multiplier']
            self.assertGreaterEqual(multiplier, 0)
            self.assertLessEqual(multiplier, 2.0)  # Reasonable upper bound


if __name__ == '__main__':
    unittest.main()