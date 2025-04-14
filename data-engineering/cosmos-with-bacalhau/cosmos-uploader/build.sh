#!/bin/bash
set -e

# Default values
DEFAULT_CONTAINER="cosmos-uploader"
DEFAULT_TAG="latest"

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Help text
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -c, --container     Container name (default: $DEFAULT_CONTAINER)"
    echo "  -t, --tag           Image tag (default: $DEFAULT_TAG)"
    echo "  -h, --help          Show this help message"
    echo
    echo "Example:"
    echo "  $0 --container cosmos-uploader --tag latest"
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

# Full image name
IMAGE_NAME="$CONTAINER:$TAG"
TIMESTAMP_TAG="$CONTAINER:$(date +%Y%m%d%H%M)"

echo "Building image: $IMAGE_NAME"
echo "Timestamp tag: $TIMESTAMP_TAG"

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
-t "$IMAGE_NAME" \
-t "$TIMESTAMP_TAG" \
-f "$TEMP_DOCKERFILE" \
"$PROJECT_ROOT"

# Clean up
rm -f "$TEMP_DOCKERFILE"

echo "Build complete! Images created:"
echo "  $IMAGE_NAME"
echo "  $TIMESTAMP_TAG"