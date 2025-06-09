import os
import pytest
from unittest.mock import patch

from src.config import ConfigManager


class TestConfigManager:
    def test_init_with_valid_config_and_identity(self):
        """Test successful initialization with valid config and identity."""
        config = {
            "database": {"path": "test.db"},
            "simulation": {"readings_per_second": 1},
        }
        identity = {
            "id": "TEST001",
            "location": "Test City",
        }
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.config == config
        assert manager.identity == identity

    def test_init_with_none_identity(self):
        """Test initialization when identity is None."""
        config = {"database": {"path": "test.db"}}
        identity = None
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.config == config
        assert manager.identity == {}

    @patch.dict(os.environ, {"SENSOR_LOCATION": "Override Location"})
    def test_env_override_sensor_location(self):
        """Test that SENSOR_LOCATION environment variable overrides identity location."""
        config = {"database": {"path": "test.db"}}
        identity = {"id": "TEST001", "location": "Original Location"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.identity["location"] == "Override Location"

    @patch.dict(os.environ, {"SENSOR_ID": "OVERRIDE_ID"})
    def test_env_override_sensor_id(self):
        """Test that SENSOR_ID environment variable overrides identity ID."""
        config = {"database": {"path": "test.db"}}
        identity = {"id": "ORIGINAL_ID", "location": "Test City"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.identity["id"] == "OVERRIDE_ID"

    @patch.dict(os.environ, {"SENSOR_LOCATION": "Env Location", "SENSOR_ID": "ENV_ID"})
    def test_env_override_both_values(self):
        """Test that both environment variables override identity values."""
        config = {"database": {"path": "test.db"}}
        identity = {"id": "ORIGINAL_ID", "location": "Original Location"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.identity["id"] == "ENV_ID"
        assert manager.identity["location"] == "Env Location"

    def test_get_sensor_config(self):
        """Test getting sensor configuration."""
        config = {
            "sensor": {"type": "temperature", "range": "0-100"},
            "other": {"value": "test"}
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_sensor_config() == {"type": "temperature", "range": "0-100"}

    def test_get_sensor_config_missing(self):
        """Test getting sensor config when sensor section is missing."""
        config = {"database": {"path": "test.db"}}
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_sensor_config() == {}

    def test_get_simulation_config(self):
        """Test getting simulation configuration."""
        config = {
            "simulation": {"readings_per_second": 10, "duration": 3600},
            "other": {"value": "test"}
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_simulation_config() == {"readings_per_second": 10, "duration": 3600}

    def test_get_simulation_config_missing(self):
        """Test getting simulation config when simulation section is missing."""
        config = {"database": {"path": "test.db"}}
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_simulation_config() == {}

    def test_get_normal_parameters(self):
        """Test getting normal parameters configuration."""
        config = {
            "normal_parameters": {
                "temperature": {"mean": 25, "std_dev": 2},
                "humidity": {"mean": 50, "std_dev": 5}
            }
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        expected = {
            "temperature": {"mean": 25, "std_dev": 2},
            "humidity": {"mean": 50, "std_dev": 5}
        }
        assert manager.get_normal_parameters() == expected

    def test_get_anomaly_config(self):
        """Test getting anomaly configuration."""
        config = {
            "anomalies": {
                "enabled": True,
                "probability": 0.05,
                "types": {"spike": {"enabled": True}}
            }
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        expected = {
            "enabled": True,
            "probability": 0.05,
            "types": {"spike": {"enabled": True}}
        }
        assert manager.get_anomaly_config() == expected

    def test_get_database_config(self):
        """Test getting database configuration."""
        config = {
            "database": {
                "path": "sensor_data.db",
                "timeout": 30,
                "batch_size": 100
            }
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        expected = {
            "path": "sensor_data.db",
            "timeout": 30,
            "batch_size": 100
        }
        assert manager.get_database_config() == expected

    def test_get_logging_config(self):
        """Test getting logging configuration."""
        config = {
            "logging": {
                "level": "DEBUG",
                "file": "sensor.log",
                "format": "%(asctime)s - %(message)s"
            }
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        expected = {
            "level": "DEBUG",
            "file": "sensor.log",
            "format": "%(asctime)s - %(message)s"
        }
        assert manager.get_logging_config() == expected

    def test_get_valid_configurations(self):
        """Test getting valid configurations."""
        config = {
            "valid_configurations": {
                "manufacturers": ["SensorTech", "EnvMonitors"],
                "models": ["Model1", "Model2"]
            }
        }
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        expected = {
            "manufacturers": ["SensorTech", "EnvMonitors"],
            "models": ["Model1", "Model2"]
        }
        assert manager.get_valid_configurations() == expected

    def test_get_identity(self):
        """Test getting identity configuration."""
        config = {"database": {"path": "test.db"}}
        identity = {
            "id": "TEST001",
            "location": "Test City",
            "latitude": 40.7128,
            "longitude": -74.0060
        }
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_identity() == identity

    def test_get_identity_empty(self):
        """Test getting identity when identity is None."""
        config = {"database": {"path": "test.db"}}
        identity = None
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_identity() == {}

    def test_all_getters_with_none_config(self):
        """Test all getters when config is None."""
        config = None
        identity = {"id": "TEST001"}
        
        manager = ConfigManager(config=config, identity=identity)
        
        assert manager.get_simulation_config() == {}
        assert manager.get_normal_parameters() == {}
        assert manager.get_anomaly_config() == {}
        assert manager.get_database_config() == {}
        assert manager.get_logging_config() == {}
        assert manager.get_valid_configurations() == {}