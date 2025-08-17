#!/bin/bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail
trap 'echo "Error on line $LINENO"' ERR

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
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

# Configuration with defaults
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
BUILDER_NAME="${BUILDER_NAME:-multiarch-builder}"
REGISTRY="${REGISTRY:-ghcr.io}"
VERSION_TAG="${VERSION_TAG:-$(date +"%y%m%d%H%M")}"
SKIP_PUSH="${SKIP_PUSH:-false}"
BUILD_CACHE="${BUILD_CACHE:-true}"
REQUIRE_LOGIN="${REQUIRE_LOGIN:-true}"
GITHUB_USER="${GITHUB_USER:-$(git config user.name || echo "GITHUB_USER_NOT_SET")}"

# If IMAGE_NAME is not set, use the current directory name
if [ -z "${IMAGE_NAME:-}" ]; then
    IMAGE_NAME="bacalhau-project/$(basename "$(pwd)")"
    log "No IMAGE_NAME provided, using directory name: $IMAGE_NAME"
fi

cleanup() {
    log "Cleaning up temporary resources..."
    if [ -n "${BUILDER_NAME:-}" ]; then
        docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1 || true
    fi
}

check_docker_login() {
    log "Checking if GITHUB_TOKEN and GITHUB_USER are set"
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        error "GITHUB_TOKEN is not set"
    fi
    if [ -z "${GITHUB_USER:-}" ]; then
        error "GITHUB_USER is not set"
    fi

    log "Logging in to Docker registry..."
    if echo "$GITHUB_TOKEN" | docker login "$REGISTRY" --username "$GITHUB_USER" --password-stdin; then
        log "Successfully logged in to Docker registry"
    else
        error "Failed to log in to Docker registry"
    fi
}

validate_requirements() {
    local requirements=(
        "docker:Docker is required but not installed"
        "git:Git is required but not installed"
    )

    for req in "${requirements[@]}"; do
        local cmd="${req%%:*}"
        local msg="${req#*:}"
        if ! command -v "$cmd" &> /dev/null; then
            error "$msg"
        fi
    done

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
        error "Docker buildx support is required. Please ensure:
        1. Docker Desktop is installed and running
        2. Enable experimental features:
           - Open Docker Desktop
           - Go to Settings/Preferences > Docker Engine
           - Ensure experimental features are enabled
        3. Restart Docker Desktop"
    fi
}

setup_builder() {
    log "Setting up buildx builder..."
    
    # Check if builder already exists
    if docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
        # Check if the builder is working by listing the nodes
        if docker buildx inspect --bootstrap "$BUILDER_NAME" | grep -q "Status: running"; then
            log "Using existing builder instance '$BUILDER_NAME'"
            docker buildx use "$BUILDER_NAME"
            return 0
        else
            warn "Existing builder instance is not running properly, recreating it"
            docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1
        fi
    fi
    
    # Create new builder if needed
    log "Creating new builder instance '$BUILDER_NAME'"
    docker buildx create --name "$BUILDER_NAME" \
        --driver docker-container \
        --bootstrap || error "Failed to create buildx builder"
    docker buildx use "$BUILDER_NAME"
}

generate_tags() {
    local base_tag="$REGISTRY/$IMAGE_NAME"
    local tags=()

    # Add version tag
    tags+=("$base_tag:$VERSION_TAG")
    
    # Add latest tag
    tags+=("$base_tag:latest")
    
    # If in git repo, add git commit hash tag
    if git rev-parse --git-dir > /dev/null 2>&1; then
        local git_hash
        git_hash=$(git rev-parse --short HEAD)
        tags+=("$base_tag:$git_hash")
    fi

    # Convert tags array to --tag arguments for docker buildx
    local tag_args=""
    for tag in "${tags[@]}"; do
        tag_args="$tag_args --tag $tag"
    done
    echo "$tag_args"
}

build_and_push_images() {
    local platforms="$1"
    local tag_args
    tag_args=$(generate_tags)
    
    log "Building for platforms: $platforms"
    
    # Create the build_args array
    local build_args=(
        --platform "$platforms"
        --file "$DOCKERFILE"
    )

    # Add tags to build_args (splitting the string into separate arguments)
    for tag_arg in $tag_args; do
        build_args+=("$tag_arg")
    done

    # Add cache settings
    if [ "$BUILD_CACHE" = "true" ]; then
        build_args+=(--cache-from "type=registry,ref=$REGISTRY/$IMAGE_NAME:buildcache")
        build_args+=(--cache-to "type=registry,ref=$REGISTRY/$IMAGE_NAME:buildcache,mode=max")
    fi

    # Add push flag if not skipping
    if [ "$SKIP_PUSH" = "false" ]; then
        build_args+=(--push)
        check_docker_login
    else
        build_args+=(--load)
    fi

    # Execute build (add the path argument ".")
    if ! docker buildx build "${build_args[@]}" .; then
        error "Build failed for $platforms"
    fi
    
    success "Successfully built images for $platforms"
}

print_usage() {
    log "Environment variables that can be set:"
    echo "  IMAGE_NAME     : Name of the image (default: derived from directory name)"
    echo "  PLATFORMS      : Target platforms (default: linux/amd64,linux/arm64)"
    echo "  DOCKERFILE     : Path to Dockerfile (default: ./Dockerfile)"
    echo "  VERSION_TAG    : Version tag (default: YYMMDDHHMM)"
    echo "  REGISTRY       : Docker registry (default: docker.io)"
    echo "  SKIP_PUSH      : Skip pushing to registry (default: false)"
    echo "  BUILD_CACHE    : Use build cache (default: true)"
    echo "  REQUIRE_LOGIN  : Require Docker registry login (default: false)"
}

main() {
    trap cleanup EXIT
    
    if [ "${1:-}" = "--help" ]; then
        print_usage
        exit 0
    fi

    log "Starting build process..."
    validate_requirements
    
    setup_builder
    build_and_push_images "$PLATFORMS"
    
    success "Build completed successfully"
    
    # Write image tags to files if push was successful
    local full_image_version="$REGISTRY/$IMAGE_NAME:$VERSION_TAG"
    local full_image_latest="$REGISTRY/$IMAGE_NAME:latest"

    log "Writing tag information to files..."
    echo "$VERSION_TAG" > .latest-image-tag
    echo "$full_image_version" > .latest-registry-image
    echo "$full_image_latest" > .latest-registry-image-latest
    log " -> .latest-image-tag: $(cat .latest-image-tag)"
    log " -> .latest-registry-image: $(cat .latest-registry-image)"
    log " -> .latest-registry-image-latest: $(cat .latest-registry-image-latest)"

    log "Pulling latest image..."
    docker pull "$full_image_latest" || warn "Failed to pull latest image"
    
    log "You can now pull and run the image with:"
    log "docker pull $REGISTRY/$IMAGE_NAME:$VERSION_TAG"
    log "docker pull $REGISTRY/$IMAGE_NAME:latest"
    
    echo ""
    success "Ready to run! Copy and paste this command:"
    echo ""
    echo -e "${GREEN}# Run the sensor locally:${NC}"
    echo "docker run --rm \\"
    echo "  --name sensor-log-generator \\"
    echo "  -v \"\$(pwd)/data\":/app/data \\"
    echo "  -v \"\$(pwd)/config\":/app/config \\"
    echo "  -e CONFIG_FILE=/app/config/config.yaml \\"
    echo "  -e IDENTITY_FILE=/app/config/identity.json \\"
    echo "  $REGISTRY/$IMAGE_NAME:latest"
    echo ""
    echo -e "${GREEN}# Or with custom sensor ID and location:${NC}"
    echo "docker run --rm \\"
    echo "  --name sensor-log-generator \\"
    echo "  -v \"\$(pwd)/data\":/app/data \\"
    echo "  -e SENSOR_ID=CUSTOM001 \\"
    echo "  -e SENSOR_LOCATION=\"Custom Location\" \\"
    echo "  $REGISTRY/$IMAGE_NAME:latest"
}

# Execute main function
main "$@"
