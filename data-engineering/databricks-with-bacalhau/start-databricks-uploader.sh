#!/usr/bin/env bash
set -euo pipefail

# Paths on the host
CONFIG_DIR="$(pwd)/sample-sensor" # Contains uploader-config.yaml
DATA_DIR="$CONFIG_DIR/data"     # Contains sensor_data.db (created by sensor)
DB_FILE="$DATA_DIR/sensor_data.db"
CONFIG_FILE="$CONFIG_DIR/uploader-config.yaml"
IMAGE="ghcr.io/astral-sh/uv:bookworm-slim"

# Check if required host files exist
if [ ! -f "$DB_FILE" ]; then
    echo "Error: Database file not found at $DB_FILE. Run the sensor script first."
    exit 1
fi
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Uploader config file not found at $CONFIG_FILE."
    exit 1
fi

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$CONFIG_DIR":/root:ro \
  -v "$DATA_DIR":/data \
  "$IMAGE" \
  uv run -s /root/sqlite_to_delta_uploader.py \
    --config /root/uploader-config.yaml \
    --sqlite /data/sensor_data.db \
    --continuous --interval 300

echo "Databricks Uploader container finished."
