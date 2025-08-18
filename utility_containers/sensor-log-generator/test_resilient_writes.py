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

"""Test script for resilient write mechanism with failure buffer."""

import os
import sqlite3
import tempfile
import time
from unittest.mock import patch, MagicMock
import sys
import logging

# Reduce logging noise for test
logging.basicConfig(level=logging.WARNING)
logging.getLogger("SensorDatabase").setLevel(logging.WARNING)

# Import directly without going through __init__.py
sys.path.insert(0, os.path.dirname(__file__))

from src.database import SensorDatabase, SensorReadingSchema


def test_failure_buffer():
    """Test that readings are buffered when disk I/O errors occur."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = SensorDatabase(db_path)
        
        # Create a test reading
        reading = SensorReadingSchema(
            timestamp="2025-08-18T01:00:00Z",
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
        
        # Store a normal reading first to ensure DB is working
        print("Storing initial reading...")
        db.store_reading(reading)
        
        # Check initial state
        stats = db.get_database_stats()
        assert stats["total_readings"] == 1
        assert stats["performance_metrics"]["failure_buffer_size"] == 0
        print(f"✓ Initial reading stored successfully")
        
        # Mock execute_write to simulate disk I/O error
        original_execute_write = db.conn_manager.execute_write
        
        def mock_execute_write(query, params):
            if "INSERT INTO sensor_readings" in query:
                raise sqlite3.OperationalError("disk I/O error")
            return original_execute_write(query, params)
        
        # Patch the method
        with patch.object(db.conn_manager, 'execute_write', side_effect=mock_execute_write):
            # Try to store readings that will fail
            print("\nSimulating disk I/O errors...")
            for i in range(5):
                reading2 = SensorReadingSchema(
                    timestamp=f"2025-08-18T01:0{i+1}:00Z",
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
            
            # Check that readings are in failure buffer
            assert len(db.failure_buffer) == 5
            print(f"✓ {len(db.failure_buffer)} readings buffered in memory")
        
        # Now let the retry mechanism work
        print("\nAttempting retry after disk I/O errors resolved...")
        time.sleep(1)  # Brief pause
        
        # Force a retry
        db.last_failure_retry_time = 0
        db._retry_failed_writes()
        
        # Check that readings were written
        stats = db.get_database_stats()
        assert len(db.failure_buffer) == 0
        assert stats["total_readings"] == 6  # 1 initial + 5 from buffer
        print(f"✓ All {stats['total_readings']-1} buffered readings successfully written to disk")
        
        # Test custom backoff intervals
        print("\nTesting custom backoff intervals...")
        db.failure_retry_count = 0
        intervals = []
        for i in range(8):  # Test beyond the defined intervals
            if i < len(db.failure_buffer_retry_intervals):
                interval = db.failure_buffer_retry_intervals[i]
            else:
                interval = db.failure_buffer_max_retry_interval
            intervals.append(interval)
            print(f"  Retry {i+1}: {interval:.0f}s interval")
        
        # Verify the exact sequence: 1s, 3s, 5s, 9s, 12s, 15s, 15s, 15s...
        assert intervals[0] == 1.0   # First retry after 1 second
        assert intervals[1] == 3.0   # Second retry after 3 seconds
        assert intervals[2] == 5.0   # Third retry after 5 seconds
        assert intervals[3] == 9.0   # Fourth retry after 9 seconds
        assert intervals[4] == 12.0  # Fifth retry after 12 seconds
        assert intervals[5] == 15.0  # Sixth retry after 15 seconds
        assert intervals[6] == 15.0  # Stays at 15 seconds
        assert intervals[7] == 15.0  # Stays at 15 seconds
        print("✓ Custom backoff intervals working correctly")
        
        # Test buffer size limit
        print("\nTesting buffer size limit...")
        with patch.object(db.conn_manager, 'execute_write', side_effect=mock_execute_write):
            # Fill the buffer beyond max size
            for i in range(db.failure_buffer_max_size + 100):
                reading3 = SensorReadingSchema(
                    timestamp=f"2025-08-18T02:{i//60:02d}:{i%60:02d}Z",
                    sensor_id="TEST001",
                    temperature=20.0,
                    humidity=45.0,
                    pressure=1013.0,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0,
                    location="Test Location",
                    latitude=40.7128,
                    longitude=-74.0060
                )
                db.store_reading(reading3)
            
            # Buffer should be at max size (oldest entries dropped)
            assert len(db.failure_buffer) <= db.failure_buffer_max_size
            print(f"✓ Buffer size limited to {len(db.failure_buffer)} (max: {db.failure_buffer_max_size})")
        
        # Clean up
        db.close()
        print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_failure_buffer()