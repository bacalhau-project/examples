#!/bin/bash

set -e

get_instance_metadata() {
    RESULT=$(curl -s -f "http://metadata.google.internal/computeMetadata/v1/instance/$1" -H "Metadata-Flavor: Google" || echo "")
    if [ -z "$RESULT" ]; then
        echo "Error: Unable to retrieve metadata for $1" >&2
        return 1
    fi
    echo "$RESULT"
}

INSTANCE_ID=$(get_instance_metadata "id") || INSTANCE_ID="unknown"
REGION=$(get_instance_metadata "zone" | sed 's|/zones/||' | sed 's|-\([a-z]*\)$|\1|' || REGION="unknown")
INSTANCE_TYPE=$(get_instance_metadata "machine-type" | sed 's|/machineTypes/||' || INSTANCE_TYPE="unknown")
INSTANCE_FAMILY=$(echo "$INSTANCE_TYPE" | cut -d. -f1)

# Get vCPU count and memory size
VCPU_COUNT=$(nproc --all || echo "unknown")
MEMORY_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
MEMORY_GB=$(awk "BEGIN {printf \"%.1f\", $MEMORY_TOTAL / 1024}")

# Get total disk size
DISK_SIZE=$(df -BG / | awk 'NR==2 {print $2}' | sed 's/G//')

# Write environment variables to /etc/node-config
cat << EOF > /etc/node-config
GCP_INSTANCE_FAMILY=$INSTANCE_FAMILY
GCP_VCPU_COUNT=$VCPU_COUNT
GCP_MEMORY_GB=$MEMORY_GB
GCP_DISK_GB=$DISK_SIZE
ORCHESTRATORS=$ORCHESTRATORS
EOF

cat << EOF > /etc/bacalhau-config.yaml
NameProvider: "uuid"
API:
  Port: 1234
Compute:
  Enabled: true
  Orchestrators:
    - $ORCHESTRATORS
  Auth:
    Token: "$TOKEN"
  TLS:
    RequireTLS: ${REQUIRE_TLS:-false}
EOF

chmod 644 /etc/node-config

echo "Node configuration has been written to /etc/node-config"
cat /etc/node-config