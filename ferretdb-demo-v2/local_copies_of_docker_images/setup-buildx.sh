#!/bin/bash

set -e

BUILDER_NAME="multiarch-builder"

# Check if builder already exists
if docker buildx ls | grep -q "$BUILDER_NAME"; then
  echo "✅ Buildx builder '$BUILDER_NAME' already exists. Using it..."
  docker buildx use "$BUILDER_NAME"
else
  echo "🔧 Creating and bootstrapping buildx builder: $BUILDER_NAME"
  docker buildx create --name "$BUILDER_NAME" --use
  docker buildx inspect --bootstrap
fi

echo "✅ Buildx builder '$BUILDER_NAME' is ready."

echo "🔍 Available platforms:"
docker buildx inspect "$BUILDER_NAME" | grep -i platforms
