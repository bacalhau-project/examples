# Databricks with Bacalhau Data Pipeline

A production-ready data pipeline that demonstrates edge-to-cloud data ingestion, designed for IoT sensor data collection and processing. The system uploads data from SQLite databases on edge nodes to S3 buckets, with intelligent routing based on data characteristics (raw, aggregated, emergency, etc.).

## 🔧 Configuration Variables

Set these variables at the beginning of your session:

```bash
# AWS Configuration
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"

# S3 Bucket Configuration
export S3_PREFIX="expanso"
export S3_REGION="us-west-2"

# Bucket Names (automatically generated from prefix and region)
export S3_BUCKET_RAW="${S3_PREFIX}-databricks-raw-${S3_REGION}"
export S3_BUCKET_SCHEMATIZED="${S3_PREFIX}-databricks-schematized-${S3_REGION}"
export S3_BUCKET_AGGREGATED="${S3_PREFIX}-databricks-aggregated-${S3_REGION}"
export S3_BUCKET_EMERGENCY="${S3_PREFIX}-databricks-emergency-${S3_REGION}"

# Database Paths
export SENSOR_DB_PATH="../sample-sensor/data/sensor_data.db"
export CONFIG_PATH="../databricks-uploader-config.yaml"

# Optional: Databricks Configuration (for future integration)
export DATABRICKS_HOST="https://your-workspace.databricks.com"
export DATABRICKS_TOKEN="your-token"
```

## 📋 Overview

This project implements a continuous data pipeline that:
1. **Collects** sensor data in SQLite databases on edge nodes
2. **Uploads** data incrementally to S3 buckets in Parquet format
3. **Routes** data based on pipeline configuration (raw, schematized, aggregated, emergency)
4. **Manages** pipeline state atomically to prevent conflicts
5. **Integrates** with Databricks for analytics (future Auto Loader ingestion)

### Key Features

- **Atomic Pipeline Management**: Database-driven configuration prevents race conditions
- **Incremental Processing**: Tracks last uploaded timestamp for efficient data transfer
- **Auto-Detection**: Automatically discovers tables and timestamp columns
- **Flexible Routing**: Route data to different S3 buckets based on processing needs
- **Production-Ready**: WAL mode, proper error handling, graceful shutdowns
- **Container-Based**: Docker deployment for sensor generation and uploading
- **Cost-Optimized**: Designed for AWS Spot instances and S3 lifecycle policies

## 🚀 Quick Start

**Important**: All commands should be run from the main `databricks-with-bacalhau` directory.

```bash
# 1. Set configuration variables (see Configuration Variables section above)
source ./set-environment.sh  # Or manually export the variables

# 2. Start the sensor data generator
# Option A: Using Docker
./start-sensor.sh

# Option B: Using local Python (no Docker required)
./start-sensor-local.sh

# 3. Create S3 buckets (first time only)
./scripts/create-s3-buckets-admin.sh --prefix ${S3_PREFIX} --region ${S3_REGION}

# 4. Run the S3 uploader
# Run once:
uv run -s databricks-uploader/sqlite_to_s3_uploader.py --config databricks-uploader-config.yaml --once

# Or run continuously:
uv run -s databricks-uploader/sqlite_to_s3_uploader.py --config databricks-uploader-config.yaml

# 5. Check pipeline status
uv run -s pipeline-manager/pipeline_controller.py --db sample-sensor/data/sensor_data.db get

# 6. Test the entire pipeline
./test-sensor-pipeline.sh
```

## 📋 Prerequisites

1. **Docker** - For running the sensor data generator
2. **UV** - Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
3. **AWS Credentials** - With S3 read/write permissions
4. **S3 Buckets** - Created using the provided scripts (see Installation)

Optional:
- **Databricks Workspace** - For querying uploaded data
- **AWS CLI** - For bucket management (`brew install awscli`)

## 🏗️ Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Sensor Container│────▶│    SQLite    │────▶│  S3 Uploader    │
│ (Data Generator)│     │   Database   │     │   (Python)      │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │                      │
                               ▼                      ▼
                      ┌──────────────┐       ┌──────────────┐
                      │Pipeline Config│       │  S3 Buckets  │
                      │(Atomic State) │       │  (Parquet)   │  
                      └──────────────┘       └──────────────┘
```

### Component Details

1. **Sensor Container** (`utility_containers/sensor-log-generator/`)
   - Generates realistic IoT sensor data
   - Writes to SQLite with proper transaction handling
   - Configurable anomaly injection
   - WAL mode with checkpointing for corruption prevention

2. **Pipeline Manager** (`databricks-uploader/pipeline_manager.py`)
   - Atomic pipeline configuration stored in SQLite
   - Prevents race conditions between multiple processes
   - Tracks execution history and statistics
   - CLI interface for operations teams

3. **S3 Uploader** (`databricks-uploader/sqlite_to_s3_uploader.py`)
   - Incremental data upload (only new records)
   - Automatic table and timestamp detection
   - Configurable batch sizes and intervals
   - Routes to different buckets based on pipeline type

### Pipeline Types

- **raw**: Unprocessed sensor data → `{prefix}-databricks-raw-{region}`
- **schematized**: Schema-validated data → `{prefix}-databricks-schematized-{region}`  
- **aggregated**: Summarized data → `{prefix}-databricks-aggregated-{region}`
- **emergency**: Critical alerts → `{prefix}-databricks-emergency-{region}`

## 📦 Installation & Setup

### Step 1: Create S3 Buckets (Admin User)

Use your admin AWS credentials to create and configure the buckets:

```bash
cd scripts

# Create buckets with full configuration (versioning, encryption, etc.)
./create-s3-buckets-admin.sh \
  --prefix ${S3_PREFIX} \
  --region ${S3_REGION} \
  --create-folders

# This creates and configures:
# - ${S3_BUCKET_RAW}
# - ${S3_BUCKET_SCHEMATIZED}
# - ${S3_BUCKET_AGGREGATED}
# - ${S3_BUCKET_EMERGENCY}
```

### Step 2: Grant Access to Application User (Optional)

If using a restricted IAM user for the uploader:

```bash
# Grant S3 access to the application user
./grant-s3-access-to-user.sh \
  --user expanso-databricks-s3-user \
  --prefix ${S3_PREFIX} \
  --region ${S3_REGION}

# Test access with the restricted user credentials
export AWS_ACCESS_KEY_ID="restricted-user-key"
export AWS_SECRET_ACCESS_KEY="restricted-user-secret"
./test-s3-access.sh ${S3_PREFIX} ${S3_REGION}
```

### Step 3: Configure Credentials

#### Option A: File-Based Setup (Production Style)

```bash
# Create credentials directory
mkdir -p credentials

# Add your AWS credentials file
cat > credentials/expanso-s3-env.sh << 'EOF'
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_REGION="us-west-2"
EOF

# Add S3 configuration
cat > credentials/expanso-databricks-s3.yaml << 'EOF'
s3_bucket_prefix: "your-company"
s3_region: "us-west-2" 
s3_buckets:
  raw: "your-company-databricks-raw-us-west-2"
  schematized: "your-company-databricks-schematized-us-west-2"
  aggregated: "your-company-databricks-aggregated-us-west-2"
  emergency: "your-company-databricks-emergency-us-west-2"
EOF

# Generate .env file
uv run -s scripts/setup-credentials.py setup
```

#### Option B: Direct Environment Variables

```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret" 
export AWS_REGION="us-west-2"
export S3_BUCKET_PREFIX="your-company"
```

### Step 3: Start Sensor Data Generator

```bash
# IMPORTANT: Always use the Docker container for data generation
cd utility_containers/sensor-log-generator

# Start the sensor container
docker-compose up -d

# Verify it's running
docker-compose ps
docker-compose logs -f sensor  # Watch data generation

# The container will:
# - Generate sensor data every few seconds
# - Handle database transactions properly
# - Prevent corruption with WAL checkpointing
# - Create realistic IoT data patterns
```

### Step 4: Configure the Uploader

```bash
cd ../../databricks-with-bacalhau

# Review/edit the configuration
cat databricks-uploader-config.yaml

# Key settings:
# - sqlite: Path to sensor database
# - s3_configuration: Bucket names and region
# - interval: Upload frequency in seconds
# - max_batch_size: Records per upload
```

## 🚀 Running the Pipeline

### Development Mode

```bash
# 1. Ensure sensor container is running
cd utility_containers/sensor-log-generator
docker-compose ps  # Should show sensor container running

# 2. Run the uploader
cd ../../databricks-with-bacalhau/databricks-uploader

# One-time upload (for testing)
uv run -s sqlite_to_s3_uploader.py --config ${CONFIG_PATH} --once

# Continuous mode (uploads every ${UPLOAD_INTERVAL} seconds)
uv run -s sqlite_to_s3_uploader.py --config ${CONFIG_PATH}

# 3. Monitor uploads
# Check S3 buckets for uploaded files
aws s3 ls s3://${S3_BUCKET_RAW}/raw/ --recursive
```

### Production Deployment

#### Using Docker

```bash
cd databricks-uploader

# Build the container
docker build -t databricks-uploader .

# Run with mounted data and credentials
docker run -d \
  --name uploader \
  -v $(pwd)/../sample-sensor/data:/data \
  -v $(pwd)/../databricks-uploader-config.yaml:/config.yaml \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_REGION=us-west-2 \
  databricks-uploader \
  uv run -s sqlite_to_s3_uploader.py --config /config.yaml
```

#### Using AWS Spot Instances

```bash
# Deploy on cost-effective Spot instances
curl -L https://tada.wang/install.sh | bash -s -- create
```

## 🔄 Pipeline Management

The pipeline type determines which S3 bucket receives the data. Use the `pipeline_manager.py` CLI to control routing.

### Viewing Current Pipeline

```bash
cd databricks-uploader

# Check current pipeline type
uv run -s pipeline_manager.py --db ${SENSOR_DB_PATH} get

# Example output:
Current pipeline configuration:
  Type: raw
  Updated: 2024-01-20 10:30:45
  Updated by: system
  Reason: Initial setup
```

### Changing Pipeline Type

```bash
# Route to aggregated bucket (summarized data)
uv run -s pipeline_manager.py --db ${SENSOR_DB_PATH} set aggregated

# Route to emergency bucket (critical alerts)
uv run -s pipeline_manager.py --db ${SENSOR_DB_PATH} set emergency

# Return to raw data collection
uv run -s pipeline_manager.py --db ${SENSOR_DB_PATH} set raw
```

### Viewing History

```bash
# See recent pipeline changes
uv run -s pipeline_manager.py --db ${SENSOR_DB_PATH} history --limit 10

# See execution statistics
uv run -s pipeline_manager.py --db ${SENSOR_DB_PATH} stats
```

### Pipeline Routing Logic

| Pipeline Type | Target Bucket | Use Case |
|--------------|---------------|----------|
| `raw` | `{prefix}-databricks-raw-{region}` | All sensor data, no filtering |
| `schematized` | `{prefix}-databricks-schematized-{region}` | Validated, enriched data |
| `aggregated` | `{prefix}-databricks-aggregated-{region}` | Summarized and aggregated data |
| `emergency` | `{prefix}-databricks-emergency-{region}` | Critical alerts requiring immediate attention |

## 🔍 Monitoring & Verification

### Check Upload Status

```bash
# View uploader state
cd databricks-uploader
cat state/s3-uploader/last_upload_state.json | jq .

# Check S3 bucket contents
aws s3 ls s3://${S3_BUCKET_RAW}/raw/ --recursive --human-readable

# Count uploaded files
aws s3 ls s3://${S3_BUCKET_RAW}/raw/ --recursive | wc -l
```

### Database Integrity

```bash
# Check sensor database health
sqlite3 ../sample-sensor/data/sensor_data.db "PRAGMA integrity_check;"

# View recent sensor readings
sqlite3 ../sample-sensor/data/sensor_data.db \
  "SELECT datetime(timestamp, 'unixepoch') as time, temperature, humidity \
   FROM sensor_readings ORDER BY timestamp DESC LIMIT 10;"

# Check pipeline config table
sqlite3 ../sample-sensor/data/sensor_data.db \
  "SELECT * FROM pipeline_config ORDER BY updated_at DESC LIMIT 5;"
```

### Troubleshooting Uploads

```bash
# Run uploader with debug output
uv run -s sqlite_to_s3_uploader.py --config ../databricks-uploader-config.yaml --once --debug

# Check for lock issues
lsof ../sample-sensor/data/sensor_data.db

# Force WAL checkpoint (if needed)
sqlite3 ../sample-sensor/data/sensor_data.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

## 📊 Databricks Integration (Future)

Once data is in S3, you can use Databricks Auto Loader for streaming ingestion:

### Create External Location

```sql
-- In Databricks SQL
CREATE STORAGE CREDENTIAL IF NOT EXISTS s3_sensor_data
WITH (AWS_IAM_ROLE = 'arn:aws:iam::YOUR_ACCOUNT:role/DatabricksS3Role');

CREATE EXTERNAL LOCATION IF NOT EXISTS sensor_data_location
URL 's3://your-company-databricks-raw-us-west-2/'
WITH (STORAGE CREDENTIAL s3_sensor_data);
```

### Auto Loader Setup

```python
# Databricks notebook
from pyspark.sql.functions import *

# Configure Auto Loader
df = spark.readStream \
  .format("cloudFiles") \
  .option("cloudFiles.format", "parquet") \
  .option("cloudFiles.schemaLocation", "/tmp/sensor_schema") \
  .option("cloudFiles.inferColumnTypes", "true") \
  .load("s3://your-company-databricks-raw-us-west-2/raw/")

# Write to Delta table
df.writeStream \
  .format("delta") \
  .outputMode("append") \
  .option("checkpointLocation", "/tmp/sensor_checkpoint") \
  .trigger(processingTime="10 seconds") \
  .table("sensor_data.raw_readings")
```

## ⚙️ Configuration Reference

### databricks-uploader-config.yaml

```yaml
# SQLite Configuration
sqlite: "../sample-sensor/data/sensor_data.db"  # Path to sensor database
sqlite_table: "sensor_readings"  # Optional - auto-detected
timestamp_col: "timestamp"       # Optional - auto-detected

# S3 Configuration
s3_configuration:
  enabled: true
  region: "us-west-2"
  prefix: "your-company"         # Used for bucket naming
  buckets:                       # Explicit bucket names
    raw: "your-company-databricks-raw-us-west-2"
    schematized: "your-company-databricks-schematized-us-west-2"
    aggregated: "your-company-databricks-aggregated-us-west-2"
    emergency: "your-company-databricks-emergency-us-west-2"

# Processing Configuration  
state_dir: "state/s3-uploader"   # Where to store upload state
interval: 30                     # Upload frequency in seconds
max_batch_size: 500             # Records per batch
enable_auto_detection: true      # Auto-detect tables/columns

# S3 Upload Settings
s3_batch_size_mb: 50            # Target Parquet file size
s3_compression: "snappy"        # Parquet compression
```

### Environment Variables

The uploader supports these environment variables (override config file):

```bash
# AWS Credentials (required)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-west-2

# Override config values
SQLITE_PATH=/custom/path/sensor.db
UPLOAD_INTERVAL=60              # Upload every minute
STATE_DIR=/var/lib/uploader/state
ONCE=true                       # Run once then exit
```

## 🔧 Troubleshooting

### Database Issues

**"Database is locked" error**
```bash
# Check what's using the database
lsof ../sample-sensor/data/sensor_data.db

# Ensure sensor container is running properly
cd utility_containers/sensor-log-generator
docker-compose ps
docker-compose restart sensor
```

**"Database disk image is malformed" error**
```bash
# The sensor container now includes corruption prevention
# If you still see this, rebuild the container:
cd utility_containers/sensor-log-generator
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### S3 Upload Issues

**No files appearing in S3**
```bash
# Check if there's new data to upload
sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_readings WHERE timestamp > (SELECT MAX(timestamp) FROM sensor_readings) - 300;"

# Check uploader state
cat state/s3-uploader/last_upload_state.json

# Run with debug logging
uv run -s sqlite_to_s3_uploader.py --config ../databricks-uploader-config.yaml --once --debug
```

**S3 permission denied**
```bash  
# Verify AWS credentials
aws sts get-caller-identity

# Test S3 access
aws s3 ls s3://your-company-databricks-raw-us-west-2/

# Check IAM permissions include:
# - s3:PutObject
# - s3:GetObject  
# - s3:ListBucket
```

### Pipeline Management Issues

**Pipeline changes not taking effect**
```bash
# Verify pipeline was changed
uv run -s pipeline_manager.py --db sensor_data.db get

# Check if uploader is reading the correct database
# The uploader logs which pipeline it's using

# Restart uploader to ensure it picks up changes
```

## 🛠️ Development

### Project Structure

```
databricks-with-bacalhau/
├── databricks-uploader/         # S3 uploader components
│   ├── sqlite_to_s3_uploader.py    # Main uploader script
│   ├── pipeline_manager.py         # Pipeline state management
│   ├── Dockerfile                  # Container image
│   └── README.md                   # Detailed uploader docs
├── scripts/                     # Infrastructure setup
│   ├── create-s3-buckets.sh       # S3 bucket creation
│   ├── setup-credentials.py       # Credential management
│   └── fix_sensor_database_corruption.sh
├── sample-sensor/              # Example sensor data
│   └── data/                      # SQLite database location
├── utility_containers/         # Data generation
│   └── sensor-log-generator/      # Sensor container
└── databricks-uploader-config.yaml # Main configuration
```

### Key Design Decisions

1. **Atomic Pipeline Management**: Pipeline configuration stored in SQLite (not config files) to prevent race conditions between uploader and management processes.

2. **WAL Mode Everything**: Both sensor writer and uploader use SQLite WAL mode for better concurrency and corruption prevention.

3. **Incremental Processing**: State tracking ensures only new data is uploaded, critical for edge computing with limited bandwidth.

4. **Container-First**: Sensor data generation must use Docker to ensure proper database handling and realistic data patterns.

### Adding New Features

**New Pipeline Type**
```python
# 1. Add to pipeline_manager.py
class PipelineType(Enum):
    RAW = "raw"
    CUSTOM = "custom"  # New type

# 2. Add S3 bucket in config
buckets:
  custom: "company-databricks-custom-region"

# 3. Update uploader routing logic
```

**Custom Data Transformation**
```python
# In sqlite_to_s3_uploader.py, modify _upload_batch()
if pipeline_type == "custom":
    # Apply transformation
    df = df.filter(...)  # Your logic
```

## 🚨 Important Notes

### Database Corruption Prevention

This project includes extensive measures to prevent SQLite corruption:
- WAL mode with automatic checkpointing
- Graceful shutdown handling in sensor container  
- Proper transaction management
- See [PREVENT_DATABASE_CORRUPTION.md](PREVENT_DATABASE_CORRUPTION.md) for details

### Security Considerations

1. **Never commit credentials**: Use environment variables or credential files
2. **IAM Least Privilege**: Grant only required S3 permissions
3. **Encryption**: S3 buckets use SSE-S3 encryption by default
4. **Network**: Consider VPC endpoints for production deployments

### Performance Tuning

- **Batch Size**: Adjust `max_batch_size` based on network bandwidth
- **Upload Interval**: Balance between latency and efficiency
- **Parquet Compression**: Use `snappy` for speed, `gzip` for size
- **State Management**: Clean old state files periodically

## 📚 Additional Documentation

- [Databricks Uploader README](databricks-uploader/README.md) - Detailed uploader documentation
- [Database Corruption Prevention](PREVENT_DATABASE_CORRUPTION.md) - WAL management guide
- [Local Testing Guide](LOCAL_TESTING_GUIDE.md) - Step-by-step testing instructions

## 🤝 Contributing

1. Always use the sensor container for data generation
2. Test with `--once` flag before continuous mode
3. Use `uv run -s` for all Python scripts  
4. Update both READMEs when adding features
5. Follow existing error handling patterns

