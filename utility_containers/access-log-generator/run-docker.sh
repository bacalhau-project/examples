#!/bin/bash

# Stop and remove any existing containers
echo "Stopping and removing existing containers..."
docker compose down -v --remove-orphans

# Start the access-log-generator
echo "Starting access-log-generator..."
docker compose up

# To run in detached mode, use:
# docker compose up -d