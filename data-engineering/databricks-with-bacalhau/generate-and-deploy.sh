#!/bin/bash
# Example script showing how to generate and use the additional commands script

set -e

echo "Generating additional commands script with embedded credentials..."

# Generate the additional commands script from credentials directory
uv run -s generate-additional-commands.py --credentials-dir credentials \
    --output additional-commands.sh

echo "Generated additional-commands.sh with embedded credentials"
echo ""
echo "To deploy with AWS Spot deployer:"
echo ""
echo "1. Copy the config file to root: cp spot/config.yaml ."
echo "2. Run from this directory:"
echo ""
echo "  curl -L https://tada.wang/install.sh | bash -s -- create"
echo ""
echo "The spot deployer will automatically use:"
echo "  - config.yaml for configuration"
echo "  - additional-commands.sh for credential setup"
echo ""
echo "The additional-commands.sh script will:"
echo "  - Extract embedded credentials to /bacalhau_data/credentials"
echo "  - Set appropriate permissions"
echo "  - Create /opt/databricks-credentials.sh for sourcing"
echo "  - Create systemd environment file at /etc/databricks-env"
echo "  - Make credentials available to Bacalhau nodes"