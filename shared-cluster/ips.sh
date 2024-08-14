#!/bin/bash

# Function to get IP addresses for a single VM
get_vm_ip() {
    local vm_name=$1
    local resource_group=$2
    
    echo "VM Name: $vm_name"
    
    # Get private IP address
    private_ip=$(az vm show -g "$resource_group" -n "$vm_name" --query "privateIps" -o tsv)
    echo "Private IP: $private_ip"
    
    # Get public IP address
    public_ip=$(az vm show -g "$resource_group" -n "$vm_name" --query "publicIps" -o tsv)
    echo "Public IP: $public_ip"
    
    echo ""
}

# Main script

# Check if resource group is provided
if [ $# -eq 0 ]; then
    echo "Please provide a resource group name."
    echo "Usage: $0 <resource_group_name>"
    exit 1
fi

resource_group=$1

# Get list of VMs in the resource group
vm_list=$(az vm list -g "$resource_group" --query "[].name" -o tsv)

# Check if any VMs exist in the resource group
if [ -z "$vm_list" ]; then
    echo "No VMs found in the resource group: $resource_group"
    exit 0
fi

echo "IP Addresses of VMs in Resource Group: $resource_group"
echo "------------------------------------------------"

# Iterate through each VM and get its IP addresses
while read -r vm_name; do
    get_vm_ip "$vm_name" "$resource_group"
done <<< "$vm_list"
