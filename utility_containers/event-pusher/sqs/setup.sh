#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[SETUP]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if pip is installed
command -v pip3 >/dev/null 2>&1 || error "pip3 is required but not installed"

# Install dependencies
log "Installing Python dependencies..."
pip3 install -r requirements.txt

log "Setup complete! You can now run ./listen_to_queue.py" 