#!/bin/bash
# Script to warm up the Docker registry cache
# This will pull images used by your Bacalhau jobs and push them to your local registry

set -e
echo "Starting registry warm-up process..."

# Define registry address
REGISTRY_ADDRESS="localhost:5000"

# Check if registry is accessible
echo "Checking registry connectivity..."
curl -s "http://${REGISTRY_ADDRESS}/v2/" > /dev/null
if [ $? -ne 0 ]; then
  echo "Error: Cannot connect to registry at ${REGISTRY_ADDRESS}"
  echo "Make sure the registry is running and accessible"
  exit 1
fi

# List of images to warm up (extracted from your YAML files)
IMAGES=(
  "ghcr.io/linuxcontainers/alpine:3.20"
  "ghcr.io/astral-sh/uv:bookworm-slim"
  "ghcr.io/bacalhau-project/cosmos-uploader:202504222125"
  "ghcr.io/bacalhau-project/sensor-log-generator:2504211458"
)

# Pull and push each image
for IMAGE in "${IMAGES[@]}"; do
  echo "Processing image: ${IMAGE}"
  
  # Extract image name without registry prefix
  IMAGE_NAME="${IMAGE#ghcr.io/}"
  
  echo "Pulling ${IMAGE}..."
  docker pull ${IMAGE}
  
  echo "Tagging as ${REGISTRY_ADDRESS}/${IMAGE_NAME}..."
  docker tag ${IMAGE} ${REGISTRY_ADDRESS}/${IMAGE_NAME}
  
  echo "Pushing to local registry..."
  docker push ${REGISTRY_ADDRESS}/${IMAGE_NAME}
  
  echo "Successfully cached ${IMAGE}"
  echo "-----------------------------"
done

echo "Testing pull from local registry..."
for IMAGE in "${IMAGES[@]}"; do
  IMAGE_NAME="${IMAGE#ghcr.io/}"
  echo "Removing local image ${REGISTRY_ADDRESS}/${IMAGE_NAME}..."
  docker rmi ${REGISTRY_ADDRESS}/${IMAGE_NAME} || true
  
  echo "Pulling from local registry: ${REGISTRY_ADDRESS}/${IMAGE_NAME}..."
  docker pull ${REGISTRY_ADDRESS}/${IMAGE_NAME}
  
  if [ $? -eq 0 ]; then
    echo "✅ Successfully pulled ${REGISTRY_ADDRESS}/${IMAGE_NAME} from local registry"
  else
    echo "❌ Failed to pull ${REGISTRY_ADDRESS}/${IMAGE_NAME} from local registry"
  fi
  echo "-----------------------------"
done

echo "Warmup complete!"
echo "You can now update your Bacalhau job YAML files to use ${REGISTRY_ADDRESS} instead of ghcr.io"