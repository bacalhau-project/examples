#!/usr/bin/env bash

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
fi

echo "Detected OS: $OS"

# Install Docker based on available package manager
if command -v apt-get >/dev/null 2>&1; then
    # Debian/Ubuntu installation
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

elif command -v yum >/dev/null 2>&1; then
    # DNF-based systems (Amazon Linux 2023, Fedora, RHEL)
    yum install docker -y
    mkdir -p /usr/local/lib/docker/cli-plugins/
    curl -SL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

else
    echo "No supported package manager found (apt-get, dnf)"
    exit 1
fi

# Start and enable Docker service
systemctl start docker
systemctl enable docker

# Verify installations
docker --version
docker compose version
