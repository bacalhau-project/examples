#!/bin/bash
# setup.sh
set -e

echo "Starting AMI setup..."

# Update system
sudo yum update -y

# Install Docker
echo "Installing Docker..."
sudo yum install -y docker
sudo systemctl enable docker
sudo systemctl start docker

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Pull the Bacalhau container
echo "Pulling Bacalhau container..."
sudo docker pull docker.io/bacalhauproject/bacalhau-dind-compute-node:latest

# Create necessary directories
sudo mkdir -p /etc/bacalhau
sudo mkdir -p /bacalhau_node

echo "Setup complete!"