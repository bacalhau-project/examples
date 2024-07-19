#!/bin/bash
set -e

# Function to print error messages
error() {
    echo "Error: $1" >&2
    exit 1
}

# If hdf5 is not in this directory, then tell the person to download it.
# The file will look like this: hdf5-1.14.4-3-ubuntu-2204_gcc.deb.tar.gz
if ! ls hdf5-*.deb.tar.gz 1> /dev/null 2>&1; then
    error "HDF5 is not in this directory. Please download it and place it in this directory. You can download a binary package from here: https://support.hdfgroup.org/ftp/HDF5/releases/"
fi

# Build the Docker image
echo "Building Docker image..."
docker build --platform=linux/amd64 -t hdf5-plugins-builder --progress=plain . || error "Docker build failed"

# Create output directory if it doesn't exist
mkdir -p ./output

# Run the container with the output directory mounted
echo "Running container to extract artifacts..."
docker run --rm -v $(pwd)/output:/output hdf5-plugins-builder || error "Failed to run container"

# Get the hash of the build
BUILD_HASH=$(docker inspect --format='{{.Id}}' hdf5-plugins-builder)
if [ $? -ne 0 ]; then
    error "Failed to get build hash"
fi
echo "Build hash: $BUILD_HASH"
echo $BUILD_HASH > ./output/build_hash.txt

echo "Build complete. The plugins are available in ./output/hdf5_plugins.tar.gz"
echo "The build version is saved in ./output/build_version.txt"
echo "The build hash is saved in ./output/build_hash.txt"