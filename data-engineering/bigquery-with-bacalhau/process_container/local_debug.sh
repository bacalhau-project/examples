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
    echo "  1 - Basic log collection"
    echo "  2 - With schema validation"
    echo "  3 - With IP sanitization"
    echo "  4 - With emergency logs and aggregation"
    echo
    echo "If input_file is not provided, defaults to logs/aperitivo_logs.log.20250115-190502"
    exit 1
}

# Check for version argument
if [ $# -lt 1 ]; then
    show_usage
fi

VERSION=$1
INPUT_FILE=${2:-"logs/access.log"}

# Validate version number
if [[ ! $VERSION =~ ^[1-4]$ ]]; then
    echo "Error: Version must be between 1 and 4"
    show_usage
fi

# Set version-specific environment variables
case $VERSION in
    1)
        echo "Running basic log collection version..."
        export DEBUG=true
        ;;
    2)
        echo "Running schema validation version..."
        export DEBUG=true
        ;;
    3)
        echo "Running IP sanitization version..."
        export DEBUG=true
        ;;
    4)
        echo "Running full version with emergency logs and aggregation..."
        export DEBUG=true
        export AGGREGATE_LOGS=true
        ;;
esac

# Run the processor
echo "Processing $INPUT_FILE using version $VERSION..."

# Truncate all tables before processing
echo "Truncating existing tables..."
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.log_results\`"
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.log_aggregates\`"
bq query --use_legacy_sql=false "TRUNCATE TABLE \`$PROJECT_ID.log_analytics.emergency_logs\`"
echo "Tables truncated successfully."

python3 log_process_${VERSION}.py "$INPUT_FILE" "SELECT * FROM log_data"