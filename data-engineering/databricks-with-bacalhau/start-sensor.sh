#!/usr/bin/env bash
set -euo pipefail

# Paths on the host
CONFIG_DIR="$(pwd)/sample-sensor" # Contains config.yaml, identity.json, cities.json
CACHE_DIR="$CONFIG_DIR/cache"   # For temporary container cache (XDG_CACHE_HOME)
DATA_DIR="$CONFIG_DIR/data"     # For persistent data (db, logs, backups, exports)

# 1) Ensure host dirs exist and are owned by you
mkdir -p "$CONFIG_DIR" "$CACHE_DIR" "$DATA_DIR"
# Ensure the top-level config dir is owned by user if it didn't exist
chown "$(id -u):$(id -g)" "$CONFIG_DIR"
# Cache and Data dirs owned by user
chown -R "$(id -u):$(id -g)" "$CACHE_DIR" "$DATA_DIR"

# 2) Run container as root, mounting:
#    - sample-sensor → /app/config (read-only config)
#    - cache dir     → /cache      (writable cache)
#    - data dir      → /root       (writable persistent data)
CONTAINER_IMAGE="ghcr.io/bacalhau-project/sensor-log-generator"
CONTAINER_VERSION="latest"

docker pull "$CONTAINER_IMAGE:$CONTAINER_VERSION"

docker run --rm \
  -v "$CONFIG_DIR":/app/config:ro \
  -v "$CACHE_DIR":/cache \
  -v "$DATA_DIR":/root \
  -e CONFIG_FILE=/app/config/sensor-config.yaml \
  -e IDENTITY_FILE=/app/config/node-identity.json \
  -e XDG_CACHE_HOME=/cache \
  -p 8080:8080 \
  "$CONTAINER_IMAGE:$CONTAINER_VERSION"
