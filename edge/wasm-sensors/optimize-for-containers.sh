#!/bin/bash
# File: optimize-for-containers.sh
# Purpose: Configure system for large-scale container deployments
# Usage: sudo bash optimize-for-containers.sh

# Exit on error
set -e

echo "== Optimizing system for large-scale container deployments =="

# 1. Adjust system limits for file descriptors
echo "Configuring file descriptor limits..."
cat << EOF > /etc/security/limits.d/91-nofile.conf
*               soft    nofile          1048576
*               hard    nofile          1048576
root            soft    nofile          1048576
root            hard    nofile          1048576
EOF

# 2. Adjust kernel parameters for networking
echo "Optimizing kernel parameters..."
cat << EOF > /etc/sysctl.d/99-container-network.conf
# File descriptor limits
fs.file-max = 2097152
fs.nr_open = 2097152

# Network connection tracking
net.netfilter.nf_conntrack_max = 1048576
net.netfilter.nf_conntrack_tcp_timeout_established = 86400
net.netfilter.nf_conntrack_tcp_timeout_close_wait = 30
net.netfilter.nf_conntrack_tcp_timeout_fin_wait = 30
net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30

# Network performance
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 250000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_keepalive_probes = 5

# Expand local port range for many outbound connections
net.ipv4.ip_local_port_range = 1024 65535

# Memory optimizations for networking
net.ipv4.tcp_mem = 786432 1048576 1572864
net.ipv4.udp_mem = 65536 131072 262144
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.ipv4.tcp_rmem = 4096 87380 33554432
net.ipv4.tcp_wmem = 4096 65536 33554432

# ARP cache sizing
net.ipv4.neigh.default.gc_thresh1 = 4096
net.ipv4.neigh.default.gc_thresh2 = 8192
net.ipv4.neigh.default.gc_thresh3 = 16384

# VM overcommit settings - good for containers
vm.overcommit_memory = 1
vm.swappiness = 10
EOF

# 3. Apply sysctl changes immediately
echo "Applying sysctl changes..."
sysctl -p /etc/sysctl.d/99-container-network.conf

# 4. Configure Docker daemon
echo "Optimizing Docker daemon configuration..."
mkdir -p /etc/docker
cat << EOF > /etc/docker/daemon.json
{
  "default-address-pools": [
    {"base": "172.17.0.0/12", "size": 24}
  ],
  "log-driver": "local",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 1048576,
      "Soft": 1048576
    }
  },
  "dns": ["8.8.8.8", "8.8.4.4"],
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10
}
EOF

# 5. Restart Docker to apply changes
echo "Restarting Docker service..."
systemctl restart docker

# 6. Verify changes
echo "Verifying system configuration:"
echo "Current file descriptor limit: $(ulimit -n)"
echo "Connection tracking max: $(sysctl -n net.netfilter.nf_conntrack_max)"
echo "Local port range: $(sysctl -n net.ipv4.ip_local_port_range)"

echo "== System optimization complete =="
echo "It's recommended to reboot the system to ensure all changes are applied correctly."