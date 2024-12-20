#!/usr/bin/env bash

set -x

# Set non-interactive mode for apt-get
export DEBIAN_FRONTEND=noninteractive

# Update package list
sudo apt-get update

# Install python3, python3-venv, and python3-pip
sudo apt-get install -y python3 python3-venv python3-pip

# Install Docker
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker

# Add the current user to the docker group
sudo usermod -aG docker "$USER"

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install pip packages
pip install -r requirements.txt

# Install k3s
curl -sfL https://get.k3s.io | sh

# Add Kubernetes repository and install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Install k3d (k3s kubectl plugin)
curl -s https://raw.githubusercontent.com/rancher/k3d/main/install.sh | bash

# Create 5 nodes
k3d cluster create "$(hostname)-cluster" --servers 3 || {
    echo "Failed to create cluster. Retrying with sudo..."
    sudo -E k3d cluster create "$(hostname)-cluster" --servers 3
}

# Ensure script.py is present
if [ ! -f ./remote/script.py ]; then
    echo "script.py not found!"
    exit 1
fi

# Ensure Kubernetes configuration file is present
if [ ! -f ~/.kube/config ]; then
    echo "Kubernetes configuration file not found!"
    exit 1
fi

# Run the Python script
.venv/bin/python3 ./remote/script.py