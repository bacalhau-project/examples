#!/bin/bash

# Exit on error
set -e

# Read project ID from config.yaml using yq
PROJECT_ID=$(yq e '.project.id' ../config.yaml)

echo "Creating and configuring tables in project: $PROJECT_ID"

echo "Checking if dataset exists..."
if ! bq show "$PROJECT_ID:log_analytics" &>/dev/null; then
    echo "Creating dataset..."
    bq mk --dataset --description "Log analytics dataset" "$PROJECT_ID:log_analytics"
else
    echo "Dataset already exists, skipping creation..."
fi

# Drop and recreate log_results table to fix schema
echo "Dropping log_results table to fix schema..."
bq rm -f -t "$PROJECT_ID:log_analytics.log_results"

echo "Creating log_results table with correct schema..."
bq query --use_legacy_sql=false \
"CREATE TABLE \`$PROJECT_ID.log_analytics.log_results\` (
    region STRING,
    nodeName STRING,
    timestamp TIMESTAMP,
    version STRING,
    message STRING,
    project_id STRING,
    sync_time TIMESTAMP,
    remote_log_id STRING,
    hostname STRING,
    alert_level STRING,
    provider STRING,
    source_module STRING,
    event_id STRING,
    ip STRING
)"

# Create aggregated logs table if it doesn't exist
echo "Dropping log_aggregates table to fix schema..."
bq rm -f -t "$PROJECT_ID:log_analytics.log_aggregates"

echo "Creating log_aggregates table with correct schema..."
bq query --use_legacy_sql=false \
"CREATE TABLE \`$PROJECT_ID.log_analytics.log_aggregates\` (
    project_id STRING,
    region STRING,
    nodeName STRING,
    provider STRING,
    hostname STRING,
    time_window TIMESTAMP,
    info_count INT64,
    warn_count INT64,
    error_count INT64,
    critical_count INT64,
    emergency_count INT64,
    alert_count INT64,
    debug_count INT64,
    total_count INT64
)"

# Drop and recreate emergency_logs table to fix schema
echo "Dropping emergency_logs table to fix schema..."
bq query --use_legacy_sql=false \
"DROP TABLE IF EXISTS \`$PROJECT_ID.log_analytics.emergency_logs\`"

echo "Creating emergency_logs table with correct schema..."
bq query --use_legacy_sql=false \
"CREATE TABLE \`$PROJECT_ID.log_analytics.emergency_logs\` (
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
    source_module STRING,
    event_id STRING,
    ip STRING,
    sync_time TIMESTAMP
)"

# Verify the columns and their types
echo -e "\nVerifying columns..."
bq query --use_legacy_sql=false --format=pretty \
"WITH required_columns AS (
  SELECT table_name, column_name, data_type
  FROM UNNEST([
    STRUCT('log_results' as table_name, 'region' as column_name, 'STRING' as data_type),
    ('log_results', 'nodeName', 'STRING'),
    ('log_results', 'timestamp', 'TIMESTAMP'),
    ('log_results', 'version', 'STRING'),
    ('log_results', 'message', 'STRING'),
    ('log_results', 'project_id', 'STRING'),
    ('log_results', 'sync_time', 'TIMESTAMP'),
    ('log_results', 'remote_log_id', 'STRING'),
    ('log_results', 'hostname', 'STRING'),
    ('log_results', 'alert_level', 'STRING'),
    ('log_results', 'provider', 'STRING'),
    ('log_results', 'source_module', 'STRING'),
    ('log_results', 'event_id', 'STRING'),
    ('log_results', 'ip', 'STRING'),
    ('log_aggregates', 'project_id', 'STRING'),
    ('log_aggregates', 'region', 'STRING'),
    ('log_aggregates', 'nodeName', 'STRING'),
    ('log_aggregates', 'provider', 'STRING'),
    ('log_aggregates', 'hostname', 'STRING'),
    ('log_aggregates', 'time_window', 'TIMESTAMP'),
    ('log_aggregates', 'info_count', 'INT64'),
    ('log_aggregates', 'warn_count', 'INT64'),
    ('log_aggregates', 'error_count', 'INT64'),
    ('log_aggregates', 'critical_count', 'INT64'),
    ('log_aggregates', 'emergency_count', 'INT64'),
    ('log_aggregates', 'alert_count', 'INT64'),
    ('log_aggregates', 'debug_count', 'INT64'),
    ('log_aggregates', 'total_count', 'INT64'),
    ('emergency_logs', 'project_id', 'STRING'),
    ('emergency_logs', 'region', 'STRING'),
    ('emergency_logs', 'nodeName', 'STRING'),
    ('emergency_logs', 'provider', 'STRING'),
    ('emergency_logs', 'hostname', 'STRING'),
    ('emergency_logs', 'timestamp', 'TIMESTAMP'),
    ('emergency_logs', 'version', 'STRING'),
    ('emergency_logs', 'message', 'STRING'),
    ('emergency_logs', 'remote_log_id', 'STRING'),
    ('emergency_logs', 'alert_level', 'STRING'),
    ('emergency_logs', 'ip', 'STRING'),
    ('emergency_logs', 'sync_time', 'TIMESTAMP')
  ])
)
SELECT 
  r.table_name,
  r.column_name,
  c.data_type as current_type,
  r.data_type as required_type,
  CASE 
    WHEN c.data_type = r.data_type THEN '✓'
    ELSE '✗'
  END as matches
FROM required_columns r
LEFT JOIN \`$PROJECT_ID.log_analytics\`.INFORMATION_SCHEMA.COLUMNS c
  ON c.table_name = r.table_name
  AND c.column_name = r.column_name
ORDER BY r.table_name, r.column_name"

echo -e "\nDone. All tables exist with correct schema." 