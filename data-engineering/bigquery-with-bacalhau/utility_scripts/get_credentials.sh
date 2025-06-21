#!/bin/bash

# A script to automate the creation of a GCP service account and BigQuery dataset.

# --- Preamble: Configuration and Initialization ---

# Generate a random number to ensure unique resource names
RANDOM_SUFFIX=$RANDOM

# Default values
# These will be used if not overridden by the config file.
DEFAULT_PREFIX="bacalhau-and-bigquery"
DEFAULT_SERVICE_ACCOUNT_NAME="${DEFAULT_PREFIX}-sa-${RANDOM_SUFFIX}"
DEFAULT_DISPLAY_NAME="Auto-generated Service Account"
DEFAULT_DATASET_NAME="${DEFAULT_PREFIX}_dataset_${RANDOM_SUFFIX}"
DEFAULT_LOCATION="US"
DEFAULT_KEY_FILE_NAME="credentials.json"

# Check for required CONFIG_FILE environment variable
if [ -z "$CONFIG_FILE" ]; then
    echo "ERROR: CONFIG_FILE environment variable is required but not set"
    exit 1
fi

# Check if the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Configuration file '$CONFIG_FILE' does not exist"
    exit 1
fi

# --- Parse YAML Configuration ---

# Function to parse YAML values
parse_yaml() {
    local yaml_file="$1"
    local key="$2"

    # Use grep and sed to extract value for the given key
    grep "^${key}:" "$yaml_file" | sed "s/^${key}:[[:space:]]*//" | sed 's/^["'\'']//' | sed 's/["'\'']$//'
}

# Function to parse nested YAML values
parse_nested_yaml() {
    local yaml_file="$1"
    local parent_key="$2"
    local child_key="$3"

    # Extract the nested value using awk
    awk -v parent="$parent_key" -v child="$child_key" '
    BEGIN { in_section = 0 }
    /^[a-zA-Z_]/ && $1 == parent ":" { in_section = 1; next }
    /^[a-zA-Z_]/ && in_section { in_section = 0 }
    in_section && $1 == child ":" {
        gsub(/^[[:space:]]*[^[:space:]]*:[[:space:]]*/, "")
        gsub(/^["'\'']/, "")
        gsub(/["'\'']$/, "")
        print $0
        exit
    }
    ' "$yaml_file"
}

# Read configuration from YAML file
echo "INFO: Reading configuration from $CONFIG_FILE"

CONFIG_PROJECT_ID=$(parse_yaml "$CONFIG_FILE" "project_id")
CONFIG_DATASET=$(parse_yaml "$CONFIG_FILE" "dataset")
CONFIG_CREDENTIALS_PATH=$(parse_yaml "$CONFIG_FILE" "credentials_path")
CONFIG_REGION=$(parse_nested_yaml "$CONFIG_FILE" "metadata" "region")
CONFIG_NODE_ID=$(parse_yaml "$CONFIG_FILE" "node_id")

# --- Variable Assignment ---

# Assign variables, using config values or defaults
PROJECT_ID=${CONFIG_PROJECT_ID:-${PROJECT_ID:-""}}
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-$DEFAULT_SERVICE_ACCOUNT_NAME}
DISPLAY_NAME=${DISPLAY_NAME:-$DEFAULT_DISPLAY_NAME}
DATASET_NAME=${CONFIG_DATASET:-$DEFAULT_DATASET_NAME}
LOCATION=${CONFIG_REGION:-$DEFAULT_LOCATION}
KEY_FILE_NAME=${CONFIG_CREDENTIALS_PATH:-$DEFAULT_KEY_FILE_NAME}

# Extract just the filename if a full path was provided
if [[ "$KEY_FILE_NAME" == *"/"* ]]; then
    KEY_FILE_NAME=$(basename "$KEY_FILE_NAME")
fi

# --- Pre-flight Checks ---

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null
then
    echo "ERROR: gcloud command could not be found. Please install the Google Cloud CLI."
    exit 1
fi

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: PROJECT_ID is not set. Please set it in config.sh or as an environment variable."
    exit 1
fi

echo "--- Configuration ---"
echo "Config File:          $CONFIG_FILE"
echo "Project ID:           $PROJECT_ID"
echo "Service Account Name: $SERVICE_ACCOUNT_NAME"
echo "Service Account Key:  $KEY_FILE_NAME"
echo "BigQuery Dataset:     $DATASET_NAME"
echo "BigQuery Location:    $LOCATION"
echo "Node ID:              $CONFIG_NODE_ID"
echo "---------------------"
echo

# --- Execution ---

# 1. Create the Service Account
echo "INFO: Creating service account: $SERVICE_ACCOUNT_NAME..."
gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --project="$PROJECT_ID" \
    --display-name="$DISPLAY_NAME"

# Construct the full service account email
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 2. Grant IAM Roles
echo "INFO: Granting BigQuery Data Editor role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/bigquery.dataEditor"

echo "INFO: Granting BigQuery Job User role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/bigquery.jobUser"

# 3. Create and Download the Service Account Key
echo "INFO: Creating and downloading service account key to $KEY_FILE_NAME..."
gcloud iam service-accounts keys create "$KEY_FILE_NAME" \
    --iam-account="$SA_EMAIL"

# 4. Create the BigQuery Dataset
echo "INFO: Creating BigQuery dataset: $DATASET_NAME..."
bq --location="$LOCATION" mk -d \
    --project_id="$PROJECT_ID" \
    "$DATASET_NAME"

echo
echo "--- ✅ Setup Complete! ---"
echo
echo "Your service account and BigQuery dataset have been created."
echo "Your service account key is saved as: $KEY_FILE_NAME"
echo "Keep this file secure and do not commit it to version control."
