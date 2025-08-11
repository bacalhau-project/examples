# Databricks with Bacalhau - Wind Turbine Data Pipeline

A production-ready data pipeline that collects sensor data from distributed wind turbines, processes it through multiple stages, and stores it in Databricks Unity Catalog for analytics.

## Overview

This project simulates a global wind turbine fleet generating sensor data (temperature, humidity, pressure, voltage) that flows through a multi-stage pipeline:

1. **Edge Collection**: SQLite databases on each turbine collect sensor readings
2. **S3 Staging**: Data is uploaded to S3 buckets for different processing stages
3. **Databricks Processing**: Auto Loader ingests data into Unity Catalog tables
4. **Analytics**: Processed data is available for querying and analysis

### Architecture

```
Wind Turbines → SQLite → S3 Buckets → Databricks Auto Loader → Unity Catalog
                          ↓
                    (raw, validated, enriched, aggregated)
```

## Prerequisites

- Python 3.11+
- Docker
- AWS Account with S3 access
- Databricks Workspace with Unity Catalog enabled
- `uv` package manager (`pip install uv`)

## Quick Start

### 1. Clone and Setup Environment

```bash
git clone https://github.com/bacalhau-project/bacalhau-examples.git
cd bacalhau-examples/data-engineering/databricks-with-bacalhau

# Create .env file with this exact content:
cat > .env << 'EOF'
# Databricks Configuration
DATABRICKS_HOST=https://dbc-ae5355ab-8b4e.cloud.databricks.com
DATABRICKS_TOKEN=your-databricks-token-here
DATABRICKS_WAREHOUSE_ID=your-warehouse-id-here
DATABRICKS_CATALOG=expanso_databricks_workspace
DATABRICKS_SCHEMA=sensor_readings

# AWS Configuration
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
S3_BUCKET_PREFIX=expanso

# Pipeline Configuration
UPLOAD_INTERVAL=60
BATCH_SIZE=500
STATE_DIR=./state
SQLITE_PATH=./sample-sensor/data/sensor_data.db
TIMESTAMP_COL=timestamp

# Sensor Configuration
SENSOR_ID=TURBINE_001
SENSOR_LOCATION=US-East Wind Farm
SENSOR_INTERVAL=5
EOF
```

### 2. Create Storage Credential (One-time UI Setup)

This is the ONLY step that requires the Databricks UI:

1. Go to your Databricks workspace: https://dbc-ae5355ab-8b4e.cloud.databricks.com
2. Navigate to **Catalog** → **External Data** → **Storage Credentials**
3. Click **Create credential**
4. Fill in:
   - **Name**: `expanso-databricks-s3-credential-us-west-2`
   - **Type**: AWS IAM Role
   - **IAM Role ARN**: `arn:aws:iam::767397752906:role/databricks-unity-catalog-expanso-role`
5. Click **Create**

### 3. Verify Infrastructure

```bash
# Check all infrastructure is ready
uv run -s databricks-setup.py verify
```

### 4. Setup Databricks Resources

```bash
# Create catalog, schemas, and tables
uv run -s databricks-setup.py setup

# Upload and run Auto Loader notebook
uv run -s databricks-setup.py upload \
  --notebook databricks-notebooks/01-setup-autoloader-demo.py
```

### 5. Start Data Pipeline

```bash
# Start sensor data generation (local testing)
./start-sensor-local.sh

# Start uploader to Databricks
./start-uploader.sh
```

### 6. Query Data

```bash
# Run sample queries
uv run -s databricks-setup.py query

# Or use SQL directly
uv run -s databricks-setup.py query \
  --sql "SELECT * FROM expanso_databricks_workspace.sensor_readings.raw_sensor_readings LIMIT 10"

# Check pipeline status
uv run -s pipeline_manager.py --db sample-sensor/data/sensor_data.db history
```

### 7. Teardown

```bash
# Remove all data and resources
uv run -s databricks-setup.py teardown
```

## Development

### Local Development

1. **Sensor Simulator**
   ```bash
   cd databricks-uploader
   uv run -s create_test_sensor_data.py
   ```

2. **Test Upload Pipeline**
   ```bash
   uv run -s test-upload.py
   ```

3. **Run Tests**
   ```bash
   # Lint code
   ruff check . && ruff format .
   
   # Run unit tests
   python -m pytest databricks-uploader/
   ```

### Container Development

1. **Build Container**
   ```bash
   ./build.sh
   ```

2. **Run in Container**
   ```bash
   docker run -v $(pwd)/state:/app/state \
              -v $(pwd)/.env:/app/.env \
              ghcr.io/bacalhau-project/databricks-uploader:latest
   ```

3. **Deploy to AWS Spot**
   ```bash
   cd spot
   # Assumes you have AWS SSO configured
   ../../bigquery-with-bacalhau/spot-sso.sh deploy \
     --instance-type t3.medium \
     --region us-west-2
   ```

## Project Structure

```
.
├── databricks-setup.py          # Main CLI tool for all operations
├── databricks-notebooks/        # Databricks notebooks
│   ├── 01-setup-autoloader-demo.py
│   └── 02-teardown-all.py
├── databricks-uploader/         # Core pipeline code
│   ├── sqlite_to_databricks_uploader.py
│   ├── pipeline_manager.py
│   └── create_test_sensor_data.py
├── scripts/                     # Infrastructure setup scripts
├── spot/                        # AWS Spot instance configs
└── state/                       # Pipeline state tracking

```

## Configuration

### Environment Variables

Key variables in `.env`:
- `DATABRICKS_HOST`: Your Databricks workspace URL
- `DATABRICKS_TOKEN`: Personal access token
- `DATABRICKS_WAREHOUSE_ID`: SQL warehouse ID
- `DATABRICKS_CATALOG`: Unity Catalog name (default: expanso_databricks_workspace)
- `AWS_REGION`: AWS region for S3 buckets
- `S3_BUCKET_PREFIX`: Prefix for bucket names

### Pipeline Configuration

Edit `databricks-uploader-config.yaml` to configure:
- Upload intervals
- Batch sizes
- Table mappings
- Processing modes

## Pipeline Stages

1. **Raw**: Unprocessed sensor data → `raw_sensor_readings` table
2. **Validated**: Schema-validated data → `validated_sensor_readings` table  
3. **Enriched**: Data with added metadata → `enriched_sensor_readings` table
4. **Aggregated**: Summarized metrics → `aggregated_sensor_metrics` table

## Monitoring

```bash
# Check pipeline status
uv run -s pipeline_manager.py --db sample-sensor/data/sensor_data.db history

# View current pipeline mode
uv run -s pipeline_manager.py --db sample-sensor/data/sensor_data.db get

# Monitor upload progress
watch -n 5 'cat state/s3-uploader/upload_state.json | jq .'

# Check Databricks table row counts
uv run -s databricks-setup.py query \
  --sql "SELECT 'raw' as table, COUNT(*) as count FROM expanso_databricks_workspace.sensor_data.raw_sensor_readings
         UNION ALL
         SELECT 'validated', COUNT(*) FROM expanso_databricks_workspace.sensor_data.validated_sensor_readings"
```

### Databricks UI Monitoring
- **Workflows**: https://dbc-ae5355ab-8b4e.cloud.databricks.com/#/jobs
- **SQL Warehouses**: https://dbc-ae5355ab-8b4e.cloud.databricks.com/sql/warehouses
- **Unity Catalog**: https://dbc-ae5355ab-8b4e.cloud.databricks.com/data

## Building a Bacalhau Cluster

### Deploy Bacalhau Cluster with AWS Spot Instances

1. **Prepare Credentials**:
   ```bash
   # Generate additional-commands.sh with embedded credentials
   uv run -s generate-additional-commands.py
   ```

2. **Deploy the Cluster**:
   ```bash
   # Use the spot-sso.sh wrapper for AWS authentication
   ../bigquery-with-bacalhau/spot-sso.sh deploy \
     --target aws \
     --region us-west-2 \
     --instance-type t3.medium \
     --nodes 3 \
     --spot \
     --additional-commands ./additional-commands.sh
   ```

3. **Verify Deployment**:
   ```bash
   # Check cluster status
   ../bigquery-with-bacalhau/spot-sso.sh status
   
   # SSH into a node to verify credentials
   ../bigquery-with-bacalhau/spot-sso.sh ssh node-1
   ls -la /bacalhau_data/credentials/
   ```

4. **Submit Jobs to Cluster**:
   ```bash
   # Submit databricks uploader job
   bacalhau job run jobs/databricks-uploader-job.yaml
   
   # Check job status
   bacalhau job list
   bacalhau job describe <job-id>
   ```

### Cluster Configuration

The cluster will:
- Use AWS Spot instances for cost savings
- Deploy credentials to `/bacalhau_data/credentials/` on each node
- Source credentials from `/opt/databricks-credentials.sh`
- Run the Databricks uploader as a Bacalhau job

## Troubleshooting

### Common Issues

1. **"Warehouse does not exist"**
   - Create a SQL warehouse in Databricks
   - Update `DATABRICKS_WAREHOUSE_ID` in `.env`

2. **"Access denied to S3"**
   - Verify AWS credentials: `aws sts get-caller-identity`
   - Check IAM role has access to `expanso-databricks-*` buckets
   - Run `uv run -s databricks-setup.py verify`

3. **"Table not found"**
   - Run setup: `uv run -s databricks-setup.py setup`
   - Check catalog name matches in `.env`

### Debug Commands

```bash
# Test Databricks connection
uv run -s test-databricks-connection.py

# Check AWS credentials and S3 access
aws sts get-caller-identity
aws s3 ls s3://expanso-databricks-ingestion-us-west-2/

# View pipeline state
cat state/s3-uploader/upload_state.json

# Check sensor data generation
sqlite3 sample-sensor/data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"

# View recent sensor readings
sqlite3 sample-sensor/data/sensor_data.db \
  "SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 5;"
```

## Contributing

1. Follow code style: `ruff check . && ruff format .`
2. Add tests for new features
3. Update documentation
4. Use `uv run -s` for all Python scripts

## Full Environment Configuration

Here's the complete `.env` configuration with all available options:

```bash
# Databricks Configuration
DATABRICKS_HOST=https://dbc-ae5355ab-8b4e.cloud.databricks.com
DATABRICKS_TOKEN=dapi1234567890abcdef  # Get from User Settings > Access Tokens
DATABRICKS_WAREHOUSE_ID=abcd1234efgh5678  # Get from SQL Warehouses page
DATABRICKS_CATALOG=expanso_databricks_workspace
DATABRICKS_SCHEMA=sensor_readings
DATABRICKS_DATABASE=expanso_databricks_workspace.sensor_data

# AWS Configuration  
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_BUCKET_PREFIX=expanso
S3_BUCKET_RAW=expanso-databricks-ingestion-us-west-2
S3_BUCKET_VALIDATED=expanso-databricks-validated-us-west-2
S3_BUCKET_ENRICHED=expanso-databricks-enriched-us-west-2
S3_BUCKET_AGGREGATED=expanso-databricks-aggregated-us-west-2

# Pipeline Configuration
UPLOAD_INTERVAL=60  # seconds between uploads
BATCH_SIZE=500  # records per batch
STATE_DIR=./state
SQLITE_PATH=./sample-sensor/data/sensor_data.db
SQLITE_TABLE_NAME=sensor_readings
TIMESTAMP_COL=timestamp
ONCE=false  # set to true for single run

# Sensor Simulator Configuration
SENSOR_ID=TURBINE_001
SENSOR_LOCATION=US-East Wind Farm
SENSOR_MANUFACTURER=Expanso Systems
SENSOR_MODEL=WT-5000
SENSOR_FIRMWARE_VERSION=3.2.1
SENSOR_INTERVAL=5  # seconds between readings
ANOMALY_PROBABILITY=0.05  # 5% chance of anomalies

# Processing Modes (managed by pipeline_manager.py)
# PROCESSING_MODE options: raw, schematized, filtered, emergency
# Use: uv run -s pipeline_manager.py --db sensor_data.db set <mode>
```