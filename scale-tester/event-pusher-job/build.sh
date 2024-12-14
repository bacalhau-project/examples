#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if required commands exist
command -v tinygo >/dev/null 2>&1 || error "tinygo is required but not installed"
command -v docker >/dev/null 2>&1 || error "docker is required but not installed"

# Create bin directory if it doesn't exist
mkdir -p bin

# Generate timestamp for tag
TIMESTAMP=$(date +%Y%m%d%H%M)

# Registry configuration
REGISTRY="docker.io"    
ORGANIZATION="bacalhau-project"      
IMAGE_NAME="event-pusher"
TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:${TIMESTAMP}"

log "Building binary with TinyGo..."
GOARCH=amd64 GOOS=linux tinygo build -o bin/app main.go || error "Failed to build with TinyGo"

log "Building Docker image..."
docker build --platform linux/amd64 -t "${TAG}" . || error "Failed to build Docker image"

log "Pushing image to registry..."
docker push "${TAG}" || error "Failed to push Docker image"

# Tag as latest
LATEST_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:latest"
docker tag "${TAG}" "${LATEST_TAG}"
docker push "${LATEST_TAG}"

log "Successfully built and pushed ${TAG}"
log "Also tagged and pushed as ${LATEST_TAG}"