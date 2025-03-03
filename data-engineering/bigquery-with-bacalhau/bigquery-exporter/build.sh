#!/bin/bash
set -e

# Default values
DEFAULT_REGISTRY="docker.io"
DEFAULT_REPOSITORY="bacalhauproject/python-bigquery-executor"
DEFAULT_PLATFORMS="linux/amd64,linux/arm64"
DEFAULT_TAG="latest"

# Help text
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -r, --registry      Container registry (default: $DEFAULT_REGISTRY)"
    echo "  -p, --repository    Repository name (default: $DEFAULT_REPOSITORY)"
    echo "  -t, --tag          Image tag (default: $DEFAULT_TAG)"
    echo "  -a, --platforms    Platforms to build for (default: $DEFAULT_PLATFORMS)"
    echo "  -h, --help         Show this help message"
    echo
    echo "Example:"
    echo "  $0 --registry docker.io --repository bacalhauproject/python-bigquery-executor --tag latest"
}

# Parse arguments
REGISTRY=$DEFAULT_REGISTRY
REPOSITORY=$DEFAULT_REPOSITORY
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
        -p|--repository)
            REPOSITORY="$2"
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
IMAGE_NAME="$REGISTRY/$REPOSITORY:$TAG"
TIMESTAMP_TAG="$REGISTRY/$REPOSITORY:$(date +%Y%m%d%H%M)"

echo "Building image: $IMAGE_NAME"
echo "Timestamp tag: $TIMESTAMP_TAG"
echo "Platforms: $PLATFORMS"

# Build and push
docker buildx build \
    --platform $PLATFORMS \
    --tag $IMAGE_NAME \
    --tag $TIMESTAMP_TAG \
    --push \
    .

echo "Build complete! Images pushed to:"
echo "  $IMAGE_NAME"
echo "  $TIMESTAMP_TAG" 