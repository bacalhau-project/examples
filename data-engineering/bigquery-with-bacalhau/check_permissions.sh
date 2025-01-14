#!/bin/bash

# Read project ID from config.yaml
PROJECT_ID=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['project']['id'])")

echo "Checking BigQuery permissions for project: $PROJECT_ID"
echo

# Check if we can access the dataset
echo "Testing dataset access..."
bq show $PROJECT_ID:log_analytics

# Check if we can modify the table
echo -e "\nChecking table permissions..."
bq show --format=prettyjson $PROJECT_ID:log_analytics.log_results

# Check IAM permissions
echo -e "\nChecking IAM roles..."
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.role,bindings.members)" \
    --filter="bindings.members:$(gcloud config get account)" 