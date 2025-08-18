#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic",
#     "psutil",
#     "pytz",
#     "numpy",
#     "pyyaml",
# ]
# ///

"""Test that disk I/O errors are only logged after 15 seconds of failures."""

import io
import logging
import sqlite3
import sys
import time
from contextlib import redirect_stderr
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, '/Users/daaronch/code/bacalhau-examples/utility_containers/sensor-log-generator')

from src.database import SensorDatabase
from src.config import ConfigManager


def test_disk_error_logging_suppression():
    """Test that disk I/O errors are suppressed until 15 seconds of failures."""
    
    # Capture all log output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)  # Only capture INFO and above
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Create database with custom logger
    db = SensorDatabase(':memory:')
    db.batch_size = 1  # Disable batching for immediate writes
    db.debug_mode = False  # Ensure debug mode is off
    db.logger.addHandler(handler)
    db.logger.setLevel(logging.DEBUG)  # Set logger to debug but handler only captures INFO+
    
    # Mock the execute_write to simulate disk I/O errors
    original_execute_write = db.conn_manager.execute_write
    call_count = 0
    
    def mock_execute_write(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail every write to simulate persistent disk I/O error
        raise sqlite3.OperationalError("disk I/O error")
    
    db.conn_manager.execute_write = mock_execute_write
    
    # Simulate writes over time
    print("Testing disk I/O error logging suppression...")
    print("-" * 60)
    
    start_time = time.time()
    write_count = 0
    
    # Write for 20 seconds to ensure we pass the 15-second threshold
    while time.time() - start_time < 20:
        try:
            db.insert_reading(
                sensor_id="TEST001",
                temperature=20.0,
                vibration=0.1,
                voltage=3.3,
                status_code=200,
                location="Test"
            )
            write_count += 1
            
            # Also trigger retry mechanism
            db._retry_failed_writes()
            
            # Check log output at different intervals
            elapsed = time.time() - start_time
            log_output = log_capture.getvalue()
            
            if elapsed < 15:
                # Before 15 seconds, should see NO disk I/O error messages at INFO level
                if "Disk I/O error" in log_output or "DISK I/O ERROR" in log_output:
                    print(f"❌ FAILED: Disk I/O error logged at {elapsed:.1f}s (should wait until 15s)")
                    print(f"Log output:\n{log_output}")
                    return False
            elif elapsed >= 15 and elapsed < 16:
                # After 15 seconds, should see the error message
                if "DISK I/O ERROR persists" in log_output:
                    print(f"✅ Error correctly logged after {elapsed:.1f}s")
                    print(f"Log excerpt: {[line for line in log_output.split('\\n') if 'DISK I/O ERROR' in line][0]}")
                    return True
            
            time.sleep(0.5)  # Write every 0.5 seconds
            
        except Exception as e:
            pass  # Expected to fail
    
    # Check final output
    final_output = log_capture.getvalue()
    if "DISK I/O ERROR persists" not in final_output:
        print(f"❌ FAILED: No error message after 20 seconds")
        print(f"Total writes attempted: {write_count}")
        print(f"Log output lines: {len(final_output.split('\\n'))}")
    else:
        print(f"✅ PASSED: Error message appeared after 15 seconds as expected")
    
    return "DISK I/O ERROR persists" in final_output


if __name__ == "__main__":
    success = test_disk_error_logging_suppression()
    sys.exit(0 if success else 1)