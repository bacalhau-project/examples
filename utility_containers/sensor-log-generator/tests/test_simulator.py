import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

# Add src directory to Python path to allow importing modules from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from src.anomaly import (
    AnomalyGenerator,  # Assuming AnomalyGenerator is in anomaly.py
)
from src.config import (
    ConfigManager,  # Assuming ConfigManager is in config.py
)
from src.database import SensorDatabase  # Assuming SensorDatabase is in database.py

# Import Enums if they are in separate files or adjust as needed
from src.simulator import SensorSimulator


# Minimal valid configuration for testing
def get_minimal_config(db_path):
    return {
        "database": {"path": db_path},
        "logging": {"file": "test_simulator.log", "level": "DEBUG"},
        "simulation": {
            "readings_per_second": 10,
            "run_time_seconds": 0.2,
        },  # Run for a very short time
        "replicas": {"count": 1, "prefix": "TEST_SENSOR", "start_index": 1},
        "normal_parameters": {
            "temperature": {"mean": 25, "std_dev": 2, "min": -10, "max": 60},
            "vibration": {"mean": 0.1, "std_dev": 0.05, "min": 0, "max": 1},
            "voltage": {"mean": 12, "std_dev": 0.5, "min": 10, "max": 14},
            "humidity": {"mean": 50, "std_dev": 5, "min": 0, "max": 100},
            "pressure": {"mean": 1012, "std_dev": 5, "min": 980, "max": 1050},
        },
        "anomaly_settings": {"enabled": False, "frequency_seconds": 600, "types": {}},
        "monitoring": {"enabled": False},
    }


# Minimal valid identity for testing
def get_minimal_identity(
    sensor_id="TEST001",
    location="TestCity",
    latitude=10.0,
    longitude=20.0,
    timezone="UTC",
):
    return {
        "id": sensor_id,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "manufacturer": "SensorTech",
        "model": "EnvMonitor-3000",
        "firmware_version": "1.4.0",
    }


class TestSensorSimulator(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for db and logs
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_sensor_data.db")

        # Ensure log directory exists if logging to file
        log_file_path = get_minimal_config(self.db_path)["logging"]["file"]
        if log_file_path:
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(
                log_dir
            ):  # Handle cases where log_file is just a name
                os.makedirs(log_dir, exist_ok=True)
            elif not log_dir and not os.path.exists(
                os.path.join(self.temp_dir.name, log_dir if log_dir else "")
            ):
                # if log_dir is empty, create log file in temp_dir
                self.log_path = os.path.join(self.temp_dir.name, log_file_path)

    def tearDown(self):
        self.temp_dir.cleanup()
        # Clean up log file if created
        log_file_path = get_minimal_config(self.db_path)["logging"]["file"]
        if log_file_path and os.path.exists(log_file_path):
            os.remove(log_file_path)
        elif hasattr(self, "log_path") and os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_simulator_run_with_valid_identity_and_db_write(self):
        config = get_minimal_config(self.db_path)
        identity = get_minimal_identity(
            sensor_id="VALID_ID_001",
            location="ValidCity",
            latitude=34.0522,
            longitude=-118.2437,
        )

        # Initialize ConfigManager with initial config and identity
        # This is to mimic how SensorSimulator receives its config and identity
        # In a real scenario, main.py would handle this.
        # For testing, we create temporary config and identity files if needed by ConfigManager
        # or pass them directly if the constructor supports it.

        # SensorSimulator expects config and identity dicts directly.
        # No need for ConfigManager instantiation here for this basic test if not using its dynamic update features.

        config_manager = ConfigManager(config=config, identity=identity)
        simulator = SensorSimulator(config_manager=config_manager)
        simulator.run()  # Runs for config["simulation"]["run_time_seconds"]

        # Check database for entries
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sensor_id, location, latitude, longitude, temperature FROM sensor_readings"
        )
        rows = cursor.fetchall()
        conn.close()

        self.assertTrue(len(rows) > 0, "No readings found in the database.")
        for row in rows:
            self.assertEqual(row[0], "VALID_ID_001")
            self.assertEqual(row[1], "ValidCity")
            self.assertAlmostEqual(row[2], 34.0522, places=6)
            self.assertAlmostEqual(row[3], -118.2437, places=6)
            self.assertIsNotNone(row[4], "Temperature should not be None")

    def test_initialization_with_invalid_location_data(self):
        config = get_minimal_config(self.db_path)

        scenarios = [
            get_minimal_identity(
                location="ValidCity", latitude=None, longitude=10.0
            ),  # Missing lat
            get_minimal_identity(
                location="ValidCity", latitude=10.0, longitude=None
            ),  # Missing long
            get_minimal_identity(
                location="ValidCity", latitude=None, longitude=None
            ),  # Missing lat & long
            get_minimal_identity(
                location=None, latitude=None, longitude=None
            ),  # Missing city, lat & long
            get_minimal_identity(
                location="", latitude=10.0, longitude=20.0
            ),  # Empty city string
        ]

        for identity in scenarios:
            with self.subTest(identity=identity):
                with self.assertRaises(ValueError) as context:
                    config_manager = ConfigManager(config=config, identity=identity)
                    SensorSimulator(config_manager=config_manager)
                self.assertTrue(
                    "incomplete location information" in str(context.exception).lower()
                    or "valid manufacturers are" in str(context.exception).lower()
                    or "valid models are" in str(context.exception).lower()
                    or "valid versions are" in str(context.exception).lower()
                    or "location is required" in str(context.exception).lower(),
                    f"Unexpected ValueError message: {str(context.exception)}",
                )


    def test_simulator_with_anomalies_enabled(self):
        """Test simulator with anomalies enabled."""
        config = get_minimal_config(self.db_path)
        config["anomaly_settings"]["enabled"] = True
        config["anomaly_settings"]["frequency_seconds"] = 1
        config["anomaly_settings"]["types"] = {
            "spike": {"enabled": True, "probability": 1.0, "duration_seconds": 1}
        }
        identity = get_minimal_identity()

        config_manager = ConfigManager(config=config, identity=identity)
        simulator = SensorSimulator(config_manager=config_manager)
        simulator.run()

        # Check that some readings were generated
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()

        self.assertGreater(count, 0, "No readings generated with anomalies enabled")

    def test_simulator_with_different_firmware_versions(self):
        """Test simulator with different firmware versions."""
        config = get_minimal_config(self.db_path)
        
        for firmware_version in ["1.4.0", "1.5.0", "2.0.0"]:
            with self.subTest(firmware_version=firmware_version):
                identity = get_minimal_identity()
                identity["firmware_version"] = firmware_version
                
                config_manager = ConfigManager(config=config, identity=identity)
                simulator = SensorSimulator(config_manager=config_manager)
                
                # Should initialize without error
                self.assertEqual(simulator.firmware_version, firmware_version)

    def test_simulator_with_different_manufacturers(self):
        """Test simulator with different manufacturers."""
        config = get_minimal_config(self.db_path)
        
        for manufacturer in ["SensorTech", "EnvMonitors", "IoTPro", "AcmeSensors", "CustomManufacturer"]:
            with self.subTest(manufacturer=manufacturer):
                identity = get_minimal_identity()
                identity["manufacturer"] = manufacturer
                
                config_manager = ConfigManager(config=config, identity=identity)
                simulator = SensorSimulator(config_manager=config_manager)
                
                # Should initialize without error
                self.assertEqual(simulator.manufacturer, manufacturer)

    def test_simulator_with_different_models(self):
        """Test simulator with different models."""
        config = get_minimal_config(self.db_path)
        
        for model in ["EnvMonitor-3000", "EnvMonitor-4000", "EnvMonitor-5000"]:
            with self.subTest(model=model):
                identity = get_minimal_identity()
                identity["model"] = model
                
                config_manager = ConfigManager(config=config, identity=identity)
                simulator = SensorSimulator(config_manager=config_manager)
                
                # Should initialize without error
                self.assertEqual(simulator.model, model)

    def test_simulator_with_monitoring_enabled(self):
        """Test simulator with monitoring enabled."""
        config = get_minimal_config(self.db_path)
        config["monitoring"]["enabled"] = True
        config["monitoring"]["port"] = 0  # Use any available port
        identity = get_minimal_identity()

        config_manager = ConfigManager(config=config, identity=identity)
        simulator = SensorSimulator(config_manager=config_manager)
        
        # Should initialize without error even with monitoring
        self.assertIsNotNone(simulator)

    def test_simulator_get_status(self):
        """Test that simulator can provide status information."""
        config = get_minimal_config(self.db_path)
        identity = get_minimal_identity()

        config_manager = ConfigManager(config=config, identity=identity)
        simulator = SensorSimulator(config_manager=config_manager)
        
        status = simulator.get_status()
        
        # Status should be a dictionary with expected keys
        self.assertIsInstance(status, dict)
        self.assertIn("sensor_id", status)
        self.assertIn("location", status)
        self.assertIn("running", status)

    def test_simulator_with_extreme_readings_per_second(self):
        """Test simulator with extreme readings per second values."""
        config = get_minimal_config(self.db_path)
        identity = get_minimal_identity()
        
        # Test very high readings per second
        config["simulation"]["readings_per_second"] = 1000
        config["simulation"]["run_time_seconds"] = 0.01  # Very short duration
        
        config_manager = ConfigManager(config=config, identity=identity)
        simulator = SensorSimulator(config_manager=config_manager)
        
        # Should handle high frequency without error
        try:
            simulator.run()
        except Exception as e:
            self.fail(f"Simulator failed with high readings_per_second: {e}")

    def test_simulator_database_error_handling(self):
        """Test simulator handles database errors gracefully."""
        # Use an invalid database path to trigger errors
        invalid_db_path = "/invalid/path/to/database.db"
        config = get_minimal_config(invalid_db_path)
        identity = get_minimal_identity()

        with self.assertRaises(Exception):
            config_manager = ConfigManager(config=config, identity=identity)
            SensorSimulator(config_manager=config_manager)


if __name__ == "__main__":
    unittest.main()
