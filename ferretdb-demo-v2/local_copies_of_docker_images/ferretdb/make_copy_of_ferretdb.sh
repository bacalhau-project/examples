docker login ghcr.io

SOURCE_IMAGE="ghcr.io/ferretdb/ferretdb:2.1.0"

TIMESTAMP=$(date +%Y%m%d%H%M)

TARGET_IMAGE="ghcr.io/bacalhau-project/examples/ferretdb-demo-ferretdb:$TIMESTAMP"

# Pull the source image
docker pull $SOURCE_IMAGE

# Set the platforms (amd64,arm64)
PLATFORMS="linux/amd64,linux/arm64"

# Build and push multi-arch image
docker buildx build \
  --platform $PLATFORMS \
  --tag $TARGET_IMAGE \
  --push .
