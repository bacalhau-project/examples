# Environment-Based Configuration Guide

This guide explains how to configure and run the Pipeline v2 using environment variables, eliminating the need for manual command-line arguments.

## Overview

All pipeline configuration is now managed through a `.env` file, making it easier to:
- Store credentials securely
- Switch between environments (dev/staging/prod)
- Share configurations across team members
- Reduce typing errors

## Initial Setup

### 1. Create Environment File

```bash
# First time setup - creates .env from template
./start-pipeline.sh

# This will create .env from .env.example
# You'll be prompted to edit the file
```

### 2. Configure Environment Variables

Edit `.env` with your specific values:

```bash
# GitHub/Docker Configuration (for container deployment)
GITHUB_TOKEN=ghp_your-actual-token-here
GITHUB_USER=bacalhau-project
REGISTRY=ghcr.io
ORGANIZATION_NAME=bacalhau-project
IMAGE_NAME=databricks-uploader

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012  # Your AWS account ID

# S3 Configuration
S3_BUCKET_PREFIX=your-company  # IMPORTANT: Set your company name
S3_REGION=${AWS_REGION}

# Databricks Configuration
DATABRICKS_HOST=your-workspace.cloud.databricks.com  # IMPORTANT: Your workspace
DATABRICKS_HTTP_PATH=/sql/1.0/endpoints/your-endpoint-id  # IMPORTANT: Your endpoint
DATABRICKS_TOKEN=dapi-your-token-here  # IMPORTANT: Your token
DATABRICKS_DATABASE=sensor_readings
DATABRICKS_ACCOUNT_ID=414351767826  # Databricks AWS account for IAM

# SQS Configuration (for anomaly notifications)
SQS_QUEUE_NAME=sensor-anomaly-notifications
SQS_REGION=${AWS_REGION}

# SQLite Source Database
SQLITE_PATH=sensor_data.db
SQLITE_TABLE_NAME=sensor_data
TIMESTAMP_COL=timestamp

# Processing Configuration
BATCH_SIZE=500
UPLOAD_INTERVAL=60
STATE_DIR=./state
LOG_LEVEL=INFO

# Monitoring Dashboard
MONITORING_PORT=8000
API_HOST=0.0.0.0
```

### 3. Validate Environment

```bash
# Load and validate all environment variables
source setup-environment.sh

# This will:
# - Check all required variables are set
# - Validate AWS credentials
# - Show derived S3 bucket names
# - Create state directory if needed
```

## Quick Start Commands

The `start-pipeline.sh` script provides all common operations:

### One-Time Setup
```bash
# Create S3 buckets and Databricks configurations
./start-pipeline.sh setup
```

### Configure Pipeline
```bash
# Set active scenarios
./start-pipeline.sh set-scenario "raw schematized lineage"

# Available scenarios:
# - raw: Direct pass-through with lineage
# - schematized: Validation with error routing
# - lineage: Enrich with metadata
# - multi_destination: Archive + aggregations
# - notification: SQS alerts for anomalies
```

### Run Pipeline
```bash
# Test run (dry mode - no uploads)
./start-pipeline.sh dry-run

# Live run (uploads to S3)
./start-pipeline.sh run

# Check status
./start-pipeline.sh status

# Monitor S3 uploads
./start-pipeline.sh monitor
```

## Environment Variables Reference

### Required Variables

These must be set for the pipeline to function:

| Variable | Description | Example |
|----------|-------------|---------|
| `S3_BUCKET_PREFIX` | Prefix for all S3 bucket names | `acme-corp` |
| `S3_REGION` | AWS region for S3 buckets | `us-east-1` |
| `DATABRICKS_HOST` | Databricks workspace URL | `acme.cloud.databricks.com` |
| `DATABRICKS_HTTP_PATH` | SQL endpoint path | `/sql/1.0/endpoints/abc123` |
| `DATABRICKS_TOKEN` | Databricks access token | `dapi-xxxxx` |
| `SQS_QUEUE_NAME` | SQS queue for notifications | `sensor-anomalies` |

### Optional Variables

These have sensible defaults:

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `DATABRICKS_DATABASE` | Database name | `sensor_data` |
| `SQLITE_PATH` | Source database | `sensor_data.db` |
| `BATCH_SIZE` | Records per batch | `500` |
| `UPLOAD_INTERVAL` | Seconds between runs | `60` |
| `STATE_DIR` | State file directory | `./state` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `MONITORING_PORT` | Dashboard port | `8000` |

### Derived Variables

These are automatically set based on other variables:

```bash
S3_BUCKET_RAW=${S3_BUCKET_PREFIX}-databricks-raw-${S3_REGION}
S3_BUCKET_SCHEMATIZED=${S3_BUCKET_PREFIX}-databricks-schematized-${S3_REGION}
S3_BUCKET_ERROR=${S3_BUCKET_PREFIX}-databricks-error-${S3_REGION}
S3_BUCKET_ARCHIVAL=${S3_BUCKET_PREFIX}-databricks-archival-${S3_REGION}
S3_BUCKET_AGGREGATED=${S3_BUCKET_PREFIX}-databricks-aggregated-${S3_REGION}
```

## Running Individual Components

All scripts now use environment variables by default:

```bash
# Always load environment first
source setup-environment.sh

# Then run any component
./pipeline_orchestrator.py
./pipeline_manager_v2.py get
./monitoring_dashboard.py
./lineage_enricher.py
./schematization_pipeline.py
```

## Multiple Environments

To manage multiple environments (dev/staging/prod):

```bash
# Create environment-specific files
cp .env .env.dev
cp .env .env.staging
cp .env .env.prod

# Load specific environment
cp .env.dev .env && source setup-environment.sh

# Or use a wrapper script
#!/bin/bash
export ENV=${1:-dev}
cp .env.$ENV .env
source setup-environment.sh
./pipeline_orchestrator.py
```

## Docker Deployment

The environment variables support Docker deployment:

```bash
# Build image
docker build -t $REGISTRY/$ORGANIZATION_NAME/$IMAGE_NAME:latest .

# Run with environment file
docker run --env-file .env \
  -v $(pwd)/sensor_data.db:/app/sensor_data.db \
  $REGISTRY/$ORGANIZATION_NAME/$IMAGE_NAME:latest

# Or use docker-compose
docker-compose up
```

## Troubleshooting

### Missing Environment Variables
```bash
# Check which variables are set
env | grep -E "S3_|DATABRICKS_|AWS_" | sort

# Reload environment
source setup-environment.sh
```

### Wrong S3 Bucket Names
```bash
# Verify bucket names
echo $S3_BUCKET_RAW
echo $S3_BUCKET_SCHEMATIZED

# Should match pattern: {prefix}-databricks-{type}-{region}
```

### Permission Errors
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify S3 access
aws s3 ls s3://$S3_BUCKET_RAW/
```

## Security Best Practices

1. **Never commit `.env` to git**
   ```bash
   # Ensure .env is in .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment-specific files**
   ```bash
   # Keep templates in repo
   git add .env.example
   
   # Keep actual configs local
   # .env.dev, .env.prod, etc.
   ```

3. **Rotate credentials regularly**
   - Update Databricks tokens monthly
   - Rotate AWS access keys quarterly
   - Use IAM roles when possible

4. **Mask sensitive values in logs**
   - The setup script automatically masks tokens
   - Check logs before sharing

## Next Steps

1. Complete environment setup: `source setup-environment.sh`
2. Create infrastructure: `./start-pipeline.sh setup`
3. Configure pipeline: `./start-pipeline.sh set-scenario "raw schematized lineage"`
4. Test pipeline: `./start-pipeline.sh dry-run`
5. Run pipeline: `./start-pipeline.sh run`
6. Monitor: Open http://localhost:8000 in browser