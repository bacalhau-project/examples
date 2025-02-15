#!/bin/bash

# Azure Service Principal Credentials
export ARM_CLIENT_ID=""
export ARM_CLIENT_SECRET=""
export ARM_SUBSCRIPTION_ID=""
export ARM_TENANT_ID=""

# Azure Resource Group
export AZURE_RESOURCE_GROUP="bacalhau-spot-rg"
export AZURE_LOCATION="eastus"

# Azure Spot VM Configuration
export AZURE_VM_SIZE="Standard_B2s"
export AZURE_SPOT_PRIORITY="Spot"
export AZURE_SPOT_EVICTION_POLICY="Delete"
export AZURE_ADMIN_USERNAME="bacalhauadmin"

# Networking
export AZURE_VNET_NAME="bacalhau-vnet"
export AZURE_SUBNET_NAME="bacalhau-subnet"

# Storage
export AZURE_STORAGE_ACCOUNT="bacalhausersa"
export AZURE_STORAGE_CONTAINER="bacalhau-data"

# Tags
export AZURE_TAGS='{"environment":"spot","project":"bacalhau"}'
