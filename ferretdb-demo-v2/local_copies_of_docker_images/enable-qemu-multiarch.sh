#!/bin/bash

set -e

BUILDER_NAME="multiarch-builder"

echo "🔧 Installing QEMU binfmt handlers (via tonistiigi/binfmt)..."
docker run --privileged --rm tonistiigi/binfmt --install all

echo "🔍 Checking for existing Buildx builder: $BUILDER_NAME"
if docker buildx ls | grep -q "$BUILDER_NAME"; then
  echo "✅ Builder '$BUILDER_NAME' already exists."
else
  echo "🔧 Creating builder '$BUILDER_NAME'"
  docker buildx create --name "$BUILDER_NAME" --use
fi

echo "🚀 Bootstrapping builder '$BUILDER_NAME'..."
docker buildx inspect --bootstrap "$BUILDER_NAME"

echo "🔎 Verifying QEMU emulation for arm64..."
ARCH=$(docker run --rm --platform linux/arm64 alpine uname -m)

if [ "$ARCH" == "aarch64" ]; then
  echo "✅ QEMU is working! Successfully ran linux/arm64 container."
else
  echo "❌ QEMU setup failed. Output from container: $ARCH"
  exit 1
fi

echo "✅ All set! You can now build and push multiarch Docker images."
