#!/bin/bash

set -e

# Function to get instance metadata
get_instance_metadata() {
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s -f || echo "")
    if [ -z "$TOKEN" ]; then
        echo "Error: Unable to retrieve metadata token" >&2
        return 1
    fi
    RESULT=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s -f "http://169.254.169.254/latest/meta-data/$1" || echo "")
    if [ -z "$RESULT" ]; then
        echo "Error: Unable to retrieve metadata for $1" >&2
        return 1
    fi
    echo "$RESULT"
}

# Get instance ID and region
INSTANCE_ID=$(get_instance_metadata "instance-id") || INSTANCE_ID="unknown"
REGION=$(get_instance_metadata "placement/region") || REGION="unknown"

# Get instance type
INSTANCE_TYPE=$(get_instance_metadata "instance-type") || INSTANCE_TYPE="unknown"
INSTANCE_FAMILY=$(echo "$INSTANCE_TYPE" | cut -d. -f1)

# Get vCPU count and memory size
VCPU_COUNT=$(nproc --all || echo "unknown")
MEMORY_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
MEMORY_GB=$(awk "BEGIN {printf \"%.1f\", $MEMORY_TOTAL / 1024}")

# Get total disk size
DISK_SIZE=$(df -BG / | awk 'NR==2 {print $2}' | sed 's/G//')

# Write environment variables to /etc/node-config
cat << EOF > /etc/node-config
EC2_INSTANCE_FAMILY=$INSTANCE_FAMILY
EC2_VCPU_COUNT=$VCPU_COUNT
EC2_MEMORY_GB=$MEMORY_GB
EC2_DISK_GB=$DISK_SIZE
ORCHESTRATORS=$ORCHESTRATORS
EOF

chmod 644 /etc/node-config

echo "Node configuration has been written to /etc/node-config"
cat /etc/node-config