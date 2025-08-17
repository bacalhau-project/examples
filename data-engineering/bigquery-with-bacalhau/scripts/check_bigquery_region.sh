#!/bin/bash
# check_bigquery_region.sh - Check BigQuery dataset location/region

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <dataset_name> [project_id]"
    echo ""
    echo "Examples:"
    echo "  $0 sensor_analytics                    # Uses current project"
    echo "  $0 sensor_analytics my-project-id      # Specify project"
    echo ""
    echo "You can also use bq command directly:"
    echo "  bq show --dataset [PROJECT_ID:]DATASET_NAME"
    exit 1
fi

DATASET="$1"
PROJECT_ID="${2:-}"

# Check if bq command is available
if ! command -v bq &> /dev/null; then
    echo "Error: bq command not found. Please install Google Cloud SDK:"
    echo "  https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Construct dataset reference
if [ -n "$PROJECT_ID" ]; then
    DATASET_REF="${PROJECT_ID}:${DATASET}"
else
    DATASET_REF="$DATASET"
fi

echo "Checking location for dataset: $DATASET_REF"
echo "----------------------------------------"

# Get dataset info
if bq show --dataset --format=prettyjson "$DATASET_REF" 2>/dev/null; then
    echo ""
    echo "Location extracted:"
    bq show --dataset --format=json "$DATASET_REF" 2>/dev/null | jq -r '.location'
else
    echo "Error: Could not retrieve dataset information"
    echo ""
    echo "Possible issues:"
    echo "1. Dataset doesn't exist"
    echo "2. No access permissions"
    echo "3. Not authenticated (run: gcloud auth login)"
    echo "4. Wrong project ID"
    exit 1
fi