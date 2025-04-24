#! /usr/bin/env bash
set -e

echo "Starting cosmos uploader on $COUNT nodes..."
bacalhau job run jobs/start_cosmos_uploader.yaml \
    --id-only \
    --wait=false
echo "Cosmos uploader jobs started."