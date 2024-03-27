#!/usr/bin/env bash

# If arg is provided, use it as a tag - otherwise use a short hash of the current date
if [ -z "$1" ]; then
    TAG=$(date +%s | sha256sum | base64 | head -c 6)
else
    TAG=$1
fi

# Create a variable for the multi-arch build driver
MULTI_ARCH='multi-arch'

# If multi-arch build driver is not installed, install it
if ! docker buildx ls | grep -q "${MULTI_ARCH}"; then
    docker buildx create --use --name "${MULTI_ARCH}" || exit 1
fi

# Use the multi-arch build driver
docker buildx use "${MULTI_ARCH}" || exit 1

docker buildx build --platform linux/amd64,linux/arm64 --push -t docker.io/bacalhauproject/justicons-editor:$TAG --push .

