#!/bin/bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail
trap 'echo "Error on line $LINENO"' ERR

# Configuration
PLATFORMS="linux/amd64,linux/arm64"
IMAGE_NAME="bacalhauproject/bacalhau-dind-compute-node"
# Generate tag based on current datetime (YYYYMMDDHHMM format)
TAG="${TAG:-$(date +"%Y%m%d%H%M")}"

DOCKERFILEDIR="docker"
DOCKERFILE="$DOCKERFILEDIR/Dockerfile"
BUILDER_NAME="multiarch-builder"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

cleanup() {
    log "Cleaning up temporary resources..."
    docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1 || true
}

# Build and push images for all platforms
build_and_push() {
    local tag="$1"
    log "Building and pushing for tag: $tag"
    
    docker buildx build \
        --platform "$PLATFORMS" \
        --file "$DOCKERFILE" \
        --tag "$IMAGE_NAME:$tag" \
        --push \
        . || error "Failed to build/push for $tag"
}

# Main execution
main() {
    trap cleanup EXIT
    
    log "Starting build process..."
    
    # Setup buildx
    docker buildx create --name "$BUILDER_NAME" --use || error "Failed to create builder"
    docker buildx inspect --bootstrap || error "Failed to bootstrap builder"
    
    # Build and push with timestamp tag
    build_and_push "$TAG"
    
    # Tag as latest and push
    build_and_push "latest"
    
    success "Build completed successfully"
    log "Images available as:"
    log "  $IMAGE_NAME:$TAG"
    log "  $IMAGE_NAME:latest"
}

# Execute main function
main 