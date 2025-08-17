import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from src.database import DatabaseConnectionManager, SensorDatabase, SensorReadingSchema, retry_on_error


class TestRetryOnError:
    def test_retry_decorator_success_first_try(self):
        """Test that decorator doesn't retry when function succeeds on first try."""
        call_count = 0
        
        @retry_on_error(max_retries=3, retry_delay=0.01)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_success_after_retries(self):
        """Test that decorator retries and eventually succeeds."""
        call_count = 0
        
        @retry_on_error(max_retries=3, retry_delay=0.01)
        def eventually_successful_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("Database locked")
            return "success"
        
        result = eventually_successful_function()
        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_max_retries_exceeded(self):
        """Test that decorator raises error after max retries."""
        call_count = 0
        
        @retry_on_error(max_retries=2, retry_delay=0.01)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("Database locked")
        
        with pytest.raises(sqlite3.OperationalError):
            always_failing_function()
        assert call_count == 3  # 1 initial + 2 retries

    def test_retry_decorator_non_database_error(self):
        """Test that decorator doesn't retry for non-database errors."""
        call_count = 0
        
        @retry_on_error(max_retries=3, retry_delay=0.01)
        def function_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a database error")
        
        with pytest.raises(ValueError):
            function_with_value_error()
        assert call_count == 1


class TestDatabaseConnectionManager:
    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")

    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_init(self):
        """Test DatabaseConnectionManager initialization."""
        manager = DatabaseConnectionManager(self.db_path, debug_mode=True)
        assert manager.db_path == self.db_path
        assert manager.debug_mode is True
        assert len(manager.pragmas) > 0

    def test_get_connection_creates_new_connection(self):
        """Test that get_connection creates a new connection."""
        manager = DatabaseConnectionManager(self.db_path)
        
        with manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            # Test that we can execute a simple query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_get_cursor_with_commit(self):
        """Test that get_cursor automatically commits transactions."""
        manager = DatabaseConnectionManager(self.db_path)
        
        # Create a test table and insert data
        with manager.get_cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            cursor.execute("INSERT INTO test (id, value) VALUES (1, 'test')")
        
        # Verify data was committed
        with manager.get_cursor() as cursor:
            cursor.execute("SELECT * FROM test")
            result = cursor.fetchone()
            assert result == (1, 'test')

    def test_execute_query(self):
        """Test execute_query method."""
        manager = DatabaseConnectionManager(self.db_path)
        
        # Create test table
        with manager.get_cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            cursor.execute("INSERT INTO test (id, value) VALUES (1, 'test1')")
            cursor.execute("INSERT INTO test (id, value) VALUES (2, 'test2')")
        
        # Test query execution
        results = manager.execute_query("SELECT * FROM test WHERE id = ?", (1,))
        assert len(results) == 1
        assert results[0] == (1, 'test1')

    def test_execute_write(self):
        """Test execute_write method."""
        manager = DatabaseConnectionManager(self.db_path)
        
        # Create test table
        with manager.get_cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER, value TEXT)")
        
        # Test write operation
        rows_affected = manager.execute_write("INSERT INTO test (id, value) VALUES (?, ?)", (1, 'test'))
        assert rows_affected == 1

    def test_execute_many(self):
        """Test execute_many method."""
        manager = DatabaseConnectionManager(self.db_path)
        
        # Create test table
        with manager.get_cursor() as cursor:
            cursor.execute("CREATE TABLE test (id INTEGER, value TEXT)")
        
        # Test bulk insert
        data = [(1, 'test1'), (2, 'test2'), (3, 'test3')]
        rows_affected = manager.execute_many("INSERT INTO test (id, value) VALUES (?, ?)", data)
        assert rows_affected == 3

    def test_close_thread_connection(self):
        """Test closing thread connection."""
        manager = DatabaseConnectionManager(self.db_path)
        
        # Create a connection
        with manager.get_connection() as conn:
            pass
        
        # Close it
        manager.close_thread_connection()
        
        # Verify new connection is created on next access
        with manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)


class TestSensorDatabase:
    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_sensor.db")

    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_init_creates_database(self):
        """Test that SensorDatabase initialization creates database and tables."""
        db = SensorDatabase(self.db_path)
        
        # Verify database file exists
        assert os.path.exists(self.db_path)
        
        # Verify table exists
        with db.conn_manager.get_cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'")
            result = cursor.fetchone()
            assert result is not None

    def test_init_preserves_existing_db(self):
        """Test that existing database is preserved when preserve_existing_db=True."""
        # Create initial database with data
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="TEST001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location"
        )
        db1.commit_batch()
        db1.close()
        
        # Create new database instance preserving existing
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Verify data still exists
        readings = db2.get_readings(limit=10)
        assert len(readings) == 1
        db2.close()

    def test_init_deletes_existing_db(self):
        """Test that existing database is deleted when preserve_existing_db=False."""
        # Create initial database with data
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="TEST001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location"
        )
        db1.commit_batch()
        db1.close()
        
        # Create new database instance (default behavior)
        db2 = SensorDatabase(self.db_path, preserve_existing_db=False)
        
        # Verify no data exists
        readings = db2.get_readings(limit=10)
        assert len(readings) == 0
        db2.close()

    def test_store_reading(self):
        """Test storing a sensor reading."""
        db = SensorDatabase(self.db_path)
        
        from src.database import SensorReadingSchema
        
        reading = SensorReadingSchema(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sensor_id="TEST001",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            latitude=40.0,
            longitude=-74.0,
            original_timezone="+00:00"
        )
        db.store_reading(reading)
        
        # Verify reading was stored
        readings = db.get_readings(limit=1)
        assert len(readings) == 1
        
        reading = readings[0]
        assert reading[2] == "TEST001"  # sensor_id
        assert reading[3] == 25.0  # temperature
        assert reading[4] == 50.0  # humidity
        
        db.close()

    def test_get_unsynced_readings(self):
        """Test getting unsynced readings."""
        db = SensorDatabase(self.db_path)
        
        # Store some readings
        for i in range(5):
            reading = SensorReadingSchema(
                timestamp=datetime.now(timezone.utc).isoformat(),
                sensor_id=f"TEST{i:03d}",
                temperature=25.0 + i,
                humidity=50.0,
                pressure=1013.0,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
                anomaly_flag=False,
                firmware_version="1.0",
                model="TestModel",
                manufacturer="TestMfg",
                location="Test Location",
                latitude=40.0,
                longitude=-74.0,
                original_timezone="+00:00"
            )
            db.store_reading(reading)
        
        # Get unsynced readings
        unsynced = db.get_unsynced_readings(limit=3)
        assert len(unsynced) == 3
        assert all(not reading["synced"] for reading in unsynced)
        
        db.close()

    def test_mark_readings_as_synced(self):
        """Test marking readings as synced."""
        db = SensorDatabase(self.db_path)
        
        # Store a reading
        reading = SensorReadingSchema(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sensor_id="TEST001",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            latitude=40.0,
            longitude=-74.0,
            original_timezone="+00:00"
        )
        db.store_reading(reading)
        
        # Get the reading and mark as synced
        unsynced = db.get_unsynced_readings()
        reading_ids = [r["id"] for r in unsynced]
        
        db.mark_readings_as_synced(reading_ids)
        
        # Verify no unsynced readings remain
        unsynced_after = db.get_unsynced_readings()
        assert len(unsynced_after) == 0
        
        db.close()

    def test_get_reading_stats(self):
        """Test getting reading statistics."""
        db = SensorDatabase(self.db_path)
        
        # Store some readings with different characteristics
        reading1 = SensorReadingSchema(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sensor_id="SENSOR1",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=True,
            anomaly_type="spike",
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Location1",
            latitude=40.0,
            longitude=-74.0,
            original_timezone="+00:00"
        )
        db.store_reading(reading1)
        
        reading2 = SensorReadingSchema(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sensor_id="SENSOR2",
            temperature=26.0,
            humidity=55.0,
            pressure=1014.0,
            vibration=0.2,
            voltage=12.5,
            status_code=0,
            anomaly_flag=False,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Location2",
            latitude=41.0,
            longitude=-75.0,
            original_timezone="+00:00"
        )
        db.store_reading(reading2)
        
        stats = db.get_reading_stats()
        
        assert stats["total_readings"] == 2
        assert stats["unsynced_readings"] == 2
        assert "spike" in stats["anomaly_stats"]
        assert stats["anomaly_stats"]["spike"] == 1
        assert len(stats["sensor_stats"]) == 2
        
        db.close()

    def test_is_healthy(self):
        """Test database health check."""
        db = SensorDatabase(self.db_path)
        
        # Database should be healthy after initialization
        assert db.is_healthy() is True
        
        db.close()

    def test_batch_operations(self):
        """Test batch insert operations."""
        db = SensorDatabase(self.db_path)
        
        # Insert multiple readings using batch method
        for i in range(5):
            db.insert_reading(
                sensor_id=f"BATCH{i:03d}",
                temperature=25.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
                anomaly_flag=False,
                firmware_version="1.0",
                model="BatchModel",
                manufacturer="BatchMfg",
                location="Batch Location"
            )
        
        # Force commit of any remaining batch
        db.commit_batch()
        
        # Verify all readings were inserted
        readings = db.get_readings(limit=10)
        assert len(readings) >= 5
        
        db.close()

    @patch('src.database.logging.getLogger')
    def test_database_error_handling(self, mock_logger):
        """Test database error handling and logging."""
        # Create database with invalid path to trigger errors
        invalid_path = "/invalid/path/to/database.db"
        
        with pytest.raises(Exception):
            SensorDatabase(invalid_path)

    def test_memory_database(self):
        """Test in-memory database functionality."""
        db = SensorDatabase(":memory:")
        
        # Store a reading
        reading = SensorReadingSchema(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sensor_id="MEM001",
            temperature=25.0,
            humidity=50.0,
            pressure=1013.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            firmware_version="1.0",
            model="MemModel",
            manufacturer="MemMfg",
            location="Memory Location",
            latitude=40.0,
            longitude=-74.0,
            original_timezone="+00:00"
        )
        db.store_reading(reading)
        
        # Verify reading exists
        readings = db.get_readings(limit=1)
        assert len(readings) == 1
        
        db.close()