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
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if required commands exist
command -v tinygo >/dev/null 2>&1 || error "tinygo is required but not installed. Install it from https://tinygo.org/getting-started/install/"
command -v go >/dev/null 2>&1 || error "go is required but not installed. Install it from https://golang.org/doc/install"

# Create output directory
mkdir -p bin

# Download dependencies
log "Downloading Go dependencies..."
go mod tidy || error "Failed to download dependencies"

# Function to build the WASM module
build_wasm() {
    local output_name=$1
    local tags=$2
    local description=$3
    
    log "Building ${description}..."
    # Note: we also add the wasm build tag explicitly, and use wasip1 GOOS
    GOOS=wasip1 GOARCH=wasm tinygo build -target=wasi -gc=leaking -no-debug -tags="wasm $tags" -o "$output_name" . || error "Failed to build with TinyGo"
    log "Successfully built $output_name"
}

# Build the full version with HTTP support
build_wasm "bin/event-pusher.wasm" "" "WebAssembly binary with HTTP support"

# Build the simulation-only version without HTTP imports
build_wasm "bin/event-pusher-nohttp.wasm" "nohttp" "simulation-only WebAssembly binary (no HTTP imports)"

log "Build completed successfully!"
log ""
log "To run the full version (requires WASI preview2 HTTP support):"
log "  wasmtime --wasi-modules=preview2 bin/event-pusher.wasm"
log ""
log "To run the simulation-only version (works with standard wasmtime):"
log "  wasmtime --env SIMULATE=true bin/event-pusher-nohttp.wasm"
log ""
log "Make sure the required environment variables are set:"
log "AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SQS_QUEUE_URL"
log "Optional variables: COLOR, VM_NAME, MAX_INTERVAL_SECONDS, RANDOM_OFF, MAX_MESSAGES, SIMULATE"