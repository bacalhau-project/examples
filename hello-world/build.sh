#!/bin/bash
set -euo pipefail

echo "Setting up Docker buildx builder..."
# Remove existing builder if it exists
docker buildx rm multiarch-builder 2>/dev/null || true
# Create new builder
docker buildx create --name multiarch-builder --driver docker-container --bootstrap
# Use the new builder
docker buildx use multiarch-builder

# Generate timestamp tag in YYYYMMDDHHMM format
TIMESTAMP_TAG=$(date '+%Y%m%d%H%M')

# Try to pre-pull the base image to ensure connectivity
echo "Pre-pulling base image..."
for i in {1..3}; do
    if docker pull registry.hub.docker.com/library/python:3.11-slim; then
        break
    fi
    echo "Pull attempt $i failed, retrying..."
    sleep 5
done

echo "Building Docker image with tags: latest and ${TIMESTAMP_TAG}..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag bacalhauproject/hello-world:latest \
    --tag bacalhauproject/hello-world:"${TIMESTAMP_TAG}" \
    --push \
    --network=host \
    .

echo "Cleaning up..."
docker buildx rm multiarch-builder
