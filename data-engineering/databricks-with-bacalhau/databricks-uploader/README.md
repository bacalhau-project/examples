# Databricks Uploader - Core Components

This directory contains the essential components for uploading data from SQLite to Databricks via S3.

## Core Pipeline Files

### Main Components
- `pipeline_manager.py` - Manages pipeline state and configuration
- `pipeline_orchestrator.py` - Orchestrates the data pipeline flow
- `sqlite_to_json_transformer.py` - Transforms SQLite data to JSON format
- `upload_state_manager.py` - Tracks upload progress and state

### Supporting Utilities
- `config_db.py` - Database configuration management
- `retry_handler.py` & `retry_manager.py` - Retry logic for failed operations
- `log_monitor.py` & `pipeline_logging.py` - Logging and monitoring
- `spec_version_manager.py` - Manages data specification versions

### Configuration Files
- `s3-uploader-config.yaml` - Main configuration for the S3 uploader
- `logging_config.yaml` - Logging configuration
- `retry_config.yaml` - Retry policies configuration

### Additional Components
- `autoloader_main.py` - Main entry point for Auto Loader
- `api_backend.py` - API backend for pipeline management
- `json_log_processor.py` - Processes JSON log files
- `sensor_data_models.py` - Data models for sensor data

## Local Testing

### Prerequisites
- Python 3.11+
- `uv` package manager (`pip install uv`)
- SQLite database with sensor data
- AWS credentials (see AWS Credentials section below)

### 1. Create Test Data (Optional)
If you don't have sensor data, create some test data:
```bash
# This creates a test SQLite database with sample sensor readings
uv run -s archive/test-files/create_test_sensor_data.py
```

### 2. Configure AWS Credentials

For headless operation (on nodes, containers, etc.), configure AWS credentials using one of these methods:

#### Option A: Environment Variables (Recommended for containers)
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"
```

#### Option B: In Configuration File
Edit `../databricks-s3-uploader-config.yaml`:
```yaml
s3_configuration:
  access_key_id: "your-access-key"
  secret_access_key: "your-secret-key"
  region: "us-west-2"
```

#### Option C: IAM Role (For EC2/ECS)
If running on AWS infrastructure, assign an IAM role with S3 write permissions.

### 3. Configure the Pipeline
Edit the configuration file at the project root: `../databricks-s3-uploader-config.yaml`

Key settings to verify:
```yaml
# SQLite source
sqlite: "sample-sensor/data/sensor_data.db"  # Path to your SQLite database
sqlite_table: "sensor_readings"               # Table name to read from
timestamp_col: "timestamp"                    # Timestamp column for incremental loads

# S3 destination
s3_configuration:
  region: "us-west-2"
  buckets:
    ingestion: "expanso-databricks-ingestion-us-west-2"
    # ... other buckets

# Processing
interval: 30  # How often to check for new data (seconds)
max_batch_size: 500  # Records per batch
```

### 4. Run the Pipeline Locally

#### One-time Upload
To process all pending data and exit:
```bash
uv run -s sqlite_to_databricks_uploader.py --config ../databricks-s3-uploader-config.yaml --once
```

#### Continuous Mode
To run continuously, checking for new data every interval:
```bash
uv run -s sqlite_to_databricks_uploader.py --config ../databricks-s3-uploader-config.yaml
```

#### Dry Run
To see what would be uploaded without actually uploading:
```bash
uv run -s sqlite_to_databricks_uploader.py --config ../databricks-s3-uploader-config.yaml --dry-run
```

### 5. Monitor Progress

The pipeline creates state files in the `state/` directory to track progress:
```bash
# Check upload state
cat state/s3-uploader/upload_state.json | jq .

# View logs
tail -f logs/pipeline.log
```

### 6. Verify S3 Uploads

Check that files are being uploaded to S3:
```bash
# List uploaded files
aws s3 ls s3://expanso-databricks-ingestion-us-west-2/ingestion/ --recursive

# Download and inspect a file
aws s3 cp s3://expanso-databricks-ingestion-us-west-2/ingestion/2024/01/data.json - | jq .
```

### Common Issues

1. **"No new data to upload"**
   - The pipeline tracks the last uploaded timestamp
   - Delete `state/s3-uploader/upload_state.json` to reprocess all data

2. **AWS credentials error**
   - Ensure AWS credentials are configured: `aws configure`
   - Or set environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

3. **SQLite table not found**
   - Verify the table name in your database: `sqlite3 your.db ".tables"`
   - Update `sqlite_table` in the config file
   - Check if `SQLITE_PATH` or `SQLITE_TABLE` environment variables are overriding your config

4. **S3 bucket access denied**
   - Verify your AWS credentials have write access to the S3 buckets
   - Check the bucket names match your actual S3 buckets

5. **Config file settings being ignored**
   - The script checks for environment variables that override config settings
   - Unset these if you want to use config file values:
     ```bash
     unset SQLITE_PATH SQLITE_TABLE
     # Or run with empty values:
     SQLITE_PATH= SQLITE_TABLE= uv run -s sqlite_to_databricks_uploader.py --config ...
     ```

## Containerized Deployment

### Local Container Testing
Once local testing is successful, you can run in a container:
```bash
# From the project root
./start-uploader.sh databricks-s3-uploader-config.yaml
```

### Bacalhau Node Deployment

For deployment on Bacalhau nodes:

1. **Credentials are deployed via `additional-commands.sh`**:
   - This file contains embedded AWS credentials
   - It's executed during node setup
   - Credentials are stored in `/bacalhau_node/aws-credentials.env`
   - **IMPORTANT**: Never commit `additional-commands.sh` to git!

2. **The container automatically loads credentials**:
   - From `/bacalhau_node/aws-credentials.env` (primary)
   - Or from `/bacalhau_data/credentials/expanso-s3-env.sh` (fallback)

3. **Submit the Bacalhau job**:
   ```bash
   bacalhau job run jobs/databricks-uploader-job.yaml
   ```

The container wrapper script (`run-uploader.sh`) ensures credentials are loaded before the Python script runs.

## Archived Files

All test files, demos, examples, and redundant implementations have been moved to the `archive/` directory for reference.
