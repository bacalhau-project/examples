# SQLite to Databricks Uploader

This tool provides a continuous data pipeline that extracts data from local SQLite databases and uploads it directly to Databricks tables. It's designed to run as a containerized service, ideal for edge computing scenarios or integration with Bacalhau compute nodes.

## Features

- **Direct Databricks Upload**: Connects directly to Databricks SQL warehouses or clusters without intermediate storage
- **Incremental Processing**: Tracks last uploaded timestamp to process only new records
- **Auto-Detection**: Automatically detects SQLite tables and timestamp columns when not specified
- **Dynamic Configuration**: Live configuration updates with automatic processing mode switching
- **Optimized Batch Upload**: Efficient 500-record batches with direct INSERT statements
- **Multiple Processing Modes**: Support for raw, schematized, sanitized, aggregated, and emergency data pipelines
- **Local Data Processing**: Built-in data transformation and filtering capabilities
- **Flexible Configuration**: Configure via YAML, environment variables, or command-line arguments
- **Query Mode**: Built-in debugging capability to query and inspect Databricks tables
- **Multi-Architecture Support**: Docker images support both AMD64 and ARM64 architectures
- **Comprehensive Testing**: Full unit test coverage with automated test suite

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
# Processing mode - dynamically changeable at runtime
processing_mode: "schematized"  # Options: raw, schematized, sanitized, aggregated, emergency

# SQLite Source
sqlite: "/path/to/sensor_data.db"
sqlite_table_name: "sensor_logs"  # Optional - auto-detected if not specified
timestamp_col: "timestamp"        # Optional - auto-detected if not specified

# Databricks Target
databricks_host: "your-workspace.cloud.databricks.com"
databricks_http_path: "/sql/1.0/warehouses/your_warehouse_id"
databricks_token: "dapi..."  # Better to use DATABRICKS_TOKEN env var
databricks_database: "your_database"
databricks_table: "your_table"  # Base name - suffixes added per processing mode

# Operational Settings
state_dir: "./state"
interval: 300  # seconds between upload cycles
max_batch_size: 500  # records per batch
fuzz_factor: 0.1  # ±10% randomization on interval

# Processing-specific configurations (optional)
gps_fuzzing:
  enabled: true
  radius_meters: 100

emergency_config:
  trigger_keywords: ["EMERGENCY", "ALERT", "CRITICAL"]

aggregate_config:
  window_minutes: 5
  aggregations: ["mean", "max", "min"]
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

-- Sanitized data table
CREATE TABLE IF NOT EXISTS sensor_data.readings_2_sanitized (
    -- Same schema as schematized, but with cleaned data
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
MAX_BATCH_SIZE=500               # Default: 500 records per batch
FUZZ_FACTOR=0.1                  # Default: 10% interval randomization
ONCE=true                         # Run once and exit

# Processing Mode
PROCESSING_MODE=schematized       # Options: raw, schematized, sanitized, aggregated, emergency

# Data Processing (Optional)
GPS_FUZZING_CONFIG='{"enabled": true, "radius_meters": 100}'
EMERGENCY_CONFIG='{"trigger_keywords": ["EMERGENCY", "ALERT"]}'
AGGREGATE_CONFIG='{"window_minutes": 5, "aggregations": {"temperature": ["mean", "max"]}}'
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

### Dynamic Configuration Reloading

The uploader monitors the configuration file every 2 seconds and automatically applies changes without requiring a restart. This is particularly useful for:

- **Switching Processing Modes**: Change between raw, schematized, sanitized, aggregated, or emergency modes on the fly
- **Updating Processing Parameters**: Modify GPS fuzzing radius, emergency keywords, or aggregation windows
- **Testing Different Configurations**: Experiment with settings without interrupting data flow

Example of dynamic mode switching:
```bash
# While uploader is running, change mode from schematized to aggregated
echo "processing_mode: aggregated" > temp.yaml
cat databricks-uploader-config.yaml | grep -v "processing_mode:" >> temp.yaml
mv temp.yaml databricks-uploader-config.yaml
```

The uploader will log the change and route data to the appropriate table on the next cycle.

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

### Processing Modes

Each processing mode routes data to a specific table with appropriate transformations:

#### 1. Raw Mode (`processing_mode: "raw"`)
- **Table**: `{database}.{table}_0_raw`
- **Purpose**: Store original data without modifications
- **Use Case**: Data archival and audit trails

#### 2. Schematized Mode (`processing_mode: "schematized"`)
- **Table**: `{database}.{table}_1_schematized`
- **Purpose**: Standardize data schema with additional metadata
- **Features**: 
  - Adds derived columns (vibration, voltage, anomaly flags)
  - Enriches with location data
  - Includes firmware and model information

#### 3. Sanitized Mode (`processing_mode: "sanitized"`)
- **Table**: `{database}.{table}_2_sanitized`
- **Purpose**: Clean and validate data
- **Features**:
  - Remove invalid readings
  - Apply range checks
  - Handle missing values

#### 4. Aggregated Mode (`processing_mode: "aggregated"`)
- **Table**: `{database}.{table}_3_aggregated`
- **Purpose**: Pre-compute time-window aggregations
- **Configuration**:
  ```yaml
  aggregate_config:
    window_minutes: 5
    group_by: ["sensor_id"]
    aggregations:
      temperature: ["mean", "max", "min"]
      humidity: ["mean"]
  ```

#### 5. Emergency Mode (`processing_mode: "emergency"`)
- **Table**: `{database}.{table}_4_emergency`
- **Purpose**: Extract and route critical alerts
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
gps_fuzzing:
  enabled: true
  radius_meters: 100
  base_lat: 37.7749  # Base coordinates
  base_lon: -122.4194
```

This feature adds random displacement within the specified radius to protect exact sensor locations.

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

### Common Issues and Solutions

1. **Authentication Errors**
   - Verify your Databricks PAT is valid
   - Ensure the token has necessary permissions for the target database/table
   - Check token hasn't expired

2. **Table Not Found**
   - Verify database and table names are correct
   - Ensure all required tables exist for your processing mode:
     - Raw mode: `{table}_0_raw`
     - Schematized: `{table}_1_schematized`
     - Sanitized: `{table}_2_sanitized`
     - Aggregated: `{table}_3_aggregated`
     - Emergency: `{table}_4_emergency`

3. **No New Records**
   - Check the state file to see the last uploaded timestamp
   - Verify your SQLite data has records newer than this timestamp
   - Delete state file to reprocess all data: `rm state/last_upload_state.json`

4. **Connection Timeouts**
   - Verify network connectivity to Databricks workspace
   - Check if SQL warehouse is running and accessible
   - Increase timeout in Databricks connection settings

5. **Schema Errors**
   ```
   Error: DeltaDataSource source does not support user-specified schema
   ```
   - This is fixed in the latest version - ensure you're using the updated code
   - The uploader now uses direct INSERT statements instead of temporary tables

6. **Timestamp Format Errors**
   ```
   Error: 'str' object has no attribute 'isoformat'
   ```
   - This is fixed in the latest version
   - The uploader properly handles timestamp conversions for state management

7. **HTTP Request Logging Noise**
   - The latest version suppresses verbose HTTP logs from Databricks connector
   - Only warnings and errors are shown by default

### Performance Tuning

1. **Slow Uploads**
   - Increase `max_batch_size` to 1000 or higher (test stability first)
   - Ensure Databricks warehouse is properly sized
   - Check network latency to Databricks

2. **Memory Issues with Large Datasets**
   - Reduce `max_batch_size` to limit memory usage
   - Process data in smaller chunks by setting lower batch size

3. **Config File Not Updating**
   - Check file permissions on config file
   - Verify config watcher is running (check logs for "Started watching config file")
   - Ensure valid YAML syntax after edits

### Debug Mode

For detailed debugging, set logging to show all operations:

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
- **Secure state files**: Protect state directory from unauthorized access
- **Validate inputs**: The uploader validates all data before upload
- **Use HTTPS only**: All Databricks connections use encrypted transport

## Production Best Practices

1. **High Availability**
   - Run multiple instances with different state directories
   - Use external state storage (S3, Azure Blob) for shared state
   - Implement proper locking for concurrent access

2. **Disaster Recovery**
   - Backup state files regularly
   - Keep SQLite WAL files for point-in-time recovery
   - Test recovery procedures periodically

3. **Performance Optimization**
   - Tune `max_batch_size` based on network and Databricks capacity
   - Use dedicated Databricks SQL warehouses for uploads
   - Monitor and optimize Databricks table partitioning

4. **Operational Excellence**
   - Implement alerting for upload failures
   - Set up log aggregation and analysis
   - Document runbooks for common issues

## License

This project is part of the Bacalhau examples repository. See the main repository for license information.