#!/usr/bin/env bash
set -euo pipefail

# Cleanup function
cleanup() {
    echo ""
    print_info "Cleaning up sensor container..."
    docker stop sensor-log-generator 2>/dev/null || true
    docker rm sensor-log-generator 2>/dev/null || true
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

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
echo -e "${GREEN}     Sensor Log Generator Container${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Paths on the host
CONFIG_DIR="$(pwd)/sample-sensor" # Contains config.yaml, identity.json, cities.json
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

# Check if config files exist, create defaults if not
if [ ! -f "$CONFIG_DIR/sensor-config.yaml" ]; then
    print_warning "sensor-config.yaml not found, creating default..."
    cat > "$CONFIG_DIR/sensor-config.yaml" << 'EOF'
# Wind Turbine Sensor Configuration
database:
  path: /root/sensor_data.db
  
sensors:
  count: 5
  prefix: WT
  type: wind_turbine
  
generation:
  interval: 1  # seconds between readings
  batch_size: 5  # readings per interval
  
metrics:
  temperature:
    min: 15
    max: 35
    unit: celsius
    variance: 0.5
  vibration:
    min: 0.0
    max: 1.0
    unit: g
    variance: 0.05
  power_output:
    min: 0
    max: 3000
    unit: kW
    correlation: wind_speed
  wind_speed:
    min: 0
    max: 30
    unit: m/s
    variance: 1.0
  rotation_speed:
    min: 0
    max: 30
    unit: rpm
    correlation: wind_speed

logging:
  level: INFO
  format: json
  
api:
  enabled: true
  port: 8080
  metrics_endpoint: /metrics
  health_endpoint: /health
EOF
    print_info "Created default sensor-config.yaml"
fi

if [ ! -f "$CONFIG_DIR/node-identity.json" ]; then
    print_warning "node-identity.json not found, creating default..."
    NODE_ID="sensor-node-$(date +%s)-$$"
    cat > "$CONFIG_DIR/node-identity.json" << EOF
{
  "node_id": "$NODE_ID",
  "location": "Wind Farm Alpha",
  "region": "us-west-2",
  "operator": "Demo Operator",
  "version": "1.0.0",
  "capabilities": ["wind_turbine", "realtime", "batch"]
}
EOF
    print_info "Created node-identity.json with ID: $NODE_ID"
fi

echo ""
print_status "Container Configuration:"
echo -e "  ${CYAN}Image:${NC} ghcr.io/bacalhau-project/sensor-log-generator:latest"
echo -e "  ${CYAN}Port:${NC} 8080 (Web UI and API)"
echo -e "  ${CYAN}Database:${NC} $DATA_DIR/sensor_data.db"
echo ""
print_status "Volume Mounts:"
echo -e "  ${CYAN}Config:${NC} $CONFIG_DIR → /app/config (read-only)"
echo -e "  ${CYAN}Cache:${NC} $CACHE_DIR → /cache"
echo -e "  ${CYAN}Data:${NC} $DATA_DIR → /root"
echo ""
print_status "Environment Variables:"
echo -e "  ${CYAN}CONFIG_FILE:${NC} /app/config/sensor-config.yaml"
echo -e "  ${CYAN}IDENTITY_FILE:${NC} /app/config/node-identity.json"
echo -e "  ${CYAN}XDG_CACHE_HOME:${NC} /cache"
echo ""
print_status "Available Endpoints:"
echo -e "  ${CYAN}Web UI:${NC} http://localhost:8080"
echo -e "  ${CYAN}Metrics:${NC} http://localhost:8080/metrics"
echo -e "  ${CYAN}Health:${NC} http://localhost:8080/health"
echo ""
echo -e "${GREEN}========================================${NC}"
print_info "Starting sensor container..."
print_info "Press ${YELLOW}Ctrl+C${NC} to stop the sensor generator"
echo -e "${GREEN}========================================${NC}"
echo ""

# Stop and remove any existing sensor container
if docker ps -a | grep -q sensor-log-generator; then
    print_warning "Stopping existing sensor container..."
    docker stop sensor-log-generator 2>/dev/null || true
    docker rm sensor-log-generator 2>/dev/null || true
fi

# 2) Run container as root, mounting:
#    - sample-sensor → /app/config (read-only config)
#    - cache dir     → /cache      (writable cache)
#    - data dir      → /app/data    (writable persistent data - matches config path)
docker run --rm \
  --name sensor-log-generator \
  -v "$CONFIG_DIR":/app/config:ro \
  -v "$CACHE_DIR":/cache \
  -v "$DATA_DIR":/app/data \
  -e CONFIG_FILE=/app/config/sensor-config.yaml \
  -e IDENTITY_FILE=/app/config/node-identity.json \
  -e XDG_CACHE_HOME=/cache \
  -p 8080:8080 \
  ghcr.io/bacalhau-project/sensor-log-generator:latest
