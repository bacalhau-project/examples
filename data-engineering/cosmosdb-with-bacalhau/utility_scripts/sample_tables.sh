#!/bin/bash

# Default config path
CONFIG_PATH="../config.yaml"
if [ -n "$1" ]; then
    CONFIG_PATH="$1"
fi

# List of tables to sample
TABLES=("raw_logs" "log_results" "log_aggregates" "emergency_logs")

# Loop through each table and sample rows
for TABLE in "${TABLES[@]}"; do
    echo "Sampling 5 rows from table: $TABLE"
    uv run -s ../duckdb-plus-cosmos/query.py \
        --config "$CONFIG_PATH" \
        --query "SELECT * FROM log_analytics.$TABLE LIMIT 5;"
    echo "----------------------------------------"
done