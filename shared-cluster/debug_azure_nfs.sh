#!/bin/bash

set -e

echo "Starting Azure NFS debugging script..."

# Function to check if a variable is set
check_var() {
    if [ -z "${!1}" ]; then
        echo "Error: $1 is not set"
        exit 1
    fi
}

# Check if required variables are set
required_vars=(
    "SUBSCRIPTION_ID" "RESOURCE_GROUP" "STORAGE_ACCOUNT_NAME" "SHARE_NAME"
    "VNET_NAME" "SUBNET_NAME" "NSG_NAME" "VM_NAME" "NIC_NAME" "LOCATION"
    "SUBNET_ID" "VM_PRIVATE_IP" "STORAGE_ACCOUNT_KEY"
)

for var in "${required_vars[@]}"; do
    check_var "$var"
done

echo "All required variables are set."

# Check Azure CLI login status
echo "Checking Azure CLI login status..."
if ! az account show &> /dev/null; then
    echo "Error: Not logged into Azure CLI. Please run 'az login' first."
    exit 1
fi
echo "Azure CLI is logged in."

# Check storage account configuration
echo "Checking storage account configuration..."
if ! az storage account show --name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP --query "networkRuleSet" &> /dev/null; then
    echo "Error: Unable to retrieve storage account network rules."
    exit 1
fi
echo "Storage account network rules retrieved successfully."

if ! az storage account show --name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP --query "enableNfsV3" &> /dev/null; then
    echo "Error: Unable to check NFS v3 status."
    exit 1
fi
echo "NFS v3 status checked successfully."

# Check file share configuration
echo "Checking file share configuration..."
if ! az storage share-rm show --storage-account $STORAGE_ACCOUNT_NAME --name $SHARE_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "Error: Unable to retrieve file share configuration."
    exit 1
fi
echo "File share configuration retrieved successfully."

# Check NSG rules
echo "Checking NSG rules..."
if ! az network nsg rule list --resource-group $RESOURCE_GROUP --nsg-name $NSG_NAME --query "[?direction=='Outbound']" &> /dev/null; then
    echo "Error: Unable to retrieve NSG rules."
    exit 1
fi
echo "NSG rules retrieved successfully."

# Check VM network interface
echo "Checking VM network interface..."
if ! az network nic show --resource-group $RESOURCE_GROUP --name $NIC_NAME &> /dev/null; then
    echo "Error: Unable to retrieve VM network interface configuration."
    exit 1
fi
echo "VM network interface configuration retrieved successfully."

# Check subnet configuration
echo "Checking subnet configuration..."
if ! az network vnet subnet show --resource-group $RESOURCE_GROUP --vnet-name $VNET_NAME --name $SUBNET_NAME &> /dev/null; then
    echo "Error: Unable to retrieve subnet configuration."
    exit 1
fi
echo "Subnet configuration retrieved successfully."

# Perform network connectivity tests
echo "Performing network connectivity tests..."
if ! nslookup ${STORAGE_ACCOUNT_NAME}.file.core.windows.net &> /dev/null; then
    echo "Error: DNS resolution failed for ${STORAGE_ACCOUNT_NAME}.file.core.windows.net"
    exit 1
fi
echo "DNS resolution successful."

ping -c 4 ${STORAGE_ACCOUNT_NAME}.file.core.windows.net
echo "Ping test completed."

timeout 5 telnet ${STORAGE_ACCOUNT_NAME}.file.core.windows.net 2049 &> /dev/null
if [ $? -eq 124 ]; then
    echo "Error: Telnet to port 2049 timed out."
else
    echo "Telnet to port 2049 completed."
fi

# Check if NFS client is installed
echo "Checking if NFS client is installed..."
if ! command -v mount.nfs &> /dev/null; then
    echo "NFS client is not installed. Please install it with: sudo apt install -y nfs-common"
else
    echo "NFS client is installed."
fi

echo "Debugging script completed."