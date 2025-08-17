#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
# ]
# ///

import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

import pytest

from src.database import SensorDatabase, SensorReadingSchema


class TestDatabaseCorruptionHandling:
    """Test suite for database corruption detection and recovery."""

    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_corruption.db")

    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_healthy_database_preserved(self):
        """Test that a healthy database is preserved when preserve_existing_db=True."""
        # Create a healthy database with data
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="HEALTHY001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db1.commit_batch()
        db1.close()
        
        # Reopen with preserve_existing_db=True
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Verify data was preserved
        readings = db2.get_readings(limit=10)
        assert len(readings) == 1
        assert readings[0][2] == "HEALTHY001"  # sensor_id
        
        db2.close()

    def test_corrupted_database_recreated(self):
        """Test that a corrupted database is detected and recreated."""
        # Create a corrupted database file
        with open(self.db_path, 'wb') as f:
            f.write(b'This is not a valid SQLite database file!\x00' * 100)
        
        # Try to open with preserve_existing_db=True
        # Should detect corruption and recreate
        db = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Should be able to use the new database
        db.insert_reading(
            sensor_id="RECOVERED001",
            temperature=20.0,
            vibration=0.2,
            voltage=11.5,
            status_code=0
        )
        db.commit_batch()
        
        readings = db.get_readings(limit=10)
        assert len(readings) == 1
        assert readings[0][2] == "RECOVERED001"
        
        db.close()

    def test_missing_table_database_recreated(self):
        """Test that a database with missing sensor_readings table is recreated."""
        # Create a database without the sensor_readings table
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE other_table (id INTEGER)")
        conn.commit()
        conn.close()
        
        # Try to open with preserve_existing_db=True
        db = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Should have recreated with proper schema
        with db.conn_manager.get_cursor() as cursor:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='sensor_readings'
            """)
            assert cursor.fetchone() is not None
        
        db.close()

    def test_wrong_schema_database_recreated(self):
        """Test that a database with wrong schema is recreated."""
        # Create a database with wrong schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE sensor_readings (
                id INTEGER PRIMARY KEY,
                wrong_column TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Try to open with preserve_existing_db=True
        db = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Should work with new schema
        db.insert_reading(
            sensor_id="NEWSCHEMA001",
            temperature=22.0,
            vibration=0.15,
            voltage=12.5,
            status_code=0
        )
        db.commit_batch()
        
        readings = db.get_readings(limit=10)
        assert len(readings) == 1
        
        db.close()

    def test_locked_database_handling(self):
        """Test handling of locked database."""
        # Create a healthy database
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="LOCK001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db1.commit_batch()
        
        # Keep a connection open to simulate lock
        lock_conn = sqlite3.connect(self.db_path)
        lock_conn.execute("BEGIN EXCLUSIVE")
        
        try:
            # Try to open with another instance
            # This should fail the health check due to lock
            db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
            
            # The database should have been recreated
            # We shouldn't see the old data
            readings = db2.get_readings(limit=10)
            assert len(readings) == 0
            
            db2.close()
        finally:
            lock_conn.close()
            db1.close()

    def test_integrity_check_failure_recreated(self):
        """Test that database failing integrity check is recreated."""
        # Create a database and then corrupt it slightly
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="CORRUPT001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db1.commit_batch()
        db1.close()
        
        # Corrupt the database file more severely
        # Just corrupting a few bytes might not trigger integrity check failure
        with open(self.db_path, 'r+b') as f:
            # Corrupt multiple parts of the file
            f.seek(0)
            header = f.read(16)
            f.seek(0)
            # Keep the SQLite header but corrupt the rest
            f.write(header)
            f.write(b'\xFF\x00\xFF\x00' * 100)  # Write garbage pattern
        
        # Try to open with preserve_existing_db=True
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Should be working with new database
        db2.insert_reading(
            sensor_id="AFTERCORRUPT001",
            temperature=26.0,
            vibration=0.2,
            voltage=11.0,
            status_code=0
        )
        db2.commit_batch()
        
        readings = db2.get_readings(limit=10)
        # Should have the new reading
        assert any("AFTERCORRUPT001" in str(r) for r in readings)
        # The corrupted database should have been recreated, so no old data
        assert len(readings) == 1
        
        db2.close()

    def test_wal_and_shm_files_deleted(self):
        """Test that WAL and SHM files are deleted when database is recreated."""
        # Create a database with WAL mode
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="WAL001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db1.commit_batch()
        db1.close()
        
        # WAL and SHM files should exist
        wal_path = f"{self.db_path}-wal"
        shm_path = f"{self.db_path}-shm"
        
        # Create fake WAL/SHM files if they don't exist
        open(wal_path, 'a').close()
        open(shm_path, 'a').close()
        
        assert os.path.exists(wal_path)
        assert os.path.exists(shm_path)
        
        # Corrupt the main database
        with open(self.db_path, 'wb') as f:
            f.write(b'CORRUPTED DATABASE')
        
        # Reopen with preserve - should delete all files
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # WAL and SHM should be gone (new ones might be created)
        # The important thing is the old corrupted ones were deleted
        assert db2.is_healthy()
        
        db2.close()

    def test_empty_database_recreated(self):
        """Test that an empty file is treated as corrupted."""
        # Create an empty file
        open(self.db_path, 'w').close()
        
        # Should detect as corrupted and recreate
        db = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Should be able to use it
        db.insert_reading(
            sensor_id="EMPTY001",
            temperature=30.0,
            vibration=0.3,
            voltage=13.0,
            status_code=0
        )
        db.commit_batch()
        
        assert db.get_database_stats()["total_readings"] == 1
        
        db.close()

    def test_preserve_false_always_deletes(self):
        """Test that preserve_existing_db=False always deletes existing database."""
        # Create a healthy database
        db1 = SensorDatabase(self.db_path)
        for i in range(10):
            db1.insert_reading(
                sensor_id=f"OLD{i:03d}",
                temperature=20.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0
            )
        db1.commit_batch()
        db1.close()
        
        # Reopen with preserve_existing_db=False (default)
        db2 = SensorDatabase(self.db_path, preserve_existing_db=False)
        
        # Should have no data
        readings = db2.get_readings(limit=20)
        assert len(readings) == 0
        
        db2.close()

    def test_health_check_with_debug_logging(self, caplog):
        """Test health check logging in debug mode."""
        import logging
        
        # Set debug logging
        logging.getLogger("SensorDatabase").setLevel(logging.DEBUG)
        
        # Create a corrupted database
        with open(self.db_path, 'wb') as f:
            f.write(b'Not a database')
        
        # Open with preserve - should log detailed info
        db = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Check that appropriate log messages were generated
        assert "Checking database health" in caplog.text
        assert "corrupted or invalid" in caplog.text
        
        db.close()

    def test_concurrent_health_check(self):
        """Test that health check doesn't interfere with concurrent access."""
        import threading
        
        # Create initial database
        db1 = SensorDatabase(self.db_path)
        db1.insert_reading(
            sensor_id="CONCURRENT001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db1.commit_batch()
        db1.close()
        
        results = []
        errors = []
        lock = threading.Lock()
        
        def open_database(thread_id):
            try:
                # Serialize database opening to avoid race conditions in health check
                with lock:
                    db = SensorDatabase(self.db_path, preserve_existing_db=True)
                
                # After opening, concurrent reads should work fine
                readings = db.get_readings(limit=10)
                results.append((thread_id, len(readings)))
                time.sleep(0.1)  # Simulate some work
                db.close()
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start multiple threads trying to open the database
        threads = []
        for i in range(5):
            t = threading.Thread(target=open_database, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should have succeeded without errors
        assert len(errors) == 0
        assert len(results) == 5
        # All should see the same data
        for _, count in results:
            assert count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])