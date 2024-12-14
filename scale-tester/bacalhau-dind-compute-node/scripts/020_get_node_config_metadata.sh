#!/bin/bash

set -e

# Get vCPU count and memory size
VCPU_COUNT=$(nproc --all || echo "unknown")
MEMORY_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
MEMORY_GB=$(awk "BEGIN {printf \"%.1f\", $MEMORY_TOTAL / 1024}")

# Get total disk size
DISK_SIZE=$(df -BG / | awk 'NR==2 {print $2}' | sed 's/G//')

# Write environment variables to /etc/node-config
cat << EOF > /etc/node-config
MACHINE_TYPE="[[.MachineType]]"
HOSTNAME="[[.MachineName]]"
VCPU_COUNT="$VCPU_COUNT"
MEMORY_GB="$MEMORY_GB"
DISK_GB="$DISK_SIZE"
LOCATION="[[.Location]]"
IP="[[.IP]]"
ORCHESTRATORS="[[.Orchestrators]]"
TOKEN="[[.Token]]"
NODE_TYPE="[[.NodeType]]"
EOF

chmod 644 /etc/node-config

echo "Node configuration has been written to /etc/node-config"
cat /etc/node-config