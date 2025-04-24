#! /usr/bin/env bash
set -e

echo "Starting sensors on $COUNT nodes..."
bacalhau job run jobs/start_sensors.yaml \
    --id-only \
    --wait=false
echo "Sensor jobs started."