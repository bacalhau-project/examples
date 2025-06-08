# SQLite to Databricks Uploader

This tool provides a continuous data pipeline that extracts data from local SQLite databases and uploads it directly to Databricks tables. It's designed to run as a containerized service, ideal for edge computing scenarios or integration with Bacalhau compute nodes.

## Features

- **Direct Databricks Upload**: Connects directly to Databricks SQL warehouses or clusters without intermediate storage
- **Incremental Processing**: Tracks last uploaded timestamp to process only new records
- **Auto-Detection**: Automatically detects SQLite tables and timestamp columns when not specified
- **Local Data Processing**: Supports optional data sanitization, filtering, and aggregation before upload
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

## Data Processing Features

The uploader includes optional data processing capabilities that can be enabled through configuration:

### Sanitization
Clean or transform data before upload:
```yaml
enable_sanitize: true
sanitize_config:
  remove_nulls: ["temperature", "humidity"]
  replace_values:
    status: {"error": "unknown", "": "unknown"}
```

### Filtering
Select specific rows based on criteria:
```yaml
enable_filter: true
filter_config:
  temperature:
    ">": -50
    "<": 150
  device_status: "active"
```

### Aggregation
Perform aggregations before upload:
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
python sqlite_to_databricks_uploader.py --config config.yaml \
  --log-level DEBUG
```

## Security Considerations

- **Never commit tokens**: Always use environment variables for sensitive credentials
- **Use read-only mounts**: Mount SQLite databases as read-only in containers
- **Rotate tokens regularly**: Update Databricks PATs periodically
- **Limit token scope**: Use tokens with minimal required permissions

## License

This project is part of the Bacalhau examples repository. See the main repository for license information.