#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pyyaml",
#     "pydantic",
# ]
# ///

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import IdentityData, LocationData, load_identity, process_identity_and_location


class TestIdentityFormats:
    """Test both legacy and new identity formats."""
    
    def test_legacy_identity_format(self):
        """Test that legacy flat identity format is correctly parsed."""
        legacy_identity = {
            "id": "SENSOR_NY_123456",
            "location": "New York",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York",
            "manufacturer": "SensorTech",
            "model": "TempSensor Pro",
            "firmware_version": "1.2.0"
        }
        
        # Validate with Pydantic model
        identity_model = IdentityData(**legacy_identity)
        
        # Check that sensor_id is set from id field
        assert identity_model.sensor_id == "SENSOR_NY_123456"
        
        # Check that location is converted to nested structure
        assert isinstance(identity_model.location, LocationData)
        assert identity_model.location.city == "New York"
        assert identity_model.location.coordinates["latitude"] == 40.7128
        assert identity_model.location.coordinates["longitude"] == -74.0060
        assert identity_model.location.timezone == "America/New_York"
        
        # Check device info is created from flat fields
        assert identity_model.device_info.manufacturer == "SensorTech"
        assert identity_model.device_info.model == "TempSensor Pro"
        assert identity_model.device_info.firmware_version == "1.2.0"
    
    def test_new_identity_format(self):
        """Test that new nested identity format is correctly parsed."""
        new_identity = {
            "sensor_id": "SENSOR_CO_DEN_8548",
            "location": {
                "city": "Denver",
                "state": "CO",
                "coordinates": {
                    "latitude": 39.733741,
                    "longitude": -104.990653
                },
                "timezone": "America/Denver",
                "address": "Denver, CO, USA"
            },
            "device_info": {
                "manufacturer": "DataLogger",
                "model": "AirData-Plus",
                "firmware_version": "DLG_v3.15.21",
                "serial_number": "DataLogger-578463",
                "manufacture_date": "2025-03-24"
            },
            "deployment": {
                "deployment_type": "mobile_unit",
                "installation_date": "2025-03-24",
                "height_meters": 8.3,
                "orientation_degrees": 183
            },
            "metadata": {
                "instance_id": "i-04d485582534851c9",
                "identity_generation_timestamp": "2025-07-15T15:42:09.444892",
                "generation_seed": 200030087626269561895877314454571578463,
                "sensor_type": "environmental_monitoring"
            }
        }
        
        # Validate with Pydantic model
        identity_model = IdentityData(**new_identity)
        
        # Check all fields are preserved
        assert identity_model.sensor_id == "SENSOR_CO_DEN_8548"
        assert identity_model.location.city == "Denver"
        assert identity_model.location.state == "CO"
        assert identity_model.location.coordinates["latitude"] == 39.733741
        assert identity_model.location.coordinates["longitude"] == -104.990653
        assert identity_model.location.timezone == "America/Denver"
        assert identity_model.location.address == "Denver, CO, USA"
        
        assert identity_model.device_info.manufacturer == "DataLogger"
        assert identity_model.device_info.model == "AirData-Plus"
        assert identity_model.device_info.firmware_version == "DLG_v3.15.21"
        assert identity_model.device_info.serial_number == "DataLogger-578463"
        assert identity_model.device_info.manufacture_date == "2025-03-24"
        
        assert identity_model.deployment.deployment_type == "mobile_unit"
        assert identity_model.deployment.installation_date == "2025-03-24"
        assert identity_model.deployment.height_meters == 8.3
        assert identity_model.deployment.orientation_degrees == 183
        
        assert identity_model.metadata.instance_id == "i-04d485582534851c9"
        assert identity_model.metadata.sensor_type == "environmental_monitoring"
    
    def test_process_identity_location_legacy(self):
        """Test process_identity_and_location with legacy format."""
        legacy_identity = {
            "id": "SENSOR_NY_123456",
            "location": "New York",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York",
            "manufacturer": "SensorTech",
            "model": "TempSensor Pro",
            "firmware_version": "1.2.0"
        }
        
        app_config = {
            "random_location": {
                "enabled": False
            }
        }
        
        processed = process_identity_and_location(legacy_identity, app_config)
        
        # Check both sensor_id and id are set
        assert processed["sensor_id"] == "SENSOR_NY_123456"
        assert processed["id"] == "SENSOR_NY_123456"
        
        # Check flat coordinates are preserved
        assert processed["latitude"] == 40.7128
        assert processed["longitude"] == -74.0060
    
    def test_process_identity_location_new(self):
        """Test process_identity_and_location with new format."""
        new_identity = {
            "sensor_id": "SENSOR_CO_DEN_8548",
            "location": {
                "city": "Denver",
                "state": "CO",
                "coordinates": {
                    "latitude": 39.733741,
                    "longitude": -104.990653
                },
                "timezone": "America/Denver",
                "address": "Denver, CO, USA"
            },
            "device_info": {
                "manufacturer": "DataLogger",
                "model": "AirData-Plus",
                "firmware_version": "DLG_v3.15.21"
            }
        }
        
        app_config = {
            "random_location": {
                "enabled": False
            }
        }
        
        processed = process_identity_and_location(new_identity, app_config)
        
        # Check both sensor_id and id are set
        assert processed["sensor_id"] == "SENSOR_CO_DEN_8548"
        assert processed["id"] == "SENSOR_CO_DEN_8548"
        
        # Check flat coordinates are set for backward compatibility
        assert processed["latitude"] == 39.733741
        assert processed["longitude"] == -104.990653
    
    def test_mixed_identity_format(self):
        """Test identity with mixed old and new fields."""
        mixed_identity = {
            "sensor_id": "SENSOR_TEST_001",
            "location": {
                "city": "Boston",
                "coordinates": {
                    "latitude": 42.3601,
                    "longitude": -71.0589
                }
            },
            # Legacy fields mixed in
            "manufacturer": "SensorTech",
            "model": "TempSensor Pro",
            "firmware_version": "1.2.0"
        }
        
        # Should parse without errors
        identity_model = IdentityData(**mixed_identity)
        
        assert identity_model.sensor_id == "SENSOR_TEST_001"
        assert identity_model.location.city == "Boston"
        assert identity_model.device_info.manufacturer == "SensorTech"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])