import pytest
from src.simulator import SensorSimulator
from src.anomaly import AnomalyGenerator


class TestSemVerValidation:
    """Test semantic version validation for firmware versions."""
    
    def test_valid_semver_formats(self):
        """Test various valid SemVer formats."""
        # Create a dummy simulator instance for testing
        simulator = SensorSimulator.__new__(SensorSimulator)
        
        valid_versions = [
            "1.0.0",
            "0.0.0",
            "1.2.3",
            "10.20.30",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-0.3.7",
            "1.0.0-x.7.z.92",
            "1.0.0+20130313144700",
            "1.0.0-beta+exp.sha.5114f85",
            "1.0.0+21AF26D3----117B344092BD",
            "2.1.0",
            "2.0.0",
            "1.5.0",
            "1.4.0",
            "3.15.21",  # Like DLG_v3.15.21 but without prefix
        ]
        
        for version in valid_versions:
            assert simulator._is_valid_semver(version), f"Version {version} should be valid"
    
    def test_invalid_semver_formats(self):
        """Test various invalid SemVer formats."""
        simulator = SensorSimulator.__new__(SensorSimulator)
        
        invalid_versions = [
            "1",
            "1.2",
            "1.2.3.4",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2-beta",
            "-1.2.3",
            "1.2.3-",
            "1.2.3-+",
            "1.2.3-+123",
            "1.2.3-",
            "DLG_v3.15.21",  # Prefix not allowed
            "v1.2.3",  # v prefix not allowed
            "1.4",  # Missing patch version
            "1.5",  # Missing patch version
            "2.0",  # Missing patch version
            "2.1",  # Missing patch version
        ]
        
        for version in invalid_versions:
            assert not simulator._is_valid_semver(version), f"Version {version} should be invalid"
    
    def test_anomaly_generator_semver_validation(self):
        """Test that AnomalyGenerator also validates SemVer correctly."""
        generator = AnomalyGenerator.__new__(AnomalyGenerator)
        
        # Test valid versions
        assert generator._is_valid_semver("1.0.0")
        assert generator._is_valid_semver("2.1.3-beta")
        
        # Test invalid versions
        assert not generator._is_valid_semver("1.4")
        assert not generator._is_valid_semver("v1.0.0")
    
    def test_model_accepts_any_string(self):
        """Test that model field accepts any string value."""
        config = {
            "anomalies": {
                "enabled": True,
                "probability": 0.1,
                "types": {}
            }
        }
        
        # Test various model names - all should be accepted
        model_names = [
            "EnvMonitor-3000",
            "EnvMonitor-4000",
            "EnvMonitor-5000",
            "TempSensor Pro",
            "WeatherStation Pro",
            "AirData-Plus",
            "CustomModel-X1",
            "My Custom Model 123",
            "Model_With_Underscores",
            "Model-With-Dashes",
            "Model.With.Dots",
            "ModelWithNumbers123",
            "UPPERCASE_MODEL",
            "lowercase_model",
            "MixedCase_Model-123.v2",
        ]
        
        for model_name in model_names:
            identity = {
                "id": "TEST001",
                "location": "Test Location",
                "latitude": 40.0,
                "longitude": -74.0,
                "firmware_version": "1.0.0",  # Valid SemVer
                "model": model_name,
                "manufacturer": "SensorTech",
            }
            
            # Should not raise any exception
            generator = AnomalyGenerator(config, identity)
            assert generator.model == model_name