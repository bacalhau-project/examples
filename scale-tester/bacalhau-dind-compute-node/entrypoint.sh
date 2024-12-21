#!/bin/bash
set -euo pipefail

# Start Docker daemon with minimal configuration
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
    "storage-driver": "vfs",
    "iptables": false,
    "live-restore": false,
    "exec-opts": ["native.cgroupdriver=cgroupfs"],
    "cgroup-parent": "docker.slice"
}
EOF

# Start Docker daemon (without duplicate flags)
dockerd &

# Wait for Docker with fail-fast
TIMEOUT=15
while ! docker info >/dev/null 2>&1; do
    if [ $((TIMEOUT--)) -le 0 ]; then
        echo "Docker daemon failed to start" >&2
        exit 1
    fi
    sleep 1
done

# Start Bacalhau with minimal config
CONFIG_FILE="${BACALHAU_CONFIG_PATH:-/root/bacalhau-cloud-config.yaml}"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Configuration file not found at $CONFIG_FILE" >&2
    exit 1
fi

exec bacalhau serve --config "$CONFIG_FILE"
