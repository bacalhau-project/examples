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

# Create raw_logs table first - this is our foundation
echo "Dropping raw_logs table if exists..."
bq rm -f -t "$PROJECT_ID:log_analytics.raw_logs"

echo "Creating raw_logs table with basic schema..."
bq query --use_legacy_sql=false \
"CREATE TABLE \`$PROJECT_ID.log_analytics.raw_logs\` (
    raw_line STRING,
    upload_time TIMESTAMP
)"

# Drop and recreate log_results table to fix schema
echo "Dropping log_results table to fix schema..."
bq rm -f -t "$PROJECT_ID:log_analytics.log_results"

echo "Creating log_results table with correct schema..."
bq query --use_legacy_sql=false \
"CREATE TABLE \`$PROJECT_ID.log_analytics.log_results\` (
    project_id STRING,
    region STRING,
    nodeName STRING,
    hostname STRING,
    provider STRING,
    sync_time TIMESTAMP,
    ip STRING,
    user_id STRING,
    timestamp TIMESTAMP,
    method STRING,
    path STRING,
    protocol STRING,
    status INTEGER,
    bytes INTEGER,
    referer STRING,
    user_agent STRING,
    status_category STRING
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
    ok_count INT64,
    redirect_count INT64,
    not_found_count INT64,
    system_error_count INT64,
    total_count INT64,
    total_bytes INT64,
    avg_bytes FLOAT64
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
    STRUCT('raw_logs' as table_name, 'timestamp' as column_name, 'TIMESTAMP' as data_type),
    ('raw_logs', 'raw_line', 'STRING'),
    ('raw_logs', 'upload_time', 'TIMESTAMP'),
    ('log_results', 'project_id', 'STRING'),
    ('log_results', 'region', 'STRING'),
    ('log_results', 'nodeName', 'STRING'),
    ('log_results', 'hostname', 'STRING'),
    ('log_results', 'provider', 'STRING'),
    ('log_results', 'sync_time', 'TIMESTAMP'),
    ('log_results', 'ip', 'STRING'),
    ('log_results', 'user_id', 'STRING'),
    ('log_results', 'timestamp', 'TIMESTAMP'),
    ('log_results', 'method', 'STRING'),
    ('log_results', 'path', 'STRING'),
    ('log_results', 'protocol', 'STRING'),
    ('log_results', 'status', 'INTEGER'),
    ('log_results', 'bytes', 'INTEGER'),
    ('log_results', 'referer', 'STRING'),
    ('log_results', 'user_agent', 'STRING'),
    ('log_results', 'status_category', 'STRING'),
    ('log_aggregates', 'project_id', 'STRING'),
    ('log_aggregates', 'region', 'STRING'),
    ('log_aggregates', 'nodeName', 'STRING'),
    ('log_aggregates', 'provider', 'STRING'),
    ('log_aggregates', 'hostname', 'STRING'),
    ('log_aggregates', 'time_window', 'TIMESTAMP'),
    ('log_aggregates', 'ok_count', 'INT64'),
    ('log_aggregates', 'redirect_count', 'INT64'),
    ('log_aggregates', 'not_found_count', 'INT64'),
    ('log_aggregates', 'system_error_count', 'INT64'),
    ('log_aggregates', 'total_count', 'INT64'),
    ('log_aggregates', 'total_bytes', 'INT64'),
    ('log_aggregates', 'avg_bytes', 'FLOAT64'),
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