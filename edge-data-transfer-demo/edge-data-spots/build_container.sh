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
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

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

# Check for --no-cache option
NO_CACHE=""
if [ "${1:-}" = "--no-cache" ] || [ "${2:-}" = "--no-cache" ]; then
    # Prune the buildx cache to force fresh build
    log "Pruning buildx cache..."
    docker buildx prune -f

    NO_CACHE="--no-cache"
    log "Building without cache"
fi

# Create and use buildx builder if it doesn't exist
if ! docker buildx inspect multiarch-builder >/dev/null 2>&1; then
    log "Creating multi-arch builder..."
    docker buildx create --name multiarch-builder --driver docker-container --bootstrap
fi
docker buildx use multiarch-builder


# Build based on whether we're pushing or not
if [ "${1:-}" = "--push" ] || [ "${2:-}" = "--push" ]; then
    # Check if user is logged into GitHub Container Registry
    if ! docker login ghcr.io >/dev/null 2>&1; then
        error "Not logged into GitHub Container Registry. Please run 'docker login ghcr.io' first."
    fi
    
    # Build and push container for multiple platforms
    log "Building Docker container for multiple platforms and pushing..."
    if ! docker buildx build \
        --platform linux/amd64,linux/arm64 \
        --push \
        -t "${REMOTE_TAG}" \
        -t "${LATEST_REMOTE_TAG}" \
        --build-arg BUILD_DATE="${BUILD_DATE}" \
        ${NO_CACHE} \
        -f Dockerfile . ; then
        error "Failed to build and push Docker container"
    fi
    
    log "Successfully pushed images to ${REGISTRY}:"
    log "  - ${REMOTE_TAG} (linux/amd64, linux/arm64)"
    log "  - ${LATEST_REMOTE_TAG} (linux/amd64, linux/arm64)"
else
    # Build for local testing (single architecture)
    log "Building for local use..."
    if ! docker buildx build \
        --platform linux/amd64 \
        --load \
        -t "${LOCAL_TAG}" \
        --build-arg BUILD_DATE="${BUILD_DATE}" \
        ${NO_CACHE} \
        -f Dockerfile . ; then
        error "Failed to build Docker container for local use"
    fi
    
    log "Container built successfully for local use: ${LOCAL_TAG}"
fi