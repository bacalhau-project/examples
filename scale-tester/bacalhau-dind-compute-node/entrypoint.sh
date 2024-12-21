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

# Initialize system
log "Initializing system..."
# Configure Docker daemon for read-only cgroup filesystem
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
    "storage-driver": "overlay2",
    "iptables": false,
    "cgroup-parent": "docker",
    "live-restore": true,
    "default-cgroupfs-mode": "private"
}
EOF

# Start Docker daemon with systemd cgroup driver
log "Starting Docker daemon..."
dockerd --storage-driver=overlay2 --iptables=false --cgroup-parent=docker &

# Wait for Docker to be ready
DOCKER_READY_TIMEOUT=30
COUNTER=0
until docker info >/dev/null 2>&1; do
    if [ $COUNTER -gt $DOCKER_READY_TIMEOUT ]; then
        error "Timeout waiting for Docker daemon. Docker logs:
$(tail -n 50 /var/log/dockerd.log)"
    fi
    log "Waiting for Docker daemon... ($COUNTER/$DOCKER_READY_TIMEOUT)"
    COUNTER=$((COUNTER + 1))
    sleep 1
done
success "Docker daemon is ready"

# Check for required configuration file
CONFIG_FILE="/root/bacalhau-cloud-config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    error "Configuration file not found at $CONFIG_FILE"
fi

# Validate configuration file
if ! yq eval "$CONFIG_FILE" > /dev/null; then
    error "Invalid YAML configuration file"
fi

# Update node configuration
log "Updating node configuration..."
update-node-config

# Start bacalhau service
log "Starting bacalhau service..."
if ! command -v bacalhau &> /dev/null; then
    error "Bacalhau binary not found. Please ensure it was installed correctly."
fi

# Apply configuration and start bacalhau
log "Starting bacalhau node with config from $CONFIG_FILE"
export BACALHAU_CONFIG_PATH="$CONFIG_FILE"
exec bacalhau serve --config "$CONFIG_FILE"
