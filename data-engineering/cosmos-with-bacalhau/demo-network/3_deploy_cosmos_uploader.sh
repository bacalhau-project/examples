#! /usr/bin/env bash
set -e

# Get count of compute nodes in the network (excluding orchestrator)
COUNT=$(bacalhau node list --output json | jq -r '[.[] | select(.Info.NodeType == "Compute")] | length')

echo "Starting cosmos uploader on $COUNT nodes..."
bacalhau job run jobs/start_cosmos_uploader.yaml \
    -V count="$COUNT" \
    --id-only \
    --wait=false
echo "Cosmos uploader jobs started."