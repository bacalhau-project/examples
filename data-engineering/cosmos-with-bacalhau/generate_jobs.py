#!/usr/bin/env python3
import json
import random
import string
import subprocess

# Define possible values for sensor attributes
locations = ["Factory A", "Factory B", "Factory C", "Warehouse D", "Office E"]
areas = ["Line 1", "Line 2", "Assembly 3", "Packaging 4", "Storage 5"]
types = ["temperature_vibration", "pressure_temp", "humidity_temp", "voltage_current"]
manufacturers = ["SensorTech", "DataSense", "ThermoMetrics", "VibrationPlus"]
models = ["TempVibe-1000", "TempVibe-2000", "PressureSense-X", "HumidityPro"]
firmware_versions = ["1.0.0", "1.2.3", "2.0.1", "2.1.5"]

# Number of jobs to generate
num_jobs = 50

for i in range(num_jobs):
    # Generate unique sensor ID
    sensor_id = f"SENSOR_{i:03d}_{random.randint(1000, 9999)}"

    # Randomly select attributes
    location = f"{random.choice(locations)} - {random.choice(areas)}"
    sensor_type = random.choice(types)
    manufacturer = random.choice(manufacturers)
    model = random.choice(models)
    firmware = random.choice(firmware_versions)

    # Create Bacalhau job command
    cmd = [
        "bacalhau",
        "docker",
        "run",
        "--env",
        f"SENSOR_ID={sensor_id}",
        "--env",
        f"SENSOR_LOCATION={location}",
        "--env",
        f"SENSOR_TYPE={sensor_type}",
        "--env",
        f"SENSOR_MANUFACTURER={manufacturer}",
        "--env",
        f"SENSOR_MODEL={model}",
        "--env",
        f"SENSOR_FIRMWARE={firmware}",
        "your-docker-image",
    ]

    # Submit job
    print(f"Submitting job for sensor {sensor_id}...")
    subprocess.run(cmd)
