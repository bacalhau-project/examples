#!/bin/bash

# Load the project ID from the config file using yq - at '../config.yaml' by default, or first argument if provided
PROJECT_ID=$(yq '.bigquery.project_id' ../config.yaml)
if [ -z "$PROJECT_ID" ]; then
  if [ -n "$1" ]; then
    PROJECT_ID=$1
  else
    echo "Error: PROJECT_ID not found in config.yaml or provided as argument."
    exit 1
  fi
fi

# List of tables to sample
TABLES=("raw_logs" "log_results" "log_aggregates" "emergency_logs")

# Loop through each table and sample rows
for TABLE in "${TABLES[@]}"; do
  echo "Sampling 5 rows from table: $TABLE"
  bq query --use_legacy_sql=false \
    "SELECT * FROM \`$PROJECT_ID.log_analytics.$TABLE\` LIMIT 5"
  echo "----------------------------------------"
done