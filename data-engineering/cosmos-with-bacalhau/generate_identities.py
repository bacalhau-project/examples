#!/usr/bin/env python3
import json
import os
import random
import string

# Define possible values for sensor attributes
locations = ["Factory A", "Factory B", "Factory C", "Warehouse D", "Office E"]
areas = ["Line 1", "Line 2", "Assembly 3", "Packaging 4", "Storage 5"]
types = ["temperature_vibration", "pressure_temp", "humidity_temp", "voltage_current"]
manufacturers = ["SensorTech", "DataSense", "ThermoMetrics", "VibrationPlus"]
models = ["TempVibe-1000", "TempVibe-2000", "PressureSense-X", "HumidityPro"]
firmware_versions = ["1.0.0", "1.2.3", "2.0.1", "2.1.5"]

# Number of identities to generate
num_identities = 50
os.makedirs("identities", exist_ok=True)

for i in range(num_identities):
    # Generate unique sensor ID
    sensor_id = f"SENSOR_{i:03d}_{random.randint(1000, 9999)}"

    # Randomly select attributes
    location = f"{random.choice(locations)} - {random.choice(areas)}"
    sensor_type = random.choice(types)
    manufacturer = random.choice(manufacturers)
    model = random.choice(models)
    firmware = random.choice(firmware_versions)

    # Create identity object
    identity = {
        "id": sensor_id,
        "type": sensor_type,
        "location": location,
        "manufacturer": manufacturer,
        "model": model,
        "firmware_version": firmware,
    }

    # Write to file
    with open(f"identities/identity_{i:03d}.json", "w") as f:
        json.dump(identity, f, indent=2)

    print(f"Generated identity for sensor {sensor_id}")
