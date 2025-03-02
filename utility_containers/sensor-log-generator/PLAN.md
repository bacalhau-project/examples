# SENSOR SIMULATOR PROJECT PLAN

## Project Overview
This project will create a containerized sensor simulator that generates realistic sensor data and stores it in a SQLite database. The simulator will be configurable via a YAML file and a node-specific JSON identity file, generating both normal data patterns and anomalies for demonstration purposes.

## Sensor Type Selection
For this project, we'll simulate an industrial temperature and vibration sensor commonly used in manufacturing equipment. These sensors are typically deployed across factories to monitor machine health and predict maintenance needs.

## Requirements

### Functional Requirements
1. Generate realistic sensor data (temperature, vibration, etc.)
2. Store data in a SQLite database with appropriate schema
3. Support configuration via YAML file and node-specific JSON identity file
4. Generate normal patterns and anomalies based on configuration
5. Run as a Docker container
6. Include comprehensive documentation

### Technical Requirements
1. Python-based implementation
2. SQLite database with efficient schema
3. Docker containerization
4. Configuration via YAML and JSON
5. Logging and error handling

## Database Schema
The SQLite database will include:
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

## Sensor Identity Configuration
Each sensor will have a unique identity defined in a JSON file:
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

## Firmware-Dependent Anomalies
The simulator will include firmware-dependent anomalies:

1. **Firmware 1.3 Issues**:
   - Higher probability of temperature spikes
   - Occasional voltage fluctuations
   - Increased noise in vibration readings

2. **Firmware 1.4 Improvements**:
   - Reduced temperature spikes
   - Stabilized voltage readings
   - Improved vibration measurement accuracy

## Other Scenario-Based Anomalies

1. **Model-Dependent Issues**:
   - TempVibe-1000: Prone to missing data anomalies
   - TempVibe-2000: Occasional pattern anomalies
   - TempVibe-3000: Rare but severe spike anomalies

2. **Location-Based Patterns**:
   - Factory locations: Higher average temperatures during work hours
   - Warehouse locations: More stable temperature, higher vibration variance
   - Outdoor locations: Greater temperature fluctuations based on time of day

3. **Manufacturer Quality Differences**:
   - SensorTech: Generally reliable with occasional issues
   - DataSense: Lower anomaly rate but more severe when they occur
   - VibrationPlus: Higher baseline vibration readings with more noise

## Implementation Checklist
- [x] Set up project structure
- [x] Create database schema and initialization script
- [x] Implement sensor data generation logic
- [x] Implement anomaly generation logic
- [x] Create configuration parser for YAML
- [x] Add support for node-specific JSON identity files
- [x] Implement firmware-dependent anomaly behavior
- [x] Implement model-dependent anomaly behavior
- [x] Implement location-based patterns
- [x] Implement manufacturer-dependent behavior
- [x] Create Dockerfile
- [x] Write comprehensive README.md
- [x] Create demo script for generating multiple sensor configurations
- [x] Test locally
- [x] Build and test Docker container

## Configuration Options
The config.yaml file will support:
- Sensor details (ID, type, location)
- Data generation rate (readings per second)
- Normal operating parameters (ranges, patterns)
- Anomaly configuration (types, frequency, intensity)
- Database settings
- Logging settings

## Anomaly Types
1. Spike anomalies: Sudden, short-lived extreme values
2. Trend anomalies: Gradual shifts away from normal operation
3. Pattern anomalies: Changes in the normal pattern of readings
4. Missing data: Simulated sensor outages
5. Noise anomalies: Increased random variation in readings

## Next Steps
1. Implement the node identity file loader
2. Modify the anomaly generator to consider firmware version
3. Add model and manufacturer-specific behaviors
4. Create the demo script for generating multiple sensor configurations
5. Complete the Docker container setup
6. Finalize documentation 