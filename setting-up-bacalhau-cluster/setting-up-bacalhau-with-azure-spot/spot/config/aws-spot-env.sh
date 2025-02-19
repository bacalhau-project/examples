#!/usr/bin/env bash
# azure-spot-env.sh
#
# This file sets environment variables used for launching
# Azure Spot Virtual Machines with Docker installed.
#
# Usage:
#   source ./azure-spot-env.sh

# Azure Configuration
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_RESOURCE_GROUP="bacalhau-scale-test-rg"
export AZURE_LOCATION="eastus"

# VM Configuration
export VM_SIZE="Standard_B1s"
export VM_IMAGE="Canonical:UbuntuServer:18.04-LTS:latest"
export SPOT_VM_COUNT="100"

# Network Configuration
export VNET_NAME="bacalhau-vnet"
export SUBNET_NAME="bacalhau-subnet"
export NSG_NAME="bacalhau-nsg"

# Tags
export VM_TAG_KEY="Name"
export VM_TAG_VALUE="bacalhau-scale-test"

echo "Environment variables for Azure Spot VMs set."
