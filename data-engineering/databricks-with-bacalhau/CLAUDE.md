# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Databricks with Bacalhau data engineering project that implements a continuous data pipeline for extracting data from local SQLite databases and uploading it to Databricks tables. The project now uses AWS Spot instances for compute and S3 buckets for data storage, designed for edge computing scenarios and integration with Bacalhau compute nodes.

## AWS Infrastructure Setup

### Creating S3 Buckets

The project uses four S3 buckets corresponding to different data processing scenarios:
- **Raw**: Unprocessed sensor data
- **Schematized**: Data with enforced schemas and validation
- **Filtered**: Data filtered based on business rules
- **Emergency**: High-priority anomaly or alert data

To create the buckets:

```bash
# Run the S3 bucket creation script
cd scripts
uv run -s create-s3-buckets.sh --prefix your-company --region us-east-1

# Or with additional options
uv run -s create-s3-buckets.sh \
  --prefix your-company \
  --region us-west-2 \
  --account-id 123456789012 \
  --create-folders
```

### AWS Spot Instance Deployment

The project uses AWS Spot instances for cost-effective compute. Use the AWS SSO wrapper script:

```bash
# Use the spot-sso.sh wrapper for AWS authentication
../bigquery-with-bacalhau/spot-sso.sh
```

This script:
- Handles AWS SSO authentication
- Exports necessary AWS credentials
- Uses the `ghcr.io/bacalhau-project/aws-spot-deployer:latest` container

## Common Development Commands

### Running the Uploader

```bash
# Run uploader directly with uv on Spot instance
cd databricks-uploader
uv run -s sqlite_to_databricks_uploader.py --config ../databricks-uploader-config.yaml

# Manage pipeline types
uv run -s pipeline_manager.py --db sensor_data.db get
uv run -s pipeline_manager.py --db sensor_data.db set filtered --by "ops_team"
uv run -s pipeline_manager.py --db sensor_data.db history --limit 20

# Run tests
cd databricks-uploader
python test_uploader.py
python test_direct_insert.py
python test_pipeline_manager.py
```

### Linting

Use `ruff` for Python linting as per user preferences:
```bash
ruff check .
ruff format .
```

## Architecture Overview

### Main Components

1. **SQLite to Databricks Uploader** (`databricks-uploader/sqlite_to_databricks_uploader.py`)
   - UV-run script with self-contained dependencies
   - Incremental data processing with state management
   - Dynamic configuration reloading without restart
   - Database-driven pipeline selection for atomic, concurrent operations
   - Multiple processing scenarios that route to different tables and S3 buckets:
     - Raw data → `raw_*` tables → `raw` S3 bucket
     - Schematized data → `schematized_*` tables → `schematized` S3 bucket
     - Filtered data → `filtered_*` tables → `filtered` S3 bucket
     - Emergency data → `emergency_*` tables → `emergency` S3 bucket

2. **Pipeline Manager** (`databricks-uploader/pipeline_manager.py`)
   - Stores pipeline configuration in SQLite for atomicity
   - Provides CLI for viewing/changing pipeline types
   - Tracks execution history with success/failure metrics
   - Supports concurrent access from multiple processes
   - Usage: `uv run -s pipeline_manager.py --db sensor.db get/set/history`

2. **AWS Infrastructure** 
   - **S3 Buckets**: Four buckets for different data scenarios
   - **Spot Instances**: Cost-effective compute using AWS Spot
   - **Bucket Creation Script** (`scripts/create-s3-buckets.sh`):
     - Creates buckets with proper naming conventions
     - Enables versioning and encryption
     - Sets up lifecycle policies for raw data
     - Configures bucket policies for Databricks access

### Key Features

- **Direct Databricks Connection**: Uses databricks-sql-connector for direct uploads
- **Incremental Processing**: Tracks last uploaded timestamp in state files
- **Auto-Detection**: Automatically detects SQLite tables and timestamp columns
- **Batch Processing**: Optimized uploads in 500-record batches
- **Config Watching**: Hot-reload configuration changes without restart
- **Query Mode**: Built-in debugging with `--run-query` flag

### Configuration

Configuration precedence (highest to lowest):
1. Command-line arguments
2. Environment variables
3. YAML configuration file
4. Default values

Key environment variables:
- **Databricks**: `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`, `DATABRICKS_DATABASE`, `DATABRICKS_TABLE`
- **SQLite**: `SQLITE_PATH`, `SQLITE_TABLE_NAME`, `TIMESTAMP_COL`
- **Processing**: `STATE_DIR`, `UPLOAD_INTERVAL`, `ONCE`
- **Pipeline Selection** (stored in SQLite database, not config file):
  - Pipeline type is managed atomically in the database
  - Use `pipeline_manager.py` CLI to view/change pipeline type
  - Supports: raw, schematized, filtered, emergency scenarios
- **S3 Configuration**:
  - `S3_BUCKET_PREFIX`: Prefix for bucket names
  - `S3_REGION`: AWS region for buckets
  - `S3_BUCKET_RAW`, `S3_BUCKET_SCHEMATIZED`, `S3_BUCKET_FILTERED`, `S3_BUCKET_EMERGENCY`

### Testing

Unit tests use mock-based testing for:
- Config watcher functionality
- Upload batch operations
- Timestamp conversion
- Databricks identifier quoting

## Development Notes

- Always use `uv` instead of `python` for running scripts
- Scripts use UV-run shebangs with inline dependencies
- State management uses JSON files in configurable state directory
- Pipeline type is stored in SQLite database for atomic, concurrent access
- Processing type determines both target table AND S3 bucket
- Use `pipeline_manager.py` CLI to change pipeline types safely
- AWS Spot instances provide cost-effective compute for the pipeline
- S3 buckets include lifecycle policies for cost optimization (raw data moves to cheaper storage tiers)
- Bucket naming follows pattern: `{prefix}-databricks-{scenario}-{region}`