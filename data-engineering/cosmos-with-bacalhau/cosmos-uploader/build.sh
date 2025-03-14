#!/bin/bash
set -e

# Default values
DEFAULT_REGISTRY="ghcr.io"
DEFAULT_ORG="bacalhau-project"
DEFAULT_CONTAINER="postgres-uploader"
DEFAULT_PLATFORMS="linux/amd64,linux/arm64"
DEFAULT_TAG="latest"

# Get GitHub token and log in to ghcr.io
echo "Getting GitHub token and logging in to ghcr.io..."
TOKEN=$(gh auth token)
if [ -z "$TOKEN" ]; then
    echo "Error getting GitHub token. Please run 'gh auth login' first"
    exit 1
fi

USERNAME=$(gh api user --jq .login)
if [ -z "$USERNAME" ]; then
    echo "Error getting GitHub username"
    exit 1
fi

echo "$TOKEN" | docker login ghcr.io -u "$USERNAME" --password-stdin
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
    echo "Failed to log into ghcr.io"
    exit 1
fi

# Help text
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -r, --registry      Container registry (default: $DEFAULT_REGISTRY)"
    echo "  -o, --org           Organization name (default: $DEFAULT_ORG)"
    echo "  -c, --container     Container name (default: $DEFAULT_CONTAINER)"
    echo "  -t, --tag          Image tag (default: $DEFAULT_TAG)"
    echo "  -a, --platforms    Platforms to build for (default: $DEFAULT_PLATFORMS)"
    echo "  -h, --help         Show this help message"
    echo
    echo "Example:"
    echo "  $0 --registry ghcr.io --org bacalhau-project --container duckdb-plus-postgres --tag latest"
}

# Parse arguments
REGISTRY=$DEFAULT_REGISTRY
ORG=$DEFAULT_ORG
CONTAINER=$DEFAULT_CONTAINER
TAG=$DEFAULT_TAG
PLATFORMS=$DEFAULT_PLATFORMS

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -r|--registry)
            REGISTRY="$2"
            shift
            shift
            ;;
        -o|--org)
            ORG="$2"
            shift
            shift
            ;;
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
        -a|--platforms)
            PLATFORMS="$2"
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

# Ensure buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    echo "Error: docker buildx is not available"
    echo "Please ensure you have Docker 19.03 or newer with experimental features enabled"
    exit 1
fi

# Set up buildx builder if needed
BUILDER_NAME="multiarch-builder"
if ! docker buildx inspect $BUILDER_NAME > /dev/null 2>&1; then
    echo "Creating new buildx builder: $BUILDER_NAME"
    docker buildx create --name $BUILDER_NAME --driver docker-container --bootstrap
fi

# Use the builder
docker buildx use $BUILDER_NAME

# Full image name
IMAGE_NAME="$REGISTRY/$ORG/$CONTAINER:$TAG"
TIMESTAMP_TAG="$REGISTRY/$ORG/$CONTAINER:$(date +%Y%m%d%H%M)"

echo "Building image: $IMAGE_NAME"
echo "Timestamp tag: $TIMESTAMP_TAG"
echo "Platforms: $PLATFORMS"

# Build and push
docker buildx build \
    --platform "$PLATFORMS" \
    --tag "$IMAGE_NAME" \
    --tag "$TIMESTAMP_TAG" \
    --label "org.opencontainers.image.source=https://github.com/$USERNAME/bacalhau-examples" \
    --label "org.opencontainers.image.description=DuckDB plus PostgreSQL image for log processing" \
    --label "org.opencontainers.image.licenses=Apache-2.0" \
    --push \
    .

echo "Build complete! Images pushed to:"
echo "  $IMAGE_NAME"
echo "  $TIMESTAMP_TAG"
