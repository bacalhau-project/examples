#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0.0",
# ]
# ///

from sensor_data_models import WindTurbineSensorData, validate_sensor_data, generate_anomaly_examples

print("Testing Parallel Upload Validation Logic")
print("="*50)

# Test data that would be validated
test_records = [
    # Valid record
    {
        "timestamp": "2024-01-15T10:30:00Z",
        "turbine_id": "WT-0001",
        "site_id": "SITE-TEX",
        "temperature": 20.0,
        "humidity": 60.0,
        "pressure": 1013.0,
        "wind_speed": 15.0,
        "wind_direction": 180.0,
        "rotation_speed": 1500.0,
        "blade_pitch": 20.0,
        "generator_temp": 65.0,
        "power_output": 3000.0,
        "vibration_x": 2.0,
        "vibration_y": 2.5,
        "vibration_z": 1.5,
    },
    # Invalid: rotation without wind
    {
        "timestamp": "2024-01-15T10:31:00Z",
        "turbine_id": "WT-0002",
        "site_id": "SITE-TEX",
        "temperature": 20.0,
        "humidity": 60.0,
        "pressure": 1013.0,
        "wind_speed": 1.0,  # Too low for rotation
        "wind_direction": 180.0,
        "rotation_speed": 1000.0,  # Should be ~0
        "blade_pitch": 20.0,
        "generator_temp": 65.0,
        "power_output": 500.0,
        "vibration_x": 2.0,
        "vibration_y": 2.5,
        "vibration_z": 1.5,
    },
    # Invalid: excessive vibration
    {
        "timestamp": "2024-01-15T10:32:00Z",
        "turbine_id": "WT-0003",
        "site_id": "SITE-TEX",
        "temperature": 20.0,
        "humidity": 60.0,
        "pressure": 1013.0,
        "wind_speed": 20.0,
        "wind_direction": 180.0,
        "rotation_speed": 2000.0,
        "blade_pitch": 25.0,
        "generator_temp": 75.0,
        "power_output": 4000.0,
        "vibration_x": 60.0,  # Critical level
        "vibration_y": 55.0,
        "vibration_z": 52.0,
    }
]

valid_count = 0
invalid_count = 0

for i, record in enumerate(test_records, 1):
    is_valid, error = validate_sensor_data(record)
    if is_valid:
        print(f"Record {i}: ✅ Valid")
        valid_count += 1
    else:
        print(f"Record {i}: ⚠️  Invalid - {error[:80]}...")
        invalid_count += 1

print(f"\nSummary:")
print(f"  Valid records: {valid_count} → would go to validated bucket")
print(f"  Invalid records: {invalid_count} → would go to anomalies bucket")
