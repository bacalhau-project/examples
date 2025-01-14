#!/bin/bash

# Exit on error
set -e

# Read project ID from config.yaml
PROJECT_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('../config.yaml'))['project']['id'])")

echo "Setting up log uploader service account for project: $PROJECT_ID"

# Create a service account specifically for log uploads
SA_NAME="log-uploader"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

echo "Creating service account..."
gcloud iam service-accounts create $SA_NAME \
    --display-name="Log Uploader Service Account" \
    --description="Restricted service account for uploading logs to BigQuery" \
    --project=$PROJECT_ID

# Create a custom role with minimal permissions
echo "Creating custom role..."
gcloud iam roles create logUploader \
    --project=$PROJECT_ID \
    --title="Log Uploader" \
    --description="Custom role for uploading logs to BigQuery" \
    --permissions=bigquery.tables.get,bigquery.tables.updateData \
    --stage=GA

# Bind the role to the service account
echo "Binding role to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="projects/$PROJECT_ID/roles/logUploader"

# Create and download a key
echo "Creating service account key..."
gcloud iam service-accounts keys create log-uploader-key.json \
    --iam-account=$SA_EMAIL \
    --project=$PROJECT_ID

# Create a directory for the credentials if it doesn't exist
mv log-uploader-key.json log_uploader_credentials.json

echo "Done. Service account key saved to ./log_uploader_credentials.json"
echo "This service account has minimal permissions:"
echo "- Can only write to BigQuery tables"
echo "- Cannot create/modify table schema"
echo "- Cannot read data from tables"
echo "- Cannot access any other GCP services" 