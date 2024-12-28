#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <parameter-name> <file-path>"
  exit 1
fi

# Assign arguments to variables
PARAMETER_NAME="$1"
FILE_PATH="$2"

# Validate parameter name
case "$PARAMETER_NAME" in
  "ORCHESTRATOR_CONFIG")
    FULL_PARAMETER_PATH="/bacalhau/ORCHESTRATOR_CONFIG"
    ;;
  "DOCKER_COMPOSE")
    FULL_PARAMETER_PATH="/bacalhau/DOCKER_COMPOSE"
    ;;
  *)
    echo "Error: Invalid parameter name. Supported parameters are: ORCHESTRATOR_CONFIG, DOCKER_COMPOSE"
    exit 1
    ;;
esac

# Check if the file exists
if [ ! -f "$FILE_PATH" ]; then
  echo "Error: File '$FILE_PATH' does not exist."
  exit 1
fi

# Read the file content
FILE_CONTENT=$(cat "$FILE_PATH")

# If the AWS_REGION environment variable is not set, then fail
if [ -z "$AWS_REGION" ]; then
  echo "Error: AWS_REGION environment variable is not set."
  exit 1
fi

# Upload/update the parameter in SSM Parameter Store
echo "Uploading/updating parameter '$FULL_PARAMETER_PATH' in region '$AWS_REGION'..."
aws ssm put-parameter \
  --name "$FULL_PARAMETER_PATH" \
  --value "$FILE_CONTENT" \
  --type "String" \
  --region "$AWS_REGION" \
  --overwrite

# Check if the command succeeded
if [ $? -eq 0 ]; then
  echo "Parameter '$FULL_PARAMETER_PATH' successfully uploaded/updated."
else
  echo "Error: Failed to upload/update parameter '$FULL_PARAMETER_PATH'."
  exit 1
fi