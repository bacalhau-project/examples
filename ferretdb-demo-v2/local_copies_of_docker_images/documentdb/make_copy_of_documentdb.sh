docker login ghcr.io

SOURCE_IMAGE="ghcr.io/ferretdb/postgres-documentdb:17-0.102.0-ferretdb-2.1.0"

TARGET_IMAGE="ghcr.io/bacalhau-project/examples/ferretdb-demo-documentdb:2504162218"

# Pull the source image
docker pull $SOURCE_IMAGE

# Set the platforms (amd64)
PLATFORMS="linux/amd64"

# Build and push multi-arch image
docker buildx build --platform $PLATFORMS --tag $TARGET_IMAGE --push .
