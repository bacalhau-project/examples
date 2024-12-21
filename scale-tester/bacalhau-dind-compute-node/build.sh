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
REGISTRY="${REGISTRY:-docker.io}"
VERSION_TAG="${VERSION_TAG:-$(date +"%y%m%d%H%M")}"
SKIP_PUSH="${SKIP_PUSH:-false}"
BUILD_CACHE="${BUILD_CACHE:-true}"
REQUIRE_LOGIN="${REQUIRE_LOGIN:-false}"

# If IMAGE_NAME is not set, use the current directory name
if [ -z "${IMAGE_NAME:-}" ]; then
    IMAGE_NAME="bacalhauproject/$(basename "$(pwd)")"
    log "No IMAGE_NAME provided, using directory name: $IMAGE_NAME"
fi

cleanup() {
    log "Cleaning up temporary resources..."
    if [ -n "${BUILDER_NAME:-}" ]; then
        docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1 || true
    fi
}

check_docker_login() {
    if [ "$REQUIRE_LOGIN" = "true" ] && ! docker system info | grep -q "Username"; then
        error "Not logged into Docker registry. Please run 'docker login' first or set REQUIRE_LOGIN=false to skip this check."
    fi
}

validate_requirements() {
    local requirements=(
        "docker:Docker is required but not installed"
        "git:Git is required but not installed"
        "curl:Curl is required but not installed"
        "python3:Python 3 is required but not installed"
        "jq:jq is required but not installed"
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
        error "Docker buildx support is required. Please ensure Docker buildx is installed and configured"
    fi
}

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

generate_tags() {
    local base_tag="$REGISTRY/$IMAGE_NAME"
    local tags=()
    
    # Add version tag
    tags+=("$base_tag:$VERSION_TAG")
    
    # Add latest tag
    tags+=("$base_tag:latest")
    
    # If in git repo, add git commit hash tag
    if git rev-parse --git-dir > /dev/null 2>&1; then
        local git_hash=$(git rev-parse --short HEAD)
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
    
    local build_args=(
        --platform "$platforms"
        --file "$DOCKERFILE"
        --build-arg BUILDKIT_INLINE_CACHE=1
        --memory="2g"
        --cpu-quota="150000"
        --squash
        --compress
        $tag_args
    )
    
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
    
    # Execute build with resource constraints
    if ! DOCKER_BUILDKIT=1 docker buildx build \
    --builder="$BUILDER_NAME" \
    "${build_args[@]}" \
    --progress=plain \
    .; then
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
    log "You can now pull and run the image with:"
    log "docker pull $REGISTRY/$IMAGE_NAME:$VERSION_TAG"
    log "docker run \
    -v orchestrator-config.yaml:/root/bacalhau-cloud-config.yaml \
    -v node-info:/etc/node-info \
    $REGISTRY/$IMAGE_NAME:$VERSION_TAG"
}

# Execute main function
main "$@"
