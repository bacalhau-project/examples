#!/bin/bash
# Script to warm up the Docker registry cache
# This will pull images used by your Bacalhau jobs and push them to your local registry
set -e
echo "Starting registry mirroring process..."

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
# List of images to warm up (extracted from your job files)
IMAGES=(
    "ghcr.io/astral-sh/uv:python3.13-bookworm-slim"
    "ghcr.io/bacalhau-project/sensor-log-generator:2505071810"
    "bash:devel-alpine3.21"
)
# Pull and push each image
for IMAGE in "${IMAGES[@]}"; do
    echo "Processing image: ${IMAGE}"
    
    # Extract image name without any registry prefix
    # For images with registry (containing "/"), remove the registry part
    # For images without registry, keep the full name
    if [[ "$IMAGE" == *"/"* && "$IMAGE" != "/"* ]]; then
        # Find the first "/" which separates registry from image path
        REGISTRY_PART=$(echo "$IMAGE" | cut -d'/' -f1)
        
        # Check if the part before first "/" contains a "." or ":" (indicating a registry domain)
        if [[ "$REGISTRY_PART" == *"."* || "$REGISTRY_PART" == *":"* ]]; then
            # Remove registry prefix (everything up to first "/")
            IMAGE_NAME="${IMAGE#*/}"
        else
            # It's likely a Docker Hub image with owner (e.g., "owner/image")
            IMAGE_NAME="$IMAGE"
        fi
    else
        # Default Docker Hub images like "ubuntu:latest" or "nginx"
        IMAGE_NAME="library/$IMAGE"
    fi
    
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
    # Use the same logic to extract the image name as above
    if [[ "$IMAGE" == *"/"* && "$IMAGE" != "/"* ]]; then
        REGISTRY_PART=$(echo "$IMAGE" | cut -d'/' -f1)
        if [[ "$REGISTRY_PART" == *"."* || "$REGISTRY_PART" == *":"* ]]; then
            IMAGE_NAME="${IMAGE#*/}"
        else
            IMAGE_NAME="$IMAGE"
        fi
    else
        IMAGE_NAME="library/$IMAGE"
    fi
    
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
echo "Mirroring complete!"
echo "You can now update your Bacalhau job YAML files to use ${REGISTRY_ADDRESS} instead of the original registry"
