#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# Configuration
DOCKER_REPO="bacalhauproject/python-runner"
ARCH="x86_64"

# Generate version
VERSION=$(date +"%Y.%m.%d.%H%M")
echo $VERSION > VERSION

# Build the Docker image
echo "Building Docker image..."
docker build --platform linux/$ARCH --progress=plain -t $DOCKER_REPO:$VERSION -t $DOCKER_REPO:latest . 2>&1 | tee build.log

# Push the images to Docker Hub
echo "Pushing images to Docker Hub..."
docker push $DOCKER_REPO:$VERSION
docker push $DOCKER_REPO:latest

echo "Build complete. Image pushed as $DOCKER_REPO:$VERSION and $DOCKER_REPO:latest"