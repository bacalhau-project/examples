#!/bin/bash

# Start sensor log generator locally (using container but with local data)
# This is a convenience wrapper around start-sensor.sh for local development

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Local Sensor Data Generator (Container)${NC}"
echo -e "${BLUE}[INFO]${NC} This runs the sensor container with local data directories"
echo -e "${BLUE}[INFO]${NC} Data will be stored in: $(pwd)/sample-sensor/data/"
echo ""

# Just call the main sensor script which uses the container
exec ./scripts/start-sensor.sh "$@"