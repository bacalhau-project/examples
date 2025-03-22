#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[RUN]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if wasmtime is installed
command -v wasmtime >/dev/null 2>&1 || error "wasmtime is required but not installed. Install it from https://wasmtime.dev/"

# Check for binary files
if [[ ! -f bin/event-pusher.wasm && ! -f bin/event-pusher-nohttp.wasm ]]; then
    log "WASM binary not found. Building it first..."
    ./build_wasm.sh
fi

# Check if we're running in simulation mode
SIMULATE=${SIMULATE:-"false"}
USE_NOHTTP=${USE_NOHTTP:-"false"}

# If SIMULATE is set and we have the no-http binary, use it
if [[ "$SIMULATE" == "true" || "$SIMULATE" == "1" || "$SIMULATE" == "yes" ]] && [[ -f bin/event-pusher-nohttp.wasm ]]; then
    BINARY_PATH="bin/event-pusher-nohttp.wasm"
    USE_NOHTTP="true"
    log "Using simulation-only binary (no HTTP imports)"
elif [[ "$USE_NOHTTP" == "true" || "$USE_NOHTTP" == "1" || "$USE_NOHTTP" == "yes" ]] && [[ -f bin/event-pusher-nohttp.wasm ]]; then
    BINARY_PATH="bin/event-pusher-nohttp.wasm"
    log "Using simulation-only binary (no HTTP imports)"
    # Force SIMULATE mode if using nohttp binary
    SIMULATE="true"
    export SIMULATE
    warn "Forcing SIMULATE=true because you're using the nohttp binary"
else
    BINARY_PATH="bin/event-pusher.wasm"
    log "Using full binary with HTTP support"
    if [[ "$SIMULATE" != "true" && "$SIMULATE" != "1" && "$SIMULATE" != "yes" ]]; then
        warn "This requires a runtime with WASI preview2 HTTP support"
        warn "If you get 'unknown import' errors, try setting SIMULATE=true or USE_NOHTTP=true"
    fi
fi

log "Running event pusher..."
log "Using environment variables:"
log "AWS_REGION=${AWS_REGION:-not set}"
log "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:+set (value hidden)}"
log "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:+set (value hidden)}"
log "SQS_QUEUE_URL=${SQS_QUEUE_URL:-not set}"
log "COLOR=${COLOR:-#000000}"
log "VM_NAME=${VM_NAME:-default}"
log "MAX_INTERVAL_SECONDS=${MAX_INTERVAL_SECONDS:-5}"
log "RANDOM_OFF=${RANDOM_OFF:-false}"
log "MAX_MESSAGES=${MAX_MESSAGES:-0 (unlimited)}"
log "SIMULATE=${SIMULATE}"
log ""
log "Starting event-pusher. Press Ctrl+C to stop."

# Build environment variable arguments
ENV_ARGS=()

# Add all known environment variables
for var in AWS_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY SQS_QUEUE_URL COLOR VM_NAME MAX_INTERVAL_SECONDS RANDOM_OFF MAX_MESSAGES SIMULATE; do
    ENV_ARGS+=(--env "$var")
done

# Add WASI preview2 flag for the full HTTP version
if [[ "$USE_NOHTTP" != "true" ]]; then
    ENV_ARGS+=(--wasi-modules=preview2)
fi

# Run the WASM module
log "Running $BINARY_PATH with wasmtime..."
wasmtime "${ENV_ARGS[@]}" "$BINARY_PATH"