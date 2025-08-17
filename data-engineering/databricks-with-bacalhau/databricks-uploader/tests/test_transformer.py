#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0.0",
# ]
# ///

import json
from sensor_data_models import WindTurbineSensorData, generate_anomaly_examples

# Test validation
print("Testing Wind Turbine Data Validation")
print("="*50)

# Test valid data
valid_data = {
    "timestamp": "2024-01-15T10:30:00Z",
    "turbine_id": "WT-0042",
    "site_id": "SITE-TEX",
    "temperature": 15.5,
    "humidity": 65.0,
    "pressure": 1013.25,
    "wind_speed": 12.5,
    "wind_direction": 225.0,
    "rotation_speed": 1200.0,
    "blade_pitch": 15.0,
    "generator_temp": 55.0,
    "power_output": 2500.0,
    "vibration_x": 2.5,
    "vibration_y": 3.1,
    "vibration_z": 1.8,
}

try:
    WindTurbineSensorData(**valid_data)
    print("✓ Valid data passed validation")
except Exception as e:
    print(f"✗ Valid data failed: {e}")

# Test anomaly examples
print("\nTesting Anomaly Detection:")
anomalies = generate_anomaly_examples()

for i, anomaly_data in enumerate(anomalies[:3], 1):
    anomaly_type = anomaly_data.pop("_anomaly")
    try:
        WindTurbineSensorData(**anomaly_data)
        print(f"✗ Anomaly {i} ({anomaly_type}): Should have failed")
    except Exception as e:
        print(f"✓ Anomaly {i} ({anomaly_type}): Correctly caught")
        print(f"  Error: {str(e)[:100]}...")
