#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[RUN]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if binary exists
if [ ! -f "bin/event-pusher" ]; then
    error "Binary not found. Please run build_binary.sh first."
fi

# Check if config.yaml exists in root directory
if [ ! -f "../config.yaml" ]; then
    error "config.yaml not found in root directory"
fi

# Run the binary with the config file from the root directory
log "Running event pusher with config.yaml..."
cd ..
./build/bin/event-pusher -config ../config.yaml 