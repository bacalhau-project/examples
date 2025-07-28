# SQLite to Databricks Uploader

This tool provides a continuous data pipeline that extracts data from local SQLite databases and uploads it directly to Databricks tables. It's designed to run as a containerized service, ideal for edge computing scenarios or integration with Bacalhau compute nodes.

## Features

- **Direct Databricks Upload**: Connects directly to Databricks SQL warehouses or clusters without intermediate storage
- **Incremental Processing**: Tracks last uploaded timestamp to process only new records
- **Auto-Detection**: Automatically detects SQLite tables and timestamp columns when not specified
- **Dynamic Configuration**: Live configuration updates without restart
- **Database-Driven Pipeline Selection**: Atomic pipeline type management stored in SQLite for concurrent access
- **Optimized Batch Upload**: Efficient 500-record batches with direct INSERT statements
- **Multiple Pipeline Types**: Support for raw, schematized, filtered, and emergency data pipelines
- **Execution Tracking**: Complete audit trail of all pipeline executions with success/failure metrics
- **Local Data Processing**: Built-in data transformation and filtering capabilities
- **Flexible Configuration**: Configure via YAML, environment variables, or command-line arguments
- **Query Mode**: Built-in debugging capability to query and inspect Databricks tables
- **Multi-Architecture Support**: Docker images support both AMD64 and ARM64 architectures

## Prerequisites

- Docker Engine (19.03+)
- Python 3.11 with `uv` CLI (for local development)
- Databricks workspace with:
  - SQL warehouse or All-Purpose Cluster
  - Target database and table configured
  - Personal Access Token (PAT) for authentication

## Quick Start

### 1. Configuration

Copy the example configuration file:

```bash
cp databricks-uploader-config.yaml.example databricks-uploader-config.yaml
```

Edit the configuration with your specific settings:

```yaml
# SQLite Source
sqlite: "/path/to/sensor_data.db"
sqlite_table_name: "sensor_logs"  # Optional - auto-detected if not specified
timestamp_col: "timestamp"        # Optional - auto-detected if not specified

# Databricks Target
databricks_host: "your-workspace.cloud.databricks.com"
databricks_http_path: "/sql/1.0/warehouses/your_warehouse_id"
databricks_token: "dapi..."  # Better to use DATABRICKS_TOKEN env var
databricks_database: "your_database"
databricks_table: "your_table"

# Operational Settings
state_dir: "./state"
interval: 300  # seconds between upload cycles
```

### 2. Build the Docker Image

```bash
# Set required environment variables
export ORGANIZATION_NAME=your-org
export IMAGE_NAME=databricks-uploader

# Build the image
./build.sh --tag v1.0.0 --push
```

### 3. Run the Uploader

For local testing:

```bash
# Run directly with uv
uv run -s sqlite_to_databricks_uploader.py --config databricks-uploader-config.yaml
```

For production deployment:

```bash
# Run as Docker container
docker run -v $(pwd)/databricks-uploader-config.yaml:/config.yaml:ro \
           -v /path/to/sqlite/data:/data:ro \
           -v $(pwd)/state:/state \
           ghcr.io/your-org/databricks-uploader:latest \
           --config /config.yaml
```

## Full Demo Walkthrough

This section provides a complete end-to-end demonstration of the uploader's capabilities.

### Step 1: Prepare Sample Data

First, create a sample SQLite database with sensor data:

```python
# create_sample_data.py
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import random

# Create sample sensor data
conn = sqlite3.connect('sensor_data.db')
base_time = datetime.now() - timedelta(hours=2)

data = []
for i in range(1000):
    data.append({
        'id': i + 1,
        'sensor_id': f'sensor_{random.randint(1, 10):03d}',
        'timestamp': base_time + timedelta(minutes=i * 0.1),
        'temperature': 20 + random.uniform(-5, 5),
        'humidity': 60 + random.uniform(-10, 10),
        'pressure': 1013 + random.uniform(-5, 5),
        'status_code': 200 if random.random() > 0.05 else 500,
        'location': random.choice(['Building A', 'Building B', 'Building C'])
    })

df = pd.DataFrame(data)
df.to_sql('sensor_logs', conn, if_exists='replace', index=False)
conn.close()
print(f"Created sensor_data.db with {len(data)} records")
```

### Step 2: Set Up Databricks Tables

Create the necessary tables in your Databricks workspace:

```sql
-- Create database
CREATE DATABASE IF NOT EXISTS sensor_data;

-- Create tables for each processing mode
-- Raw data table
CREATE TABLE IF NOT EXISTS sensor_data.readings_0_raw (
    id BIGINT,
    sensor_id STRING,
    timestamp TIMESTAMP,
    temperature DOUBLE,
    humidity DOUBLE,
    pressure DOUBLE,
    status_code INT,
    location STRING,
    databricks_inserted_at TIMESTAMP
);

-- Schematized data table
CREATE TABLE IF NOT EXISTS sensor_data.readings_1_schematized (
    reading_id BIGINT,
    sensor_id STRING,
    timestamp TIMESTAMP,
    temperature DOUBLE,
    humidity DOUBLE,
    pressure DOUBLE,
    vibration DOUBLE,
    voltage DOUBLE,
    status_code INT,
    anomaly_flag INT,
    anomaly_type STRING,
    firmware_version STRING,
    model STRING,
    manufacturer STRING,
    location STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    original_timezone STRING,
    synced INT,
    databricks_inserted_at TIMESTAMP
);

-- Filtered data table
CREATE TABLE IF NOT EXISTS sensor_data.readings_2_filtered (
    -- Same schema as schematized, but with filtered/sanitized data
    reading_id BIGINT,
    sensor_id STRING,
    timestamp TIMESTAMP,
    temperature DOUBLE,
    humidity DOUBLE,
    pressure DOUBLE,
    location STRING,
    databricks_inserted_at TIMESTAMP
);

-- Aggregated data table
CREATE TABLE IF NOT EXISTS sensor_data.readings_3_aggregated (
    sensor_id STRING,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    avg_temperature DOUBLE,
    max_temperature DOUBLE,
    min_temperature DOUBLE,
    avg_humidity DOUBLE,
    record_count INT,
    databricks_inserted_at TIMESTAMP
);

-- Emergency data table
CREATE TABLE IF NOT EXISTS sensor_data.readings_4_emergency (
    alert_id BIGINT,
    sensor_id STRING,
    timestamp TIMESTAMP,
    alert_type STRING,
    severity STRING,
    message STRING,
    databricks_inserted_at TIMESTAMP
);
```

### Step 3: Configure and Run the Uploader

Create your configuration file:

```yaml
# demo-config.yaml
processing_mode: "schematized"

# SQLite Source
sqlite: "./sensor_data.db"
sqlite_table_name: "sensor_logs"
timestamp_col: "timestamp"

# Databricks Connection
databricks_host: "dbc-12345678-abcd.cloud.databricks.com"
databricks_http_path: "/sql/1.0/warehouses/your_warehouse_id"
databricks_database: "sensor_data"
databricks_table: "readings"

# Processing Configuration
state_dir: "./state"
interval: 60  # Check every minute for demo
max_batch_size: 500
fuzz_factor: 0.1

# Processing modes configuration
gps_fuzzing:
  enabled: true
  radius_meters: 50
  base_lat: 37.7749
  base_lon: -122.4194

emergency_config:
  trigger_keywords: ["EMERGENCY", "CRITICAL", "ALERT"]
  severity_thresholds:
    temperature: 35
    pressure: 1030

aggregate_config:
  window_minutes: 5
  group_by: ["sensor_id"]
  aggregations:
    temperature: ["mean", "max", "min"]
    humidity: ["mean"]
```

### Step 4: Run the Tests

Before running the uploader, verify everything works:

```bash
# Run unit tests
uv run python test_uploader.py -v

# Expected output:
# test_config_watcher_detects_changes ... ok
# test_upload_batch_via_file_success ... ok
# ... (all tests should pass)
```

### Step 5: Start the Uploader

```bash
# Set your Databricks token
export DATABRICKS_TOKEN="dapi..."

# Run the uploader
uv run sqlite_to_databricks_uploader.py --config demo-config.yaml
```

You should see output like:
```
2024-12-20 10:30:00,123 INFO Started watching config file: demo-config.yaml
2024-12-20 10:30:00,456 INFO Successfully connected to Databricks: dbc-12345678-abcd.cloud.databricks.com
2024-12-20 10:30:01,789 INFO PRE-UPLOAD STATUS:
2024-12-20 10:30:01,789 INFO   Available records in SQLite: 1000
2024-12-20 10:30:01,789 INFO   ID range: 1 to 1000
2024-12-20 10:30:01,789 INFO   Will fetch up to 500 records
2024-12-20 10:30:05,123 INFO Uploading 500 records to `sensor_data`.`readings_1_schematized` in batches of 500...
2024-12-20 10:30:10,456 INFO Successfully uploaded 500 records
```

### Step 6: Test Dynamic Configuration

While the uploader is running, modify the configuration file to change processing modes:

```bash
# In another terminal, update the config
sed -i 's/processing_mode: "schematized"/processing_mode: "aggregated"/' demo-config.yaml
```

You'll see in the logs:
```
2024-12-20 10:32:00,123 INFO Config file changed, reloading...
2024-12-20 10:32:00,124 INFO Processing mode changed from 'schematized' to 'aggregated'
2024-12-20 10:32:05,456 INFO Routing data to table: `sensor_data`.`readings_3_aggregated` (processing mode: aggregated)
```

### Step 7: Query Results in Databricks

Use the built-in query mode to verify data upload:

```bash
# Check record counts
uv run sqlite_to_databricks_uploader.py --config demo-config.yaml \
  --run-query "SELECT processing_mode, COUNT(*) as count FROM (
    SELECT 'raw' as processing_mode, COUNT(*) as count FROM sensor_data.readings_0_raw
    UNION ALL
    SELECT 'schematized', COUNT(*) FROM sensor_data.readings_1_schematized
    UNION ALL
    SELECT 'aggregated', COUNT(*) FROM sensor_data.readings_3_aggregated
  ) GROUP BY processing_mode"

# View recent uploads
uv run sqlite_to_databricks_uploader.py --config demo-config.yaml \
  --run-query "SELECT * FROM sensor_data.readings_1_schematized ORDER BY databricks_inserted_at DESC LIMIT 10"
```

### Step 8: Continuous Data Generation (Optional)

For a more realistic demo, continuously generate new sensor data:

```python
# continuous_data_generator.py
import sqlite3
import time
import random
from datetime import datetime

conn = sqlite3.connect('sensor_data.db')
cursor = conn.cursor()

# Get the max ID
cursor.execute("SELECT MAX(id) FROM sensor_logs")
max_id = cursor.fetchone()[0] or 0

while True:
    max_id += 1
    cursor.execute("""
        INSERT INTO sensor_logs (id, sensor_id, timestamp, temperature, humidity, pressure, status_code, location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        max_id,
        f'sensor_{random.randint(1, 10):03d}',
        datetime.now(),
        20 + random.uniform(-5, 5),
        60 + random.uniform(-10, 10),
        1013 + random.uniform(-5, 5),
        200 if random.random() > 0.05 else 500,
        random.choice(['Building A', 'Building B', 'Building C'])
    ))
    conn.commit()
    print(f"Generated record {max_id}")
    time.sleep(5)  # Generate one record every 5 seconds
```

## Configuration Options

### Configuration Precedence

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **YAML configuration file**
4. **Default values** (lowest priority)

### Environment Variables

```bash
# Databricks Connection (Required)
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your_warehouse_id
DATABRICKS_TOKEN=dapi...  # Store securely!
DATABRICKS_DATABASE=sensor_data
DATABRICKS_TABLE=raw_readings

# SQLite Source
SQLITE_PATH=/data/sensor.db
SQLITE_TABLE_NAME=sensor_logs      # Optional
TIMESTAMP_COL=event_timestamp      # Optional

# Script Behavior
STATE_DIR=/state                   # Default: /state
UPLOAD_INTERVAL=300               # Default: 300 seconds
ONCE=true                         # Run once and exit

# Data Processing (Optional)
ENABLE_SANITIZE=true
SANITIZE_CONFIG='{"remove_nulls": ["temperature", "humidity"]}'
ENABLE_FILTER=true
FILTER_CONFIG='{"temperature": {">": -50, "<": 150}}'
ENABLE_AGGREGATE=true
AGGREGATE_CONFIG='{"group_by": ["device_id"], "aggregations": {"temperature": "avg"}}'
```

### Command-Line Arguments

```bash
# View all available options
python sqlite_to_databricks_uploader.py --help

# Common usage examples
python sqlite_to_databricks_uploader.py \
  --config uploader-config.yaml \
  --sqlite /data/new_sensor.db \
  --once

# Query mode for debugging
python sqlite_to_databricks_uploader.py \
  --config uploader-config.yaml \
  --run-query "SELECT COUNT(*) FROM sensor_data.raw_readings"

# Get table information
python sqlite_to_databricks_uploader.py \
  --config uploader-config.yaml \
  --run-query "INFO"
```

## Advanced Features

### Pipeline Management

The uploader now uses a database-driven pipeline selection system that ensures atomic updates and supports concurrent access from multiple processes.

#### Managing Pipeline Types

Use the included `pipeline_manager.py` tool to view and change pipeline types:

```bash
# View current pipeline type
uv run -s pipeline_manager.py --db /path/to/sensor_data.db get

# Change pipeline type
uv run -s pipeline_manager.py --db /path/to/sensor_data.db set filtered --by "operations_team"

# View execution history
uv run -s pipeline_manager.py --db /path/to/sensor_data.db history --limit 20
```

#### Available Pipeline Types

- **raw**: Original data without modifications (routes to `{table}_0_raw`)
- **schematized**: Structured data with enforced schema (routes to `{table}_1_schematized`)
- **filtered**: Cleaned and filtered data (routes to `{table}_2_filtered`)
- **emergency**: Critical alerts and anomalies only (routes to `{table}_4_emergency`)

#### Migration from Old Configurations

The uploader automatically migrates from old configuration formats:

- `processing_mode: "sanitized"` → `filtered` pipeline
- `processing_mode: "aggregated"` → `emergency` pipeline
- `enable_sanitization: true` → `schematized` pipeline
- `enable_aggregation: true` → `emergency` pipeline

### Dynamic Configuration Reloading

The uploader monitors the configuration file every 2 seconds and automatically applies changes without requiring a restart. This is particularly useful for:

- **Updating Processing Parameters**: Modify GPS fuzzing radius, emergency keywords, or aggregation windows
- **Testing Different Configurations**: Experiment with settings without interrupting data flow
- **Changing Connection Settings**: Update database paths or Databricks credentials

Note: Pipeline type selection is now managed through the database, not the config file.

### Optimized Batch Processing

The uploader uses efficient batch INSERT statements with configurable batch sizes:

- **Default Batch Size**: 500 records per INSERT statement
- **Direct SQL Upload**: No temporary tables or intermediate files
- **Automatic Batching**: Large datasets are automatically split into optimal chunks
- **Progress Tracking**: Clear logging of batch progress during upload

Configure batch size via:
```yaml
max_batch_size: 1000  # Increase for better performance with stable connections
```

### Pipeline Types

Each pipeline type routes data to a specific table with appropriate transformations:

#### 1. Raw Pipeline
- **Table**: `{database}.{table}_0_raw`
- **Purpose**: Store original data without modifications
- **Use Case**: Data archival and audit trails
- **Selection**: `uv run -s pipeline_manager.py --db sensor.db set raw`

#### 2. Schematized Pipeline
- **Table**: `{database}.{table}_1_schematized`
- **Purpose**: Standardize data schema with additional metadata
- **Features**: 
  - Adds derived columns (vibration, voltage, anomaly flags)
  - Enriches with location data
  - Includes firmware and model information
- **Selection**: `uv run -s pipeline_manager.py --db sensor.db set schematized`

#### 3. Filtered Pipeline
- **Table**: `{database}.{table}_2_filtered`
- **Purpose**: Clean, validate, and filter data
- **Features**:
  - GPS coordinate fuzzing for privacy
  - Remove invalid readings
  - Apply business rules filtering
- **Selection**: `uv run -s pipeline_manager.py --db sensor.db set filtered`

#### 4. Emergency Pipeline
- **Table**: `{database}.{table}_4_emergency`
- **Purpose**: Extract and route critical alerts
- **Configuration**:
  ```yaml
  aggregate_config:
    window_minutes: 5
    group_by: ["sensor_id"]
    aggregations:
      temperature: ["mean", "max", "min"]
      humidity: ["mean"]
  ```

- **Configuration**:
  ```yaml
  emergency_config:
    trigger_keywords: ["EMERGENCY", "CRITICAL", "ALERT"]
    severity_thresholds:
      temperature: 35
      pressure: 1030
  ```

### GPS Fuzzing

Add random noise to GPS coordinates for privacy:

```yaml
enable_aggregate: true
aggregate_config:
  group_by: ["device_id", "hour"]
  aggregations:
    temperature: "avg"
    humidity: "max"
    readings: "count"
```

## Databricks Table Setup

Before running the uploader, ensure your target table exists in Databricks:

```sql
-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS sensor_data;

-- Create table with schema matching your SQLite data
CREATE TABLE IF NOT EXISTS sensor_data.raw_readings (
    id BIGINT,
    device_id STRING,
    timestamp TIMESTAMP,
    temperature DOUBLE,
    humidity DOUBLE,
    status STRING
);
```

## Debugging and Monitoring

### Query Mode

Use the `--run-query` flag to inspect your Databricks tables:

```bash
# Get table metadata and row count
python sqlite_to_databricks_uploader.py --config config.yaml --run-query "INFO"

# Query specific data
python sqlite_to_databricks_uploader.py --config config.yaml \
  --run-query "SELECT * FROM sensor_data.raw_readings WHERE timestamp > current_date() - 1 LIMIT 10"
```

### Logs

The uploader provides detailed logging:
- Connection status to SQLite and Databricks
- Number of records processed in each cycle
- Any errors during processing or upload
- State file updates

### State Management

The uploader maintains state in a JSON file to track the last successfully uploaded timestamp:

```json
{
  "last_upload": "2024-01-15T14:30:00Z"
}
```

This file is stored in the directory specified by `state_dir` configuration.

## Docker Deployment

### Building the Image

The included `build.sh` script supports multi-architecture builds:

```bash
# Build for multiple platforms
export PLATFORMS="linux/amd64,linux/arm64"
./build.sh --tag v1.0.0 --push

# Build for local testing only
./build.sh --tag dev --registry local
```

### Running in Production

Example docker-compose.yml:

```yaml
version: '3.8'
services:
  databricks-uploader:
    image: ghcr.io/your-org/databricks-uploader:latest
    volumes:
      - ./config.yaml:/config.yaml:ro
      - /data/sqlite:/data:ro
      - ./state:/state
    environment:
      - DATABRICKS_TOKEN=${DATABRICKS_TOKEN}
    command: ["--config", "/config.yaml"]
    restart: unless-stopped
```

## Integration with Bacalhau

This uploader is designed to work seamlessly with Bacalhau compute jobs. Example Bacalhau job specification:

```yaml
name: databricks-upload-job
type: batch
compute:
  image: ghcr.io/your-org/databricks-uploader:latest
inputs:
  - source:
      type: localDirectory
      path: /data/sqlite
    target: /data
  - source:
      type: localFile
      path: ./config.yaml
    target: /config.yaml
env:
  DATABRICKS_TOKEN: ${DATABRICKS_TOKEN}
command:
  - "--config"
  - "/config.yaml"
  - "--once"
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify your Databricks PAT is valid
   - Ensure the token has necessary permissions for the target database/table

2. **Table Not Found**
   - Verify database and table names are correct
   - Ensure the table exists in Databricks before running the uploader

3. **No New Records**
   - Check the state file to see the last uploaded timestamp
   - Verify your SQLite data has records newer than this timestamp

4. **Connection Timeouts**
   - Verify network connectivity to Databricks workspace
   - Check if SQL warehouse is running and accessible

### Debug Mode

For detailed debugging, run with verbose logging:

```bash
# Show all SQL queries and operations
PYTHONUNBUFFERED=1 uv run sqlite_to_databricks_uploader.py \
  --config config.yaml 2>&1 | tee debug.log
```

### Testing Components

Run the test suite to verify your installation:

```bash
# Run all tests
uv run python test_uploader.py -v

# Run specific test
uv run python test_uploader.py TestConfigWatcher -v
```

## Monitoring and Observability

### Execution Tracking

The pipeline manager automatically tracks all executions with detailed metrics:

```bash
# View recent execution history
uv run -s pipeline_manager.py --db sensor.db history --limit 50

# Example output:
# ID | Pipeline    | Started             | Completed           | Records | Status    | Error
# 25 | filtered    | 2024-01-15 10:30:00 | 2024-01-15 10:30:05 | 500     | completed | 
# 24 | filtered    | 2024-01-15 10:25:00 | 2024-01-15 10:25:04 | 487     | completed |
# 23 | emergency   | 2024-01-15 10:20:00 | 2024-01-15 10:20:02 | 12      | completed |
# 22 | raw         | 2024-01-15 10:15:00 | 2024-01-15 10:15:10 | 1000    | failed    | Connection timeout
```

Execution metrics include:
- Pipeline type used
- Start and completion timestamps
- Number of records processed
- Success/failure status
- Error messages for failed executions

### Log Output Format

The uploader provides structured logging with clear status updates:

```
2024-12-20 10:30:00,123 INFO Started watching config file: demo-config.yaml
2024-12-20 10:30:01,789 INFO ============================================================
2024-12-20 10:30:01,789 INFO PRE-UPLOAD STATUS:
2024-12-20 10:30:01,789 INFO   Available records in SQLite: 1000
2024-12-20 10:30:01,789 INFO   ID range: 1 to 1000
2024-12-20 10:30:01,789 INFO   Will fetch up to 500 records
2024-12-20 10:30:01,789 INFO ============================================================
2024-12-20 10:30:05,123 INFO Uploading 500 records in batches of 500...
2024-12-20 10:30:10,456 INFO Successfully uploaded 500 records
2024-12-20 10:30:10,789 INFO ============================================================
2024-12-20 10:30:10,789 INFO POST-UPLOAD STATUS:
2024-12-20 10:30:10,789 INFO   Records uploaded: 500
2024-12-20 10:30:10,789 INFO   Uploaded ID range: 1 to 500
2024-12-20 10:30:10,789 INFO   Remaining records in SQLite: 500
2024-12-20 10:30:10,789 INFO   Remaining ID range: 501 to 1000
2024-12-20 10:30:10,789 INFO ============================================================
```

### Key Metrics to Monitor

1. **Upload Success Rate**: Track successful vs failed uploads
2. **Records Per Cycle**: Monitor data volume trends
3. **Processing Time**: Measure upload duration for performance
4. **Queue Depth**: Watch remaining records to ensure keeping up
5. **Config Changes**: Log when processing modes change

### Integration with Monitoring Systems

Export metrics by parsing logs:

```bash
# Extract upload metrics
grep "POST-UPLOAD STATUS" -A 5 uploader.log | \
  grep "Records uploaded:" | \
  awk '{print $NF}' | \
  prometheus-push-gateway --job databricks-uploader --metric records_uploaded
```

### Health Checks

For containerized deployments, use state file updates as health indicator:

```bash
# health_check.sh
#!/bin/bash
STATE_FILE="/state/last_upload_state.json"
MAX_AGE=600  # 10 minutes

if [ ! -f "$STATE_FILE" ]; then
  echo "State file not found"
  exit 1
fi

FILE_AGE=$(($(date +%s) - $(stat -f %m "$STATE_FILE" 2>/dev/null || stat -c %Y "$STATE_FILE")))
if [ $FILE_AGE -gt $MAX_AGE ]; then
  echo "State file too old: ${FILE_AGE}s"
  exit 1
fi

echo "Healthy"
exit 0
```

## Security Considerations

- **Never commit tokens**: Always use environment variables for sensitive credentials
- **Use read-only mounts**: Mount SQLite databases as read-only in containers
- **Rotate tokens regularly**: Update Databricks PATs periodically
- **Limit token scope**: Use tokens with minimal required permissions

## License

This project is part of the Bacalhau examples repository. See the main repository for license information.