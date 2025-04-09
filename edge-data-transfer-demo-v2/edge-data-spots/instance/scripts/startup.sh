#!/bin/bash

set -e

BACALHAU_NODE_DIR="${BACALHAU_NODE_DIR:-/bacalhau_node}"

get_cloud_metadata() {
    cloud=$(cloud-init query cloud-name)

    if [ "${cloud}" = "gce" ]; then
        echo "Detected GCP environment"
        CLOUD_PROVIDER="GCP"
        REGION=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | cut -d'/' -f4)
        ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | cut -d'/' -f4)
        PUBLIC_IP=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip")
        PRIVATE_IP=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip")
        INSTANCE_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/id")
        INSTANCE_TYPE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/machine-type" | cut -d'/' -f4)
        PROJECT_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/project/project-id")
        return 0
    elif [ "${cloud}" = "aws" ]; then
        echo "Detected AWS environment"
        CLOUD_PROVIDER="AWS"
        TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
        REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
        ZONE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
        PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
        PRIVATE_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/local-ipv4)
        INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
        INSTANCE_TYPE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-type)
        return 0
    elif [ "${cloud}" = "azure" ]; then
        echo "Detected Azure environment"
        CLOUD_PROVIDER="AZURE"
        METADATA=$(curl -s -H "Metadata:true" "http://169.254.169.254/metadata/instance?api-version=2021-02-01")
        REGION=$(echo "$METADATA" | jq -r .compute.location)
        ZONE=$(echo "$METADATA" | jq -r .compute.zone)
        PUBLIC_IP=$(curl -s ip.me)
        PRIVATE_IP=$(echo "$METADATA" | jq -r .network.interface[0].ipv4.ipAddress[0].privateIpAddress)
        INSTANCE_ID=$(echo "$METADATA" | jq -r .compute.vmId)
        INSTANCE_TYPE=$(echo "$METADATA" | jq -r .compute.vmSize)
        return 0
    else
        echo "Could not detect cloud provider - no node info will be set"
        return 0
    fi
}

get_cloud_metadata
cat > "${BACALHAU_NODE_DIR}/node-info" << EOF
CLOUD_PROVIDER=${CLOUD_PROVIDER}
REGION=${REGION}
ZONE=${ZONE}
PUBLIC_IP=${PUBLIC_IP}
PRIVATE_IP=${PRIVATE_IP}
INSTANCE_ID=${INSTANCE_ID}
INSTANCE_TYPE=${INSTANCE_TYPE}
EOF


LABELS=$(awk -F= '{print $1 "=" $2}' /bacalhau_node/node-info | tr '\n' ',' | sed 's/,$//')


sed -i '/^LABELS=/d' /etc/environment
echo "LABELS=${LABELS}" >> /etc/environment


sed -i '/^export LABELS=/d' ~/.profile
echo 'export LABELS=$(grep LABELS /etc/environment | cut -d "=" -f2-)' >> ~/.profile


source ~/.profile

if [ "$CLOUD_PROVIDER" = "GCP" ]; then
    echo "PROJECT_ID=${PROJECT_ID}" >> "${BACALHAU_NODE_DIR}/node-info"
fi

# shellcheck disable=SC1091
source "${BACALHAU_NODE_DIR}/node-info"

echo "Verifying Docker service..."
if ! systemctl is-active --quiet docker; then
    echo "Docker is not running. Starting Docker..."
    systemctl start docker
    sleep 5  # Give Docker time to start
fi

echo "Setting up configuration..."
if [ -f "${BACALHAU_NODE_DIR}/config.yaml" ]; then
    echo "Configuration file exists at ${BACALHAU_NODE_DIR}/config.yaml"
else
    echo "Error: Configuration file not found at ${BACALHAU_NODE_DIR}/config.yaml"
    exit 1
fi

echo "Starting Docker Compose services..."
if [ -f "${BACALHAU_NODE_DIR}/docker-compose.yaml" ]; then
    cd "${BACALHAU_NODE_DIR}" || exit
    echo "Stopping and removing any existing containers..."
    docker compose down
    if docker ps -a | grep -q "bacalhau_node-bacalhau-node"; then
        echo "Found stray containers, removing them..."
        docker ps -a | grep "bacalhau_node-bacalhau-node" | awk '{print $1}' | xargs -r docker rm -f
    fi
    echo "Pulling latest images..."
    docker compose pull
    echo "Starting services..."
    docker compose up -d
    echo "Docker Compose started."
else
    echo "Error: docker-compose.yaml not found at ${BACALHAU_NODE_DIR}/docker-compose.yaml"
    exit 1
fi

echo "Bacalhau node setup complete in ${CLOUD_PROVIDER} region ${REGION}"
echo "Public IP: ${PUBLIC_IP}"
echo "Private IP: ${PRIVATE_IP}"

exit 0
