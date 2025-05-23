#!/bin/bash
# File: optimize-for-containers.sh
# Purpose: Configure system for large-scale container deployments
# Usage: sudo bash optimize-for-containers.sh
# Optimized for: 40 CPU cores, 251GB RAM system

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

# 1b. Add process limits configuration
echo "Configuring process limits..."
cat << EOF > /etc/security/limits.d/90-nproc.conf
*               soft    nproc           1048576
*               hard    nproc           1048576
root            soft    nproc           1048576
root            hard    nproc           1048576
EOF

# 2. Adjust kernel parameters for networking
echo "Optimizing kernel parameters..."
cat << EOF > /etc/sysctl.d/99-container-network.conf
# File descriptor limits
fs.file-max = 2621440
fs.nr_open = 2621440

# Network connection tracking - increased for 40 cores
net.netfilter.nf_conntrack_max = 3145728
net.netfilter.nf_conntrack_tcp_timeout_established = 86400
net.netfilter.nf_conntrack_tcp_timeout_close_wait = 30
net.netfilter.nf_conntrack_tcp_timeout_fin_wait = 30
net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30

# Network performance - increased for 40 cores
net.core.somaxconn = 81920
net.core.netdev_max_backlog = 375000
net.ipv4.tcp_max_syn_backlog = 81920
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_keepalive_probes = 5

# Expand local port range for many outbound connections
net.ipv4.ip_local_port_range = 1024 65535

# Memory optimizations for networking - increased for 251GB RAM
net.ipv4.tcp_mem = 1048576 1572864 2097152
net.ipv4.udp_mem = 131072 262144 524288
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# ARP cache sizing - increased for larger network
net.ipv4.neigh.default.gc_thresh1 = 32768
net.ipv4.neigh.default.gc_thresh2 = 65536
net.ipv4.neigh.default.gc_thresh3 = 131072

net.unix.max_dgram_qlen = 1024
net.core.netdev_budget = 1000
net.core.netdev_budget_usecs = 25000

# VM overcommit settings - good for containers with large RAM
vm.overcommit_memory = 1
vm.swappiness = 5
vm.max_map_count = 1048576
vm.vfs_cache_pressure = 50
EOF

# 2b. Add cgroup v2 and process kernel parameters
echo "Adding cgroup v2 and process limits to kernel parameters..."
cat << EOF > /etc/sysctl.d/99-container-process.conf
# Process limits for container-heavy workloads
kernel.pid_max = 4194304
kernel.threads-max = 4194304

# Increase inotify limits for container monitoring
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches = 524288
EOF

# 3. Apply sysctl changes immediately
echo "Applying sysctl changes..."
sysctl -p /etc/sysctl.d/99-container-network.conf
sysctl -p /etc/sysctl.d/99-container-process.conf

# 3b. Configure systemd defaults
echo "Setting systemd DefaultTasksMax..."
if grep -q "^#DefaultTasksMax" /etc/systemd/system.conf; then
  # Uncomment and set if it exists but is commented
  sed -i 's/^#DefaultTasksMax=.*/DefaultTasksMax=1048576/' /etc/systemd/system.conf
else
  # Add if it doesn't exist
  echo "DefaultTasksMax=1048576" >> /etc/systemd/system.conf
fi

# 4. Configure Docker daemon
echo "Optimizing Docker daemon configuration..."
mkdir -p /etc/docker
cat << EOF > /etc/docker/daemon.json
{
  "default-address-pools": [
    {"base": "172.20.0.0/16", "size": 20}
  ],
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "1",
    "compress": "false"
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 1048576,
      "Soft": 1048576
    },
    "nproc": {
      "Name": "nproc",
      "Hard": 1048576,
      "Soft": 1048576
    }
  },
  "mtu": 1450,
  "dns": ["1.1.1.1"],
  "max-concurrent-downloads": 20,
  "max-concurrent-uploads": 20,
  "storage-driver": "overlay2",
  "default-cgroupns-mode": "host"
}
EOF

# 4b. Create systemd override for Docker
echo "Creating systemd override for Docker..."
mkdir -p /etc/systemd/system/docker.service.d/
cat << EOF > /etc/systemd/system/docker.service.d/override.conf
[Service]
LimitNOFILE=1048576
LimitNPROC=1048576
LimitCORE=infinity
TasksMax=infinity
TimeoutStartSec=300
TimeoutStopSec=300
OOMScoreAdjust=-500
EOF

# 5. Restart Docker to apply changes
echo "Restarting Docker service..."
systemctl daemon-reload
systemctl restart docker

# 6. Verify changes
echo "Verifying system configuration:"
echo "Current file descriptor limit: $(ulimit -n)"
echo "Current process limit: $(ulimit -u)"
echo "Connection tracking max: $(sysctl -n net.netfilter.nf_conntrack_max)"
echo "Local port range: $(sysctl -n net.ipv4.ip_local_port_range)"
echo "PID max: $(sysctl -n kernel.pid_max)"
echo "CPU cores available: $(nproc)"
echo "Memory available: $(free -h | grep Mem | awk '{print $2}')"
echo "Systemd DefaultTasksMax: $(grep DefaultTasksMax /etc/systemd/system.conf)"
echo "Docker TasksMax: $(systemctl show docker | grep TasksMax)"

echo "== System optimization complete =="
echo "It's recommended to reboot the system to ensure all changes are applied correctly."