#!/usr/bin/env python3
"""Simple test to verify disk I/O errors are suppressed for 15 seconds."""

import logging
import os
import sys
import time

# Configure logging to show INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.simulator import SensorSimulator
from src.config import ConfigManager

# Create config with disk I/O errors
config_dict = {
    'sensor_count': 1,
    'interval': 0.25,  # Generate readings every 250ms
    'batch_size': 10,
    'error_injection': {
        'enabled': True,
        'disk_io_error_rate': 1.0  # 100% disk I/O errors
    },
    'database': {
        'path': 'test_errors.db'
    }
}

# Clean up any existing test database
if os.path.exists('test_errors.db'):
    os.remove('test_errors.db')

print("Starting test - monitoring for disk I/O error messages...")
print("Expected behavior: NO error messages for first 15 seconds")
print("-" * 60)

# Create identity
identity_dict = {
    'sensor_id': 'TEST001',
    'location': 'Test Location',
    'latitude': 0.0,
    'longitude': 0.0,
    'timezone': 'UTC',
    'manufacturer': 'TestCorp',
    'model': 'TestModel',
    'firmware_version': '1.0.0'
}

# Create simulator
config = ConfigManager(config_dict, identity_dict)
sim = SensorSimulator(config)

# Start simulator
sim.start()

# Monitor for 20 seconds
start_time = time.time()
try:
    while time.time() - start_time < 20:
        elapsed = time.time() - start_time
        print(f"\rElapsed: {elapsed:.1f}s", end='', flush=True)
        time.sleep(0.5)
except KeyboardInterrupt:
    pass

print("\n" + "-" * 60)
print("Test completed - check console output above")
print("If you saw disk I/O error messages before 15s, the test FAILED")
print("If you only saw error messages after 15s, the test PASSED")

# Stop simulator
sim.stop()

# Clean up
if os.path.exists('test_errors.db'):
    os.remove('test_errors.db')