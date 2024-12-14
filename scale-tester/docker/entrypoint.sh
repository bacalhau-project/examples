#!/bin/bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail
trap 'echo "Error on line $LINENO"' ERR

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check for required configuration file
CONFIG_FILE="/root/bacalhau-cloud-config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    error "Configuration file not found at $CONFIG_FILE"
fi

# Validate configuration file
if ! command -v yq &> /dev/null; then
    log "Installing yq for YAML processing..."
    wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq
fi

# Validate YAML syntax
if ! yq eval "$CONFIG_FILE" > /dev/null; then
    error "Invalid YAML configuration file"
fi

# Start bacalhau service
log "Starting bacalhau service..."
if ! command -v bacalhau &> /dev/null; then
    error "Bacalhau binary not found. Please ensure it was installed correctly."
fi

# Apply configuration
log "Applying configuration from $CONFIG_FILE"
export BACALHAU_CONFIG_PATH="$CONFIG_FILE"

# Start bacalhau in the foreground
log "Starting bacalhau node..."
exec bacalhau serve --config "$CONFIG_FILE" 