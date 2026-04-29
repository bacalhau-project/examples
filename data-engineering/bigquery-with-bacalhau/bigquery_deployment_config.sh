#!/bin/bash
# BigQuery deployment configuration template.
# Source this file after exporting SERVICE_ACCOUNT_KEY_BASE64 in your shell:
#     export SERVICE_ACCOUNT_KEY_BASE64=$(base64 -w 0 path/to/sa.json)
#     source bigquery_deployment_config.sh

export PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
export DATASET="${DATASET:-sensor_analytics}"
export SERVICE_ACCOUNT_KEY_BASE64="${SERVICE_ACCOUNT_KEY_BASE64:?SERVICE_ACCOUNT_KEY_BASE64 must be set (base64-encoded GCP service account JSON)}"
export DOCKER_IMAGE="${DOCKER_IMAGE:-ghcr.io/bacalhau-project/bigquery-uploader-sqlite:latest}"
export REGION="${REGION:-us-central1}"
