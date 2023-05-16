#!/bin/bash
# shellcheck disable=SC1091,SC2312
set -euo pipefail
IFS=$'\n\t'

function setup-directories() {
    mkdir -p /data # for all data for Bacalhau

    mkdir -p /node # for node setup scripts
    chmod 0700 /node
}

function install-go() {
  echo "Installing Go..."
  rm -fr /usr/local/go /usr/local/bin/go
  curl --silent --show-error --location --fail https://go.dev/dl/go1.20.4.linux-amd64.tar.gz | sudo tar --extract --gzip --file=- --directory=/usr/local
  sudo ln -s /usr/local/go/bin/go /usr/local/bin/go
  go version
}

function install-docker() {
  echo "Installing Docker"
  sudo apt-get install -y \
      ca-certificates \
      curl \
      gnupg \
      lsb-release
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
}

function install-git() {
  echo "Installing Git..."
  sudo apt-get update -y
  sudo apt-get install -y git
  echo "...Git installation is complete!"
}

function install-git-lfs() {
  echo "Installing Git Large File Storage (LFS)..."
  # Update package lists
  sudo apt-get update -y
  # Add git-lfs package repository
  curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash
  # Install git-lfs
  sudo apt-get install -y git-lfs
  # Initialize git-lfs
  git lfs install
  echo "...Git-LFS installation is complete!"
}

function install-gpu() {
  echo "Installing GPU drivers"
  if [[ "${GPU_NODE}" = "true" ]]; then
    echo "Installing GPU drivers"
    distribution=$(. /etc/os-release;echo "${ID}${VERSION_ID}" | sed -e 's/\.//g') \
      && wget https://developer.download.nvidia.com/compute/cuda/repos/"${distribution}"/x86_64/cuda-keyring_1.0-1_all.deb \
      && sudo dpkg -i cuda-keyring_1.0-1_all.deb
    distribution=$(. /etc/os-release;echo "${ID}${VERSION_ID}") \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/"${distribution}"/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    sudo apt-get update && sudo apt-get install -y \
      linux-headers-"$(uname -r)" \
      cuda-drivers \
      nvidia-docker2
    sudo systemctl restart docker
    nvidia-smi # No idea why we have to run this once, but we do. Only then does nvidia-container-cli work.
  else
    echo "Not installing GPU drivers because GPU_NODE=${GPU_NODE}"
  fi
}

function install-bacalhau() {
  echo "Installing Bacalhau from release ${BACALHAU_VERSION}"
  sudo apt-get -y install --no-install-recommends jq
  wget "https://github.com/bacalhau-project/bacalhau/releases/download/${BACALHAU_VERSION}/bacalhau_${BACALHAU_VERSION}_linux_amd64.tar.gz"
  tar xfv "bacalhau_${BACALHAU_VERSION}_linux_amd64.tar.gz"
  sudo mv ./bacalhau /usr/local/bin/bacalhau
}

function mount-disk() {
  echo "Mounting disk"
  # wait for /dev/sdb to exist
  while [[ ! -e /dev/sdb ]]; do
    sleep 1
    echo "waiting for /dev/sdb to exist"
  done
  # mount /dev/sdb at /data
  sudo mkdir -p /data
  sudo mount /dev/sdb /data || (sudo mkfs -t ext4 /dev/sdb && sudo mount /dev/sdb /data)
}

function install() {
  setup-directories
  install-go
  install-docker
  install-git
  install-git-lfs
  install-gpu
  install-bacalhau
  mount-disk
}

install
