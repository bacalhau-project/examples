#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# Configuration
DOCKER_REPO="bacalhauproject/python-runner"
BUILDER_NAME="mybuilder"

# Check if the builder already exists
builder_exists=$(docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1 && echo "yes" || echo "no")

if [ "$builder_exists" = "no" ]; then
  echo "Builder '$BUILDER_NAME' does not exist. Creating it..."
  # Create a new buildx builder
  docker buildx create --name "$BUILDER_NAME" --use
  docker buildx inspect --bootstrap
  echo "Builder '$BUILDER_NAME' has been created and set as the current builder."
else
  echo "Builder '$BUILDER_NAME' already exists. Using it..."
  # Set the builder as the current one
  docker buildx use "$BUILDER_NAME"
fi

# Check that the builder is available
docker buildx inspect "$BUILDER_NAME"

# Generate version
VERSION=$(date +"%Y.%m.%d.%H%M")
echo $VERSION > VERSION

# Build the Docker image for multiple platforms
echo "Building Docker image for multiple platforms..."
docker buildx build --platform linux/amd64,linux/arm64 --progress=plain -t $DOCKER_REPO:$VERSION -t $DOCKER_REPO:latest . 2>&1 | tee build.log

# Push the images to Docker Hub
echo "Pushing images to Docker Hub..."
docker buildx build --platform linux/amd64,linux/arm64 --push -t $DOCKER_REPO:$VERSION -t $DOCKER_REPO:latest .

echo "Build complete. Images pushed as $DOCKER_REPO:$VERSION and $DOCKER_REPO:latest"

