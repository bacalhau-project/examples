#!/bin/sh

# Generate a random 6-character hex string for the VM name
VM_NAME="vm-$(head -c 3 /dev/urandom | xxd -p | cut -c1-6)"

# Set the VM name environment variable
export VM_NAME

# Execute the main application
exec /app 