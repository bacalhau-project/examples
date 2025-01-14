#!/bin/bash
set -e

# Check if credentials file exists
if [ ! -f "log_uploader_credentials.json" ]; then
    echo "Error: log_uploader_credentials.json not found in current directory"
    exit 1
fi

# Read and encode the credentials
echo "Reading and encoding credentials..."
CREDS_B64=$(base64 -i log_uploader_credentials.json)

# Create and encode the Python script directly in memory
SCRIPT_B64=$(cat << 'EOF' | base64
#!/usr/bin/env python3
import base64
import os
import stat
import sys

try:
    # Get the credentials from environment variable
    creds_b64 = os.environ.get('CREDS_B64')
    if not creds_b64:
        print("Error: CREDS_B64 environment variable not found")
        sys.exit(1)

    # Decode the credentials
    creds = base64.b64decode(creds_b64)

    # If DEBUG is set, list the contents of the directory
    if os.environ.get('DEBUG'):
        print("Listing contents of /var/log:")
        print(os.listdir('/var/log'))

    # Write the credentials
    creds_path = '/var/log/logs_to_process/log_uploader_credentials.json'
    with open(creds_path, 'wb') as f:
        f.write(creds)

    # Set permissions to be readable only by owner (600)
    os.chmod(creds_path, stat.S_IRUSR | stat.S_IWUSR)

    # Verify the write
    if not os.path.exists(creds_path):
        print("Error: Failed to write credentials file")
        sys.exit(1)

    # Verify the permissions
    perms = oct(os.stat(creds_path).st_mode)[-3:]
    if perms != '600':
        print(f"Warning: Unexpected permissions: {perms}")
        sys.exit(1)

    print(f"Successfully wrote credentials to {creds_path}")
    print(f"File permissions: {perms}")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)
EOF
)

echo "Distributing credentials to all nodes..."
bacalhau docker run \
    -e SCRIPT_B64="$SCRIPT_B64" \
    -e CREDS_B64="$CREDS_B64" \
    -e DEBUG=true \
    --target all \
    --input file:///bacalhau_data,dst=/var/log/logs_to_process,opt=readwrite=true \
    python:3.11-slim \
    -- /bin/bash -c 'echo "$SCRIPT_B64" | base64 -d > /tmp/write_creds.py && python /tmp/write_creds.py'

echo "Credentials distribution complete."