#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Running Databricks Uploader in Docker${NC}"

# Configuration
IMAGE="${IMAGE:-ghcr.io/bacalhau-project/databricks-uploader:latest}"
CONFIG_FILE="${CONFIG_FILE:-databricks-uploader-config.yaml}"
CREDENTIALS_DIR="${CREDENTIALS_DIR:-$(pwd)/credentials}"
DB_PATH="${DB_PATH:-$(pwd)/sample-sensor/data/sensor_data.db}"
STATE_DIR="${STATE_DIR:-$(pwd)/uploader-state}"

# Check if we're running from the right directory
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}Warning: Config file not found at $CONFIG_FILE${NC}"
    echo "Make sure you're running from the project root directory"
fi

# Create directories if they don't exist
mkdir -p "$CREDENTIALS_DIR" "$STATE_DIR"

echo -e "${GREEN}Starting uploader with:${NC}"
echo "  Image: $IMAGE"
echo "  Config: $CONFIG_FILE"
echo "  Credentials: $CREDENTIALS_DIR"
echo "  Database: $DB_PATH"
echo "  State: $STATE_DIR"
echo ""

# Run the container with all necessary mounts
docker run --rm \
  --name databricks-uploader \
  -v "$CONFIG_FILE:/app/config.yaml:ro" \
  -v "$CREDENTIALS_DIR:/bacalhau_data/credentials:ro" \
  -v "$DB_PATH:/app/sensor_data.db" \
  -v "$STATE_DIR:/app/state" \
  "$IMAGE"

# Alternative: Run in detached mode (background)
# Add -d flag after --rm to run in background:
# docker run --rm -d \
#   --name databricks-uploader \
#   -v "$CONFIG_FILE:/app/config.yaml:ro" \
#   -v "$CREDENTIALS_DIR:/bacalhau_data/credentials:ro" \
#   -v "$DB_PATH:/app/sensor_data.db" \
#   -v "$STATE_DIR:/app/state" \
#   "$IMAGE"