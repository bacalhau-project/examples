#!/usr/bin/env bash

# Set the working directory
cd /app

# Run the dotnet application with the provided arguments
exec dotnet CosmosUploader.dll "$@"