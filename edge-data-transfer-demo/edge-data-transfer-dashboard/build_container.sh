#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if required commands exist
command -v docker >/dev/null 2>&1 || error "docker is required but not installed"

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    error "Dockerfile not found in current directory"
fi

# Generate timestamp for tag
TIMESTAMP=$(date +%Y%m%d%H%M)

# Registry configuration
REGISTRY="ghcr.io"    
ORGANIZATION="bacalhau-project"      

# Check for required environment variables
if [ -z "${IMAGE_NAME:-}" ]; then
    error "IMAGE_NAME environment variable is not set"
fi

if [ -z "${LOCAL_TAG:-}" ]; then
    error "LOCAL_TAG environment variable is not set"
fi

REMOTE_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:${TIMESTAMP}"
LATEST_REMOTE_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:latest"

# Validate registry configuration
if [ -z "${REGISTRY}" ] || [ -z "${ORGANIZATION}" ] || [ -z "${IMAGE_NAME}" ]; then
    error "Invalid registry configuration"
fi

# Create and use buildx builder if it doesn't exist
if ! docker buildx inspect multiarch-builder >/dev/null 2>&1; then
    log "Creating multi-arch builder..."
    docker buildx create --name multiarch-builder --driver docker-container --bootstrap
fi
docker buildx use multiarch-builder

# Build container for multiple platforms
log "Building Docker container for multiple platforms..."
if ! docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "${LOCAL_TAG}" \
    -t "${REMOTE_TAG}" \
    -t "${LATEST_REMOTE_TAG}" \
    -f Dockerfile . ; then
    error "Failed to build Docker container"
fi

log "Container built successfully for all platforms!"

# Push to registry if requested
if [ "${1:-}" = "--push" ]; then
    # Check if user is logged into GitHub Container Registry
    if ! docker login ghcr.io >/dev/null 2>&1; then
        error "Not logged into GitHub Container Registry. Please run 'docker login ghcr.io' first."
    fi

    # Tag and push with timestamp
    log "Tagging image with timestamp ${TIMESTAMP}..."
    if ! docker tag "${LOCAL_TAG}" "${REMOTE_TAG}"; then
        error "Failed to tag Docker image with timestamp"
    fi
    
    log "Pushing timestamped image..."
    if ! docker push "${REMOTE_TAG}"; then
        error "Failed to push timestamped image"
    fi
    
    # Tag and push as latest
    log "Tagging image as latest..."
    if ! docker tag "${LOCAL_TAG}" "${LATEST_REMOTE_TAG}"; then
        error "Failed to tag Docker image as latest"
    fi
    
    log "Pushing latest tag..."
    if ! docker push "${LATEST_REMOTE_TAG}"; then
        error "Failed to push latest tag"
    fi
    
    log "Successfully pushed images to ${REGISTRY}:"
    log "  - ${REMOTE_TAG} (linux/amd64, linux/arm64)"
    log "  - ${LATEST_REMOTE_TAG} (linux/amd64, linux/arm64)"
fi