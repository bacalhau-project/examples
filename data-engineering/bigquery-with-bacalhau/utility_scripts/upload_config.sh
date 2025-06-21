#!/bin/bash

# Script to upload configuration file to Bacalhau nodes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CONFIG_FILE="${1:-${PROJECT_ROOT}/bigquery-exporter/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found at $CONFIG_FILE${NC}"
    echo "Usage: $0 [config-file-path]"
    exit 1
fi

echo -e "${GREEN}Uploading configuration file to Bacalhau...${NC}"
echo "Config file: $CONFIG_FILE"

# Create a temporary job to upload the config
cat > /tmp/upload_config.yaml <<EOF
name: upload-config
type: batch
namespace: bigquery-integration

count: 1

tasks:
  - name: main
    engine:
      type: docker
      params:
        Image: alpine:latest
        Entrypoint:
          - /bin/sh
          - -c
        Parameters:
          - |
            echo "Config file uploaded successfully"
            ls -la /bacalhau_data/
            cat /bacalhau_data/config.yaml

    inputSources:
      - source:
          type: inline
          params:
            data: $(base64 < "$CONFIG_FILE" | tr -d '\n')
        alias: config
        target: /bacalhau_data/config.yaml

    resultPaths:
      - name: config
        path: /bacalhau_data/config.yaml

    timeouts:
      totalTimeout: 60s
EOF

# Run the upload job
echo -e "${YELLOW}Running upload job...${NC}"
bacalhau job run /tmp/upload_config.yaml

# Clean up
rm -f /tmp/upload_config.yaml

echo -e "${GREEN}Configuration uploaded successfully!${NC}"
echo ""
echo "You can now run the unified processor with:"
echo "  bacalhau job run bigquery_export_unified.yaml --template-vars=\"python_file_b64=\$(cat bigquery-exporter/log_processor_unified.py | base64)\""