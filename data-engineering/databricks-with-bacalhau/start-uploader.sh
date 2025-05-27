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

CONFIG_PATH="${1:-databricks-uploader/config.yaml}"
CONFIG_DIR=$(readlink -f "$(dirname "$CONFIG_PATH")")

# Determine the absolute path for the SQLite database file
# Default to a path relative to the CONFIG_DIR if SQLITE_PATH is relative
DB_FILE="${DB_FILE:-$CONFIG_DIR/sensor_data.db}"

docker run --rm \
  -v "$CONFIG_DIR":/app \
  ghcr.io/bacalhau-project/databricks-uploader:latest \
  --config /app/$(basename "$CONFIG_PATH")