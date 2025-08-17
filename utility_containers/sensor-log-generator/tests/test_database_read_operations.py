#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pytest-timeout",
# ]
# ///

import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.database import SensorDatabase, SensorReadingSchema


class TestDatabaseReadOperations:
    """Test suite for database read operations and data retrieval."""

    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_read.db")
        self.db = SensorDatabase(self.db_path)
        
    def teardown_method(self):
        """Clean up after each test."""
        if hasattr(self, 'db'):
            self.db.close()
        self.temp_dir.cleanup()

    def _create_test_data(self, count=10):
        """Helper to create test data."""
        for i in range(count):
            self.db.insert_reading(
                sensor_id=f"READ{i:03d}",
                temperature=20.0 + i,
                vibration=0.1 + i * 0.01,
                voltage=12.0 + i * 0.1,
                status_code=i % 3,
                anomaly_flag=i % 5 == 0
            )
        self.db.commit_batch()

    def test_get_readings_with_limit(self):
        """Test reading data with different limits."""
        self._create_test_data(20)
        
        # Test with limit
        readings = self.db.get_readings(limit=5)
        assert len(readings) == 5
        
        # Test with larger limit than data
        readings = self.db.get_readings(limit=50)
        assert len(readings) == 20
        
        # Test default limit
        readings = self.db.get_readings()
        assert len(readings) <= 100

    def test_get_readings_ordering(self):
        """Test that readings are returned in correct order."""
        self._create_test_data(10)
        
        readings = self.db.get_readings(limit=10)
        
        # Verify readings are in descending timestamp order (newest first)
        timestamps = [r[1] for r in readings]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_readings_after_offset(self):
        """Test reading data with offset using direct SQL."""
        self._create_test_data(20)
        
        # Get first batch
        first_batch = self.db.get_readings(limit=10)
        
        # Get second batch with offset using direct SQL
        with self.db.conn_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10 OFFSET 10"
            )
            second_batch = cursor.fetchall()
        
        # Ensure no overlap
        first_ids = [r[0] for r in first_batch]
        second_ids = [r[0] for r in second_batch]
        assert len(set(first_ids) & set(second_ids)) == 0

    def test_get_readings_by_sensor_id(self):
        """Test filtering readings by sensor ID."""
        self._create_test_data(10)
        
        # Add readings for specific sensor
        for i in range(5):
            self.db.insert_reading(
                sensor_id="SPECIAL001",
                temperature=30.0 + i,
                vibration=0.2,
                voltage=13.0,
                status_code=0
            )
        self.db.commit_batch()
        
        # Query specific sensor
        with self.db.conn_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sensor_readings WHERE sensor_id = ? ORDER BY timestamp DESC",
                ("SPECIAL001",)
            )
            readings = cursor.fetchall()
        
        assert len(readings) == 5
        assert all(r[2] == "SPECIAL001" for r in readings)

    def test_get_readings_by_time_range(self):
        """Test filtering readings by time range."""
        # Insert readings with specific timestamps
        base_time = time.time()
        for i in range(10):
            timestamp = base_time - (i * 60)  # 1 minute apart
            self.db.store_reading(
                timestamp=timestamp,
                sensor_id=f"TIME{i:03d}",
                temperature=25.0,
                humidity=50.0,
                pressure=1013.0,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
                anomaly_flag=False,
                anomaly_type=None,
                firmware_version="1.0",
                model="TestModel",
                manufacturer="TestMfg",
                location="Test Location",
                latitude=40.0,
                longitude=-74.0,
                timezone_str="+00:00"
            )
        
        # Query last 5 minutes
        cutoff_time = base_time - (5 * 60)
        with self.db.conn_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sensor_readings WHERE timestamp > ? ORDER BY timestamp DESC",
                (cutoff_time,)
            )
            readings = cursor.fetchall()
        
        assert len(readings) == 5

    def test_get_anomaly_readings(self):
        """Test retrieving only anomaly readings."""
        self._create_test_data(20)
        
        # Query anomaly readings
        with self.db.conn_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sensor_readings WHERE anomaly_flag = 1 ORDER BY timestamp DESC"
            )
            anomalies = cursor.fetchall()
        
        # Every 5th reading should be an anomaly (0, 5, 10, 15)
        assert len(anomalies) == 4
        assert all(r[9] == 1 for r in anomalies)  # anomaly_flag column

    def test_get_readings_with_specific_status(self):
        """Test filtering by status code."""
        self._create_test_data(15)
        
        # Query readings with status code 1
        with self.db.conn_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sensor_readings WHERE status_code = ? ORDER BY timestamp DESC",
                (1,)
            )
            readings = cursor.fetchall()
        
        # Should be 5 readings with status code 1 (indices 1, 4, 7, 10, 13)
        assert len(readings) == 5
        assert all(r[8] == 1 for r in readings)  # status_code column

    def test_aggregate_statistics(self):
        """Test aggregate statistics queries."""
        self._create_test_data(100)
        
        with self.db.conn_manager.get_cursor() as cursor:
            # Average temperature
            cursor.execute("SELECT AVG(temperature) FROM sensor_readings")
            avg_temp = cursor.fetchone()[0]
            assert 65 < avg_temp < 75  # Should be around 69.5
            
            # Min and max vibration
            cursor.execute("SELECT MIN(vibration), MAX(vibration) FROM sensor_readings")
            min_vib, max_vib = cursor.fetchone()
            assert min_vib >= 0.1
            assert max_vib < 2.0
            
            # Count by status code
            cursor.execute(
                "SELECT status_code, COUNT(*) FROM sensor_readings GROUP BY status_code"
            )
            status_counts = dict(cursor.fetchall())
            assert len(status_counts) == 3  # Status codes 0, 1, 2

    def test_get_database_stats(self):
        """Test comprehensive database statistics."""
        self._create_test_data(50)
        
        stats = self.db.get_database_stats()
        
        assert stats["total_readings"] == 50
        assert stats["database_size_mb"] > 0
        assert "sensor_stats" in stats
        assert "anomaly_stats" in stats
        assert "performance_metrics" in stats

    def test_empty_database_reads(self):
        """Test reading from empty database."""
        # Don't insert any data
        
        readings = self.db.get_readings()
        assert len(readings) == 0
        
        stats = self.db.get_database_stats()
        assert stats["total_readings"] == 0
        assert stats["unsynced_readings"] == 0

    def test_concurrent_read_write(self):
        """Test concurrent read and write operations."""
        import threading
        
        write_complete = threading.Event()
        read_results = []
        
        def writer():
            for i in range(20):
                self.db.insert_reading(
                    sensor_id=f"CONCURRENT{i:03d}",
                    temperature=25.0 + i,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0
                )
                time.sleep(0.01)  # Small delay
            self.db.commit_batch()
            write_complete.set()
        
        def reader():
            while not write_complete.is_set():
                readings = self.db.get_readings(limit=5)
                read_results.append(len(readings))
                time.sleep(0.02)
            # Final read
            readings = self.db.get_readings(limit=30)
            read_results.append(len(readings))
        
        write_thread = threading.Thread(target=writer)
        read_thread = threading.Thread(target=reader)
        
        write_thread.start()
        read_thread.start()
        
        write_thread.join(timeout=5)
        read_thread.join(timeout=5)
        
        # Verify reads succeeded
        assert len(read_results) > 0
        assert max(read_results) >= 20

    def test_get_readings_with_pydantic_schema(self):
        """Test reading data that conforms to Pydantic schema."""
        # Insert data using Pydantic model
        for i in range(5):
            reading = SensorReadingSchema(
                timestamp=f"2025-01-{i+1:02d}T12:00:00Z",
                sensor_id=f"PYDANTIC{i:03d}",
                temperature=22.0 + i,
                humidity=45.0 + i,
                pressure=1010.0 + i,
                vibration=0.05 + i * 0.01,
                voltage=11.5 + i * 0.1,
                status_code=0,
                anomaly_flag=False,
                firmware_version="2.0.0",
                model="TestModel",
                manufacturer="TestMfg",
                location=f"Location{i}",
                latitude=40.0 + i * 0.1,
                longitude=-74.0 + i * 0.1,
                original_timezone="+00:00"
            )
            self.db.store_reading(reading)
        
        readings = self.db.get_readings(limit=10)
        assert len(readings) == 5
        
        # Verify data integrity
        for reading in readings:
            assert reading[2].startswith("PYDANTIC")  # sensor_id

    def test_pagination(self):
        """Test paginated reading of large datasets."""
        # Create large dataset
        self._create_test_data(100)
        
        page_size = 10
        all_readings = []
        
        for page in range(10):
            offset = page * page_size
            with self.db.conn_manager.get_cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                )
                readings = cursor.fetchall()
            all_readings.extend(readings)
            
            if page < 9:
                assert len(readings) == page_size
        
        # Verify we got all unique readings
        reading_ids = [r[0] for r in all_readings]
        assert len(set(reading_ids)) == 100

    def test_get_latest_reading_per_sensor(self):
        """Test getting the latest reading for each sensor."""
        # Create readings for multiple sensors
        sensors = ["SENSOR_A", "SENSOR_B", "SENSOR_C"]
        for sensor in sensors:
            for i in range(5):
                time.sleep(0.01)  # Ensure different timestamps
                self.db.insert_reading(
                    sensor_id=sensor,
                    temperature=25.0 + i,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0
                )
        self.db.commit_batch()
        
        # Get latest reading for each sensor
        with self.db.conn_manager.get_cursor() as cursor:
            cursor.execute("""
                SELECT sensor_id, MAX(timestamp) as latest, temperature
                FROM sensor_readings
                GROUP BY sensor_id
                ORDER BY sensor_id
            """)
            latest_readings = cursor.fetchall()
        
        assert len(latest_readings) == 3
        for reading in latest_readings:
            assert reading[0] in sensors
            assert reading[2] == 29.0  # Last temperature value


class TestDatabaseEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        
    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_corrupted_database_recovery(self):
        """Test handling of corrupted database."""
        db_path = os.path.join(self.temp_dir.name, "corrupted.db")
        
        # Create a corrupted database file
        with open(db_path, 'wb') as f:
            f.write(b'This is not a valid SQLite database')
        
        # Attempt to open corrupted database
        with pytest.raises(sqlite3.DatabaseError):
            db = SensorDatabase(db_path, preserve_existing_db=True)

    def test_missing_database_file(self):
        """Test handling when database file is missing."""
        db_path = os.path.join(self.temp_dir.name, "missing.db")
        
        # Create database
        db = SensorDatabase(db_path)
        db.insert_reading(
            sensor_id="TEST001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db.commit_batch()
        db.close()
        
        # Delete database file
        os.remove(db_path)
        
        # Try to open with preserve_existing_db=True
        db2 = SensorDatabase(db_path, preserve_existing_db=True)
        readings = db2.get_readings()
        assert len(readings) == 0  # New empty database created
        db2.close()

    def test_read_only_database(self):
        """Test handling of read-only database."""
        db_path = os.path.join(self.temp_dir.name, "readonly.db")
        
        # Create database
        db = SensorDatabase(db_path)
        db.insert_reading(
            sensor_id="READONLY001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db.commit_batch()
        db.close()
        
        # Make database read-only
        os.chmod(db_path, 0o444)
        
        # Try to open read-only database
        try:
            db2 = SensorDatabase(db_path, preserve_existing_db=True)
            # Reading should work
            readings = db2.get_readings()
            assert len(readings) == 1
            
            # Writing should fail
            with pytest.raises(sqlite3.OperationalError):
                db2.insert_reading(
                    sensor_id="READONLY002",
                    temperature=26.0,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0
                )
                db2.commit_batch()
            
            db2.close()
        finally:
            # Restore write permissions for cleanup
            os.chmod(db_path, 0o644)

    def test_database_locked_error(self):
        """Test handling of database locked errors."""
        db_path = os.path.join(self.temp_dir.name, "locked.db")
        
        db1 = SensorDatabase(db_path)
        
        # Start a transaction in db1
        with db1.conn_manager.get_connection() as conn:
            conn.execute("BEGIN EXCLUSIVE")
            
            # Try to write from another connection (should timeout or fail)
            db2 = SensorDatabase(db_path, preserve_existing_db=True)
            db2.conn_manager.conn.execute("PRAGMA busy_timeout = 100")  # Short timeout
            
            with pytest.raises(sqlite3.OperationalError):
                db2.insert_reading(
                    sensor_id="LOCKED001",
                    temperature=25.0,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0
                )
                db2.commit_batch()
            
            db2.close()
        
        db1.close()

    def test_very_large_batch(self):
        """Test handling of very large batch inserts."""
        db_path = os.path.join(self.temp_dir.name, "large_batch.db")
        db = SensorDatabase(db_path)
        
        # Insert a very large batch
        large_batch_size = 10000
        for i in range(large_batch_size):
            db.insert_reading(
                sensor_id=f"LARGE{i:05d}",
                temperature=20.0 + (i % 10),
                vibration=0.1 + (i % 100) * 0.001,
                voltage=12.0 + (i % 5) * 0.1,
                status_code=i % 3
            )
        
        # Commit the large batch
        committed = db.commit_batch()
        assert committed == large_batch_size
        
        # Verify all data was inserted
        stats = db.get_database_stats()
        assert stats["total_readings"] == large_batch_size
        
        db.close()

    def test_null_values_handling(self):
        """Test handling of null/None values in optional fields."""
        db_path = os.path.join(self.temp_dir.name, "null_values.db")
        db = SensorDatabase(db_path)
        
        # Insert reading with minimal required fields
        db.store_reading(
            timestamp=time.time(),
            sensor_id="NULL001",
            temperature=25.0,
            humidity=None,  # Optional
            pressure=None,  # Optional
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,  # Optional
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            latitude=None,  # Optional
            longitude=None,  # Optional
            timezone_str="+00:00"
        )
        
        readings = db.get_readings()
        assert len(readings) == 1
        
        # Verify null values are preserved
        reading = readings[0]
        # Check that some columns can be NULL
        assert reading is not None
        
        db.close()

    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        db_path = os.path.join(self.temp_dir.name, "unicode.db")
        db = SensorDatabase(db_path)
        
        # Insert reading with Unicode characters
        db.store_reading(
            timestamp=time.time(),
            sensor_id="UNICODE_001_🌡️",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type="spike_🔥",
            firmware_version="1.0",
            model="Model_测试",
            manufacturer="Mfg_製造商",
            location="Location_מיקום",
            latitude=40.0,
            longitude=-74.0,
            timezone_str="+00:00"
        )
        
        readings = db.get_readings()
        assert len(readings) == 1
        assert "🌡️" in readings[0][2]  # sensor_id contains emoji
        
        db.close()

    def test_timestamp_edge_cases(self):
        """Test handling of edge case timestamps."""
        db_path = os.path.join(self.temp_dir.name, "timestamp_edge.db")
        db = SensorDatabase(db_path)
        
        # Test very old timestamp (1970)
        db.store_reading(
            timestamp=0.0,
            sensor_id="OLD001",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            latitude=40.0,
            longitude=-74.0,
            timezone_str="+00:00"
        )
        
        # Test future timestamp (2100)
        future_timestamp = datetime(2100, 1, 1, tzinfo=timezone.utc).timestamp()
        db.store_reading(
            timestamp=future_timestamp,
            sensor_id="FUTURE001",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            latitude=40.0,
            longitude=-74.0,
            timezone_str="+00:00"
        )
        
        readings = db.get_readings()
        assert len(readings) == 2
        
        # Verify timestamps are preserved
        timestamps = [r[1] for r in readings]
        assert 0.0 in timestamps
        assert any(t > time.time() for t in timestamps)  # Future timestamp
        
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])