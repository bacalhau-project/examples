#!/bin/bash
# set-environment.sh - Set all required environment variables for the Databricks pipeline
#
# Usage: source ./set-environment.sh
#
# Edit this file with your actual values before sourcing

# AWS Configuration
# Option 1: Use AWS SSO (recommended)
# Run: aws sso login --profile your-profile
# Then: eval "$(aws configure export-credentials --profile your-profile --format env)"

# Option 2: Use temporary credentials with session token
# export AWS_SESSION_TOKEN="your-session-token"
# export AWS_ACCESS_KEY_ID="your-access-key"
# export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Option 3: Use permanent credentials (not recommended for production)
# export AWS_ACCESS_KEY_ID="your-access-key"
# export AWS_SECRET_ACCESS_KEY="your-secret-key"

export AWS_REGION="us-west-2"

# S3 Bucket Configuration
export S3_PREFIX="expanso"
export S3_REGION="us-west-2"

# Bucket Names (automatically generated from prefix and region)
export S3_BUCKET_RAW="${S3_PREFIX}-databricks-raw-${S3_REGION}"
export S3_BUCKET_SCHEMATIZED="${S3_PREFIX}-databricks-schematized-${S3_REGION}"
export S3_BUCKET_AGGREGATED="${S3_PREFIX}-databricks-aggregated-${S3_REGION}"
export S3_BUCKET_EMERGENCY="${S3_PREFIX}-databricks-emergency-${S3_REGION}"
export S3_BUCKET_REGIONAL="${S3_PREFIX}-databricks-regional-${S3_REGION}"

# Database Paths
export SENSOR_DB_PATH="../sample-sensor/data/sensor_data.db"
export CONFIG_PATH="../databricks-uploader-config.yaml"

# Processing Configuration
export UPLOAD_INTERVAL="30"  # seconds
export MAX_BATCH_SIZE="500"
export STATE_DIR="state"

# Optional: Databricks Configuration (for future integration)
# export DATABRICKS_HOST="https://your-workspace.databricks.com"
# export DATABRICKS_TOKEN="your-token"
# export DATABRICKS_DATABASE="sensor_data"
# export DATABRICKS_TABLE="sensor_readings"

# IAM Configuration
export IAM_USER="expanso-databricks-s3-user"
export IAM_ROLE="databricks-s3-storage-role"
export AWS_ACCOUNT_ID="767397752906"

echo "Environment variables set:"
echo "  AWS_REGION: ${AWS_REGION}"
if [ -n "$AWS_SESSION_TOKEN" ]; then
    echo "  AWS Auth: Using session token (temporary credentials)"
elif [ -n "$AWS_ACCESS_KEY_ID" ]; then
    echo "  AWS Auth: Using access key credentials"
else
    echo "  AWS Auth: No credentials set (will use default credential chain)"
fi
echo "  S3_PREFIX: ${S3_PREFIX}"
echo "  S3_REGION: ${S3_REGION}"
echo "  Buckets:"
echo "    - Raw: ${S3_BUCKET_RAW}"
echo "    - Schematized: ${S3_BUCKET_SCHEMATIZED}"
echo "    - Aggregated: ${S3_BUCKET_AGGREGATED}"
echo "    - Emergency: ${S3_BUCKET_EMERGENCY}"
echo "    - Regional: ${S3_BUCKET_REGIONAL}"
echo "  Database: ${SENSOR_DB_PATH}"
echo "  Config: ${CONFIG_PATH}"
