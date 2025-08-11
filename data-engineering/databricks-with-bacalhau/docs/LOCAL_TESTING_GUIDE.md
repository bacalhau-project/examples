# Local Testing Guide - Pipeline v2

This guide shows how to run the complete pipeline locally with three terminal windows.

## Prerequisites

1. **AWS Credentials**: Configure AWS CLI with appropriate credentials
   ```bash
   aws configure
   ```

2. **Environment Setup**: 
   ```bash
   # First time setup - creates .env from template
   ./start-pipeline.sh
   
   # Edit .env with your values
   nano .env  # or your preferred editor
   
   # Key variables to update:
   # - GITHUB_TOKEN (if using Docker registry)
   # - S3_BUCKET_PREFIX (your company name)
   # - DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
   # - AWS_REGION (if not us-east-1)
   
   # Load and validate environment
   source setup-environment.sh
   ```

3. **Python Dependencies**: All scripts use `uv` with inline dependencies (auto-installed)

## Quick Start Commands

For the fastest setup, use the start-pipeline.sh wrapper:

```bash
# 1. Initial setup (creates .env, validates environment, creates S3 buckets)
./start-pipeline.sh setup

# 2. Configure pipeline scenarios
./start-pipeline.sh set-scenario "raw schematized lineage"

# 3. Test run (dry mode)
./start-pipeline.sh dry-run

# 4. Run pipeline (live mode)
./start-pipeline.sh run

# 5. Check status
./start-pipeline.sh status

# 6. Monitor S3 uploads
./start-pipeline.sh monitor
```

## Terminal 1: Setup and Pipeline Orchestrator

### Initial Setup (One Time Only)

```bash
# Load environment variables
source setup-environment.sh

# Create S3 buckets and generate Auto Loader configs
./setup_databricks_autoloader.py \
  --prefix "$S3_BUCKET_PREFIX" \
  --region "$S3_REGION" \
  --databricks-account-id "$DATABRICKS_ACCOUNT_ID"

# Review generated configurations
ls -la databricks_autoloader_configs/
cat databricks_autoloader_configs/setup_instructions.md
```

### Running the Pipeline

```bash
# Always load environment first
source setup-environment.sh

# Check current scenarios
./pipeline_manager_v2.py get

# Set desired scenarios
./pipeline_manager_v2.py set raw schematized lineage --by "$USER"

# Or enable all scenarios
./pipeline_manager_v2.py set raw schematized lineage multi_destination notification --by "$USER"

# Dry run first to test without S3/SQS
./pipeline_orchestrator.py --dry-run --once

# Run continuously (uploads to S3)
./pipeline_orchestrator.py

# The orchestrator will show a live status table:
# ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
# ┃ Scenario           ┃ Status    ┃ Processed ┃ Success Rate ┃ Details          ┃
# ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
# │ raw                │ 🟢 Active │       100 │       100.0% │                  │
# │ schematized        │ 🟢 Active │       100 │       100.0% │ Valid: 95, Invalid: 5 │
# │ lineage            │ 🟢 Active │       100 │       100.0% │                  │
# │ multi_destination  │ ⚫ Inactive│         - │            - │                  │
# │ notification       │ ⚫ Inactive│         - │            - │                  │
# └────────────────────┴───────────┴───────────┴──────────────┴──────────────────┘
```

## Terminal 2: Pipeline Manager and Testing

### Monitor Pipeline Execution

```bash
# Load environment
source setup-environment.sh

# Watch execution history
watch -n 5 "./pipeline_manager_v2.py history --limit 10"

# View statistics
./pipeline_manager_v2.py stats

# Change scenarios on the fly
./pipeline_manager_v2.py set raw schematized multi_destination --by "$USER"
```

### Run Component Tests

```bash
# Test individual components
./lineage_enricher.py
./schematization_pipeline.py
./windowing_aggregator.py
./anomaly_notifier.py

# Test with real sensor data
./test_aggregation_with_real_data.py

# Test pipeline manager
./test_pipeline_manager_v2.py
```

## Terminal 3: Monitoring Dashboard

### Start the Monitoring Dashboard

```bash
# Update the monitoring dashboard for v2 (if needed)
./monitoring_dashboard.py

# Dashboard will be available at:
# - http://localhost:8000/          (Main dashboard)
# - http://localhost:8000/docs      (API documentation)
```

### Monitor S3 Uploads

```bash
# Load environment
source setup-environment.sh

# List recent uploads to each bucket
aws s3 ls s3://$S3_BUCKET_RAW/ --recursive | tail -20
aws s3 ls s3://$S3_BUCKET_SCHEMATIZED/ --recursive | tail -20
aws s3 ls s3://$S3_BUCKET_ERROR/ --recursive | tail -20
aws s3 ls s3://$S3_BUCKET_AGGREGATED/ --recursive | tail -20

# View a sample file (example)
aws s3 ls s3://$S3_BUCKET_SCHEMATIZED/validated/ --recursive | tail -1 | awk '{print $4}' | \
  xargs -I {} aws s3 cp s3://$S3_BUCKET_SCHEMATIZED/{} - | jq .
```

### Monitor SQS Queue (if notification scenario is active)

```bash
# Get queue URL
QUEUE_URL=$(aws sqs get-queue-url --queue-name $SQS_QUEUE_NAME --region $SQS_REGION --query 'QueueUrl' --output text)

# Check queue attributes
aws sqs get-queue-attributes --queue-url $QUEUE_URL --attribute-names All

# Receive messages (for testing)
aws sqs receive-message --queue-url $QUEUE_URL --max-number-of-messages 1 | jq .
```

## Databricks Setup

### 1. Configure Instance Profile

In Databricks workspace:
1. Go to Admin Console → Instance Profiles
2. Add the IAM role created by setup script
3. Note the role ARN from `databricks_autoloader_configs/setup_instructions.md`

### 2. Create Delta Tables

Run in Databricks SQL or notebook:

```sql
-- Create database
CREATE DATABASE IF NOT EXISTS sensor_data;
USE sensor_data;

-- Create tables (from setup_instructions.md)
-- ... (copy SQL from generated file)
```

### 3. Start Auto Loader

1. Create new Databricks notebook
2. Copy Auto Loader configuration from `databricks_autoloader_configs/autoloader_raw.py`
3. Run the notebook to start streaming from S3

### 4. Monitor in Databricks

```sql
-- Check incoming data
SELECT COUNT(*) as total_records,
       MAX(processed_at) as latest_record
FROM sensor_data.raw_sensor_data;

-- View recent records with lineage
SELECT sensor_id, 
       temperature,
       humidity,
       location,
       job_id,
       processed_at
FROM sensor_data.raw_sensor_data
ORDER BY processed_at DESC
LIMIT 20;

-- Check aggregated data
SELECT * 
FROM sensor_data.aggregated_sensor_data
WHERE window_start >= current_timestamp() - INTERVAL 1 HOUR
ORDER BY window_start DESC;
```

## Testing Scenarios

Always start with:
```bash
source setup-environment.sh
```

### 1. Test Raw Scenario
```bash
./pipeline_manager_v2.py set raw --by "$USER"
# Check S3: aws s3 ls s3://$S3_BUCKET_RAW/raw/ --recursive
```

### 2. Test Schematization with Errors
```bash
./pipeline_manager_v2.py set schematized --by "$USER"
# Valid records → aws s3 ls s3://$S3_BUCKET_SCHEMATIZED/validated/ --recursive
# Invalid records → aws s3 ls s3://$S3_BUCKET_ERROR/validation-errors/ --recursive
```

### 3. Test Multi-Destination
```bash
./pipeline_manager_v2.py set multi_destination --by "$USER"
# Check archival: aws s3 ls s3://$S3_BUCKET_ARCHIVAL/multi/ --recursive
# Check aggregated: aws s3 ls s3://$S3_BUCKET_AGGREGATED/1-minute/ --recursive
```

### 4. Test Anomaly Notifications
```bash
./pipeline_manager_v2.py set notification --by "$USER"
# Generate anomalies in sensor data
# Check SQS: aws sqs receive-message --queue-url $(aws sqs get-queue-url --queue-name $SQS_QUEUE_NAME --query 'QueueUrl' --output text)
```

## Troubleshooting

### Pipeline Not Processing Records
1. Check SQLite database has data: `sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_data;"`
2. Check state file: `cat state/orchestrator_state.json`
3. Reset state: `rm state/orchestrator_state.json`

### S3 Upload Errors
1. Check AWS credentials: `aws sts get-caller-identity`
2. Verify bucket exists: `aws s3 ls`
3. Check IAM permissions

### Databricks Auto Loader Not Working
1. Verify IAM role trust relationship
2. Check S3 bucket permissions
3. Review Auto Loader checkpoint location
4. Check Databricks cluster logs

### Component Errors
1. Run component test individually
2. Check validation spec: `cat sensor_validation_spec_v2.yaml`
3. Verify all environment variables are set

## Performance Tuning

- Adjust batch size in `pipeline-config-v2.yaml`
- Modify upload interval for faster/slower processing
- Configure windowing interval for aggregations
- Tune Auto Loader trigger interval in Databricks