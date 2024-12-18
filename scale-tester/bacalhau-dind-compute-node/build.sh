#!/bin/bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail
trap 'echo "Error on line $LINENO"' ERR

# Colors for output (define these first)
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
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


# Configuration
PLATFORMS="linux/amd64,linux/arm64"

# If IMAGE_NAME is not set, use the current directory name
if [ -z "${IMAGE_NAME:-}" ]; then
    IMAGE_NAME="bacalhauproject/$(basename "$(pwd)")"
    echo -e "${BLUE}[INFO]${NC} No IMAGE_NAME provided, using directory name: $IMAGE_NAME"
fi

# Generate tag based on current datetime (YYMMDDHHMM format) or git commit hash
if [ -z "${TAG:-}" ]; then
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        TAG="dev-$(git rev-parse --short HEAD)"
    else
        TAG="$(date +"%y%m%d%H%M")"
    fi
fi

DOCKERFILE="Dockerfile"
BUILDER_NAME="multiarch-builder"

validate_requirements() {
    # Check for docker installation
    if ! command -v docker &> /dev/null; then
        error "Docker is required but not installed"
    fi

    # Check if dockerfile exists
    if [ ! -f "$DOCKERFILE" ]; then
        error "Dockerfile not found at $DOCKERFILE"
    fi

    # Check docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running"
    fi

    # Check buildx support
    if ! docker buildx version >/dev/null 2>&1; then
        error "Docker buildx support is required. Please ensure:\n\
        1. Docker Desktop is installed and running\n\
        2. Enable experimental features:\n\
        - Open Docker Desktop\n\
        - Go to Settings/Preferences > Docker Engine\n\
        - Ensure experimental features are enabled\n\
        3. Restart Docker Desktop"
    fi
}

# Setup buildx builder
setup_builder() {
    log "Setting up buildx builder..."
    if docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
        warn "Removing existing builder instance"
        docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1
    fi
    
    docker buildx create --name "$BUILDER_NAME" \
        --driver docker-container \
        --bootstrap || error "Failed to create buildx builder"
    docker buildx use "$BUILDER_NAME"
}

# Build images
build_images() {
    local platforms="$1"
    log "Building for platforms: $platforms"
        
    for platform in $(echo "$platforms" | tr ',' ' '); do
        log "Building for $platform..."
        docker buildx build \
            --platform "$platform" \
            --file "Dockerfile" \
            --tag "$IMAGE_NAME:$TAG-$(echo "$platform" | tr '/' '-')" \
            --load \
            . || error "Build failed for $platform"
        
        # Also tag as latest for the platform
        docker tag "$IMAGE_NAME:$TAG-$(echo "$platform" | tr '/' '-')" \
            "$IMAGE_NAME:latest-$(echo "$platform" | tr '/' '-')"
        
        success "Successfully built image for $platform"
    done
}

# Create and annotate manifest
create_manifest() {
    log "Creating manifest for $IMAGE_NAME:$TAG"
    
    # Push individual platform images
    for platform in $(echo "$PLATFORMS" | tr ',' ' '); do
        platform_tag="$TAG-$(echo "$platform" | tr '/' '-')"
        log "Pushing $IMAGE_NAME:$platform_tag"
        docker push "$IMAGE_NAME:$platform_tag" || error "Failed to push $platform_tag"
    done
    
    # Remove existing manifest if it exists
    docker manifest rm "$IMAGE_NAME:$TAG" 2>/dev/null || true
    
    # Create new manifest
    manifest_create_cmd="docker manifest create $IMAGE_NAME:$TAG"
    for platform in $(echo "$PLATFORMS" | tr ',' ' '); do
        platform_tag="$TAG-$(echo "$platform" | tr '/' '-')"
        manifest_create_cmd+=" $IMAGE_NAME:$platform_tag"
    done
    eval "$manifest_create_cmd" || error "Failed to create manifest"
    
    # Annotate manifest for each platform
    for platform in $(echo "$PLATFORMS" | tr ',' ' '); do
        os=$(echo "$platform" | cut -d'/' -f1)
        arch=$(echo "$platform" | cut -d'/' -f2)
        platform_tag="$TAG-$os-$arch"
        
        docker manifest annotate "$IMAGE_NAME:$TAG" \
            "$IMAGE_NAME:$platform_tag" --os "$os" --arch "$arch" || \
            error "Failed to annotate manifest for $platform"
    done
    
    # Push the manifest
    docker manifest push "$IMAGE_NAME:$TAG" || error "Failed to push manifest"
    
    # Also create latest manifest
    log "Creating latest manifest"
    docker manifest rm "$IMAGE_NAME:latest" 2>/dev/null || true
    
    manifest_create_cmd="docker manifest create $IMAGE_NAME:latest"
    for platform in $(echo "$PLATFORMS" | tr ',' ' '); do
        manifest_create_cmd+=" $IMAGE_NAME:latest-$(echo "$platform" | tr '/' '-')"
    done
    eval "$manifest_create_cmd" || error "Failed to create latest manifest"
    
    # Annotate latest manifest
    for platform in $(echo "$PLATFORMS" | tr ',' ' '); do
        os=$(echo "$platform" | cut -d'/' -f1)
        arch=$(echo "$platform" | cut -d'/' -f2)
        platform_tag="latest-$os-$arch"
        
        docker manifest annotate "$IMAGE_NAME:latest" \
            "$IMAGE_NAME:$platform_tag" --os "$os" --arch "$arch" || \
            error "Failed to annotate latest manifest for $platform"
    done
    
    # Push the latest manifest
    docker manifest push "$IMAGE_NAME:latest" || error "Failed to push latest manifest"
}

# Main execution
main() {
    trap cleanup EXIT
    
    log "Starting build process..."
    validate_requirements
    
    setup_builder
    build_images "$PLATFORMS"
    create_manifest
    
    success "Build completed successfully"
    log "Pulling the newly created image..."
    docker pull "$IMAGE_NAME:$TAG"
    log "You can now run: docker run -v ~/bacalhau-cloud-config.yaml:/root/bacalhau-cloud-config.yaml $IMAGE_NAME:$TAG"
}

# Execute main function
main