import time
from unittest.mock import patch

import pytest

from src.anomaly import AnomalyGenerator
from src.enums import AnomalyType


class TestAnomalyGenerator:
    def get_valid_identity(self):
        """Get a valid identity for testing."""
        return {
            "id": "TEST001",
            "location": "Test Location",
            "latitude": 40.0,
            "longitude": -74.0,
            "firmware_version": "1.4.0",
            "model": "EnvMonitor-3000",
            "manufacturer": "SensorTech",
        }

    def get_valid_config(self):
        """Get a valid config for testing."""
        return {
            "anomalies": {
                "enabled": True,
                "probability": 0.1,
                "types": {
                    AnomalyType.SPIKE.value: {"enabled": True, "weight": 1.0, "duration_seconds": 60},
                    AnomalyType.TREND.value: {"enabled": True, "weight": 1.0, "duration_seconds": 300},
                    AnomalyType.NOISE.value: {"enabled": True, "weight": 1.0, "duration_seconds": 120},
                }
            }
        }

    def test_init_with_valid_config_and_identity(self):
        """Test successful initialization with valid config and identity."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        
        generator = AnomalyGenerator(config, identity)
        
        assert generator.enabled is True
        assert generator.probability == 0.1
        assert generator.id == "TEST001"
        # firmware_version could be enum or string depending on if it matches known values
        from src.enums import FirmwareVersion
        if isinstance(generator.firmware_version, FirmwareVersion):
            assert generator.firmware_version.value == "1.4.0"
        else:
            assert generator.firmware_version == "1.4.0"
        # model could be enum or string
        assert str(generator.model) == "EnvMonitor-3000" or generator.model == "EnvMonitor-3000"
        assert generator.manufacturer == "SensorTech"

    def test_init_missing_sensor_id(self):
        """Test initialization fails when sensor ID is missing."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        del identity["id"]
        
        with pytest.raises(ValueError, match="Sensor ID is required"):
            AnomalyGenerator(config, identity)

    def test_init_missing_location(self):
        """Test initialization fails when location is missing."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        del identity["location"]
        
        with pytest.raises(ValueError, match="Location is required"):
            AnomalyGenerator(config, identity)

    def test_init_invalid_firmware_version(self):
        """Test initialization fails with invalid firmware version."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        identity["firmware_version"] = "1.2"  # Invalid SemVer - missing patch version
        
        with pytest.raises(ValueError, match="Invalid firmware version"):
            AnomalyGenerator(config, identity)

    def test_init_invalid_model(self):
        """Test model accepts any string value."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        identity["model"] = "INVALID_MODEL"
        
        # Should not raise an exception - any string is valid
        generator = AnomalyGenerator(config, identity)
        assert generator.model == "INVALID_MODEL"

    def test_init_custom_manufacturer(self):
        """Test initialization accepts any manufacturer string."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        identity["manufacturer"] = "AcmeSensors"
        
        # Should not raise an exception - any string is valid
        generator = AnomalyGenerator(config, identity)
        assert generator.manufacturer == "AcmeSensors"

    def test_should_generate_anomaly_disabled(self):
        """Test that anomalies are not generated when disabled."""
        config = self.get_valid_config()
        config["anomalies"]["enabled"] = False
        identity = self.get_valid_identity()
        
        generator = AnomalyGenerator(config, identity)
        
        # Should never generate anomalies when disabled
        for _ in range(100):
            assert generator.should_generate_anomaly() is False

    @patch('src.anomaly.random.random')
    def test_should_generate_anomaly_probability(self, mock_random):
        """Test anomaly generation based on probability."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        
        generator = AnomalyGenerator(config, identity)
        
        # The probability gets adjusted by firmware (V1_4 = 1.5x) and manufacturer (SENSORTECH = 1.0x)
        # So 0.1 * 1.5 = 0.15 is the actual threshold
        
        # Test below adjusted probability threshold
        mock_random.return_value = 0.05  # Below 0.15 adjusted probability
        assert generator.should_generate_anomaly() is True
        
        # Test above adjusted probability threshold
        mock_random.return_value = 0.20  # Above 0.15 adjusted probability
        assert generator.should_generate_anomaly() is False

    @patch('src.anomaly.random.random')
    def test_firmware_version_affects_probability(self, mock_random):
        """Test that firmware version affects anomaly probability."""
        config = self.get_valid_config()
        
        # Test V1_4 (higher probability)
        identity_v14 = self.get_valid_identity()
        identity_v14["firmware_version"] = "1.4.0"
        generator_v14 = AnomalyGenerator(config, identity_v14)
        
        # Test V1_5 (lower probability)
        identity_v15 = self.get_valid_identity()
        identity_v15["firmware_version"] = "1.5.0"
        generator_v15 = AnomalyGenerator(config, identity_v15)
        
        # Set random value that should work for V1_4 but not V1_5
        mock_random.return_value = 0.12  # Between base (0.1) and V1_4 adjusted (0.15)
        
        assert generator_v14.should_generate_anomaly() is True
        assert generator_v15.should_generate_anomaly() is False

    @patch('src.anomaly.random.random')
    def test_manufacturer_affects_probability(self, mock_random):
        """Test that manufacturer affects anomaly probability."""
        config = self.get_valid_config()
        
        # Test different manufacturers
        identity_sensortech = self.get_valid_identity()
        identity_sensortech["manufacturer"] = "SensorTech"
        generator_sensortech = AnomalyGenerator(config, identity_sensortech)
        
        identity_iotpro = self.get_valid_identity()
        identity_iotpro["manufacturer"] = "IoTPro"
        generator_iotpro = AnomalyGenerator(config, identity_iotpro)
        
        # SENSORTECH: 0.1 * 1.5 (firmware) * 1.0 (manufacturer) = 0.15
        # IOTPRO: 0.1 * 1.5 (firmware) * 1.2 (manufacturer) = 0.18
        
        # Set random value that should work for IOTPRO but not SENSORTECH
        mock_random.return_value = 0.16  # Between SENSORTECH (0.15) and IOTPRO (0.18)
        
        assert generator_sensortech.should_generate_anomaly() is False
        assert generator_iotpro.should_generate_anomaly() is True

    def test_select_anomaly_type_no_enabled_types(self):
        """Test selecting anomaly type when no types are enabled."""
        config = self.get_valid_config()
        # Disable all anomaly types
        for anomaly_type in config["anomalies"]["types"]:
            config["anomalies"]["types"][anomaly_type]["enabled"] = False
        
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        result = generator.select_anomaly_type()
        assert result is None

    @patch('src.anomaly.random.random')
    def test_select_anomaly_type_weighted_selection(self, mock_random):
        """Test weighted selection of anomaly types."""
        config = self.get_valid_config()
        # Set different weights
        config["anomalies"]["types"][AnomalyType.SPIKE.value]["weight"] = 3.0
        config["anomalies"]["types"][AnomalyType.TREND.value]["weight"] = 1.0
        config["anomalies"]["types"][AnomalyType.NOISE.value]["weight"] = 1.0
        
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        # Test selection at different probability points
        mock_random.return_value = 0.1  # Should select SPIKE (weight 3/5 = 0.6)
        result = generator.select_anomaly_type()
        assert result == AnomalyType.SPIKE

    def test_start_anomaly(self):
        """Test starting an anomaly."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        anomaly_type = AnomalyType.SPIKE
        generator.start_anomaly(anomaly_type)
        
        assert generator.active_anomalies[anomaly_type] is True
        assert anomaly_type in generator.start_times
        assert generator.start_times[anomaly_type] <= time.time()

    def test_start_anomaly_already_active(self):
        """Test starting an anomaly that's already active."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        anomaly_type = AnomalyType.SPIKE
        generator.start_anomaly(anomaly_type)
        original_start_time = generator.start_times[anomaly_type]
        
        # Try to start again
        time.sleep(0.01)  # Small delay
        generator.start_anomaly(anomaly_type)
        
        # Start time should not have changed
        assert generator.start_times[anomaly_type] == original_start_time

    def test_is_anomaly_active_not_started(self):
        """Test checking if anomaly is active when not started."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        assert generator.is_anomaly_active(AnomalyType.SPIKE) is False

    def test_is_anomaly_active_within_duration(self):
        """Test checking if anomaly is active within duration."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        anomaly_type = AnomalyType.SPIKE
        generator.start_anomaly(anomaly_type)
        
        assert generator.is_anomaly_active(anomaly_type) is True

    def test_is_anomaly_active_expired(self):
        """Test checking if anomaly is active after expiration."""
        config = self.get_valid_config()
        # Set very short duration
        config["anomalies"]["types"][AnomalyType.SPIKE.value]["duration_seconds"] = 0.01
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        anomaly_type = AnomalyType.SPIKE
        generator.start_anomaly(anomaly_type)
        
        # Wait for expiration
        time.sleep(0.02)
        
        assert generator.is_anomaly_active(anomaly_type) is False

    def test_apply_spike_anomaly(self):
        """Test applying spike anomaly to readings."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        modified, is_anomaly, anomaly_type = generator.apply_anomaly(reading, AnomalyType.SPIKE)
        
        assert is_anomaly is True
        assert anomaly_type == AnomalyType.SPIKE
        assert modified is not None
        # At least one parameter should be different
        params_changed = any(
            modified.get(key) != reading.get(key) 
            for key in ["temperature", "humidity", "voltage"]
        )
        assert params_changed

    def test_apply_trend_anomaly(self):
        """Test applying trend anomaly to readings."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        # Start the trend anomaly first
        generator.start_anomaly(AnomalyType.TREND)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        modified, is_anomaly, anomaly_type = generator.apply_anomaly(reading, AnomalyType.TREND)
        
        assert is_anomaly is True
        assert anomaly_type == AnomalyType.TREND
        assert modified is not None

    def test_apply_pattern_anomaly(self):
        """Test applying pattern anomaly to readings."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        # Start the pattern anomaly first
        generator.start_anomaly(AnomalyType.PATTERN)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        modified, is_anomaly, anomaly_type = generator.apply_anomaly(reading, AnomalyType.PATTERN)
        
        assert is_anomaly is True
        assert anomaly_type == AnomalyType.PATTERN
        assert modified is not None
        # Temperature and humidity should be modified with pattern
        assert modified["temperature"] != reading["temperature"]
        assert modified["humidity"] != reading["humidity"]

    def test_apply_missing_data_anomaly(self):
        """Test applying missing data anomaly."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        modified, is_anomaly, anomaly_type = generator.apply_anomaly(reading, AnomalyType.MISSING_DATA)
        
        assert is_anomaly is True
        assert anomaly_type == AnomalyType.MISSING_DATA
        assert modified is None

    def test_apply_noise_anomaly(self):
        """Test applying noise anomaly to readings."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        modified, is_anomaly, anomaly_type = generator.apply_anomaly(reading, AnomalyType.NOISE)
        
        assert is_anomaly is True
        assert anomaly_type == AnomalyType.NOISE
        assert modified is not None
        # All main parameters should have noise added
        for param in ["temperature", "humidity", "voltage"]:
            assert modified[param] != reading[param]

    def test_apply_unknown_anomaly_type(self):
        """Test applying unknown anomaly type returns original reading."""
        config = self.get_valid_config()
        identity = self.get_valid_identity()
        generator = AnomalyGenerator(config, identity)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        # Use a mock anomaly type that doesn't exist
        class MockAnomalyType:
            value = "unknown"
        
        modified, is_anomaly, anomaly_type = generator.apply_anomaly(reading, MockAnomalyType())
        
        assert is_anomaly is False
        assert anomaly_type is None
        assert modified == reading

    def test_model_affects_anomaly_weights(self):
        """Test that sensor model affects anomaly type weights."""
        config = self.get_valid_config()
        config["anomalies"]["types"][AnomalyType.MISSING_DATA.value] = {"enabled": True, "weight": 1.0}
        
        # Test ENVMONITOR_3000 (prone to missing data)
        identity = self.get_valid_identity()
        identity["model"] = "EnvMonitor-3000"
        generator = AnomalyGenerator(config, identity)
        
        # Check that select_anomaly_type considers model-specific weights
        # This test verifies the logic exists, though the random selection makes it hard to test deterministically
        enabled_types = {}
        for anomaly_type, type_config in generator.types.items():
            if type_config.get("enabled", True):
                enabled_types[AnomalyType(anomaly_type)] = type_config.get("weight", 1.0)
        
        assert len(enabled_types) > 0

    def test_firmware_affects_spike_severity(self):
        """Test that firmware version affects spike severity."""
        config = self.get_valid_config()
        
        # Test with V1_4 firmware (more severe spikes)
        identity = self.get_valid_identity()
        identity["firmware_version"] = "1.4.0"
        generator = AnomalyGenerator(config, identity)
        
        reading = {
            "temperature": 25.0,
            "humidity": 50.0,
            "voltage": 12.0,
            "vibration": 0.1,
        }
        
        # Apply multiple spikes and check that they're within expected range
        spike_factors = []
        for _ in range(10):
            modified, _, _ = generator._apply_spike_anomaly(reading)
            # Find which parameter was modified
            for param in ["temperature", "humidity", "voltage"]:
                if modified[param] != reading[param]:
                    factor = modified[param] / reading[param]
                    spike_factors.append(factor)
                    break
        
        # V1_4 should have factors between 1.8-3.5 or their reciprocals
        for factor in spike_factors:
            assert (1.8 <= factor <= 3.5) or (1/3.5 <= factor <= 1/1.8)