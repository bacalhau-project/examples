#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Parse arguments
PUSH=false
ARCH=""
for arg in "$@"; do
    case $arg in
        --push)
            PUSH=true
            ;;
        --arch=*)
            ARCH="${arg#*=}"
            ;;
        *)
            error "Unknown argument: $arg"
            ;;
    esac
done

# Check if required commands exist
command -v go >/dev/null 2>&1 || error "go is required but not installed"
command -v node >/dev/null 2>&1 || error "node is required but not installed"
command -v npm >/dev/null 2>&1 || error "npm is required but not installed"

# Only check for docker if we're pushing
if [ "$PUSH" = true ]; then
    command -v docker >/dev/null 2>&1 || error "docker is required but not installed"
fi

# Create bin directory if it doesn't exist
mkdir -p bin

# Detect system architecture if not specified
if [ -z "$ARCH" ]; then
    case "$(uname -m)" in
        x86_64)
            ARCH="amd64"
            ;;
        aarch64|arm64)
            ARCH="arm64"
            ;;
        *)
            error "Unsupported architecture: $(uname -m)"
            ;;
    esac
fi

# Set build environment variables
export GOOS="darwin"
export GOARCH="$ARCH"
export CGO_ENABLED=0

# Build the dashboard (now mandatory)
log "Building dashboard..."
cd dashboard
npm install
npm run build
cd ..

# Build the Go binary
log "Building binary for ${GOOS}/${GOARCH}..."
go build -o bin/event-puller \
    -ldflags="-s -w" \
    -trimpath \
    ./main.go

# Verify the binary
if [ ! -f "bin/event-puller" ]; then
    error "Binary was not created"
fi

# Check binary architecture
BINARY_ARCH=$(file bin/event-puller | awk '{print $NF}')
log "Binary architecture: ${BINARY_ARCH}"

log "Build complete! You can now run ./bin/event-puller"

# If --push is specified, build and push the Docker image
if [ "$PUSH" = true ]; then
    log "Building multi-architecture Docker image..."
    
    # Create and use a new builder instance if it doesn't exist
    if ! docker buildx inspect multiarch-builder >/dev/null 2>&1; then
        log "Creating new buildx builder..."
        docker buildx create --name multiarch-builder --driver docker-container --bootstrap
    fi
    docker buildx use multiarch-builder

    # Generate timestamp for tag
    TIMESTAMP=$(date +%Y%m%d%H%M)
    
    # Registry configuration
    REGISTRY="ghcr.io"    
    ORGANIZATION="bacalhau-project"      
    IMAGE_NAME="event-puller"
    TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:${TIMESTAMP}"
    LATEST_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:latest"

    # Build and push multi-architecture image
    log "Building and pushing for amd64 and arm64..."
    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        --tag "${TAG}" \
        --tag "${LATEST_TAG}" \
        --push \
        .

    log "Successfully built and pushed ${TAG}"
    log "Also tagged and pushed as ${LATEST_TAG}"
fi