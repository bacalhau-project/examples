# Industrial Sensor Simulator

This project simulates an industrial temperature and vibration sensor commonly used in manufacturing equipment. It generates realistic sensor data and stores it in a SQLite database, including both normal operating patterns and various types of anomalies.

## Features

- Generates realistic sensor data (temperature, vibration, voltage)
- Configurable via YAML file and node-specific JSON identity file
- Simulates various types of anomalies:
  - Spike anomalies: Sudden, short-lived extreme values
  - Trend anomalies: Gradual shifts away from normal operation
  - Pattern anomalies: Changes in the normal pattern of readings
  - Missing data: Simulated sensor outages
  - Noise anomalies: Increased random variation in readings
- Firmware-dependent behavior (different versions exhibit different anomaly patterns)
- Model and manufacturer-specific characteristics
- Location-based environmental patterns
- Stores data in a lightweight SQLite database
- Runs as a Docker container

## Use Case

This simulator is designed to replicate a scenario where a company might have tens of thousands of sensors deployed across its infrastructure (factories, office buildings, transportation vehicles, etc.). It can be used for:

- Testing data processing pipelines
- Developing anomaly detection algorithms
- Training machine learning models
- Demonstrating monitoring dashboards
- Benchmarking database performance
- Simulating firmware upgrades and their effects

## Getting Started

### Prerequisites

- Docker
- Python 3.8+ (if running without Docker)

### Configuration

The simulator uses two configuration files:

1. **Global Configuration** (`config.yaml`): Contains general simulation parameters
2. **Node Identity** (`node_identity.json`): Contains sensor-specific identity and characteristics

#### Example config.yaml
```yaml
simulation:
  readings_per_second: 1
  run_time_seconds: 3600  # 1 hour

normal_parameters:
  temperature:
    mean: 65.0  # Celsius
    std_dev: 2.0
    min: 50.0
    max: 80.0
  vibration:
    mean: 2.5  # mm/s²
    std_dev: 0.5
    min: 0.1
    max: 10.0
  voltage:
    mean: 12.0  # Volts
    std_dev: 0.1
    min: 11.5
    max: 12.5

anomalies:
  enabled: true
  probability: 0.05  # 5% chance of anomaly per reading

database:
  path: "sensor_data.db"

logging:
  level: "INFO"
  file: "sensor_simulator.log"
```

#### Example node_identity.json
```json
{
  "id": "SENSOR_001",
  "type": "temperature_vibration",
  "location": "Factory A - Line 1",
  "manufacturer": "SensorTech",
  "model": "TempVibe-2000",
  "firmware_version": "1.3"
}
```

### Running with Docker

1. Build the Docker image:
   ```
   docker build -t sensor-simulator .
   ```

2. Run the container with your configuration:
   ```
   docker run -v $(pwd)/config.yaml:/app/config.yaml \
              -v $(pwd)/node_identity.json:/app/node_identity.json \
              -v $(pwd)/data:/app/data \
              sensor-simulator
   ```

### Running without Docker

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the simulator:
   ```
   python main.py --config config.yaml --identity node_identity.json
   ```

## Firmware-Dependent Behavior

The simulator demonstrates how firmware versions can affect sensor behavior:

### Firmware 1.3
- Higher probability of temperature spikes
- Occasional voltage fluctuations
- Increased noise in vibration readings

### Firmware 1.4
- Reduced temperature spikes
- Stabilized voltage readings
- Improved vibration measurement accuracy

This allows you to simulate firmware upgrades and observe how they improve sensor reliability.

## Other Scenario-Based Behaviors

### Model-Dependent Issues
- TempVibe-1000: Prone to missing data anomalies
- TempVibe-2000: Occasional pattern anomalies
- TempVibe-3000: Rare but severe spike anomalies

### Location-Based Patterns
- Factory locations: Higher average temperatures during work hours
- Warehouse locations: More stable temperature, higher vibration variance
- Outdoor locations: Greater temperature fluctuations based on time of day

### Manufacturer Quality Differences
- SensorTech: Generally reliable with occasional issues
- DataSense: Lower anomaly rate but more severe when they occur
- VibrationPlus: Higher baseline vibration readings with more noise

## Demo Script

The following script generates multiple sensor configurations with different characteristics and runs the simulator for each:

```bash
#!/bin/bash
# generate_sensors.sh - Create multiple sensor configurations and run simulations

# Create output directories
mkdir -p data
mkdir -p identities

# Generate sensor identities
echo "Generating sensor identities..."

# Factory sensors with older firmware
for i in {1..5}; do
  cat > identities/factory_old_$i.json << EOF
{
  "id": "FACTORY_${i}_OLD",
  "type": "temperature_vibration",
  "location": "Factory A - Line ${i}",
  "manufacturer": "SensorTech",
  "model": "TempVibe-2000",
  "firmware_version": "1.3"
}
EOF
done

# Factory sensors with newer firmware
for i in {1..5}; do
  cat > identities/factory_new_$i.json << EOF
{
  "id": "FACTORY_${i}_NEW",
  "type": "temperature_vibration",
  "location": "Factory A - Line ${i}",
  "manufacturer": "SensorTech",
  "model": "TempVibe-2000",
  "firmware_version": "1.4"
}
EOF
done

# Warehouse sensors with different models
for i in {1..3}; do
  cat > identities/warehouse_$i.json << EOF
{
  "id": "WAREHOUSE_${i}",
  "type": "temperature_vibration",
  "location": "Warehouse B - Section ${i}",
  "manufacturer": "DataSense",
  "model": "TempVibe-${i}000",
  "firmware_version": "1.3"
}
EOF
done

# Outdoor sensors
for i in {1..2}; do
  cat > identities/outdoor_$i.json << EOF
{
  "id": "OUTDOOR_${i}",
  "type": "temperature_vibration",
  "location": "Outdoor - Area ${i}",
  "manufacturer": "VibrationPlus",
  "model": "TempVibe-3000",
  "firmware_version": "1.4"
}
EOF
done

echo "Generated $(ls identities | wc -l) sensor identities"

# Run simulations
echo "Running simulations..."

# Function to run a simulation
run_simulation() {
  identity_file=$1
  sensor_id=$(grep -o '"id": "[^"]*' $identity_file | cut -d'"' -f4)
  echo "Starting simulation for $sensor_id..."
  
  # Run for 10 minutes (600 seconds)
  docker run -d \
    -v $(pwd)/config.yaml:/app/config.yaml \
    -v $(pwd)/$identity_file:/app/node_identity.json \
    -v $(pwd)/data:/app/data \
    --name "sensor_${sensor_id}" \
    sensor-simulator
}

# Run simulations for each identity
for identity in identities/*.json; do
  run_simulation $identity
done

echo "All simulations started. Data will be stored in the 'data' directory."
echo "To view logs for a specific sensor, use: docker logs sensor_SENSOR_ID"
```

## Analyzing the Data

After running the simulations, you can analyze the data to observe:

1. How firmware 1.3 sensors show more anomalies than firmware 1.4 sensors
2. How different models exhibit different types of anomalies
3. How location affects sensor readings
4. How manufacturer affects overall reliability

Example SQLite query to compare anomaly rates by firmware version:

```sql
SELECT 
  firmware_version,
  COUNT(*) as total_readings,
  SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) as anomaly_count,
  ROUND(100.0 * SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as anomaly_percentage
FROM sensor_readings
GROUP BY firmware_version
ORDER BY anomaly_percentage DESC;
```

## Database Schema

The SQLite database includes the following fields:

- `id` (PRIMARY KEY): Unique identifier for each reading
- `timestamp`: When the reading was taken
- `sensor_id`: Identifier for the simulated sensor
- `temperature`: Temperature reading in Celsius
- `vibration`: Vibration reading in mm/s²
- `voltage`: Power supply voltage
- `status_code`: Sensor status code
- `anomaly_flag`: Boolean flag indicating if this is an anomaly
- `anomaly_type`: Type of anomaly (if anomaly_flag is true)
- `firmware_version`: Version of sensor firmware
- `model`: Sensor model
- `manufacturer`: Sensor manufacturer
- `location`: Sensor location

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
