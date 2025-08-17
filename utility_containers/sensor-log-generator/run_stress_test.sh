#!/bin/bash
# Comprehensive stress test for sensor database configuration

set -e

echo "========================================="
echo "SENSOR DATABASE STRESS TEST SUITE"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TEST_DB="stress_test_sensor.db"
SENSOR_CONFIG="stress_test_config.yaml"
SENSOR_IDENTITY="stress_test_identity.json"
TEST_DURATION=30

# Clean up function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    
    # Kill sensor process if running
    if [ ! -z "$SENSOR_PID" ]; then
        kill $SENSOR_PID 2>/dev/null || true
    fi
    
    # Kill monitor process if running
    if [ ! -z "$MONITOR_PID" ]; then
        kill $MONITOR_PID 2>/dev/null || true
    fi
    
    # Remove test files
    rm -f $TEST_DB $TEST_DB-wal $TEST_DB-shm
    rm -f $SENSOR_CONFIG $SENSOR_IDENTITY
    rm -f test_sensor_data.db test_sensor_data.db-wal test_sensor_data.db-shm
    
    echo "Cleanup complete"
}

# Set up trap for cleanup
trap cleanup EXIT

echo -e "\n${GREEN}1. Creating test configuration files...${NC}"

# Create test config file with aggressive settings
cat > $SENSOR_CONFIG << EOF
version: 1
database:
  path: $TEST_DB
  batch_size: 20
  batch_timeout: 5.0
  preserve_existing_db: false

simulation:
  readings_per_second: 10  # Aggressive write rate
  run_time_seconds: $TEST_DURATION

anomaly:
  enabled: true
  base_probability: 0.1

logging:
  level: WARNING  # Reduce noise during test
EOF

# Create test identity file
cat > $SENSOR_IDENTITY << EOF
{
  "sensor_id": "STRESS_TEST_001",
  "location": {
    "city": "Test City",
    "coordinates": {
      "latitude": 0.0,
      "longitude": 0.0
    },
    "timezone": "UTC"
  },
  "device_info": {
    "manufacturer": "TestCorp",
    "model": "StressTest-1000",
    "firmware_version": "1.0.0"
  }
}
EOF

echo -e "${GREEN}2. Starting sensor simulator...${NC}"

# Start the sensor in background
python main.py --config $SENSOR_CONFIG --identity $SENSOR_IDENTITY &
SENSOR_PID=$!

# Wait for sensor to start
sleep 2

# Check if sensor is running
if ! kill -0 $SENSOR_PID 2>/dev/null; then
    echo -e "${RED}Failed to start sensor simulator${NC}"
    exit 1
fi

echo -e "${GREEN}3. Starting external reader monitor...${NC}"

# Start continuous monitoring in background
python external_reader.py $TEST_DB --mode monitor --interval 2 > monitor.log 2>&1 &
MONITOR_PID=$!

sleep 2

echo -e "${GREEN}4. Running concurrent stress test...${NC}"

# Run the stress test with custom configuration
STRESS_CONFIG='{
    "num_writers": 3,
    "num_readers": 5,
    "writes_per_second": 20,
    "test_duration": 20,
    "db_path": "'$TEST_DB'"
}'

python stress_test.py "$STRESS_CONFIG"
STRESS_RESULT=$?

echo -e "\n${GREEN}5. Validating database integrity...${NC}"

# Check database integrity
sqlite3 $TEST_DB "PRAGMA integrity_check;" > integrity_result.txt
INTEGRITY=$(cat integrity_result.txt)

if [ "$INTEGRITY" = "ok" ]; then
    echo -e "${GREEN}✅ Database integrity check: PASSED${NC}"
else
    echo -e "${RED}❌ Database integrity check: FAILED${NC}"
    echo "Result: $INTEGRITY"
fi

# Get final statistics
echo -e "\n${GREEN}6. Final database statistics:${NC}"
sqlite3 $TEST_DB << EOF
.mode column
.headers on
SELECT 
    COUNT(*) as total_readings,
    COUNT(DISTINCT sensor_id) as unique_sensors,
    MIN(timestamp) as first_reading,
    MAX(timestamp) as last_reading,
    SUM(anomaly_flag) as anomalies
FROM sensor_readings;
EOF

# Check monitor log for issues
echo -e "\n${GREEN}7. External reader results:${NC}"
if [ -f monitor.log ]; then
    MONITOR_ERRORS=$(grep -c "Error" monitor.log || true)
    MONITOR_READINGS=$(grep -c "New readings" monitor.log || true)
    
    echo "  Monitor readings received: $MONITOR_READINGS"
    echo "  Monitor errors encountered: $MONITOR_ERRORS"
    
    if [ $MONITOR_ERRORS -eq 0 ]; then
        echo -e "${GREEN}  ✅ No errors in external reader${NC}"
    else
        echo -e "${YELLOW}  ⚠️  External reader encountered $MONITOR_ERRORS errors${NC}"
        echo "  First few errors:"
        grep "Error" monitor.log | head -3
    fi
fi

# Overall result
echo -e "\n========================================="
if [ $STRESS_RESULT -eq 0 ] && [ "$INTEGRITY" = "ok" ] && [ $MONITOR_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo "The database configuration is resilient to concurrent access!"
    EXIT_CODE=0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo "Issues detected with database configuration:"
    [ $STRESS_RESULT -ne 0 ] && echo "  - Stress test failed"
    [ "$INTEGRITY" != "ok" ] && echo "  - Database integrity compromised"
    [ $MONITOR_ERRORS -gt 0 ] && echo "  - External reader encountered errors"
    EXIT_CODE=1
fi
echo "========================================="

# Clean up monitor log
rm -f monitor.log integrity_result.txt

exit $EXIT_CODE