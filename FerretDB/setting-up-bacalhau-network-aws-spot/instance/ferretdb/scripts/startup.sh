#!/bin/bash

set -e

SCRIPT_DIR="${SCRIPT_DIR:-/ferretdb}"

echo "Verifying Docker service..."
if ! systemctl is-active --quiet docker; then
    echo "Docker is not running. Starting Docker..."
    systemctl start docker
    sleep 5
fi

echo "Starting Docker Compose services..."
if [ -f "${SCRIPT_DIR}/docker-compose.yaml" ]; then
    cd "${SCRIPT_DIR}" || exit
    echo "Stopping and removing any existing containers..."
    docker compose down
#    if docker ps -a | grep -q "postgres-documentdb"; then
#        echo "Found stray containers, removing them..."
#        docker ps -a | grep "bacalhau_node-bacalhau-node" | awk '{print $1}' | xargs -r docker rm -f
#    fi
    echo "Pulling latest images..."
    docker compose pull
    echo "Starting services..."
    docker compose up -d
    echo "Docker Compose started."
else
    echo "Error: docker-compose.yaml not found at ${SCRIPT_DIR}/docker-compose.yaml"
    exit 1
fi

echo "Setup complete in ${CLOUD_PROVIDER} region ${REGION}"
echo "Public IP: ${PUBLIC_IP}"
echo "Private IP: ${PRIVATE_IP}"

exit 0
