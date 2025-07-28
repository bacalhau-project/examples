# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Databricks with Bacalhau data engineering project that implements a continuous data pipeline for extracting data from local SQLite databases and uploading it to Databricks tables. The project now uses AWS Spot instances for compute and S3 buckets for data storage, designed for edge computing scenarios and integration with Bacalhau compute nodes.

The project supports both scenario-based and regional data routing:
- **Scenario-based**: Routes data to different buckets based on processing type (raw, schematized, filtered, emergency)
- **Regional**: Routes data to region-specific buckets based on node deployment location

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

### Regional S3 Architecture

The project includes support for multi-region deployments where nodes upload to region-specific buckets:

1. **Create Regional Buckets**:
```bash
cd scripts
# Set up regional infrastructure (buckets + IAM + tests)
uv run -s setup.py regional

# Or manually create buckets for specific regions
bash create-regional-s3-buckets.sh expanso "us-east-1 us-west-2 eu-west-1 ap-southeast-1"
```

2. **Regional Bucket Naming**:
- Pattern: `{prefix}-databricks-regional-{region}`
- Example: `expanso-databricks-regional-us-west-2`

3. **Region Detection**:
The uploader automatically detects the deployment region using:
- Environment variables: `AWS_REGION` or `AWS_DEFAULT_REGION`
- EC2 instance metadata (for nodes running on EC2)
- Fallback to configured default region

4. **Unity Catalog Setup**:
Run the `create-regional-external-locations.sql` notebook in Databricks to:
- Create external locations for each regional bucket
- Create views for querying regional data
- Create a unified view for cross-region analytics

### AWS Spot Instance Deployment

The project uses AWS Spot instances for cost-effective compute. Use the Spot Deployer installer:

```bash
# Install and run the spot deployer
curl -L https://tada.wang/install.sh | bash -s -- create
```

This script:
- Handles AWS SSO authentication
- Exports necessary AWS credentials
- Uses the `ghcr.io/bacalhau-project/aws-spot-deployer:latest` container

## Common Development Commands

### Running the Uploader

```bash
# Run S3 uploader directly with uv
cd databricks-uploader
uv run -s sqlite_to_s3_uploader.py --config ../databricks-uploader-config.yaml

# Manage pipeline types
uv run -s pipeline_manager.py --db sensor_data.db get
uv run -s pipeline_manager.py --db sensor_data.db set filtered --by "ops_team"
uv run -s pipeline_manager.py --db sensor_data.db set regional --by "deployment_script"
uv run -s pipeline_manager.py --db sensor_data.db history --limit 20

# Run tests
cd scripts
uv run -s test-regional-scenario.py  # Test regional bucket routing
```

### Linting

Use `ruff` for Python linting as per user preferences:
```bash
ruff check .
ruff format .
```

## Architecture Overview

### Main Components

1. **SQLite to S3 Uploader** (`databricks-uploader/sqlite_to_s3_uploader.py`)
   - UV-run script with self-contained dependencies
   - Uploads data to S3 in Parquet format with JSON metadata
   - Incremental data processing with state management
   - Database-driven pipeline selection for atomic, concurrent operations
   - Multiple processing scenarios that route to different S3 buckets:
     - Raw data → `raw` S3 bucket
     - Schematized data → `schematized` S3 bucket
     - Filtered data → `filtered` S3 bucket
     - Emergency data → `emergency` S3 bucket
     - Regional data → region-specific bucket based on deployment location
   - Time-based partitioning (year/month/day/hour) for efficient querying
   - Automatic region detection for regional scenario

2. **Pipeline Manager** (`databricks-uploader/pipeline_manager.py`)
   - Stores pipeline configuration in SQLite for atomicity
   - Provides CLI for viewing/changing pipeline types
   - Tracks execution history with success/failure metrics
   - Supports concurrent access from multiple processes
   - Pipeline types: raw, schematized, filtered, emergency, regional
   - Usage: `uv run -s pipeline_manager.py --db sensor.db get/set/history`

3. **AWS Infrastructure** 
   - **S3 Buckets**: 
     - Four scenario-based buckets (raw, schematized, filtered, emergency)
     - Regional buckets for multi-region deployments
   - **Spot Instances**: Cost-effective compute using AWS Spot
   - **Bucket Creation Scripts**:
     - `scripts/create-s3-buckets.sh`: Creates scenario-based buckets
     - `scripts/create-regional-s3-buckets.sh`: Creates regional buckets
     - Both enable versioning, encryption, and Databricks access policies

### Key Features

- **S3-Based Architecture**: Uploads data to S3 for Databricks Auto Loader ingestion
- **Incremental Processing**: Tracks last uploaded timestamp in state files
- **Auto-Detection**: Automatically detects SQLite tables and timestamp columns
- **Batch Processing**: Uploads data in configurable batch sizes with metadata
- **Region-Aware**: Automatically detects and routes to appropriate regional buckets
- **Time Partitioning**: Organizes data by year/month/day/hour for efficient queries
- **Parquet Format**: Uses columnar storage for optimal query performance

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
  - Supports: raw, schematized, filtered, emergency, regional scenarios
  - Regional scenario uses automatic region detection for bucket routing
- **S3 Configuration**:
  - `S3_BUCKET_PREFIX`: Prefix for bucket names
  - `S3_REGION`: AWS region for buckets
  - `S3_BUCKET_RAW`, `S3_BUCKET_SCHEMATIZED`, `S3_BUCKET_FILTERED`, `S3_BUCKET_EMERGENCY`
  - `AWS_REGION` or `AWS_DEFAULT_REGION`: Used for region detection in regional scenario
  - Regional buckets follow pattern: `{prefix}-databricks-regional-{region}`

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

## AWS Credential Management Notes

- Always use the AWS session tokens, not the AWS keys. Make sure we test for the session token before looking at the AWS credential environment variables.

## Memory Notes

- Do not go above this directory for this project 

## Project Execution Guidelines

- Have all scripts be executed from the main directory, not inside of databricks-uploader or pipeline-manager

## Memories

- When writing test scripts, ensure they are concurrent processing friendly and do not disturb existing databases