#!/usr/bin/env bash
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "docker",
#     "pyyaml"
# ]
# ///

set -euo pipefail

# Install UV using the official installation script
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add UV to PATH
export PATH="/root/.local/bin:$PATH"

# Verify installation
if ! command -v uv &> /dev/null; then
    echo "UV installation failed"
    exit 1
fi

echo "UV installed successfully"
