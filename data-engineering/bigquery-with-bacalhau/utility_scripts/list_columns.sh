#!/bin/bash

# Read project ID from config.yaml
PROJECT_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['project']['id'])")

echo "Listing columns for table: $PROJECT_ID.log_analytics.log_results"
echo

bq query --use_legacy_sql=false --format=pretty \
"SELECT 
  column_name,
  data_type,
  is_nullable
FROM \`$PROJECT_ID.log_analytics\`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = 'log_results'
ORDER BY ordinal_position" 