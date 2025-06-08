# Industrial Sensor Simulator

This project simulates industrial environmental sensors that monitor temperature, humidity, pressure, and voltage. It generates realistic sensor data and stores it in a SQLite database, including both normal operating patterns and various types of anomalies.

## Features

- Generates realistic sensor data (temperature, humidity, pressure, voltage)
- Configurable via YAML file and node-specific JSON identity file
- Random location generation with GPS coordinates
- Sensor replication for testing at scale
- Simulates various types of anomalies:
  - **Spike anomalies**: Sudden, short-lived extreme values
  - **Trend anomalies**: Gradual shifts away from normal operation
  - **Pattern anomalies**: Changes in the normal pattern of readings
  - **Missing data**: Simulated sensor outages
  - **Noise anomalies**: Increased random variation in readings
- Firmware-dependent behavior (different versions exhibit different anomaly patterns)
- Model and manufacturer-specific characteristics
- Location-based environmental patterns
- Stores data in a lightweight SQLite database
- Runs as a Docker container with uv for dependency management
- **Dynamic configuration reloading**: Changes to configuration files are automatically detected and applied
- **Database sync support**: Includes a `synced` flag for integration with external data collection systems

## Getting Started

### Prerequisites

- Docker
- Python 3.11+ (if running without Docker)
- SQLite3 (for querying the database)

### Quick Start with Docker

Run the container with default settings:

```bash
docker run -v $(pwd)/data:/app/data ghcr.io/bacalhau-project/sensor-log-generator:latest
```

Or with custom sensor ID and location:

```bash
docker run -v $(pwd)/data:/app/data \
          -e SENSOR_ID=CUSTOM001 \
          -e SENSOR_LOCATION="Custom Location" \
          ghcr.io/bacalhau-project/sensor-log-generator:latest
```

### Using Docker Compose

1. Create a `docker-compose.yml` file:

```yaml
services:
  sensor-simulator:
    image: ghcr.io/bacalhau-project/sensor-log-generator:latest
    container_name: sensor-simulator
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/var/log/app
```

1. Run with Docker Compose:

```bash
docker-compose up -d
```

### Building Locally

1. Clone the repository:

```bash
git clone https://github.com/bacalhau-project/bacalhau-examples.git
cd bacalhau-examples/utility_containers/sensor-log-generator
```

1. Build the Docker image:

```bash
docker build -t sensor-simulator .
```

1. Run the container:

```bash
docker run -v $(pwd)/data:/app/data sensor-simulator
```

1. Test the container with the provided script:

```bash
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

```bash
pip install requests numpy pyyaml psutil
```

1. Run the simulator:

```bash
python main.py --config config.yaml --identity node_identity.json
```

## Configuration

The simulator uses two primary configuration files:

1. **Global Configuration** (`config.yaml`): Contains general simulation parameters
2. **Node Identity** (`node_identity.json`): Contains sensor-specific identity and characteristics

### Configuration Options

#### Sensor Configuration

| Option | Description | Default | Env Variable |
|--------|-------------|---------|--------------|
| `sensor.id` | Unique sensor identifier (auto-generated as 6-digit number if not provided) | None | SENSOR_ID |
| `sensor.type` | Type of sensor | environmental | - |
| `sensor.location` | Physical location (REQUIRED, must not be a placeholder) | None | SENSOR_LOCATION |
| `sensor.manufacturer` | Manufacturer name (must be from valid list) | None | - |
| `sensor.model` | Model number (must be from valid list) | None | - |
| `sensor.firmware_version` | Firmware version (must be from valid list) | None | - |

#### Validation Rules

1. **Sensor ID**:
   - If not provided, will be auto-generated as a 6-digit number
   - Format: `[A-Z]{3}_[0-9]{6}` (e.g., "CHI_123456")
   - Will exit with error if manually provided ID doesn't match format

2. **Location**:
   - Required field with no default value
   - Must be a valid, non-placeholder location
   - Will exit with error if:
     - Location is not provided
     - Location is a placeholder (e.g., "REPLACE_WITH_LOCATION", "DEFAULT LOCATION", "UNKNOWN", "TBD")
     - Location is empty or whitespace

3. **Manufacturer, Model, and Firmware**:
   - Must be from predefined valid lists
   - Will exit with error if any value is not in the valid list

#### Simulation Parameters

| Option | Description | Default |
|--------|-------------|---------|
| `simulation.readings_per_second` | Number of readings per second | 1 |
| `simulation.run_time_seconds` | Total simulation duration | 3600 (1 hour) |
| `simulation.start_delay_seconds` | Delay before starting simulation | 0 |

#### Operating Parameters

| Option | Description | Default |
|--------|-------------|---------|
| `normal_parameters.temperature.mean` | Average temperature (°C) | 61.0 |
| `normal_parameters.temperature.std_dev` | Standard deviation | 2.0 |
| `normal_parameters.temperature.min` | Minimum value | 50.0 |
| `normal_parameters.temperature.max` | Maximum value | 80.0 |
| `normal_parameters.humidity.mean` | Average humidity (%) | 3.0 |
| `normal_parameters.humidity.std_dev` | Standard deviation | 0.5 |
| `normal_parameters.humidity.min` | Minimum value | 0.0 |
| `normal_parameters.humidity.max` | Maximum value | 100.0 |
| `normal_parameters.pressure.mean` | Average pressure (bar) | 12.0 |
| `normal_parameters.pressure.std_dev` | Standard deviation | 0.5 |
| `normal_parameters.pressure.min` | Minimum value | 10.0 |
| `normal_parameters.pressure.max` | Maximum value | 15.0 |
| `normal_parameters.voltage.mean` | Average voltage (V) | 12.0 |
| `normal_parameters.voltage.std_dev` | Standard deviation | 0.1 |
| `normal_parameters.voltage.min` | Minimum value | 11.5 |
| `normal_parameters.voltage.max` | Maximum value | 12.5 |

#### Anomaly Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `anomalies.enabled` | Master switch for anomaly generation | true |
| `anomalies.probability` | Probability of starting a new anomaly per reading | 0.05 (5%) |
| `anomalies.types.spike.enabled` | Enable spike anomalies | true |
| `anomalies.types.spike.weight` | Relative frequency | 0.4 |
| `anomalies.types.trend.enabled` | Enable trend anomalies | true |
| `anomalies.types.trend.weight` | Relative frequency | 0.2 |
| `anomalies.types.trend.duration_seconds` | How long the anomaly lasts | 300 |
| `anomalies.types.pattern.enabled` | Enable pattern anomalies | true |
| `anomalies.types.pattern.weight` | Relative frequency | 0.1 |
| `anomalies.types.pattern.duration_seconds` | How long the anomaly lasts | 600 |
| `anomalies.types.missing_data.enabled` | Enable missing data anomalies | true |
| `anomalies.types.missing_data.weight` | Relative frequency | 0.1 |
| `anomalies.types.missing_data.duration_seconds` | How long the anomaly lasts | 30 |
| `anomalies.types.noise.enabled` | Enable noise anomalies | true |
| `anomalies.types.noise.weight` | Relative frequency | 0.2 |
| `anomalies.types.noise.duration_seconds` | How long the anomaly lasts | 180 |

#### Database Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `database.path` | Path to SQLite database file | sensor_data.db |
| `database.backup_enabled` | Enable automatic backups | false |
| `database.backup_interval_hours` | How often to create backups | 24 |
| `database.backup_path` | Where to store backups | ./backups/ |
| `database.max_size_mb` | Maximum database size | 1000 |

#### Logging Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `logging.level` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | INFO |
| `logging.file` | Log file path | sensor_simulator.log |
| `logging.format` | Log format | %(asctime)s - %(name)s - %(levelname)s - %(message)s |
| `logging.console_output` | Whether to output logs to console | true |
| `logging.max_file_size_mb` | Maximum log file size | 10 |
| `logging.backup_count` | Number of log backups to keep | 5 |

#### Random Location Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `random_location.enabled` | Enable random location generation | false |
| `random_location.number_of_cities` | Number of cities to use | 10 |
| `random_location.gps_variation` | Variation around city center (meters) | 100 |
| `random_location.cities_file` | Path to custom cities file | cities.json |

#### Replication Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `replicas.count` | Number of instances to run | 1 |
| `replicas.prefix` | Prefix for sensor IDs | SENSOR |
| `replicas.start_index` | Starting index for sensor IDs | 1 |

### Example Configuration

#### Basic config.yaml

```yaml
# Sensor Simulator Configuration
sensor:
  # id will be auto-generated if not provided
  type: "environmental"
  location: "Chicago"  # Required, must be a valid location
  manufacturer: "SensorTech"  # Must be from valid list
  model: "EnvMonitor-3000"  # Must be from valid list
  firmware_version: "1.4"  # Must be from valid list

simulation:
  readings_per_second: 1
  run_time_seconds: 3600  # 1 hour

normal_parameters:
  temperature:
    mean: 61.0  # Celsius
    std_dev: 2.0
    min: 50.0
    max: 80.0
  humidity:
    mean: 3.0  # Percentage
    std_dev: 0.5
    min: 0.0
    max: 100.0
  pressure:
    mean: 12.0  # Bar
    std_dev: 0.5
    min: 10.0
    max: 15.0
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
  console_output: true
```

#### Random Location with Replicas

```yaml
sensor:
  type: "temperature_vibration"
  manufacturer: "SensorTech"
  model: "TempVibe-2000"
  firmware_version: "1.4"

random_location:
  enabled: true
  number_of_cities: 10
  gps_variation: 100  # meters

replicas:
  count: 5
  prefix: "SENSOR"
  start_index: 1

anomalies:
  enabled: true
  probability: 0.05
```

#### Zero Anomaly Configuration

```yaml
sensor:
  id: "SENSOR001"
  manufacturer: "DataSense"  # 20% fewer anomalies
  model: "TempVibe-3000"     # More stable model
  firmware_version: "1.4"    # 30% lower anomaly probability

anomalies:
  enabled: false  # Disable all anomalies
  probability: 0.0
```

### Database Schema

The SQLite database includes the following fields:

- `id` (PRIMARY KEY): Unique identifier for each reading
- `timestamp`: When the reading was taken
- `sensor_id`: Identifier for the simulated sensor
- `temperature`: Temperature reading in Celsius
- `humidity`: Humidity reading in percentage
- `pressure`: Pressure reading in bar
- `voltage`: Power supply voltage
- `status_code`: Sensor status code (0=normal, 1=anomaly)
- `anomaly_flag`: Boolean flag indicating if this is an anomaly
- `anomaly_type`: Type of anomaly (if anomaly_flag is true)
- `firmware_version`: Version of sensor firmware
- `model`: Sensor model
- `manufacturer`: Sensor manufacturer
- `location`: Sensor location (required)
- `synced`: Boolean flag indicating if this reading has been synced to a central database (0=not synced, 1=synced)

## Querying the Data

Example SQLite queries:

### Compare anomaly rates by firmware version

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

### Analyze anomaly types by model

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

### Get readings by location

```sql
SELECT 
  location,
  COUNT(*) as readings,
  AVG(temperature) as avg_temperature,
  AVG(vibration) as avg_vibration
FROM sensor_readings
GROUP BY location
ORDER BY readings DESC;
```

## Technical Implementation

The simulator is built with a modular architecture:

- **main.py**: Entry point that parses arguments and starts the simulator
- **src/simulator.py**: Core simulation logic that generates readings and applies anomalies
- **src/anomaly.py**: Implements different types of anomalies and their behaviors
- **src/database.py**: Handles database connections and operations
- **src/config.py**: Loads and manages configuration from files and environment variables
- **src/location.py**: Generates random locations and manages replicas

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### SQLite Disk I/O Errors in Containers

If you encounter "disk I/O error" when running in containers with multiple processes accessing the same SQLite database, follow these steps:

#### 1. Enable Debug Logging

Set the logging level to DEBUG in your `config.yaml`:

```yaml
logging:
  level: DEBUG
  file: sensor_simulator.log
  console_output: true
```

This will provide detailed information about:

- Container environment detection
- SQLite connection settings and pragmas
- File permissions and disk space
- WAL (Write-Ahead Logging) mode status
- Process and thread IDs
- File locking information

#### 2. Set SQLite Temporary Directory

In container environments, the default `/tmp` directory might have issues. Set a custom temporary directory:

```bash
# Docker run example
docker run -v $(pwd)/data:/app/data \
  -e SQLITE_TMPDIR=/app/data/tmp \
  -e CONFIG_FILE=/app/config.yaml \
  -e IDENTITY_FILE=/app/identity.json \
  sensor-simulator

# Docker Compose example
environment:
  - SQLITE_TMPDIR=/app/data/tmp
  - CONFIG_FILE=/app/config.yaml
  - IDENTITY_FILE=/app/identity.json
```

Make sure the temporary directory exists and is writable:

```bash
mkdir -p data/tmp
chmod 777 data/tmp
```

#### 3. Volume Mount Considerations

When using Docker volumes, ensure:

1. **Proper permissions**: The container user must have read/write access

   ```bash
   # Set permissions on the host
   chmod -R 777 data/
   ```

2. **Avoid network filesystems**: SQLite doesn't work well with NFS or similar network filesystems

3. **Use named volumes for better performance**:

   ```yaml
   volumes:
     sensor_data:
   
   services:
     sensor:
       volumes:
         - sensor_data:/app/data
   ```

#### 4. Container Resource Limits

Ensure your container has sufficient resources:

```yaml
# Docker Compose example
services:
  sensor:
    mem_limit: 512m
    cpus: '1.0'
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

#### 5. SQLite Configuration

The database module automatically sets these SQLite pragmas for better container compatibility:

- `journal_mode=WAL` - Write-Ahead Logging for better concurrency
- `busy_timeout=30000` - 30-second timeout for locked database
- `synchronous=NORMAL` - Balance between safety and performance
- `temp_store=MEMORY` - Use memory for temporary tables
- `mmap_size=268435456` - 256MB memory-mapped I/O
- `cache_size=-64000` - 64MB cache size

#### 6. Debug Output Analysis

When debug mode is enabled, look for these key indicators:

```text
=== Database Debug Information ===
Running in container: True
SQLITE_TMPDIR: /app/data/tmp
Database absolute path: /app/data/sensor_data.db
Directory writable: True
Disk free: 45.23 GB
WAL file exists, size: 32768 bytes
```

Common issues to look for:

- "Directory writable: False" - Permission issues
- "Disk free: 0.00 GB" - No disk space
- "WAL file exists" with large size - May need WAL checkpoint
- Multiple "File locks" entries - Concurrent access issues

#### 7. Multi-Process Access

If multiple processes need to access the same database:

1. **Use a single writer process**: Have one process write and others read
2. **Implement proper retry logic**: The module includes automatic retries
3. **Consider using a client-server database** like PostgreSQL for heavy concurrent access

#### 8. Recovery from Corruption

If the database becomes corrupted:

```bash
# Backup the corrupted database
cp data/sensor_data.db data/sensor_data.db.backup

# Try to recover using SQLite
sqlite3 data/sensor_data.db ".recover" | sqlite3 data/sensor_data_recovered.db

# Or start fresh
rm data/sensor_data.db*
```

### Common Error Messages

- **"disk I/O error"**: Usually permissions, disk space, or container filesystem issues
- **"database is locked"**: Too many concurrent writers, increase busy_timeout
- **"no such table"**: Database initialization failed, check permissions
- **"out of memory"**: Reduce cache_size or batch_size settings
