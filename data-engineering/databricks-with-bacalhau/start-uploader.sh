#!/usr/bin/env bash
# start-uploader.sh
#
# Wrapper script to launch the uploader container in continuous mode.
# Usage: ./start-uploader.sh <config.yaml>
# Environment variables:
#   DB_FILE         Path to the SQLite database file (default: ./sensor_data.db)
#   STATE_DIR       Directory to persist uploader state (default: ./state)
#   UPLOAD_INTERVAL Seconds between upload cycles (default: 300)
#   UPLOADER_IMAGE  Docker image to use (default: uploader-image:latest)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path to config.yaml>"
  exit 1
fi

CONFIG_PATH="$1"
DB_FILE="${DB_FILE:-./sensor_data.db}"
STATE_DIR="${STATE_DIR:-./state}"
UPLOAD_INTERVAL="${UPLOAD_INTERVAL:-300}"
UPLOADER_IMAGE="${UPLOADER_IMAGE:-uploader-image:latest}"

mkdir -p "$STATE_DIR"

docker run --rm \
  -v "$DB_FILE":/data/sensor.db:ro \
  -v "$STATE_DIR":/state \
  -v "$CONFIG_PATH":/app/config.yaml:ro \
  -e UPLOAD_INTERVAL="$UPLOAD_INTERVAL" \
  "$UPLOADER_IMAGE" \
  --config /app/config.yaml