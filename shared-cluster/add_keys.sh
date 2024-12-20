#!/bin/bash

# Check if public key argument is provided
if [[ -z "$1" ]]; then
  echo "Usage: $0 <public_key_string>"
  exit 1
fi

PUBLIC_KEY="$1"

# Iterate through each machine in the JSON array (passed as the second argument)
jq -c '.[]' <<< "$2" | while read -r machine; do
    IP_ADDRESS=$(jq -r '.ip_addresses[] | select(.public) | .public' <<< "$machine")
    USERNAME=$(jq -r '.ssh_username' <<< "$machine")

    # Ensure IP address and username are valid
    if [[ -z "$IP_ADDRESS" ]] || [[ -z "$USERNAME" ]]; then
        echo "Invalid or missing IP address or username for machine $(jq -r '.name' <<< "$machine")"
        continue  # Skip to the next machine
    fi

    # Add the public key directly to the root account's authorized_keys 
    ssh -o StrictHostKeyChecking=no "$USERNAME@$IP_ADDRESS" "sudo bash -c \"
        mkdir -p /root/.ssh &&
        chmod 700 /root/.ssh &&
        echo '$PUBLIC_KEY' >> /root/.ssh/authorized_keys &&
        chmod 600 /root/.ssh/authorized_keys
    \""

done

