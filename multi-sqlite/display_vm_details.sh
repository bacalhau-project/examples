#!/bin/bash

# specify the resource group
resourceGroup=$1

# loop through each VM in the resource group
for vm in $(az vm list -g "$resourceGroup" --query "[].{name:name}" -o tsv)
do
    # get the VM location
    location=$(az vm show -g "$resourceGroup" -n "$vm" --query "location" -o tsv)
    
    # get the public IP address of the VM's NIC
    nic=$(az vm show -d -g "$resourceGroup" -n "$vm" --query "publicIps" -o tsv)
    
    echo "VM Name: $vm"
    echo "Location: $location"
    echo "IP Address: $nic"
    echo "-----------------------------"
done