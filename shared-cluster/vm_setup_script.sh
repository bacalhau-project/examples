#!/bin/bash

# Update and install cifs-utils
sudo apt-get update
sudo apt-get install -y cifs-utils


# Mount Azure File Share
sudo mkdir -p /mnt/azureshare
sudo mount -t cifs //"${STORAGE_ACCOUNT_NAME}".file.core.windows.net/"${STORAGE_SHARE_NAME}" /mnt/azureshare -o vers=3.0,username="${STORAGE_ACCOUNT_NAME}",password="${STORAGE_KEY}",serverino

# Create and set permissions for sharedir
sudo mkdir -p /mnt/azureshare/sharedir
sudo chmod 777 /mnt/azureshare/sharedir

# Ensure the mount persists after reboot
echo "//${STORAGE_ACCOUNT_NAME}.file.core.windows.net/${STORAGE_SHARE_NAME} /mnt/azureshare cifs vers=3.0,username=${STORAGE_ACCOUNT_NAME},password=${STORAGE_KEY},serverino,_netdev,dir_mode=0777,file_mode=0777 0 0" | sudo tee -a /etc/fstab
