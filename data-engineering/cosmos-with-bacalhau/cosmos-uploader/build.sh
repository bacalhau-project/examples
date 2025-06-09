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

# Default values
DEFAULT_CONTAINER="cosmos-uploader"
DEFAULT_TAG="latest"
REGISTRY_NAME="ghcr.io"
ORGANIZATION_NAME="bacalhau-project"
IMAGE_NAME="cosmos-uploader"
PUSH_TO_REGISTRY=true
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
BUILDER_NAME="${BUILDER_NAME:-multiarch-builder}"
BUILD_CACHE="${BUILD_CACHE:-true}"
REQUIRE_LOGIN="${REQUIRE_LOGIN:-true}"
GITHUB_USER="${GITHUB_USER:-$(git config user.name || echo "GITHUB_USER_NOT_SET")}"

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile"

# Help text
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -c, --container     Container name (default: $DEFAULT_CONTAINER)"
    echo "  -t, --tag           Image tag (default: auto-generated from timestamp)"
    echo "  -p, --push          Push to registry after building (default: false)"
    echo "  -r, --registry      Container registry (default: $REGISTRY_NAME)"
    echo "  -h, --help          Show this help message"
    echo
    echo "Environment variables:"
    echo "  PLATFORMS          : Target platforms (default: $PLATFORMS)"
    echo "  BUILD_CACHE        : Use build cache (default: $BUILD_CACHE)"
    echo "  REQUIRE_LOGIN      : Require Docker registry login (default: $REQUIRE_LOGIN)"
    echo "  GITHUB_USER        : GitHub username (default: $GITHUB_USER)"
    echo
    echo "Examples:"
    echo "  $0 --tag v20250416 --push             # Build and push with specific tag"
    echo "  $0 --push                             # Build with auto timestamp tag and push"
    echo "  $0 --tag v20250416                    # Build locally only, no push"
}

cleanup() {
    log "Cleaning up temporary resources..."
    if [ -n "${BUILDER_NAME:-}" ]; then
        docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1 || true
    fi
}

check_docker_login() {
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        error "GITHUB_TOKEN is not set"
    fi
    if [ -z "${GITHUB_USER:-}" ]; then
        error "GITHUB_USER is not set"
    fi

    log "Logging in to Docker registry..."
    if echo "$GITHUB_TOKEN" | docker login ghcr.io --username "$GITHUB_USER" --password-stdin; then
        log "Successfully logged in to Docker registry"
    else
        error "Failed to log in to Docker registry"
    fi
}

validate_requirements() {
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
        error "Docker buildx support is required"
    fi
}

setup_builder() {
    log "Setting up buildx builder..."
    if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
        docker buildx create --name "$BUILDER_NAME" --driver docker-container --bootstrap || error "Failed to create buildx builder"
    fi
    docker buildx use "$BUILDER_NAME"
}

# Parse arguments
CONTAINER=$DEFAULT_CONTAINER
TAG=$DEFAULT_TAG

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -c|--container)
            CONTAINER="$2"
            shift
            shift
        ;;
        -t|--tag)
            TAG="$2"
            shift
            shift
        ;;
        -p|--push)
            PUSH_TO_REGISTRY=true
            shift
        ;;
        -r|--registry)
            REGISTRY_NAME="$2"
            shift
            shift
        ;;
        -h|--help)
            show_help
            exit 0
        ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
        ;;
    esac
done

# Generate timestamp tag if no explicit tag was provided
if [ "$TAG" = "latest" ]; then
    TIMESTAMP=$(date +%Y%m%d%H%M)
    TAG="$TIMESTAMP"
    log "No specific tag provided, using timestamp-based tag: $TAG"
fi

# Full image names
LOCAL_IMAGE_NAME="$REGISTRY_NAME/$ORGANIZATION_NAME/$IMAGE_NAME:$TAG"
LOCAL_LATEST_TAG="$REGISTRY_NAME/$ORGANIZATION_NAME/$IMAGE_NAME:latest"
REGISTRY_IMAGE_NAME="$LOCAL_IMAGE_NAME"
REGISTRY_LATEST_TAG="$LOCAL_LATEST_TAG"

log "Building image with tag: $TAG"
log "Local image name: $LOCAL_IMAGE_NAME"
if [ "$PUSH_TO_REGISTRY" = true ]; then
    log "Will push to registry as: $REGISTRY_IMAGE_NAME"
fi

# Verify .NET source files
APP_DIR="${PROJECT_ROOT}/cosmos-uploader"
if [ ! -d "$APP_DIR" ]; then
    error "Application directory not found at $APP_DIR"
fi

if [ ! -f "$APP_DIR/CosmosUploader.csproj" ]; then
    error "CosmosUploader.csproj not found at $APP_DIR"
fi

# Main build process
main() {
    trap cleanup EXIT

    log "Starting build process..."
    validate_requirements
    setup_builder

    # Build arguments
    local build_args=(
        --platform "$PLATFORMS"
        --file "$DOCKERFILE"
        --tag "$LOCAL_IMAGE_NAME"
        --tag "$LOCAL_LATEST_TAG"
        --build-arg "BUILD_CONFIGURATION=Release"
    )

    # Add cache settings
    if [ "$BUILD_CACHE" = "true" ]; then
        build_args+=(--cache-from "type=registry,ref=$REGISTRY_NAME/$ORGANIZATION_NAME/$IMAGE_NAME:buildcache")
        build_args+=(--cache-to "type=registry,ref=$REGISTRY_NAME/$ORGANIZATION_NAME/$IMAGE_NAME:buildcache,mode=max")
    fi

    # Only add --push if PUSH_TO_REGISTRY is true
    if [ "$PUSH_TO_REGISTRY" = true ]; then
        check_docker_login
        build_args+=(--push)
    else
        build_args+=(--load)
    fi

    # Execute build
    if ! docker buildx build "${build_args[@]}" "$SCRIPT_DIR"; then
        error "Build failed"
    fi

    success "Build completed successfully"

    # Write the tag to a file for other scripts to use
    echo "$TAG" > "$SCRIPT_DIR/latest-tag"
    if [ "$PUSH_TO_REGISTRY" = true ]; then
        echo "$REGISTRY_IMAGE_NAME" > "$PROJECT_ROOT/.latest-registry-image"
    fi

    # Print out instructions that are copy and pasteable
    echo "To run the image, use the following command:"
    echo "docker pull $REGISTRY_NAME/$ORGANIZATION_NAME/$IMAGE_NAME:$TAG"
    echo "or"
    echo "docker pull $REGISTRY_NAME/$ORGANIZATION_NAME/$IMAGE_NAME:latest"
}

# Execute main function
main "$@"