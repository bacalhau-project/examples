#!/bin/bash

# Create the node-config file with placeholder values
cat << EOF > /etc/node-config.template
MACHINE_TYPE="[[.MachineType]]"
HOSTNAME="[[.MachineName]]"
VCPU_COUNT="\${VCPU_COUNT}"
MEMORY_GB="\${MEMORY_GB}"
DISK_GB="\${DISK_GB}"
LOCATION="[[.Location]]"
IP="[[.IP]]"
ORCHESTRATORS="[[.Orchestrators]]"
TOKEN="[[.Token]]"
NODE_TYPE="[[.NodeType]]"
EOF

# Create a script to populate the actual values at runtime
cat << 'EOF' > /usr/local/bin/update-node-config
#!/bin/bash

set -e

# Get vCPU count and memory size
VCPU_COUNT=$(nproc --all || echo "unknown")
MEMORY_TOTAL=$(free -m 2>/dev/null || echo "0" | awk '/^Mem:/{print $2}')
MEMORY_GB=$(awk "BEGIN {printf \"%.1f\", $MEMORY_TOTAL / 1024}")

# Get total disk size
DISK_SIZE=$(df -BG / 2>/dev/null | awk 'NR==2 {print $2}' | sed 's/G//' || echo "unknown")

# Create the actual config file from template
envsubst < /etc/node-config.template > /etc/node-config

chmod 644 /etc/node-config

echo "Node configuration has been updated in /etc/node-config"
EOF

chmod +x /usr/local/bin/update-node-config