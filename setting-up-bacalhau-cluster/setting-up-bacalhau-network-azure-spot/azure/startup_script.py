import base64
import io
import logging
import os
import tarfile


def tar_and_encode_scripts(script_dir):
    memory_file = io.BytesIO()
    with tarfile.open(fileobj=memory_file, mode="w:gz") as tar:
        for script_file in sorted(os.listdir(script_dir)):
            if script_file.endswith(".sh"):
                script_path = os.path.join(script_dir, script_file)
                tar.add(script_path, arcname=script_file)

    memory_file.seek(0)
    return base64.b64encode(memory_file.getvalue()).decode()


def get_azure_startup_script(orchestrators, script_dir, token="", tls="false"):
    # Check if orchestrators are provided
    if not orchestrators:
        logging.error("Orchestrators are empty. Stopping creation.")
        return ""
    encoded_tar = tar_and_encode_scripts(script_dir)
    return f"""#!/bin/bash

# Export ORCHESTRATORS
export ORCHESTRATORS="{','.join(orchestrators)}"
export TOKEN="{token}"
export REQUIRE_TLS="{tls}"

# Decode and extract scripts
SCRIPT_DIR="/tmp/spot_scripts"
mkdir -p "$SCRIPT_DIR"
echo "{encoded_tar}" | base64 -d | tar -xzv -C "$SCRIPT_DIR"

# Set up metadata for Azure-specific features
INSTANCE_ID=$(curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance/compute/vmId?api-version=2021-02-01&format=text")
ZONE=$(curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance/compute/zone?api-version=2021-02-01&format=text" | awk -F'/' '{{print ${{NF}}}}')
SUBSCRIPTION_ID=$(curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance/compute/subscriptionId?api-version=2021-02-01&format=text")

# Export Azure-specific environment variables
export INSTANCE_ID="$INSTANCE_ID"
export ZONE="$ZONE"
export SUBSCRIPTION_ID="SUBSCRIPTION_ID"

# Run scripts in order
for script in $(ls -1 "$SCRIPT_DIR"/*.sh | sort); do
    echo "Running $script"
    bash "$script"
done

# Clean up
rm -rf "$SCRIPT_DIR"
"""
