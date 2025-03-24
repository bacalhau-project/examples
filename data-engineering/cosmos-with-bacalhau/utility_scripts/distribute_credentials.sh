#!/bin/bash
set -e

# Check if config file exists
if [ ! -f "../config.yaml" ]; then
    echo "Error: config.yaml not found in parent directory"
    exit 1
fi

# Read and encode the config file
echo "Reading and encoding config file..."
CONFIG_B64=$(base64 -i ../config.yaml)

# Create and encode the Python script directly in memory
SCRIPT_B64=$(cat << 'EOF' | base64
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///
import base64
import os
import stat
import sys
import yaml

try:
    # Get config from environment variables
    config_b64 = os.environ.get('CONFIG_B64')
    
    if not config_b64:
        print("Error: CONFIG_B64 environment variable not found")
        sys.exit(1)

    # Create the target directory if it doesn't exist
    target_dir = '/var/log/logs_to_process'
    os.makedirs(target_dir, exist_ok=True)

    # Write the config file
    config_path = os.path.join(target_dir, 'config.yaml')
    with open(config_path, 'wb') as f:
        f.write(base64.b64decode(config_b64))
    
    # Set permissions to be readable only by owner (600)
    os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)

    # Verify the write
    if not os.path.exists(config_path):
        print(f"Error: Failed to write file: {config_path}")
        sys.exit(1)
    
    perms = oct(os.stat(config_path).st_mode)[-3:]
    if perms != '600':
        print(f"Warning: Unexpected permissions for {config_path}: {perms}")
        sys.exit(1)

    print(f"Successfully wrote config to {config_path}")
    print("File permissions: 600")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)
EOF
)

echo "Distributing config to all nodes..."
# shellcheck disable=SC1073,SC2016
bacalhau docker run \
    -e SCRIPT_B64="$SCRIPT_B64" \
    -e CONFIG_B64="$CONFIG_B64" \
    --network=full \
    --target all \
    --input file:///bacalhau_data,dst=/var/log/logs_to_process,opt=readwrite=true \
    ghcr.io/astral-sh/uv:python3.13-bookworm-slim \
    -- /bin/bash -c 'echo "$SCRIPT_B64" | base64 -d > /tmp/write_files.py && uv run -s /tmp/write_files.py'


echo "Config distribution complete."