#!/bin/bash

# Read the UNIQUEID from the file
UNIQUEID=$(cat UNIQUEID)

# Set the resource group name
export RESOURCE_GROUP="bac-sci-$UNIQUEID"

echo "Using Resource Group: $RESOURCE_GROUP"

# Get the subscription ID
export SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Get the first VM in the resource group
export VM_NAME=$(az vm list -g $RESOURCE_GROUP --query "[0].name" -o tsv)

# Get the VM's network interface
export NIC_NAME=$(az vm show -g $RESOURCE_GROUP -n $VM_NAME --query "networkProfile.networkInterfaces[0].id" -o tsv | cut -d'/' -f9)

# Get the VM's VNet and Subnet
SUBNET_ID=$(az vm show -g $RESOURCE_GROUP -n $VM_NAME --query "networkProfile.networkInterfaces[0].id" -o tsv)
export VNET_NAME=$(az network nic show --ids $SUBNET_ID --query "ipConfigurations[0].subnet.id" -o tsv | cut -d'/' -f9)
export SUBNET_NAME=$(az network nic show --ids $SUBNET_ID --query "ipConfigurations[0].subnet.id" -o tsv | cut -d'/' -f11)

# Get the NSG associated with the subnet
export NSG_NAME=$(az network vnet subnet show -g $RESOURCE_GROUP --vnet-name $VNET_NAME -n $SUBNET_NAME --query "networkSecurityGroup.id" -o tsv | cut -d'/' -f9)

# Get the storage account (assuming there's only one in the resource group)
export STORAGE_ACCOUNT_NAME=$(az storage account list -g $RESOURCE_GROUP --query "[0].name" -o tsv)

# Get the file share (assuming there's only one in the storage account)
export SHARE_NAME=$(az storage share list --account-name $STORAGE_ACCOUNT_NAME --account-key $(az storage account keys list -g $RESOURCE_GROUP -n $STORAGE_ACCOUNT_NAME --query "[0].value" -o tsv) --query "[0].name" -o tsv)

# Get the location
export LOCATION=$(az group show -n $RESOURCE_GROUP --query location -o tsv)

# Get additional information
export SUBNET_ID=$(az network vnet subnet show -g $RESOURCE_GROUP --vnet-name $VNET_NAME -n $SUBNET_NAME --query id -o tsv)
export VM_PRIVATE_IP=$(az vm show -g $RESOURCE_GROUP -n $VM_NAME -d --query privateIps -o tsv)
export STORAGE_ACCOUNT_KEY=$(az storage account keys list -g $RESOURCE_GROUP -n $STORAGE_ACCOUNT_NAME --query "[0].value" -o tsv)

# Get the storage account endpoint
export STORAGE_ACCOUNT_ENDPOINT=$(az storage account show -g $RESOURCE_GROUP -n $STORAGE_ACCOUNT_NAME --query primaryEndpoints.file -o tsv | sed 's/https://')

# Create mount point directory
export MOUNT_POINT="/mnt/azure_nfs"

# Print out the variables as export statements
echo "export UNIQUEID=\"$UNIQUEID\""
echo "export RESOURCE_GROUP=\"$RESOURCE_GROUP\""
echo "export SUBSCRIPTION_ID=\"$SUBSCRIPTION_ID\""
echo "export VM_NAME=\"$VM_NAME\""
echo "export NIC_NAME=\"$NIC_NAME\""
echo "export VNET_NAME=\"$VNET_NAME\""
echo "export SUBNET_NAME=\"$SUBNET_NAME\""
echo "export NSG_NAME=\"$NSG_NAME\""
echo "export STORAGE_ACCOUNT_NAME=\"$STORAGE_ACCOUNT_NAME\""
echo "export SHARE_NAME=\"$SHARE_NAME\""
echo "export LOCATION=\"$LOCATION\""
echo "export SUBNET_ID=\"$SUBNET_ID\""
echo "export VM_PRIVATE_IP=\"$VM_PRIVATE_IP\""
echo "export STORAGE_ACCOUNT_KEY=\"$STORAGE_ACCOUNT_KEY\""
echo "export STORAGE_ACCOUNT_ENDPOINT=\"$STORAGE_ACCOUNT_ENDPOINT\""
echo "export MOUNT_POINT=\"$MOUNT_POINT\""