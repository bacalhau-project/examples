# Databricks Uploader

This directory contains two uploader scripts for moving data from SQLite to cloud storage:

1. **S3 Uploader** (`sqlite_to_s3_uploader.py`) - Uploads data to S3 buckets
2. **Databricks Uploader** (`sqlite_to_databricks_uploader.py`) - Direct upload to Databricks tables

## S3 Uploader (Recommended)

The S3 uploader reads data from a local SQLite database and uploads it to S3 buckets in Parquet format. The target bucket is determined by the pipeline type stored in the database.

### Configuration

Create a configuration file (see `databricks-uploader-config.yaml`):

```yaml
# SQLite Configuration
sqlite: "../sample-sensor/data/sensor_data.db"
sqlite_table: "sensor_readings"  # Optional - auto-detected if not specified
timestamp_col: "timestamp"       # Optional - auto-detected if not specified

# S3 Configuration
s3_configuration:
  enabled: true
  region: "us-west-2"
  prefix: "expanso"
  buckets:
    raw: "expanso-databricks-raw-us-west-2"
    schematized: "expanso-databricks-schematized-us-west-2"
    filtered: "expanso-databricks-filtered-us-west-2"
    emergency: "expanso-databricks-emergency-us-west-2"

# Processing Configuration
state_dir: "state/s3-uploader"
interval: 30  # seconds
max_batch_size: 500
```

### Running the S3 Uploader

```bash
# One-time upload
export $(grep -v '^#' ../.env | xargs)  # Load AWS credentials
uv run -s sqlite_to_s3_uploader.py --config ../databricks-uploader-config.yaml --once

# Continuous mode (uploads every 30 seconds)
uv run -s sqlite_to_s3_uploader.py --config ../databricks-uploader-config.yaml
```

### Pipeline Management

The uploader reads the pipeline type from the SQLite database. Use the pipeline controller to change it:

```bash
cd ../pipeline-manager

# View current pipeline
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db get

# Change pipeline type
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db set aggregated

# View history
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db history
```

Pipeline types determine the target S3 bucket:
- `raw` → raw S3 bucket (unprocessed data)
- `schematized` → schematized S3 bucket (validated & enriched)
- `aggregated` → aggregated S3 bucket (summarized data)
- `emergency` → emergency S3 bucket (critical alerts)
- `regional` → regional S3 bucket (based on AWS region)

### Features

- **Incremental Upload**: Tracks last uploaded timestamp
- **Atomic Reads**: Uses SQLite WAL mode for concurrent access
- **Auto-detection**: Automatically finds tables and timestamp columns
- **Batch Processing**: Uploads data in configurable batches
- **State Management**: Persists upload state between runs
- **Error Handling**: Comprehensive error messages with recovery suggestions

## Databricks Direct Uploader

For direct uploads to Databricks tables (bypassing S3), use `sqlite_to_databricks_uploader.py`.

### Configuration

See `databricks-uploader-config.yaml.example` for Databricks-specific configuration.

### Running

```bash
# Ensure Databricks credentials are set
export DATABRICKS_HOST="https://your-workspace.databricks.com"
export DATABRICKS_TOKEN="your-token"

# Run uploader
uv run -s sqlite_to_databricks_uploader.py --config databricks-config.yaml
```

## Docker Deployment

```bash
# Build container
docker build -t databricks-uploader .

# Run with S3 uploader
docker run -v $(pwd)/data:/data \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_REGION=us-west-2 \
  databricks-uploader \
  uv run -s sqlite_to_s3_uploader.py --config /data/config.yaml
```

## Testing

```bash
# Test S3 uploader
python test_s3_uploader.py

# Test pipeline routing
python test_s3_pipeline_routing.py

# Test configuration parsing
python test_config_parser.py
```

## State Management

The uploader maintains state in the SQLite database in the `upload_state` table. This provides:
- Atomic operations to prevent race conditions
- Per-scenario state tracking
- Upload history and metrics

To view and manage state:
```bash
# View current state
uv run -s upload_state_manager.py --db ../sample-sensor/data/sensor_data.db list

# Reset state for a table
uv run -s upload_state_manager.py --db ../sample-sensor/data/sensor_data.db reset sensor_readings
```

## Troubleshooting

### Database Locked
If you see "database is locked" errors:
1. Ensure only one uploader instance is running
2. Check if the sensor container is running
3. The uploader uses WAL mode for better concurrency

### S3 Access Denied
If you see S3 permission errors:
1. Check AWS credentials: `aws sts get-caller-identity`
2. Verify IAM permissions for the buckets
3. Ensure bucket exists in the correct region

### No Data Uploaded
If no data is being uploaded:
1. Check if there's new data: `sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_readings"`
2. Check state file for last timestamp
3. Verify timestamp column is correctly detected

### Pipeline Not Changing
If pipeline changes aren't reflected:
1. Ensure pipeline_config table exists in the database
2. Use pipeline_controller.py to change pipeline type
3. Check for any error messages in the uploader output