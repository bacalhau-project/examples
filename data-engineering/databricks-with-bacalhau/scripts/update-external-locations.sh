#!/bin/bash
# Wrapper script to update external locations

cd "$(dirname "$0")"

echo "Updating Databricks external locations..."
echo "This will create external locations for all S3 buckets including checkpoints."
echo ""

# Run the setup script
cd scripts && uv run -s setup-databricks-external-locations.py

echo ""
echo "Done! You can now use the checkpoints bucket in Auto Loader."