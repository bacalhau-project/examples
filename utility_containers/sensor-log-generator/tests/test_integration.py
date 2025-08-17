"""Integration tests for the sensor simulator system."""
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager
from src.database import SensorDatabase
from src.simulator import SensorSimulator
from src.enums import SensorType, MetricType


class TestMainIntegration:
    """Test the full integration through main.py."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "data").mkdir()
            (temp_path / "logs").mkdir()
            (temp_path / "config").mkdir()
            yield temp_path
    
    @pytest.fixture
    def test_config(self, temp_dirs):
        """Create a test configuration file."""
        config = {
            "sensor": {
                "sensor_id": "TEST001",
                "location": {
                    "city": "TestCity",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "timezone": "America/New_York"
                },
                "device_info": {
                    "manufacturer": "TestMfr",
                    "model": "TestModel",
                    "firmware_version": "1.0.0"
                }
            },
            "simulation": {
                "readings_per_second": 10,
                "run_time_seconds": 2,  # Short runtime for tests
                "anomaly_probability": 0.01
            },
            "database": {
                "db_path": str(temp_dirs / "data" / "test.db"),
                "batch_size": 5,
                "flush_interval": 1
            },
            "logging": {
                "level": "DEBUG",
                "log_path": str(temp_dirs / "logs" / "test.log"),
                "rotation": {
                    "max_bytes": 10485760,
                    "backup_count": 3
                }
            }
        }
        config_path = temp_dirs / "config" / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        return config_path
    
    @pytest.fixture
    def test_identity(self, temp_dirs):
        """Create a test identity file."""
        identity = {
            "sensor_id": "TEST001",
            "location": {
                "city": "TestCity",
                "coordinates": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "timezone": "America/New_York"
            },
            "device_info": {
                "manufacturer": "TestMfr",
                "model": "TestModel",
                "firmware_version": "1.0.0"
            }
        }
        identity_path = temp_dirs / "config" / "identity.json"
        with open(identity_path, 'w') as f:
            json.dump(identity, f)
        return identity_path
    
    def test_main_execution_flow(self, test_config, test_identity, temp_dirs):
        """Test that main.py actually calls simulator.run() and writes data."""
        # Run main.py as a subprocess with short timeout
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).parent.parent)
        
        process = subprocess.Popen(
            [sys.executable, "main.py", 
             "--config", str(test_config),
             "--identity", str(test_identity)],
            cwd=str(Path(__file__).parent.parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Let it run for the configured time plus buffer
        time.sleep(3)
        
        # Send shutdown signal
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=5)
        
        # Check that data was written to database
        db_path = temp_dirs / "data" / "test.db"
        assert db_path.exists(), f"Database not created. Stdout: {stdout}\nStderr: {stderr}"
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        
        # Should have ~20 readings (10 per second for 2 seconds)
        assert count > 0, f"No data written to database. Count: {count}\nStdout: {stdout}\nStderr: {stderr}"
        assert count >= 10, f"Too few readings. Expected ~20, got {count}"
    
    def test_simulator_run_is_called(self, test_config, test_identity):
        """Test that simulator.run() is actually called from main."""
        # Import main module
        import main
        
        # Mock the simulator to track if run() is called
        with patch('main.SensorSimulator') as MockSimulator:
            mock_instance = MagicMock()
            MockSimulator.return_value = mock_instance
            
            # Mock parse_args to return our test config
            with patch('main.parse_args') as mock_args:
                mock_args.return_value = MagicMock(
                    config=str(test_config),
                    identity=str(test_identity),
                    generate_identity=False,
                    validate=False,
                    no_monitor=True
                )
                
                # Mock signal handlers to prevent actual signal handling
                with patch('main.signal.signal'):
                    # Run main
                    try:
                        main.main()
                    except SystemExit:
                        pass  # Expected on normal completion
            
            # Verify simulator.run() was called
            mock_instance.run.assert_called_once()
    
    def test_database_writes_during_simulation(self, temp_dirs):
        """Test that simulator actually writes to database during run."""
        config = SensorConfig(
            sensor_id="TEST002",
            location={
                "city": "TestCity",
                "latitude": 40.0,
                "longitude": -74.0,
                "timezone": "UTC"
            },
            device_info={
                "manufacturer": "Test",
                "model": "TestModel",
                "firmware_version": "1.0.0"
            },
            simulation={
                "readings_per_second": 10,
                "run_time_seconds": 1,
                "anomaly_probability": 0.0
            },
            database={
                "db_path": str(temp_dirs / "test.db"),
                "batch_size": 5,
                "flush_interval": 0.5
            },
            logging={
                "level": "DEBUG",
                "log_path": str(temp_dirs / "test.log")
            }
        )
        
        config_mgr = ConfigManager(config=config)
        simulator = SensorSimulator(config_mgr)
        
        # Run simulation
        simulator.run()
        
        # Check database
        conn = sqlite3.connect(str(temp_dirs / "test.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        
        # Should have ~10 readings (10 per second for 1 second)
        assert count >= 8, f"Expected at least 8 readings, got {count}"
        assert count <= 12, f"Expected at most 12 readings, got {count}"


class TestDatabaseIntegration:
    """Test database operations in realistic scenarios."""
    
    @pytest.fixture
    def db_manager(self, tmp_path):
        """Create a database manager for testing."""
        db_path = tmp_path / "test.db"
        config = SensorConfig(
            sensor_id="TEST003",
            location={"city": "Test", "latitude": 0, "longitude": 0, "timezone": "UTC"},
            device_info={"manufacturer": "Test", "model": "Test", "firmware_version": "1.0"},
            simulation={"readings_per_second": 1, "run_time_seconds": 1},
            database={"db_path": str(db_path), "batch_size": 10, "flush_interval": 1},
            logging={"level": "DEBUG", "log_path": str(tmp_path / "test.log")}
        )
        config_mgr = ConfigManager(config=config)
        return DatabaseManager(config_mgr)
    
    def test_concurrent_writes(self, db_manager):
        """Test that concurrent writes work correctly."""
        import concurrent.futures
        from datetime import datetime
        
        def write_batch(thread_id):
            """Write a batch of readings from a thread."""
            readings = []
            for i in range(10):
                readings.append({
                    'timestamp': datetime.now().isoformat(),
                    'sensor_id': f'TEST_THREAD_{thread_id}',
                    'sensor_type': SensorType.TEMPERATURE.value,
                    'metric_type': MetricType.GAUGE.value,
                    'value': 20.0 + i,
                    'unit': 'celsius',
                    'location': 'Test',
                    'quality_score': 0.95,
                    'is_anomaly': False
                })
            db_manager.write_batch(readings)
            return len(readings)
        
        # Write from multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_batch, i) for i in range(5)]
            results = [f.result() for f in futures]
        
        # Verify all writes succeeded
        assert sum(results) == 50
        
        # Check database
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 50, f"Expected 50 readings, got {count}"
    
    def test_database_persistence(self, tmp_path):
        """Test that data persists across database manager instances."""
        db_path = tmp_path / "persist.db"
        config = SensorConfig(
            sensor_id="TEST004",
            location={"city": "Test", "latitude": 0, "longitude": 0, "timezone": "UTC"},
            device_info={"manufacturer": "Test", "model": "Test", "firmware_version": "1.0"},
            simulation={"readings_per_second": 1, "run_time_seconds": 1},
            database={"db_path": str(db_path), "batch_size": 10, "flush_interval": 1},
            logging={"level": "DEBUG", "log_path": str(tmp_path / "test.log")}
        )
        config_mgr = ConfigManager(config=config)
        
        # Write with first instance
        db1 = DatabaseManager(config_mgr)
        readings = [{
            'timestamp': '2025-01-01T00:00:00',
            'sensor_id': 'TEST004',
            'sensor_type': SensorType.TEMPERATURE.value,
            'metric_type': MetricType.GAUGE.value,
            'value': 25.0,
            'unit': 'celsius',
            'location': 'Test',
            'quality_score': 0.95,
            'is_anomaly': False
        }]
        db1.write_batch(readings)
        db1.close()
        
        # Read with second instance
        db2 = DatabaseManager(config_mgr)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        db2.close()
        
        assert count == 1, f"Data not persisted. Count: {count}"


class TestSignalHandling:
    """Test signal handling and graceful shutdown."""
    
    def test_graceful_shutdown_on_sigint(self, tmp_path):
        """Test that SIGINT triggers graceful shutdown."""
        config = SensorConfig(
            sensor_id="TEST005",
            location={"city": "Test", "latitude": 0, "longitude": 0, "timezone": "UTC"},
            device_info={"manufacturer": "Test", "model": "Test", "firmware_version": "1.0"},
            simulation={"readings_per_second": 10, "run_time_seconds": 10},
            database={"db_path": str(tmp_path / "test.db"), "batch_size": 5, "flush_interval": 1},
            logging={"level": "DEBUG", "log_path": str(tmp_path / "test.log")}
        )
        config_mgr = ConfigManager(config=config)
        simulator = SensorSimulator(config_mgr)
        
        # Start simulator in thread
        thread = threading.Thread(target=simulator.run)
        thread.start()
        
        # Let it run briefly
        time.sleep(0.5)
        
        # Trigger shutdown
        simulator.shutdown_event.set()
        
        # Wait for thread to finish
        thread.join(timeout=2)
        assert not thread.is_alive(), "Simulator didn't shut down gracefully"
        
        # Check that some data was written
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count > 0, "No data written before shutdown"
        assert count < 100, "Too much data - shutdown may not have worked"


class TestEndToEnd:
    """End-to-end tests for the complete system."""
    
    def test_full_simulation_cycle(self, tmp_path):
        """Test a complete simulation cycle from start to finish."""
        # Create config
        config = SensorConfig(
            sensor_id="TEST_E2E",
            location={
                "city": "TestCity",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "America/New_York"
            },
            device_info={
                "manufacturer": "TestCorp",
                "model": "SensorPro",
                "firmware_version": "2.0.0"
            },
            simulation={
                "readings_per_second": 5,
                "run_time_seconds": 2,
                "anomaly_probability": 0.1,
                "seasonal_variation": True,
                "noise_level": 0.1
            },
            database={
                "db_path": str(tmp_path / "e2e.db"),
                "batch_size": 10,
                "flush_interval": 1
            },
            logging={
                "level": "INFO",
                "log_path": str(tmp_path / "e2e.log")
            }
        )
        
        # Run simulation
        config_mgr = ConfigManager(config=config)
        simulator = SensorSimulator(config_mgr)
        stats = simulator.run()
        
        # Verify statistics
        assert stats['total_readings'] >= 8, f"Too few readings: {stats['total_readings']}"
        assert stats['total_readings'] <= 12, f"Too many readings: {stats['total_readings']}"
        assert 'anomalies' in stats
        assert 'duration' in stats
        
        # Verify database content
        conn = sqlite3.connect(str(tmp_path / "e2e.db"))
        cursor = conn.cursor()
        
        # Check total count
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        assert count == stats['total_readings']
        
        # Check data quality
        cursor.execute("""
            SELECT sensor_type, COUNT(*) as cnt 
            FROM sensor_readings 
            GROUP BY sensor_type
        """)
        sensor_types = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Should have multiple sensor types
        assert len(sensor_types) >= 3, f"Too few sensor types: {sensor_types}"
        
        # Check for anomalies if any were generated
        cursor.execute("SELECT COUNT(*) FROM sensor_readings WHERE is_anomaly = 1")
        anomaly_count = cursor.fetchone()[0]
        assert anomaly_count == stats['anomalies']
        
        conn.close()
        
        # Verify log file was created
        log_path = tmp_path / "e2e.log"
        assert log_path.exists(), "Log file not created"
        assert log_path.stat().st_size > 0, "Log file is empty"