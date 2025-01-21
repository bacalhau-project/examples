#!/bin/bash

# Exit on error
set -e

# Read project ID from config.yaml using yq
PROJECT_ID=$(yq '.project.id' ../config.yaml)

# Get the service account email from the credentials file
SERVICE_ACCOUNT=$(jq -r '.client_email' log_uploader_credentials.json)

echo "Setting up minimal BigQuery permissions for log uploader service account: $SERVICE_ACCOUNT"

# Grant minimal BigQuery permissions at the dataset level
echo "Granting dataset-level permissions..."
bq show --format=json $PROJECT_ID:log_analytics > dataset_info.json

# Update the access field in the dataset info
jq --arg email "$SERVICE_ACCOUNT" '.access += [{"role": "WRITER", "userByEmail": $email}]' dataset_info.json > dataset_info_updated.json

echo "Updating dataset access..."
bq update --source dataset_info_updated.json $PROJECT_ID:log_analytics

# Grant minimal project-level permission for job creation
echo "Granting minimal project-level permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/bigquery.jobUser"

# Clean up
rm dataset_info.json dataset_info_updated.json

echo "Done. Service account $SERVICE_ACCOUNT now has minimal permissions to write to BigQuery tables." 