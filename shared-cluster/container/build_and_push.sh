#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# If hdf5 is not in this directory, then tell the person to download it.
# The file will look like this: hdf5-1.14.4-3-ubuntu-2204_gcc.deb.tar.gz
if ! ls build_plugins/hdf5-*.deb.tar.gz 1> /dev/null 2>&1; then
    error "HDF5 is not in build_plugins/ directory. Please download it and place it in build_plugins/ directory. You can download a binary package from here: https://support.hdfgroup.org/ftp/HDF5/releases/"
fi

# Configuration
DOCKER_REPO="bacalhauproject/python-runner"
ARCH="amd64"

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