#!/bin/bash

# Exit on error
set -e

# Read project ID from config.yaml
PROJECT_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['project']['id'])")

echo "Ensuring all required columns exist in table: $PROJECT_ID.log_analytics.log_results"

# First, drop the timestamp columns if they exist with wrong type
echo "Dropping timestamp columns to recreate with correct type..."
bq query --use_legacy_sql=false \
"ALTER TABLE \`$PROJECT_ID.log_analytics.log_results\`
DROP COLUMN IF EXISTS timestamp,
DROP COLUMN IF EXISTS sync_time"

# Add or modify columns to ensure correct schema
echo "Adding/updating columns..."
bq query --use_legacy_sql=false \
"ALTER TABLE \`$PROJECT_ID.log_analytics.log_results\`
ADD COLUMN IF NOT EXISTS region STRING,
ADD COLUMN IF NOT EXISTS nodeName STRING,
ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP,
ADD COLUMN IF NOT EXISTS version STRING,
ADD COLUMN IF NOT EXISTS message STRING,
ADD COLUMN IF NOT EXISTS project_id STRING,
ADD COLUMN IF NOT EXISTS sync_time TIMESTAMP,
ADD COLUMN IF NOT EXISTS remote_log_id STRING,
ADD COLUMN IF NOT EXISTS hostname STRING,
ADD COLUMN IF NOT EXISTS public_ip STRING,
ADD COLUMN IF NOT EXISTS private_ip STRING,
ADD COLUMN IF NOT EXISTS alert_level STRING,
ADD COLUMN IF NOT EXISTS provider STRING"

# Verify the columns and their types
echo -e "\nVerifying columns..."
bq query --use_legacy_sql=false --format=pretty \
"WITH required_columns AS (
  SELECT column_name, data_type
  FROM UNNEST([
    STRUCT('region' as column_name, 'STRING' as data_type),
    ('nodeName', 'STRING'),
    ('timestamp', 'TIMESTAMP'),
    ('version', 'STRING'),
    ('message', 'STRING'),
    ('project_id', 'STRING'),
    ('sync_time', 'TIMESTAMP'),
    ('remote_log_id', 'STRING'),
    ('hostname', 'STRING'),
    ('public_ip', 'STRING'),
    ('private_ip', 'STRING'),
    ('alert_level', 'STRING'),
    ('provider', 'STRING')
  ])
)
SELECT 
  c.column_name,
  c.data_type as current_type,
  r.data_type as required_type,
  CASE 
    WHEN c.data_type = r.data_type THEN '✓'
    ELSE '✗'
  END as matches
FROM \`$PROJECT_ID.log_analytics\`.INFORMATION_SCHEMA.COLUMNS c
RIGHT JOIN required_columns r
  ON c.column_name = r.column_name
WHERE c.table_name = 'log_results'
ORDER BY r.column_name"

echo -e "\nDone. All required columns should now exist with correct types." 