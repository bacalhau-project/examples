#!/bin/bash

# Detect where the script is run from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Check if .env file exists
if [ -f "$ENV_FILE" ]; then
  echo "Loading environment variables from .env file at $ENV_FILE..."
  # Process the .env file line by line to handle quotes and special characters
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" == \#* ]] && continue
    
    # Extract variable name (everything before the first =)
    var_name="${line%%=*}"
    # Extract variable value (everything after the first =)
    var_value="${line#*=}"
    
    # Skip if var_name is empty
    if [ -z "$var_name" ]; then
      continue
    fi
    
    # Use regular export instead of eval, to avoid issues with special characters
    export "$var_name"="$var_value"
  done < "$ENV_FILE"
else
  echo "No .env file found at $ENV_FILE, using defaults..."
fi

# Run tests based on arguments
if [ $# -eq 0 ]; then
  # Run all tests
  echo "Running all tests..."
  go test -v ./...
else
  # Run specific tests
  echo "Running tests: $@"
  go test -v ./... -run "$@"
fi