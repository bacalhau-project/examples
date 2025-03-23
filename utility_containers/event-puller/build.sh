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

# Check if required commands exist
command -v go >/dev/null 2>&1 || error "go is required but not installed"
command -v docker >/dev/null 2>&1 || error "docker is required but not installed"

# Create bin directory if it doesn't exist
mkdir -p bin

# Generate timestamp for tag
TIMESTAMP=$(date +%Y%m%d%H%M)

# Registry configuration
REGISTRY="docker.io"    
ORGANIZATION="bacalhauproject"      
IMAGE_NAME="event-puller"
TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:${TIMESTAMP}"

# Build the dashboard if Node.js is available
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    log "Building Next.js dashboard..."
    
    # Check if dashboard directory exists and has package.json
    if [ -d "dashboard" ] && [ -f "dashboard/package.json" ]; then
        # Go to dashboard directory
        cd dashboard
        
        # Install dependencies
        log "Installing dashboard dependencies..."
        npm install || warn "Failed to install dashboard dependencies, continuing with build"
        
        # Build the dashboard
        log "Building the dashboard..."
        npm run build || warn "Failed to build dashboard, continuing with build"
        
        # Export as static site if export script exists
        if grep -q "\"export\"" package.json; then
            log "Exporting dashboard as static site..."
            npm run export || warn "Failed to export dashboard, continuing with build"
        fi
        
        # Return to parent directory
        cd ..
    else
        warn "Dashboard directory or package.json not found, skipping dashboard build"
    fi
else
    warn "Node.js or npm not found, skipping dashboard build"
fi

log "Building binary with Go..."
CGO_ENABLED=0 GOARCH=amd64 GOOS=linux go build -ldflags="-s -w" -o bin/event-puller . || error "Failed to build with Go"

if command -v upx >/dev/null 2>&1; then
  log "Compressing binary with UPX..."
  upx --best --lzma bin/event-puller || error "Failed to compress binary"
fi

log "Building Docker image..."
docker build --platform linux/amd64 -t "${TAG}" . || error "Failed to build Docker image"

log "Pushing image to registry..."
docker push "${TAG}" || error "Failed to push Docker image"

# Tag as latest
LATEST_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:latest"
docker tag "${TAG}" "${LATEST_TAG}"
docker push "${LATEST_TAG}"

log "Successfully built and pushed ${TAG}"
log "Also tagged and pushed as ${LATEST_TAG}"