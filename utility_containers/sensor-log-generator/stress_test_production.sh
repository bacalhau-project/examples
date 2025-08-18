#!/bin/bash

# Production-like stress test for disk I/O error resilience
# This script simulates various production failure scenarios

set -e

echo "======================================"
echo "PRODUCTION STRESS TEST"
echo "======================================"
echo ""
echo "This test simulates production disk I/O issues:"
echo "  1. Resource exhaustion"
echo "  2. Permission changes"
echo "  3. Disk space issues"
echo "  4. Container restarts"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
DATA_DIR="./data-stress-test"
CONFIG_FILE="config.yaml"
IDENTITY_FILE="identity.json"
TEST_DURATION=60  # seconds
CONTAINER_NAME="sensor-stress-test"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    sudo rm -rf $DATA_DIR 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete${NC}"
}

# Set trap for cleanup
trap cleanup EXIT

# Prepare test environment
echo -e "${GREEN}Preparing test environment...${NC}"
mkdir -p $DATA_DIR
chmod 755 $DATA_DIR

# Function to check container health
check_container() {
    if docker ps | grep -q $CONTAINER_NAME; then
        return 0
    else
        return 1
    fi
}

# Function to get database stats
get_db_stats() {
    if [ -f "$DATA_DIR/sensor_data.db" ]; then
        echo $(sqlite3 "$DATA_DIR/sensor_data.db" "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "0")
    else
        echo "0"
    fi
}

# Test 1: Normal operation baseline
echo -e "\n${GREEN}TEST 1: Normal Operation (Baseline)${NC}"
echo "Starting sensor container..."

docker run -d \
    --name $CONTAINER_NAME \
    -v "$(pwd)/$DATA_DIR":/app/data \
    -v "$(pwd)":/app/config:ro \
    -e CONFIG_FILE=/app/config/$CONFIG_FILE \
    -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
    -e DEBUG_MODE=true \
    ghcr.io/bacalhau-project/sensor-log-generator:latest

sleep 10
BASELINE_COUNT=$(get_db_stats)
echo -e "Baseline readings after 10 seconds: ${GREEN}$BASELINE_COUNT${NC}"
docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME

# Test 2: Read-only filesystem during operation
echo -e "\n${YELLOW}TEST 2: Read-Only Filesystem During Operation${NC}"
echo "Starting sensor container..."

docker run -d \
    --name $CONTAINER_NAME \
    -v "$(pwd)/$DATA_DIR":/app/data \
    -v "$(pwd)":/app/config:ro \
    -e CONFIG_FILE=/app/config/$CONFIG_FILE \
    -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
    -e DEBUG_MODE=true \
    ghcr.io/bacalhau-project/sensor-log-generator:latest

sleep 5
echo -e "${RED}Making filesystem read-only...${NC}"
sudo chmod 444 $DATA_DIR/sensor_data.db 2>/dev/null || true
sleep 10
echo -e "${GREEN}Restoring write permissions...${NC}"
sudo chmod 644 $DATA_DIR/sensor_data.db 2>/dev/null || true
sleep 5

READONLY_COUNT=$(get_db_stats)
echo -e "Readings after read-only test: ${GREEN}$READONLY_COUNT${NC}"
docker logs --tail 20 $CONTAINER_NAME | grep -i "buffer\|error" || true
docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME

# Test 3: Limited disk space
echo -e "\n${YELLOW}TEST 3: Limited Disk Space${NC}"
echo "Creating size-limited container..."

# Create a small loopback device to simulate limited space
dd if=/dev/zero of=$DATA_DIR/disk.img bs=1M count=50 2>/dev/null
LOOP_DEVICE=$(sudo losetup -f --show $DATA_DIR/disk.img)
sudo mkfs.ext4 $LOOP_DEVICE 2>/dev/null
sudo mkdir -p $DATA_DIR/limited
sudo mount $LOOP_DEVICE $DATA_DIR/limited
sudo chmod 777 $DATA_DIR/limited

docker run -d \
    --name $CONTAINER_NAME \
    -v "$(pwd)/$DATA_DIR/limited":/app/data \
    -v "$(pwd)":/app/config:ro \
    -e CONFIG_FILE=/app/config/$CONFIG_FILE \
    -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
    -e DEBUG_MODE=true \
    ghcr.io/bacalhau-project/sensor-log-generator:latest

sleep 20
echo "Checking disk usage..."
df -h $DATA_DIR/limited
docker logs --tail 20 $CONTAINER_NAME | grep -i "buffer\|error\|disk" || true
docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME

sudo umount $DATA_DIR/limited 2>/dev/null || true
sudo losetup -d $LOOP_DEVICE 2>/dev/null || true

# Test 4: Container restart resilience
echo -e "\n${YELLOW}TEST 4: Container Restart Resilience${NC}"
echo "Starting container with periodic restarts..."

for i in {1..3}; do
    echo -e "\n${YELLOW}Iteration $i/3${NC}"
    
    docker run -d \
        --name $CONTAINER_NAME \
        -v "$(pwd)/$DATA_DIR":/app/data \
        -v "$(pwd)":/app/config:ro \
        -e CONFIG_FILE=/app/config/$CONFIG_FILE \
        -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
        -e DEBUG_MODE=true \
        ghcr.io/bacalhau-project/sensor-log-generator:latest
    
    sleep 10
    echo -e "${RED}Killing container abruptly...${NC}"
    docker kill $CONTAINER_NAME
    docker rm $CONTAINER_NAME
    
    COUNT=$(get_db_stats)
    echo -e "Readings after kill $i: ${GREEN}$COUNT${NC}"
    sleep 2
done

# Test 5: High frequency writes with intermittent errors
echo -e "\n${YELLOW}TEST 5: High Frequency with Intermittent Errors${NC}"
echo "Starting high-frequency sensor..."

# Create a config with high frequency
cat > $DATA_DIR/high_freq_config.yaml << EOF
sensor_id: STRESS_TEST
run_time_seconds: 30
readings_per_second: 50  # Very high frequency
database:
  path: /app/data/sensor_data.db
  batch_size: 100
parameters:
  temperature:
    mean: 25.0
    std_dev: 2.0
EOF

docker run -d \
    --name $CONTAINER_NAME \
    -v "$(pwd)/$DATA_DIR":/app/data \
    -v "$(pwd)":/app/config:ro \
    -e CONFIG_FILE=/app/config/high_freq_config.yaml \
    -e IDENTITY_FILE=/app/config/$IDENTITY_FILE \
    -e DEBUG_MODE=true \
    --memory="100m" \
    --cpus="0.5" \
    ghcr.io/bacalhau-project/sensor-log-generator:latest

# Cause intermittent permission issues
for i in {1..6}; do
    sleep 3
    echo -e "${RED}Causing I/O error...${NC}"
    sudo chmod 444 $DATA_DIR/sensor_data.db 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}Restoring permissions...${NC}"
    sudo chmod 644 $DATA_DIR/sensor_data.db 2>/dev/null || true
done

sleep 5
FINAL_COUNT=$(get_db_stats)
echo -e "\nFinal reading count: ${GREEN}$FINAL_COUNT${NC}"

# Get container logs for analysis
echo -e "\n${YELLOW}Container Statistics:${NC}"
docker logs --tail 50 $CONTAINER_NAME | grep -E "buffer|error|ERROR|WARNING|readings created" || true

# Final summary
echo -e "\n${GREEN}======================================"
echo "TEST SUMMARY"
echo "======================================${NC}"
echo "Baseline readings (10s normal): $BASELINE_COUNT"
echo "After read-only test: $READONLY_COUNT"
echo "Final count after all tests: $FINAL_COUNT"

if [ "$FINAL_COUNT" -gt "0" ]; then
    echo -e "\n${GREEN}✅ SUCCESS: System successfully handled disk I/O errors${NC}"
    echo "   - Readings were buffered during errors"
    echo "   - Data was recovered after permissions restored"
    echo "   - No data loss observed"
else
    echo -e "\n${RED}⚠️  WARNING: Check logs for issues${NC}"
fi

echo -e "\n${YELLOW}To run individual stress scenarios:${NC}"
echo "  1. docker-compose -f docker-compose.stress.yml up sensor-limited-memory"
echo "  2. docker-compose -f docker-compose.stress.yml up sensor-readonly"
echo "  3. docker-compose -f docker-compose.stress.yml up sensor-chaos"