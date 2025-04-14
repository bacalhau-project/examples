#!/usr/bin/env bash

# Set the working directory
cd /app

# Check if config file exists
if [ ! -f "$1" ]; then
    echo "Error: Configuration file not found: $1"
    exit 1
fi

# Run the dotnet application with the provided arguments
exec dotnet CosmosUploader.dll "$@"