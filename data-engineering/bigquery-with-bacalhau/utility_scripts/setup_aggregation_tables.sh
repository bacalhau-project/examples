#!/bin/bash

# Exit on error
set -e

# Read project ID from config.yaml
PROJECT_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['project']['id'])")

echo "Creating aggregation tables in project: $PROJECT_ID"

# Create table for 5-minute aggregated logs
echo "Creating aggregated logs table..."
bq query --use_legacy_sql=false \
"CREATE TABLE IF NOT EXISTS \`$PROJECT_ID.log_analytics.log_aggregates\`
(
  project_id STRING,
  region STRING,
  nodeName STRING,
  provider STRING,
  hostname STRING,
  time_window TIMESTAMP,
  log_count INT64,
  messages ARRAY<STRING>
)"

# Create table for emergency events
echo "Creating emergency logs table..."
bq query --use_legacy_sql=false \
"CREATE TABLE IF NOT EXISTS \`$PROJECT_ID.log_analytics.emergency_logs\`
(
  project_id STRING,
  region STRING,
  nodeName STRING,
  provider STRING,
  hostname STRING,
  timestamp TIMESTAMP,
  version STRING,
  message STRING,
  remote_log_id STRING,
  alert_level STRING,
  public_ip STRING,
  private_ip STRING
)"

echo "Done. Created tables:"
echo "- $PROJECT_ID.log_analytics.log_aggregates (5-minute windows)"
echo "- $PROJECT_ID.log_analytics.emergency_logs (immediate alerts)"
echo
echo "To use aggregation mode, set environment variable:"
echo "AGGREGATE_LOGS=true" 