#!/usr/bin/env bash

# Install docker
sudo apt-get update && \
sudo apt-get install -y docker.io && \
sudo apt-get clean

# Start docker
sudo systemctl start docker

# Enable docker to start on boot
sudo systemctl enable docker