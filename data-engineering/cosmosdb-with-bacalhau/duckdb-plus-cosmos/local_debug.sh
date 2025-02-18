#!/usr/bin/env bash

set -e

# Default environment settings
export LOGS_DIR=./logs
export CREDENTIALS_PATH=./log_uploader_credentials.json
export PROJECT_ID=bq-2501151036
export REGION=us-central1
export NODE_NAME=local-test
export CLOUD_PROVIDER=local

# Function to show usage
show_usage() {
    echo "Usage: $0 <version_number> [input_file]"
    echo "Version numbers:"
    echo "  0 - Basic log collection"
    echo "  1 - With schema validation"
    echo "  2 - With IP sanitization"
    echo "  3 - With emergency logs and aggregation"
    echo
    echo "If input_file is not provided, defaults to logs/access.log"
    exit 1
}

# Check for version argument
if [ $# -lt 1 ]; then
    show_usage
fi

VERSION=$1
INPUT_FILE=${2:-"logs/access.log"}

# Validate version number
if [[ ! $VERSION =~ ^[0-3]$ ]]; then
    echo "Error: Version must be between 0 and 3"
    show_usage
fi

# Set version-specific environment variables
case $VERSION in
    0)
        echo "Running basic log collection version..."
        ;;
    1)
        echo "Running schema validation version..."
        ;;
    2)
        echo "Running IP sanitization version..."
        ;;
    3)
        echo "Running full version with emergency logs and aggregation..."
        export AGGREGATE_LOGS=true
        ;;
esac

# Run the processor
echo "Processing $INPUT_FILE using version $VERSION..."

# Truncate all tables before processing
echo "Truncating existing tables..."
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.raw_logs\`"
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.log_results\`"
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.log_aggregates\`"
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.emergency_logs\`"
echo "Tables truncated successfully."

python3 log_process_"${VERSION}".py "$INPUT_FILE"