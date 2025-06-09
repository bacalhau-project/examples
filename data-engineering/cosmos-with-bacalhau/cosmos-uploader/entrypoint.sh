#!/usr/bin/env bash

# Set MTU
echo "--- Attempting to set MTU --- "
DEFAULT_INTERFACE=$(ip route | grep default | awk "{print \$5}" | head -n1)
if [ -n "$DEFAULT_INTERFACE" ]; then
    echo "Attempting to set MTU to 1400 on interface: $DEFAULT_INTERFACE"
    ip link set dev "$DEFAULT_INTERFACE" mtu 1400 || echo "Warning: Failed to set MTU on $DEFAULT_INTERFACE. Proceeding anyway."
    echo "Current MTU settings:"
    ip link show "$DEFAULT_INTERFACE"
else
    echo "Warning: Could not determine default interface to set MTU."
fi
echo "--- Finished MTU check ---"

# Set the working directory
cd /app


# Run the dotnet application with the provided arguments
exec dotnet CosmosUploader.dll "$@"