#!/usr/bin/env bash

set -e

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
fi

echo "Detected OS: $OS"
retry_command() {
    local n=0
    local max=5
    local delay=15
    while true; do
        "$@" && break || {
            if [[ $n -lt $max ]]; then
                ((n++))
                echo "Command failed. Attempt $n/$max. Retrying in $delay seconds..."
                sleep $delay
            else
                echo "The command has failed after $n attempts."
                return 1
            fi
        }
    done
}

if command -v apt-get >/dev/null 2>&1; then
    echo "Using apt package manager..."
    
    retry_command apt-get update
    retry_command apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        pigz \
        jq \
        libltdl7 \
        libslirp0 \
        slirp4netns \
        apt-transport-https \
        software-properties-common

    install -m 0755 -d /etc/apt/keyrings
    rm -f /etc/apt/keyrings/docker.gpg
    retry_command curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    retry_command apt-get update

    retry_command apt-get install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

elif command -v yum >/dev/null 2>&1; then
    echo "Using yum package manager..."
    retry_command yum install -y docker
    mkdir -p /usr/local/lib/docker/cli-plugins/
    retry_command curl -SL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

else
    echo "No supported package manager found (apt-get, dnf)"
    exit 1
fi

echo "Starting Docker service..."
systemctl start docker || {
    echo "Failed to start Docker service. Waiting 10 seconds and trying again..."
    sleep 10
    systemctl start docker
}

echo "Enabling Docker service..."
systemctl enable docker || {
    echo "Failed to enable Docker service. Waiting 10 seconds and trying again..."
    sleep 10
    systemctl enable docker
}

echo "Verifying Docker installation..."
if command -v docker >/dev/null 2>&1; then
    docker --version
    docker compose version
else
    echo "Docker installation verification failed"
    exit 1
fi
