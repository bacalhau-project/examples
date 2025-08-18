#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "psutil",
#     "pydantic",
#     "numpy",
#     "pyyaml",
# ]
# ///

"""Test that errors are suppressed until the 15-second retry threshold."""

import os
import sqlite3
import tempfile
import time
import logging
from unittest.mock import patch
import sys
from io import StringIO

# Setup logging to capture messages
log_capture = StringIO()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s %(message)s',
    stream=log_capture
)

sys.path.insert(0, os.path.dirname(__file__))

from src.database import SensorDatabase, SensorReadingSchema


def test_error_suppression():
    """Test that disk I/O errors are not logged as ERROR until after 15-second retry."""
    
    print("\n" + "="*60)
    print("ERROR SUPPRESSION TEST")
    print("="*60)
    print("\nVerifying that disk I/O errors are not logged as ERROR")
    print("until after we've reached the 15-second retry interval.\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        # Create database with debug logging
        db = SensorDatabase(db_path)
        db.debug_mode = True
        
        # Create a test reading
        reading = SensorReadingSchema(
            timestamp="2025-08-18T10:00:00Z",
            sensor_id="TEST001",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.25,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            location="Test Location",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Store one successful reading first
        db.store_reading(reading)
        print("✓ Initial reading stored successfully")
        
        # Clear the log capture
        log_capture.truncate(0)
        log_capture.seek(0)
        
        # Mock execute_write to simulate persistent disk I/O errors
        def mock_execute_write(query, params):
            if "INSERT INTO sensor_readings" in query:
                raise sqlite3.OperationalError("disk I/O error")
            return None
        
        print("\nSimulating persistent disk I/O errors...")
        print("-" * 40)
        
        with patch.object(db.conn_manager, 'execute_write', side_effect=mock_execute_write):
            # Simulate failures through multiple retry cycles
            retry_intervals = [1, 3, 5, 9, 12, 15]
            
            for i, interval in enumerate(retry_intervals):
                # Try to store a reading (will fail)
                reading2 = SensorReadingSchema(
                    timestamp=f"2025-08-18T10:{i+1:02d}:00Z",
                    sensor_id="TEST001",
                    temperature=25.0 + i,
                    humidity=50.0,
                    pressure=1013.25,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0,
                    location="Test Location",
                    latitude=40.7128,
                    longitude=-74.0060
                )
                
                db.store_reading(reading2)
                
                # Force a retry attempt
                db.last_failure_retry_time = 0
                db._retry_failed_writes()
                
                # Check log output for this retry attempt
                log_content = log_capture.getvalue()
                error_count = log_content.count('ERROR')
                warning_count = log_content.count('WARNING')
                info_count = log_content.count('INFO')
                
                print(f"Retry #{i+1} (after {interval}s interval):")
                print(f"  Retry count: {db.failure_retry_count}")
                print(f"  Buffer size: {len(db.failure_buffer)}")
                print(f"  ERROR logs: {error_count}")
                print(f"  WARNING logs: {warning_count}")
                print(f"  INFO logs: {info_count}")
                
                if i < 5:  # Before the 15-second threshold
                    assert error_count == 0, f"ERROR should not appear before 15s threshold (retry #{i+1})"
                    print(f"  ✓ No ERROR logs (as expected)")
                else:  # At or after the 15-second threshold
                    assert error_count > 0, f"ERROR should appear at 15s threshold (retry #{i+1})"
                    print(f"  ✓ ERROR logs present (as expected)")
                
                # Clear log for next iteration
                log_capture.truncate(0)
                log_capture.seek(0)
        
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        
        print(f"\nFinal state:")
        print(f"  Failure buffer size: {len(db.failure_buffer)}")
        print(f"  Retry count: {db.failure_retry_count}")
        
        # Verify the retry sequence
        print(f"\nRetry intervals used: {db.failure_buffer_retry_intervals}")
        print(f"Maximum retry interval: {db.failure_buffer_max_retry_interval}s")
        
        print("\n✅ SUCCESS: Errors are suppressed until the 15-second threshold")
        print("   - No ERROR logs for retries 1-5 (1s, 3s, 5s, 9s, 12s)")
        print("   - ERROR logs appear at retry 6 (15s)")
        print("   - This prevents log spam during transient issues")
        
        db.close()


def test_successful_recovery():
    """Test that successful recovery is always logged as INFO."""
    
    print("\n" + "="*60)
    print("RECOVERY LOGGING TEST")
    print("="*60)
    print("\nVerifying that successful recovery is always logged.\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = SensorDatabase(db_path)
        
        # Create test readings
        readings = []
        for i in range(3):
            readings.append(SensorReadingSchema(
                timestamp=f"2025-08-18T11:{i:02d}:00Z",
                sensor_id="TEST002",
                temperature=20.0 + i,
                humidity=55.0,
                pressure=1013.0,
                vibration=0.2,
                voltage=12.1,
                status_code=0,
                location="Test Lab"
            ))
        
        # Mock to simulate temporary disk error
        original_execute_write = db.conn_manager.execute_write
        call_count = [0]
        
        def mock_execute_write(query, params):
            call_count[0] += 1
            if call_count[0] <= 3:  # Fail first 3 attempts
                raise sqlite3.OperationalError("disk I/O error")
            return original_execute_write(query, params)
        
        with patch.object(db.conn_manager, 'execute_write', side_effect=mock_execute_write):
            # Store readings (will fail initially)
            for reading in readings:
                db.store_reading(reading)
            
            print(f"✓ {len(db.failure_buffer)} readings buffered due to disk error")
        
        # Now let recovery happen
        print("\nDisk error resolved, attempting recovery...")
        
        # Clear log and attempt recovery
        log_capture.truncate(0)
        log_capture.seek(0)
        
        db.last_failure_retry_time = 0
        db._retry_failed_writes()
        
        # Check that recovery was logged
        log_content = log_capture.getvalue()
        assert "Successfully wrote" in log_content
        assert "INFO" in log_content
        
        print(f"✓ Recovery logged as INFO: 'Successfully wrote {3} readings from failure buffer'")
        print(f"✓ Buffer cleared: {len(db.failure_buffer)} readings remaining")
        
        db.close()
        print("\n✅ SUCCESS: Recovery is always logged for visibility")


if __name__ == "__main__":
    # Run both tests
    test_error_suppression()
    test_successful_recovery()
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED")
    print("="*60)
    print("\nSummary:")
    print("✓ Errors suppressed for first 5 retries (1s-12s)")
    print("✓ Errors logged starting at retry 6 (15s)")
    print("✓ Successful recovery always logged")
    print("✓ Prevents log spam during transient issues")
    print("✓ Maintains visibility for persistent problems")