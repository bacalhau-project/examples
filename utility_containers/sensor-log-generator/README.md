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
- Runs as a Docker container with uv for dependency management
- **Dynamic configuration reloading**: Changes to configuration files are automatically detected and applied
- **Database sync support**: Includes a `synced` flag for integration with external data collection systems
- **Robust error handling**: Automatic retries for database operations and graceful degradation on failure
- **Comprehensive logging**: Detailed logs for troubleshooting and monitoring

## Use Case

This simulator is designed to replicate a scenario where a company might have tens of thousands of sensors deployed across its infrastructure (factories, office buildings, transportation vehicles, etc.). It can be used for:

- Testing data processing pipelines
- Developing anomaly detection algorithms
- Training machine learning models
- Demonstrating monitoring dashboards
- Benchmarking database performance
- Simulating firmware upgrades and their effects
- Testing distributed data collection systems like Bacalhau

## Getting Started

### Prerequisites

- Docker
- Python 3.11+ (if running without Docker)
- SQLite3 (for querying the database)

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
  types:
    spike:
      enabled: true
      weight: 0.4
    trend:
      enabled: true
      weight: 0.2
      duration_seconds: 300  # 5 minutes
    pattern:
      enabled: true
      weight: 0.1
      duration_seconds: 600  # 10 minutes
    missing_data:
      enabled: true
      weight: 0.1
      duration_seconds: 30  # 30 seconds
    noise:
      enabled: true
      weight: 0.2
      duration_seconds: 180  # 3 minutes

database:
  path: "/app/data/sensor_data.db"

logging:
  level: "INFO"
  file: "/app/data/sensor_simulator.log"
  console_output: true

# Configuration for dynamic reloading
config_reload:
  enabled: true
  check_interval_seconds: 60
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
   docker run -v $(pwd)/data:/app/data \
              -e SENSOR_ID=CUSTOM001 \
              -e SENSOR_LOCATION="Custom Location" \
              sensor-simulator
   ```

3. Test the container with the provided script:
   ```
   ./test_container.sh
   ```
   This script:
   - Builds the Docker container
   - Clears and recreates the data directory
   - Runs the container for 30 seconds
   - Verifies the database was created and shows statistics
   - Displays sample data from the database

### Running without Docker

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the simulator:
   ```
   python main.py --config config.yaml --identity node_identity.json
   ```

## Dynamic Configuration Reloading

The simulator now supports dynamic configuration reloading, which means you can change the configuration files while the simulator is running, and the changes will be automatically detected and applied.

### How It Works

1. The simulator periodically checks if the configuration files have been modified
2. If changes are detected, the new configuration is loaded and applied to the running simulation
3. Most configuration changes take effect immediately, including:
   - Sensor identity (ID, location, manufacturer, model, firmware version)
   - Normal parameter distributions (mean, standard deviation, min/max)
   - Anomaly probabilities and types
   - Readings per second

### Configuration

You can control the dynamic reloading behavior in the `config.yaml` file:

```yaml
config_reload:
  enabled: true                # Enable or disable dynamic reloading
  check_interval_seconds: 60   # How often to check for changes (in seconds)
```

### Limitations

Some configuration changes cannot be applied to a running simulation:
- The `run_time_seconds` parameter is only applied when the simulation starts
- Database path changes require a restart to take effect

## Error Handling and Reliability

The simulator includes robust error handling to ensure reliable operation even in the face of failures.

### Database Retry Logic

Database operations automatically retry on failure:

- **Automatic Retries**: Failed database operations are automatically retried up to 3 times
- **Exponential Backoff**: Each retry waits longer to allow temporary issues to resolve
- **Fallback Mechanisms**: If the database file cannot be accessed, an in-memory database is used as a fallback
- **Transaction Safety**: All database operations use proper transaction handling with commit/rollback

### Graceful Degradation

The simulator can continue operating even when parts of the system fail:

- **Default Values**: If parameter generation fails, sensible defaults are used
- **Error Limits**: The simulator stops after too many consecutive errors to prevent data corruption
- **Detailed Logging**: All errors are logged with context for easier troubleshooting
- **Health Checks**: The simulator includes methods to check the health of its components

### Error Reporting

The simulator provides detailed error reporting:

- **Success Rate**: At the end of a simulation run, a summary shows the success rate of readings
- **Error Counts**: The number of errors encountered is tracked and reported
- **Error Classification**: Errors are classified by type (database, configuration, etc.)
- **Status API**: The simulator provides a status API that includes error information

## Database Sync Support

The simulator stores all readings in a SQLite database with a `synced` flag that can be used by external data collection systems to track which readings have been synchronized to a central database.

### Database Schema

The SQLite database includes the following fields:

- `id` (PRIMARY KEY): Unique identifier for each reading
- `timestamp`: When the reading was taken
- `sensor_id`: Identifier for the simulated sensor
- `temperature`: Temperature reading in Celsius
- `vibration`: Vibration reading in mm/s²
- `voltage`: Power supply voltage
- `status_code`: Sensor status code (0=normal, 1=anomaly)
- `anomaly_flag`: Boolean flag indicating if this is an anomaly
- `anomaly_type`: Type of anomaly (if anomaly_flag is true)
- `firmware_version`: Version of sensor firmware
- `model`: Sensor model
- `manufacturer`: Sensor manufacturer
- `location`: Sensor location
- `synced`: Boolean flag indicating if this reading has been synced to a central database (0=not synced, 1=synced)

### Using the Sync Functionality

External data collection systems can use the `synced` flag to track which readings have been synchronized:

1. Query for unsynced readings:
   ```sql
   SELECT * FROM sensor_readings WHERE synced = 0 ORDER BY timestamp ASC LIMIT 100
   ```

2. After successfully syncing the readings, mark them as synced:
   ```sql
   UPDATE sensor_readings SET synced = 1 WHERE id IN (1, 2, 3, ...)
   ```

3. Check sync statistics:
   ```sql
   SELECT 
       COUNT(*) as total_readings,
       SUM(CASE WHEN synced = 1 THEN 1 ELSE 0 END) as synced_readings,
       SUM(CASE WHEN synced = 0 THEN 1 ELSE 0 END) as unsynced_readings
   FROM sensor_readings
   ```

## How Anomalies Are Simulated

The simulator uses a sophisticated approach to generate realistic anomalies:

### 1. Anomaly Probability

The base probability of an anomaly occurring is set in the configuration (default: 5% per reading). This probability is then adjusted based on:

- **Firmware Version**: 
  - Firmware 1.3: 50% higher anomaly probability (7.5%)
  - Firmware 1.4: 30% lower anomaly probability (3.5%)

- **Manufacturer**:
  - SensorTech: Standard probability
  - DataSense: 20% lower probability but more severe anomalies
  - VibrationPlus: 20% higher probability

### 2. Anomaly Type Selection

When an anomaly occurs, the type is selected based on weighted probabilities that are further adjusted by:

- **Model Type**:
  - TempVibe-1000: 2x more likely to have missing data anomalies
  - TempVibe-2000: 1.5x more likely to have pattern anomalies
  - TempVibe-3000: 1.5x more likely to have spike anomalies

### 3. Anomaly Implementation

Each anomaly type is implemented differently:

#### Spike Anomalies
- Randomly selects a parameter (temperature, vibration, or voltage)
- For firmware 1.3, temperature is selected 60% of the time
- Multiplies the value by a factor between 1.5-3.0 (or divides by this factor for negative spikes)
- Firmware 1.3 has more severe spikes (factor 1.8-3.5)

#### Trend Anomalies
- Gradually increases or decreases a parameter over time
- Can reach up to 50% increase/decrease by the end of the anomaly duration
- Progress is calculated based on elapsed time vs. configured duration

#### Pattern Anomalies
- Applies sinusoidal patterns to temperature and vibration
- Creates opposite patterns between parameters (when one goes up, the other goes down)
- Amplitude is 20% of the normal value

#### Missing Data Anomalies
- Simply returns None instead of a reading
- Simulates complete sensor outage or communication failure

#### Noise Anomalies
- Adds random noise to all parameters
- Firmware 1.3 has 15% noise factor vs. 10% for other versions
- VibrationPlus sensors have 50% more vibration noise

### 4. Daily Patterns

Even normal readings include daily patterns:
- Temperature follows a sinusoidal pattern based on time of day
- Peak at 3 PM, trough at 3 AM
- Amplitude is one standard deviation

## Firmware-Dependent Behavior

The simulator demonstrates how firmware versions can affect sensor behavior:

### Firmware 1.3
- 50% higher probability of anomalies overall
- 60% of anomalies affect temperature (vs. equal distribution in other versions)
- Temperature spikes are more severe (up to 3.5x normal vs. 3.0x)
- 15% noise factor (vs. 10% in other versions)
- More voltage fluctuations

### Firmware 1.4
- 30% lower probability of anomalies
- More balanced distribution of anomaly types
- Less severe spikes (maximum 3.0x normal)
- Lower noise factor (10%)
- More stable voltage readings

This allows you to simulate firmware upgrades and observe how they improve sensor reliability.

## Other Scenario-Based Behaviors

### Model-Dependent Issues
- TempVibe-1000: 2x more likely to have missing data anomalies
- TempVibe-2000: 1.5x more likely to have pattern anomalies
- TempVibe-3000: 1.5x more likely to have spike anomalies

### Location-Based Patterns
- Factory locations: Higher average temperatures during work hours
- Warehouse locations: More stable temperature, higher vibration variance
- Outdoor locations: Greater temperature fluctuations based on time of day

### Manufacturer Quality Differences
- SensorTech: Generally reliable with standard anomaly rates
- DataSense: 20% fewer anomalies but more severe when they occur
- VibrationPlus: 20% more anomalies and 50% more vibration noise

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

Example query to analyze anomaly types by model:

```sql
SELECT 
  model,
  anomaly_type,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY model), 2) as percentage
FROM sensor_readings
WHERE anomaly_flag = 1
GROUP BY model, anomaly_type
ORDER BY model, percentage DESC;
```

Example query to check sync status:

```sql
SELECT 
  firmware_version,
  COUNT(*) as total_readings,
  SUM(CASE WHEN synced = 1 THEN 1 ELSE 0 END) as synced_readings,
  ROUND(100.0 * SUM(CASE WHEN synced = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as sync_percentage
FROM sensor_readings
GROUP BY firmware_version
ORDER BY sync_percentage;
```

## Technical Implementation

The simulator is built with a modular architecture:

- **main.py**: Entry point that parses arguments and starts the simulator
- **src/simulator.py**: Core simulation logic that generates readings and applies anomalies
- **src/anomaly.py**: Implements different types of anomalies and their behaviors
- **src/database.py**: Handles database connections and operations
- **src/config.py**: Loads and manages configuration from files and environment variables

The Docker container uses:
- Python 3.11 with uv for dependency management
- Environment variables for configuration overrides
- Volume mounting for persistent data storage

## Testing

The project includes a test script (`test_container.sh`) that:
1. Builds the Docker container
2. Clears and recreates the data directory
3. Runs the container for 30 seconds
4. Verifies the database was created
5. Shows statistics and sample data

Run the test with:
```bash
./test_container.sh
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
