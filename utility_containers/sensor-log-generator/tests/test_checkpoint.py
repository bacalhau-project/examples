#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pytest-timeout",
# ]
# ///

import os
import signal
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from src.database import DatabaseConnectionManager, SensorDatabase, SensorReadingSchema


class TestDatabaseCheckpointing:
    """Test suite for database checkpointing and data persistence."""

    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_checkpoint.db")

    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_batch_timeout_triggers_checkpoint(self):
        """Test that batch timeout properly triggers a checkpoint."""
        db = SensorDatabase(self.db_path)
        
        # Use insert_reading which uses batch buffer
        db.insert_reading(
            sensor_id="TEST001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        
        # Verify data is in buffer but not yet persisted
        assert len(db.batch_buffer) == 1
        
        # Wait for batch timeout
        time.sleep(db.batch_timeout + 0.5)
        
        # Force another operation to trigger timeout check
        db.insert_reading(
            sensor_id="TEST002",
            temperature=26.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        
        # Verify batch was committed
        assert len(db.batch_buffer) < db.batch_size
        
        # Close and reopen database to verify persistence
        db.close()
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        readings = db2.get_readings(limit=10)
        assert len(readings) >= 1
        db2.close()

    def test_batch_size_triggers_checkpoint(self):
        """Test that reaching batch size triggers a checkpoint."""
        db = SensorDatabase(self.db_path)
        db.batch_size = 5  # Set smaller batch size for testing
        
        # Insert exactly batch_size readings
        for i in range(5):
            db.insert_reading(
                sensor_id=f"BATCH{i:03d}",
                temperature=25.0 + i,
                vibration=0.1,
                voltage=12.0,
                status_code=0
            )
        
        # Verify batch was auto-committed (buffer should be empty or small)
        assert len(db.batch_buffer) < db.batch_size
        
        # Close and reopen to verify persistence
        db.close()
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        readings = db2.get_readings(limit=10)
        assert len(readings) >= 5
        db2.close()

    def test_explicit_commit_batch(self):
        """Test explicit commit_batch functionality."""
        db = SensorDatabase(self.db_path)
        
        # Insert some readings without reaching batch size
        for i in range(3):
            db.insert_reading(
                sensor_id=f"COMMIT{i:03d}",
                temperature=20.0 + i,
                vibration=0.2,
                voltage=11.5,
                status_code=0
            )
        
        # Verify data is in buffer
        assert len(db.batch_buffer) == 3
        
        # Explicitly commit
        committed = db.commit_batch()
        assert committed == 3
        assert len(db.batch_buffer) == 0
        
        # Verify persistence
        readings = db.get_readings(limit=10)
        assert len(readings) == 3
        db.close()

    def test_wal_checkpoint_behavior(self):
        """Test SQLite WAL checkpoint behavior."""
        db = SensorDatabase(self.db_path)
        
        # Verify WAL mode is enabled
        with db.conn_manager.get_cursor() as cursor:
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode == "wal"
        
        # Insert data and commit
        for i in range(10):
            db.insert_reading(
                sensor_id=f"WAL{i:03d}",
                temperature=30.0 + i,
                vibration=0.3,
                voltage=13.0,
                status_code=0
            )
        db.commit_batch()
        
        # Check WAL file existence
        wal_path = f"{self.db_path}-wal"
        shm_path = f"{self.db_path}-shm"
        
        # Force a manual checkpoint
        with db.conn_manager.get_cursor() as cursor:
            cursor.execute("PRAGMA wal_checkpoint(FULL);")
            result = cursor.fetchone()
            # result is (busy, checkpointed, total)
            assert result is not None
        
        db.close()

    def test_database_close_commits_pending(self):
        """Test that closing database commits any pending batch."""
        db = SensorDatabase(self.db_path)
        
        # Insert readings without reaching batch size
        for i in range(7):
            db.insert_reading(
                sensor_id=f"CLOSE{i:03d}",
                temperature=15.0 + i,
                vibration=0.15,
                voltage=10.5,
                status_code=0
            )
        
        # Verify data is in buffer
        buffer_size = len(db.batch_buffer)
        assert buffer_size > 0
        
        # Close database (should commit pending batch)
        db.close()
        
        # Reopen and verify all data was persisted
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        readings = db2.get_readings(limit=10)
        assert len(readings) == 7
        db2.close()

    def test_transaction_rollback_on_error(self):
        """Test that transactions are rolled back on error."""
        db = SensorDatabase(self.db_path)
        
        # Attempt to execute invalid SQL
        with pytest.raises(sqlite3.OperationalError):
            with db.conn_manager.get_cursor() as cursor:
                cursor.execute("INSERT INTO nonexistent_table VALUES (1, 2, 3)")
        
        # Verify database is still healthy
        assert db.is_healthy()
        
        # Verify we can still insert valid data
        db.insert_reading(
            sensor_id="ROLLBACK001",
            temperature=22.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0
        )
        db.commit_batch()
        
        readings = db.get_readings(limit=1)
        assert len(readings) == 1
        db.close()

    def test_concurrent_writes_with_checkpointing(self):
        """Test concurrent writes don't interfere with checkpointing."""
        db = SensorDatabase(self.db_path)
        results = []
        errors = []
        
        def writer_thread(thread_id, num_writes):
            try:
                for i in range(num_writes):
                    db.insert_reading(
                        sensor_id=f"THREAD{thread_id}_{i:03d}",
                        temperature=20.0 + thread_id + i,
                        vibration=0.1 * thread_id,
                        voltage=12.0,
                        status_code=0
                    )
                    # Occasionally force commit
                    if i % 3 == 0:
                        db.commit_batch()
                results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start multiple writer threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=writer_thread, args=(i, 5))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=10)
        
        # Final commit
        db.commit_batch()
        
        # Verify no errors
        assert len(errors) == 0
        assert len(results) == 3
        
        # Verify all data was written
        readings = db.get_readings(limit=20)
        # Due to timing, some threads might have inserted extra entries
        # We should have at least 15 entries (3 threads × 5 writes)
        assert len(readings) >= 15
        
        db.close()

    def test_database_checkpoint_performance_metrics(self):
        """Test checkpoint performance metrics are tracked correctly."""
        db = SensorDatabase(self.db_path)
        
        # Insert multiple batches
        for batch in range(3):
            for i in range(db.batch_size):
                db.insert_reading(
                    sensor_id=f"PERF{batch}_{i:03d}",
                    temperature=25.0,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0
                )
        
        # Get performance stats
        stats = db.get_database_stats()
        
        # Verify metrics
        assert stats["performance_metrics"]["total_batches"] >= 3
        assert stats["performance_metrics"]["total_inserts"] >= 3 * db.batch_size
        assert stats["performance_metrics"]["avg_batch_size"] > 0
        assert stats["performance_metrics"]["avg_insert_time_ms"] >= 0
        
        db.close()

    def test_checkpoint_with_pydantic_validation(self):
        """Test checkpointing with Pydantic model validation."""
        db = SensorDatabase(self.db_path)
        
        # Create valid readings
        valid_readings = []
        for i in range(5):
            reading = SensorReadingSchema(
                timestamp=f"2025-01-01T00:{i:02d}:00Z",
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
                original_timezone=f"+0{i}:00"
            )
            valid_readings.append(reading)
            db.store_reading(reading)
        
        # Force checkpoint
        db.commit_batch()
        
        # Verify all readings were stored
        readings = db.get_readings(limit=10)
        assert len(readings) == 5
        
        # Verify data integrity
        for i, reading in enumerate(readings):
            assert f"PYDANTIC{4-i:03d}" in str(reading)  # Readings returned in reverse order
        
        db.close()

    def test_checkpoint_recovery_after_crash(self):
        """Test database recovery after simulated crash."""
        # First session - write data without proper close
        db1 = SensorDatabase(self.db_path)
        
        for i in range(20):
            db1.insert_reading(
                sensor_id=f"CRASH{i:03d}",
                temperature=30.0 + i,
                vibration=0.2,
                voltage=14.0,
                status_code=0
            )
        
        # Get connection manager reference before "crash"
        # Note: In real crash, process would terminate
        conn_manager = db1.conn_manager
        
        # Simulate abrupt termination (no close)
        # Just abandon the database object
        db1 = None
        
        # Second session - recover and verify data
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        
        # Check what was persisted
        readings = db2.get_readings(limit=30)
        
        # At least the completed batches should be persisted
        assert len(readings) >= (20 // db2.batch_size) * db2.batch_size
        
        # Verify database is healthy after recovery
        assert db2.is_healthy()
        
        db2.close()

    @pytest.mark.timeout(10)
    def test_signal_handler_checkpoint(self):
        """Test that signal handlers properly checkpoint data."""
        # This test would require implementing signal handlers in the main code
        # For now, we'll test the concept
        
        db = SensorDatabase(self.db_path)
        
        # Insert some data
        for i in range(15):
            db.insert_reading(
                sensor_id=f"SIGNAL{i:03d}",
                temperature=28.0 + i,
                vibration=0.25,
                voltage=13.5,
                status_code=0
            )
        
        # Simulate signal handler behavior
        # In real implementation, this would be triggered by SIGTERM/SIGINT
        def signal_handler(signum, frame):
            db.commit_batch()
            db.close()
        
        # Call our simulated handler
        signal_handler(signal.SIGTERM, None)
        
        # Verify data was persisted
        db2 = SensorDatabase(self.db_path, preserve_existing_db=True)
        readings = db2.get_readings(limit=20)
        assert len(readings) == 15
        db2.close()


class TestCheckpointIntegration:
    """Integration tests for checkpoint functionality."""

    def test_checkpoint_integration_with_database(self):
        """Test database checkpointing functionality in isolation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "integration_test.db")
            db = SensorDatabase(db_path)
            
            # Simulate inserting readings over time
            for i in range(150):  # More than batch size
                db.insert_reading(
                    sensor_id=f"INTEG_{i:03d}",
                    temperature=20.0 + (i % 10),
                    vibration=0.1 + (i % 5) * 0.01,
                    voltage=12.0 + (i % 3) * 0.1,
                    status_code=0
                )
                
                # Simulate time passing for periodic checkpoints
                if i == 50:
                    # Force time to pass for checkpoint interval
                    db.last_checkpoint_time = time.time() - 400  # More than checkpoint_interval
                    
            # Ensure final commit
            db.commit_batch()
            
            # Get stats before close
            stats = db.get_database_stats()
            total_before_close = stats["total_readings"]
            
            # Close database (should trigger final checkpoint)
            db.close()
            
            # Reopen database and verify all data persisted
            db2 = SensorDatabase(db_path, preserve_existing_db=True)
            stats2 = db2.get_database_stats()
            
            assert stats2["total_readings"] == 150
            assert stats2["total_readings"] == total_before_close
            
            # Verify checkpoint configuration is set
            assert db2.checkpoint_on_close is True
            assert db2.checkpoint_interval == 300  # 5 minutes
            
            db2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])