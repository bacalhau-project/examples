#!/usr/bin/env bash
set -euo pipefail

# Paths on the host
CONFIG_DIR="$(pwd)/sample-sensor"
CACHE_DIR="$CONFIG_DIR/cache"
LOG_DIR="$CONFIG_DIR/logs"

# 1) Ensure host dirs exist and are owned by you
mkdir -p "$CACHE_DIR" "$LOG_DIR"
chown -R "$(id -u):$(id -g)" "$CACHE_DIR" "$LOG_DIR"

# 2) Run container as your UID:GID, mounting:
#    - sample-sensor → /app/config
#    - cache dir     → /cache
#    - logs dir      → /root     (where the app writes its .log)
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$CONFIG_DIR":/app/config \
  -v "$CACHE_DIR":/cache \
  -v "$LOG_DIR":/root \
  -e CONFIG_FILE=/app/config/sensor-config.yaml \
  -e IDENTITY_FILE=/app/config/node-identity.json \
  -e XDG_CACHE_HOME=/cache \
  -p 8080:8080 \
  ghcr.io/bacalhau-project/sensor-log-generator:latest
