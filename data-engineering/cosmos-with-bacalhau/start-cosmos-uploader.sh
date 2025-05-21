#!/usr/bin/env bash
set -euo pipefail

# Paths on the host
CONFIG_DIR="$(pwd)/sample-sensor" # Contains cosmos-config.yaml
DATA_DIR="$CONFIG_DIR/data"     # Contains sensor_data.db (created by sensor)
DB_FILE="$DATA_DIR/sensor_data.db"
CONFIG_FILE="$CONFIG_DIR/cosmos-config.yaml"
IMAGE_NAME="ghcr.io/bacalhau-project/cosmos-uploader"
LATEST_TAG_FILE="cosmos-uploader/latest-tag"

# Check if the tag file exists and read the tag
if [ ! -f "$LATEST_TAG_FILE" ]; then
    echo "Error: Tag file not found at $LATEST_TAG_FILE. Run the build script first."
    exit 1
fi
LATEST_TAG=$(cat "$LATEST_TAG_FILE")

# Check if required host files exist
if [ ! -f "$DB_FILE" ]; then
    echo "Error: Database file not found at $DB_FILE. Run the sensor script first."
    exit 1
fi
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Cosmos config file not found at $CONFIG_FILE."
    exit 1
fi

# Run container as your UID:GID, mounting:
#    - sample-sensor dir → /app/config (read-only for cosmos config)
#    - data dir          → /data       (writable for db and archive)
# NOTE: Ensure cosmos-config.yaml exists in sample-sensor/ with your credentials.
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$CONFIG_DIR":/app/config:ro \
  -v "$DATA_DIR":/data \
  "$IMAGE_NAME:$LATEST_TAG" \
  --config /app/config/cosmos-config.yaml \
  --update-notification-file-path /data/update-notification.json \
  --sqlite /data/sensor_data.db \
  --continuous \
  --interval 60 # Interval is now handled inside the C# app
  # --debug

echo "Cosmos Uploader container finished."
