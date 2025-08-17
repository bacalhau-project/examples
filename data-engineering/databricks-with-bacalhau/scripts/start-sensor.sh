#!/usr/bin/env bash

# Simple sensor start script - no fancy features, just run the container

# Stop any existing sensor container
docker stop sensor-log-generator 2>/dev/null || true
docker rm sensor-log-generator 2>/dev/null || true

# Print the Docker command for reference
echo "Docker command to run sensor:"
echo ""
echo "docker run --rm \\"
echo "  --name sensor-log-generator \\"
echo "  -v \"$(pwd)/sample-sensor/data\":/app/data \\"
echo "  -v \"$(pwd)/sample-sensor\":/app/config \\"
echo "  -e CONFIG_FILE=/app/config/sensor-config.yaml \\"
echo "  -e IDENTITY_FILE=/app/config/identity.json \\"
echo "  -p 8080:8080 \\"
echo "  ghcr.io/bacalhau-project/sensor-log-generator:latest"
echo ""

# Run the sensor container
docker run --rm \
  --name sensor-log-generator \
  -v "$(pwd)/sample-sensor/data":/app/data \
  -v "$(pwd)/sample-sensor":/app/config \
  -e CONFIG_FILE=/app/config/sensor-config.yaml \
  -e IDENTITY_FILE=/app/config/identity.json \
  -p 8080:8080 \
  ghcr.io/bacalhau-project/sensor-log-generator:latest