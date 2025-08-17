#!/usr/bin/env bash
set -euo pipefail

# Parse arguments
WITH_ANOMALIES=false
for arg in "$@"; do
    case $arg in
        --with-anomalies)
            WITH_ANOMALIES=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--with-anomalies]"
            echo "  --with-anomalies  Generate wind turbine data with anomalies"
            exit 0
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[SENSOR]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_config() {
    echo -e "${CYAN}[CONFIG]${NC} $1"
}

# Banner
echo -e "${GREEN}========================================${NC}"
if [ "$WITH_ANOMALIES" = true ]; then
    echo -e "${GREEN}  Wind Turbine Sensor with Anomalies${NC}"
else
    echo -e "${GREEN}     Sensor Log Generator Container${NC}"
fi
echo -e "${GREEN}========================================${NC}"
echo ""

# Paths on the host - use different dir for anomaly mode
if [ "$WITH_ANOMALIES" = true ]; then
    CONFIG_DIR="$(pwd)/sample-sensor-anomaly"
else
    CONFIG_DIR="$(pwd)/sample-sensor"
fi
CACHE_DIR="$CONFIG_DIR/cache"     # For temporary container cache (XDG_CACHE_HOME)
DATA_DIR="$CONFIG_DIR/data"       # For persistent data (db, logs, backups, exports)

print_status "Initializing sensor environment..."
print_config "Configuration directory: $CONFIG_DIR"
print_config "Cache directory: $CACHE_DIR"
print_config "Data directory: $DATA_DIR"
echo ""

# 1) Ensure host dirs exist
print_status "Creating required directories..."
mkdir -p "$CONFIG_DIR" "$CACHE_DIR" "$DATA_DIR"

# Check if config files exist
if [ ! -f "$CONFIG_DIR/sensor-config.yaml" ]; then
    print_error "sensor-config.yaml not found in $CONFIG_DIR"
    print_info "Please ensure the configuration file exists before running the sensor."
    exit 1
fi

# Use identity.json (which has the proper format)
if [ -f "$CONFIG_DIR/identity.json" ]; then
    IDENTITY_FILE="identity.json"
    print_info "Using identity.json for sensor identity"
elif [ -f "$CONFIG_DIR/node-identity.json" ]; then
    IDENTITY_FILE="node-identity.json"
    print_info "Using node-identity.json for sensor identity"
else
    print_error "No identity file found in $CONFIG_DIR"
    print_info "Please ensure identity.json or node-identity.json exists"
    exit 1
fi

echo ""
print_status "Container Configuration:"
echo -e "  ${CYAN}Image:${NC} ghcr.io/bacalhau-project/sensor-log-generator:latest"
echo -e "  ${CYAN}Port:${NC} 8080 (Web UI and API)"
if [ "$WITH_ANOMALIES" = true ]; then
    echo -e "  ${CYAN}Database:${NC} $DATA_DIR/wind_turbine_sensors.db"
    echo -e "  ${YELLOW}Mode:${NC} Anomaly Generation Enabled"
else
    echo -e "  ${CYAN}Database:${NC} $DATA_DIR/sensor_data.db"
fi

echo ""
print_status "Volume Mounts:"
echo -e "  ${CYAN}Config:${NC} $CONFIG_DIR → /app/config"
echo -e "  ${CYAN}Data:${NC} $DATA_DIR → /app/data"

echo ""
print_status "Environment Variables:"
echo -e "  ${CYAN}CONFIG_FILE:${NC} /app/config/config.yaml"
echo -e "  ${CYAN}IDENTITY_FILE:${NC} /app/config/$IDENTITY_FILE"

echo ""
print_status "Available Endpoints:"
echo -e "  ${CYAN}Web UI:${NC} http://localhost:8080"
echo -e "  ${CYAN}Metrics:${NC} http://localhost:8080/metrics"
echo -e "  ${CYAN}Health:${NC} http://localhost:8080/health"

echo ""
echo -e "${GREEN}========================================${NC}"
print_info "Sensor will generate data for 1 hour (3600 seconds)"
print_info "Press ${YELLOW}Ctrl+C${NC} to stop the sensor early"
echo -e "${GREEN}========================================${NC}"
echo ""

# Stop and remove any existing sensor container
if docker ps -a | grep -q sensor-log-generator; then
    print_warning "Stopping existing sensor container..."
    docker stop sensor-log-generator 2>/dev/null || true
    docker rm sensor-log-generator 2>/dev/null || true
fi

# Run container in FOREGROUND mode (no monitoring or trap handlers)
if [ "$WITH_ANOMALIES" = true ]; then
    print_info "Starting sensor container (will run for 1 hour)..."
    docker run --rm \
      --name sensor-log-generator \
      -v "$DATA_DIR":/app/data \
      -v "$CONFIG_DIR":/app/config \
      -e CONFIG_FILE=/app/config/sensor-config.yaml \
      -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
      -e ANOMALY_MODE=true \
      -p 8080:8080 \
      ghcr.io/bacalhau-project/sensor-log-generator:latest
else
    print_info "Starting sensor container (will run for 1 hour)..."
    docker run --rm \
      --name sensor-log-generator \
      -v "$DATA_DIR":/app/data \
      -v "$CONFIG_DIR":/app/config \
      -e CONFIG_FILE=/app/config/sensor-config.yaml \
      -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
      -p 8080:8080 \
      ghcr.io/bacalhau-project/sensor-log-generator:latest
fi