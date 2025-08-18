# Industrial Sensor Simulator 🏭

**Your Swiss Army knife for testing data pipelines, monitoring systems, and edge computing deployments!**

This industrial sensor simulator generates hyper-realistic environmental sensor data complete with configurable anomalies, making it perfect for:

- **Testing data ingestion pipelines** without expensive hardware
- **Developing anomaly detection algorithms** with controlled, reproducible scenarios
- **Load testing time-series databases** with concurrent sensor streams
- **Training machine learning models** on realistic sensor patterns
- **Demonstrating edge computing architectures** with distributed sensors
- **Validating monitoring and alerting systems** with predictable anomalies

The simulator creates authentic sensor readings (temperature, humidity, pressure, voltage) with manufacturer-specific quirks, firmware-dependent behaviors, and location-based patterns—just like real industrial IoT deployments!

## ⚡ Why This Simulator?

Unlike basic data generators that produce random numbers, this simulator models the **real-world complexity** of industrial IoT:

- **📦 Hardware variations**: Different manufacturers have different failure rates (SensorTech fails 20% more!)
- **💾 Firmware bugs**: Beta versions are 50% more likely to glitch (just like real life)
- **🌡️ Environmental effects**: Sensors drift differently in hot vs. cold locations
- **⚙️ Realistic anomalies**: Not just random spikes, but patterned failures that mirror actual sensor decay
- **🔄 Concurrent operations**: Multiple sensors can write to the same database safely (goodbye, disk I/O errors!)
- **📈 Production-ready**: Monitoring endpoints, health checks, and metrics for integration with your observability stack

Perfect for teams who need to test their systems against realistic sensor behavior without deploying expensive hardware!

## 🚀 Key Features

### Realistic Data Generation
- **Multi-sensor readings**: Temperature, humidity, pressure, and voltage with authentic noise patterns
- **Manufacturer quirks**: Different brands exhibit unique failure modes and accuracy levels
- **Firmware behaviors**: Beta versions are buggy, stable releases are... mostly stable
- **Location awareness**: Sensors in Denver behave differently than those in Miami

### Powerful Anomaly Simulation 
Perfect for testing your detection algorithms:
- **🔥 Spike anomalies**: Sudden sensor freakouts (that one sensor that always acts up)
- **📈 Trend anomalies**: Gradual drift from normal (like that slowly failing bearing)
- **🔄 Pattern anomalies**: When sensors get "confused" and change their rhythm
- **🚫 Missing data**: Simulated network outages and sensor failures
- **📊 Noise anomalies**: Increased jitter (electrical interference, anyone?)

### Enterprise-Ready Features
- **🔄 Hot configuration reloading**: Tweak anomaly rates without restarting
- **🎯 Concurrent database access**: Multiple sensors writing to the same database safely
- **📡 HTTP monitoring API**: Real-time health checks and metrics endpoints
- **🏷️ Semantic versioning**: Properly versioned Docker images with our new Python build system
- **🔐 Data sync support**: Built-in `synced` flag for data pipeline integration
- **📝 LLM-optimized documentation**: AI assistants can understand your setup instantly

## 🎯 Common Use Cases

### Testing Anomaly Detection
Want to validate your anomaly detection system? Create controlled chaos:

```yaml
# chaos-test.yaml
anomalies:
  enabled: true
  probability: 0.20  # 20% anomaly rate - bring on the chaos!
  types:
    spike:
      enabled: true
      weight: 0.5  # Lots of spikes to test your threshold alerts
    trend:
      enabled: true
      weight: 0.3
      duration_seconds: 600  # Long trends to test your drift detection
```

### Load Testing Databases
Need to stress test your time-series database? Spawn a sensor army:

```yaml
# load-test.yaml
replicas:
  count: 100  # 100 concurrent sensors
  prefix: "LOAD_TEST"
simulation:
  readings_per_second: 10  # 1000 readings/second total
```

### Training ML Models
Building a predictive maintenance model? Generate training data with known patterns:

```yaml
# ml-training.yaml
anomalies:
  enabled: true
  probability: 0.05  # Realistic 5% failure rate
sensor:
  manufacturer: "SensorTech"  # Known to fail more often
  firmware_version: "3.0.0-beta"  # Buggy firmware for more anomalies
```

## 🚀 Quick Start

### Prerequisites

- Docker (recommended) or Python 3.11+ with uv
- SQLite3 (for data analysis)

### 30-Second Setup

```bash
# Run with default settings (1 sensor, moderate anomalies)
docker run -v $(pwd)/data:/app/data \
  ghcr.io/bacalhau-project/sensor-log-generator:latest

# Run with custom identity (specific location, model, etc.)
docker run -v $(pwd)/data:/app/data \
  -e SENSOR_ID=SENSOR_NYC_001 \
  -e SENSOR_LOCATION="New York Factory Floor 3" \
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
    environment:
      - CONFIG_FILE=/app/config/config.yaml
      - IDENTITY_FILE=/app/config/node_identity.json
```

2. Run with Docker Compose:

```bash
docker-compose up -d
```

For local development with custom configuration:

```bash
docker-compose -f docker-compose-local.yml up
```

### 🏗️ Building and Versioning

We use a Python-based build system with proper semantic versioning:

```bash
# Build with automatic minor version bump (e.g., 1.2.0 -> 1.3.0)
./build.py

# Build with major version bump (e.g., 1.2.0 -> 2.0.0)
./build.py --version-bump major

# Build with specific version
./build.py --version-tag 2.5.3

# Test build without pushing (dry run)
./build.py --skip-push
```

Each build creates three tags:
- **latest**: Always points to the newest build
- **datetime**: Unique timestamp (e.g., `2508180755`)
- **semver**: Semantic version (e.g., `v1.2.3`)

The build system:
- Supports linux/amd64 and linux/arm64 architectures
- Uses Docker buildx for multi-platform builds
- Automatically creates and pushes git tags
- Validates semantic version format
- Provides rich terminal output with build progress

### 🛠️ Local Development

1. Clone and setup:

```bash
git clone https://github.com/bacalhau-project/bacalhau-examples.git
cd bacalhau-examples/utility_containers/sensor-log-generator
```

2. Build and test locally:

```bash
# Quick test with the test script
./test_container.sh

# Or build manually
docker build -t sensor-simulator .
docker run -v $(pwd)/data:/app/data sensor-simulator
```

3. Run with custom configuration:

```bash
# Copy example config
cp config.example.yaml my-config.yaml
# Edit my-config.yaml to your needs

# Run with your config
docker run -v $(pwd)/data:/app/data \
  -v $(pwd)/my-config.yaml:/app/config.yaml \
  sensor-simulator
```

### 🐍 Running with Python (using uv)

For development or when Docker isn't available:

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run directly with uv (dependencies auto-installed)
uv run main.py --config config.yaml --identity node_identity.json

# Generate a new identity file
uv run main.py --generate-identity

# Run tests
uv run pytest tests/
```

### Environment Variables

The simulator supports the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to configuration YAML file | config.yaml |
| `IDENTITY_FILE` | Path to identity JSON file | node_identity.json |
| `SENSOR_ID` | Override sensor ID | None (auto-generated) |
| `SENSOR_LOCATION` | Override sensor location | None (required in config) |
| `SQLITE_TMPDIR` | SQLite temporary directory (for containers) | /tmp |
| `LOG_LEVEL` | Override logging level | INFO |
| `PRESERVE_EXISTING_DB` | Preserve existing database on startup | false |
| `DEBUG_MODE` | Enable debug logging and diagnostics | false |

Environment variables take precedence over configuration file values.

## Configuration

The simulator uses two primary configuration files:

1. **Global Configuration** (`config.yaml`): Contains general simulation parameters
2. **Node Identity** (`node_identity.json`): Contains sensor-specific identity and characteristics

### Node Identity File Formats

The simulator supports two identity file formats:

#### Legacy Format (Flat Structure)
Simple, backward-compatible format with basic sensor information:

```json
{
  "id": "SENSOR_NY_123456",
  "location": "New York",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "timezone": "America/New_York",
  "manufacturer": "SensorTech",
  "model": "TempSensor Pro",
  "firmware_version": "1.2.0"
}
```

#### New Format (Nested Structure)
Enhanced format with detailed metadata and deployment information:

```json
{
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
    "sensor_type": "environmental_monitoring"
  }
}
```

Example identity files are provided:
- `config/node-identity-legacy.json` - Legacy flat format example
- `config/node-identity-new.json` - New nested format example

To generate a new identity file template:
```bash
uv run main.py --generate-identity
```

### Configuration File Versions

The simulator supports two configuration file versions:

- **Version 1** (Legacy): Basic configuration without monitoring or dynamic reloading
- **Version 2** (Current): Enhanced configuration with monitoring API and dynamic reloading support

Example configuration files are provided:
- `config.example.yaml` - Complete version 2 configuration with all options documented
- `config.v1.example.yaml` - Legacy version 1 configuration for backward compatibility
- `config/sensor-config-with-monitoring.yaml` - Production-ready version 2 configuration

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
   - Must be from predefined valid lists (defined in `src/enums.py`)
   - Will exit with error if any value is not in the valid list
   
   Valid Manufacturers:
   - SensorTech (20% more anomalies)
   - DataLogger (10% more anomalies)
   - DataSense (20% fewer anomalies)
   - MonitorPro (10% fewer anomalies)
   
   Valid Models by Manufacturer:
   - SensorTech: TempSensor Pro, HumidCheck 2000, PressureGuard, EnvMonitor-3000
   - DataLogger: DataLogger-X1, AirData-Plus, ClimateTracker, IndustrialMonitor-5000
   - DataSense: TempVibe-3000, HumidPress-4000, AllSense-Pro, FactoryGuard-7000
   - MonitorPro: ProTemp-500, ProHumid-600, ProPressure-700, ProEnviron-800
   
   Valid Firmware Versions:
   - 1.0, 1.2.0, 1.4 (30% lower anomaly probability)
   - 2.1, 2.3.5, 2.5 (15% lower anomaly probability)
   - 3.0.0-beta, 3.1.2-alpha, 3.2-rc1 (50% higher anomaly probability)

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

#### Monitoring Configuration (Version 2 only)

| Option | Description | Default |
|--------|-------------|---------|
| `monitoring.enabled` | Enable HTTP monitoring API | false |
| `monitoring.port` | Port for monitoring API | 8080 |
| `monitoring.host` | Host to bind monitoring API | 0.0.0.0 |

#### Dynamic Configuration Reloading

Version 2 configurations support dynamic reloading. Changes to configuration files are automatically detected and applied without restarting the simulator. The following settings can be changed at runtime:

- Anomaly settings (probability, types, durations)
- Logging level
- Normal operating parameters (temperature, humidity, pressure, voltage ranges)

Note: Some settings like database path and sensor identity cannot be changed at runtime.

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

The SQLite database uses the following schema (defined in `src/database.py`):

#### Core Sensor Data Fields
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT): Unique identifier for each reading
- `timestamp` (DATETIME): When the reading was taken
- `sensor_id` (TEXT): Identifier for the simulated sensor
- `temperature` (REAL): Temperature reading in Celsius
- `humidity` (REAL): Humidity reading in percentage
- `pressure` (REAL): Pressure reading in bar
- `vibration` (REAL): Vibration reading (not currently used, always 0.0)
- `voltage` (REAL): Power supply voltage

#### Status and Anomaly Fields
- `status_code` (INTEGER): Sensor status code (0=normal, 1=anomaly)
- `anomaly_flag` (BOOLEAN): Boolean flag indicating if this is an anomaly
- `anomaly_type` (TEXT): Type of anomaly if anomaly_flag is true (spike, trend, pattern, missing_data, noise)
- `synced` (BOOLEAN DEFAULT 0): Boolean flag indicating if this reading has been synced to a central database

#### Device Information Fields
- `firmware_version` (TEXT): Version of sensor firmware
- `model` (TEXT): Sensor model
- `manufacturer` (TEXT): Sensor manufacturer
- `serial_number` (TEXT): Device serial number
- `manufacture_date` (TEXT): Date device was manufactured

#### Location Information Fields
- `location` (TEXT): Sensor location (required)
- `latitude` (REAL): GPS latitude coordinate
- `longitude` (REAL): GPS longitude coordinate
- `original_timezone` (TEXT): Timezone of the sensor location

#### Deployment Information Fields
- `deployment_type` (TEXT): Type of deployment (e.g., fixed, mobile_unit)
- `installation_date` (TEXT): Date sensor was installed
- `height_meters` (REAL): Installation height in meters
- `orientation_degrees` (REAL): Sensor orientation in degrees

#### Metadata Fields
- `instance_id` (TEXT): Cloud instance identifier (e.g., AWS EC2 instance ID)
- `sensor_type` (TEXT): Type of sensor (e.g., environmental_monitoring)

## 📊 Analyzing Your Data

The simulator creates rich, queryable data perfect for analysis:

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

## 🌐 HTTP Monitoring API

When monitoring is enabled, access real-time metrics and health checks:

### Health and Status Endpoints

- **GET `/healthz`** - Health check endpoint
  - Returns: `{"status": "healthy", "timestamp": "2025-01-21T10:00:00Z"}`
  - HTTP 200 if healthy, 503 if unhealthy

- **GET `/statusz`** - Simulator status information
  - Returns current simulator state including:
    - Configuration details
    - Runtime statistics
    - Current anomaly states
    - Database connection status

### Metrics and Data Endpoints

- **GET `/metricz`** - JSON metrics endpoint
  - Returns operational metrics:
    - Total readings generated
    - Anomaly counts by type
    - Database write statistics
    - Error counts

- **GET `/samplez`** - Sample data endpoint
  - Returns the last 10 sensor readings in JSON format
  - Useful for debugging and monitoring data quality

- **GET `/db_stats`** - Database statistics
  - Returns:
    - Total record count
    - Database file size
    - Disk usage statistics
    - Table information

### Enabling Monitoring

To enable the monitoring API, use a version 2 configuration file with monitoring enabled:

```yaml
version: 2
monitoring:
  enabled: true
  port: 8080
  host: "0.0.0.0"
```

## 🏗️ Architecture

The simulator uses a modular, extensible architecture:

### Core Components
- **main.py**: Entry point with CLI argument parsing
- **src/simulator.py**: Core simulation engine with configurable timing
- **src/anomaly.py**: Anomaly generation with weighted random selection
- **src/database.py**: Resilient SQLite operations with retry logic and WAL mode
- **src/config.py**: Dynamic configuration with hot reloading support
- **src/location.py**: GPS coordinate generation and city database
- **src/monitor.py**: HTTP server for health checks and metrics
- **src/enums.py**: Type-safe enumerations for manufacturers and models

### Key Features
- **Concurrent-safe database access**: Multiple sensors can write to the same database
- **Graceful degradation**: Continues operating even with disk errors
- **Memory-efficient**: Streams data without buffering large datasets
- **Cloud-native**: Designed for containerized deployments
- **LLM-friendly**: Structured for easy AI assistant comprehension

## 🔬 Advanced Testing Scenarios

### Simulating Sensor Decay
Test how your system handles gradually failing sensors:

```yaml
# sensor-decay.yaml
anomalies:
  enabled: true
  probability: 0.01  # Start with 1% anomaly rate
  
# Then use dynamic reloading to gradually increase:
# After 1 hour: probability: 0.05
# After 2 hours: probability: 0.10
# After 3 hours: probability: 0.25
```

### Geographic Distribution Testing
Simulate a global sensor network:

```yaml
# global-network.yaml
random_location:
  enabled: true
  number_of_cities: 50  # Use 50 different cities
  gps_variation: 1000   # 1km variation around city centers

replicas:
  count: 50
  prefix: "GLOBAL"
```

### Firmware Rollout Simulation
Test how firmware updates affect your fleet:

```bash
# Start with stable firmware
docker run -v $(pwd)/data:/app/data \
  -e SENSOR_FIRMWARE="1.4" \
  sensor-simulator

# Simulate rolling update to beta firmware
docker run -v $(pwd)/data:/app/data \
  -e SENSOR_FIRMWARE="3.0.0-beta" \
  sensor-simulator
```

## 📚 LLM Integration

This project includes LLM-optimized documentation for AI assistants:

- **CLAUDE.md**: Instructions for Claude and other AI coding assistants
- **llm_docs.py**: Generates comprehensive project documentation
- **Structured configs**: YAML and JSON formats that LLMs can easily parse

To generate fresh LLM documentation:

```bash
uv run python src/llm_docs.py > LLM_DOCUMENTATION.md
```

## 🤝 Contributing

We welcome contributions! This sensor simulator is perfect for:

- Adding new sensor types (vibration, sound, air quality)
- Implementing additional anomaly patterns
- Creating industry-specific presets
- Improving database performance
- Adding export formats (Parquet, CSV, etc.)

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔧 Troubleshooting

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
