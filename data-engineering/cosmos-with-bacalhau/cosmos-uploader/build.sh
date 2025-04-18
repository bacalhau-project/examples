#!/bin/bash
set -e

# Default values
DEFAULT_CONTAINER="cosmos-uploader"
DEFAULT_TAG="latest"
REGISTRY="ghcr.io/bacalhau-project"
PUSH_TO_REGISTRY=false

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Help text
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -c, --container     Container name (default: $DEFAULT_CONTAINER)"
    echo "  -t, --tag           Image tag (default: auto-generated from timestamp)"
    echo "  -p, --push          Push to registry after building (default: false)"
    echo "  -r, --registry      Container registry (default: $REGISTRY)"
    echo "  -h, --help          Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --tag v20250416 --push             # Build and push with specific tag"
    echo "  $0 --push                             # Build with auto timestamp tag and push"
    echo "  $0 --tag v20250416                    # Build locally only, no push"
    echo
    echo "IMPORTANT: When used with the Python sensor manager, you must:"
    echo "  1. Build with the --push flag to push to registry"
    echo "  2. Use the same tag with sensor_manager: --uploader-tag <TAG>"
}

# Parse arguments
CONTAINER=$DEFAULT_CONTAINER
TAG=$DEFAULT_TAG

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -c|--container)
            CONTAINER="$2"
            shift
            shift
        ;;
        -t|--tag)
            TAG="$2"
            shift
            shift
        ;;
        -p|--push)
            PUSH_TO_REGISTRY=true
            shift
        ;;
        -r|--registry)
            REGISTRY="$2"
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

# Generate timestamp tag if no explicit tag was provided
if [ "$TAG" = "latest" ]; then
    TIMESTAMP=$(date +%Y%m%d%H%M)
    TAG="v$TIMESTAMP"
    echo "No specific tag provided, using timestamp-based tag: $TAG"
fi

# Full image names
LOCAL_IMAGE_NAME="$CONTAINER:$TAG"
LOCAL_LATEST_TAG="$CONTAINER:latest"
REGISTRY_IMAGE_NAME="$REGISTRY/$CONTAINER:$TAG"
REGISTRY_LATEST_TAG="$REGISTRY/$CONTAINER:latest"

echo "Building image with tag: $TAG"
echo "Local image name: $LOCAL_IMAGE_NAME"
if [ "$PUSH_TO_REGISTRY" = true ]; then
    echo "Will push to registry as: $REGISTRY_IMAGE_NAME"
fi

# Verify .NET source files
APP_DIR="${PROJECT_ROOT}/cosmos-uploader"
if [ ! -d "$APP_DIR" ]; then
    echo "Error: Application directory not found at $APP_DIR"
    exit 1
fi

if [ ! -f "$APP_DIR/CosmosUploader.csproj" ]; then
    echo "Error: CosmosUploader.csproj not found at $APP_DIR"
    exit 1
fi

# Create a temporary Dockerfile that will work with the context
TEMP_DOCKERFILE="$SCRIPT_DIR/Dockerfile.tmp"
cat > "$TEMP_DOCKERFILE" << EOF
# Use .NET 8.0 SDK as the build image
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build

# Set working directory for project file
WORKDIR /src

# DEBUG: List directories
RUN ls -la /

# Copy project file and restore dependencies
COPY cosmos-uploader/CosmosUploader.csproj .
RUN dotnet restore

# Copy all files needed for the build
WORKDIR /src/app
COPY cosmos-uploader/. .

# DEBUG: List content in build context
RUN ls -la

# Build and publish
RUN dotnet publish -c Release -o /app

# DEBUG: List published files
RUN echo "Build completed. Files in /app:" && ls -la /app

# Build runtime image
FROM mcr.microsoft.com/dotnet/runtime:8.0

WORKDIR /app

# Copy built application from build stage
COPY --from=build /app .

# Copy the entrypoint script directly
COPY cosmos-uploader/entrypoint.sh /app/

# Make the entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# DEBUG: List runtime files
RUN echo "Files in runtime image:" && ls -la /app

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
EOF

# Build the Docker image from project root with temporary Dockerfile
echo "Building Docker image with .NET implementation..."
docker build \
--no-cache \
-t "$LOCAL_IMAGE_NAME" \
-t "$LOCAL_LATEST_TAG" \
-f "$TEMP_DOCKERFILE" \
"$PROJECT_ROOT"

# Clean up
rm -f "$TEMP_DOCKERFILE"

echo "✅ Build completed and tagged as:"
echo "  - $LOCAL_IMAGE_NAME"
echo "  - $LOCAL_LATEST_TAG"

# Push to registry if requested
if [ "$PUSH_TO_REGISTRY" = true ]; then
    echo "Pushing images to registry..."
    
    # Tag with registry prefix
    echo "Tagging for registry..."
    docker tag "$LOCAL_IMAGE_NAME" "$REGISTRY_IMAGE_NAME"
    docker tag "$LOCAL_LATEST_TAG" "$REGISTRY_LATEST_TAG"
    
    # Push both tags to registry
    echo "Pushing versioned tag to registry..."
    docker push "$REGISTRY_IMAGE_NAME"
    
    echo "Pushing latest tag to registry..."
    docker push "$REGISTRY_LATEST_TAG"
    
    echo "✅ Successfully pushed to registry:"
    echo "  - $REGISTRY_IMAGE_NAME"
    echo "  - $REGISTRY_LATEST_TAG"
    
    # Update docker-compose.yml with registry name
    COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
    if [ -f "$COMPOSE_FILE" ]; then
        echo "✅ Updated docker-compose.yml to use registry image: $REGISTRY_IMAGE_NAME"
    else
        echo "Note: docker-compose.yml not found in project root, no file updated."
    fi
else
    echo "Skipping registry push (use --push to enable)"
    
    # Update docker-compose.yml with local name
    COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
    if [ -f "$COMPOSE_FILE" ]; then
        echo "✅ Updated docker-compose.yml to use tagged image: $LOCAL_IMAGE_NAME"
    else
        echo "Note: docker-compose.yml not found in project root, no file updated."
    fi
fi

# Write the tag to a file for other scripts to use
echo "$TAG" > "$PROJECT_ROOT/.latest-image-tag"
if [ "$PUSH_TO_REGISTRY" = true ]; then
    echo "$REGISTRY_IMAGE_NAME" > "$PROJECT_ROOT/.latest-registry-image"
fi