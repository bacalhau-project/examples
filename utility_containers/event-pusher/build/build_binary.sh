#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if config.yaml exists in root directory
if [ ! -f "../config.yaml" ]; then
    error "config.yaml not found in root directory"
fi

# Create build directory if it doesn't exist
mkdir -p bin

# Build the binary
log "Building Go binary..."
cd ../src
if ! go build -o ../build/bin/event-pusher; then
    error "Failed to build Go binary"
fi
cd ../build

# Make the binary executable
chmod +x bin/event-pusher

log "Binary built successfully. Run ./run_binary.sh to execute." 