#! /usr/bin/env bash
set -e

# Get count of compute nodes in the network (excluding orchestrator)
COUNT=$(bacalhau node list --output json | jq -r '[.[] | select(.Info.NodeType == "Compute")] | length')

echo "Starting sensors on $COUNT nodes..."
bacalhau job run jobs/start_sensors.yaml \
    -V count="$COUNT"
echo "Sensor jobs started."