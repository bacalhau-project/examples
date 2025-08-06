#!/bin/bash

# Start a local sensor log generator (without Docker)
# Run from the main databricks-with-bacalhau directory

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Local Sensor Data Generator${NC}"

# Ensure we're in the right directory
if [ ! -f "databricks-uploader-config.yaml" ]; then
    echo -e "${RED}Error: Must run from databricks-with-bacalhau directory${NC}"
    exit 1
fi

# Create necessary directories
mkdir -p sample-sensor/data
mkdir -p sample-sensor/config

# Simple Python sensor generator
echo -e "${YELLOW}Using built-in sensor generator...${NC}"

# Create the sensor generator script
cat > /tmp/simple_sensor_generator.py << 'PYTHON_EOF'
#!/usr/bin/env python3
import sqlite3
import random
import time
import json
from datetime import datetime, timezone
import os
import signal
import sys

# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print('\nStopping sensor generator...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Configuration
DB_PATH = "sample-sensor/data/sensor_data.db"
INTERVAL = 5  # seconds
BATCH_SIZE = 10

# Ensure database directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Create database and table
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
    CREATE TABLE IF NOT EXISTS sensor_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        sensor_type TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        location TEXT NOT NULL,
        quality TEXT DEFAULT 'good',
        metadata TEXT
    )
""")
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp 
    ON sensor_readings(timestamp)
""")
conn.commit()

print(f"Simple sensor generator started. Generating {BATCH_SIZE} readings every {INTERVAL} seconds...")
print("Press Ctrl+C to stop")

# Sensor configurations
sensors = [
    {"id": "SENS001", "type": "temperature", "unit": "celsius", "min": 15, "max": 30},
    {"id": "SENS002", "type": "humidity", "unit": "percent", "min": 30, "max": 70},
    {"id": "SENS003", "type": "pressure", "unit": "hPa", "min": 1000, "max": 1020},
]

locations = ["Building A", "Building B", "Building C", "Outdoor"]

while True:
    batch = []
    timestamp = datetime.now(timezone.utc).isoformat()
    
    for _ in range(BATCH_SIZE):
        sensor = random.choice(sensors)
        value = round(random.uniform(sensor["min"], sensor["max"]), 2)
        location = random.choice(locations)
        quality = "good" if random.random() > 0.05 else "degraded"
        
        metadata = json.dumps({
            "manufacturer": "TestSensor Inc",
            "firmware": "v1.0.0",
            "battery": round(random.uniform(80, 100), 1)
        })
        
        batch.append((
            sensor["id"],
            sensor["type"],
            value,
            sensor["unit"],
            timestamp,
            location,
            quality,
            metadata
        ))
    
    # Insert batch
    conn.executemany("""
        INSERT INTO sensor_readings 
        (sensor_id, sensor_type, value, unit, timestamp, location, quality, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    conn.commit()
    
    print(f"Generated {len(batch)} sensor readings at {timestamp}")
    
    time.sleep(INTERVAL)
PYTHON_EOF

echo -e "${GREEN}Starting simple sensor generator...${NC}"
echo "Database: sample-sensor/data/sensor_data.db"
echo "Press Ctrl+C to stop"
echo ""

python3 /tmp/simple_sensor_generator.py