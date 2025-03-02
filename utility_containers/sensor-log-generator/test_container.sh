#!/bin/bash

# Exit on error
set -e

# Colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Print section header
section() {
  echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}\n"
}

# Function to safely list directory contents without LSCOLORS errors
safe_ls() {
  # Temporarily unset LSCOLORS to avoid errors on macOS
  local old_lscolors=$LSCOLORS
  unset LSCOLORS
  ls -la "$@"
  # Restore original LSCOLORS if it was set
  if [ -n "$old_lscolors" ]; then
    export LSCOLORS=$old_lscolors
  fi
}

# Clear the terminal
clear

section "BUILDING CONTAINER"
echo -e "${YELLOW}Building sensor simulator container...${NC}"
docker build -t sensor-simulator:test .

section "PREPARING TEST ENVIRONMENT"
echo -e "${YELLOW}Clearing and recreating data directory...${NC}"
rm -rf data
mkdir -p data
echo -e "Current directory: ${BOLD}$(pwd)${NC}"
echo -e "Data directory: ${BOLD}$(pwd)/data${NC}"
echo -e "Data directory is now ${GREEN}empty${NC}"

section "RUNNING CONTAINER"
echo -e "${YELLOW}Running container for 30 seconds...${NC}"
echo -e "Mounting ${BOLD}$(pwd)/data${NC} to ${BOLD}/app/data${NC} in the container"
echo -e "Container will run with these environment variables:"
echo -e "  - ${BOLD}SENSOR_ID${NC}=TEST001"
echo -e "  - ${BOLD}SENSOR_LOCATION${NC}=Test Location"
echo -e "\n${YELLOW}Starting container...${NC}"

timeout 30s docker run --rm \
  -e SENSOR_ID=TEST001 \
  -e SENSOR_LOCATION="Test Location" \
  -v "$(pwd)/data:/app/data" \
  sensor-simulator:test || true

section "CHECKING RESULTS"
echo -e "${YELLOW}Container finished. Checking results...${NC}"
echo -e "Data directory contents after running container:"
safe_ls data/

echo -e "\n${YELLOW}Checking if database was created...${NC}"
if [ -f "data/sensor_data.db" ]; then
  echo -e "${GREEN}${BOLD}SUCCESS!${NC} Database file was created at ${BOLD}data/sensor_data.db${NC}"
  
  # Show some stats about the database
  echo -e "\n${YELLOW}Database statistics:${NC}"
  DB_SIZE=$(du -h data/sensor_data.db | cut -f1)
  RECORD_COUNT=$(sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings" 2>/dev/null || echo "Unable to count records")
  
  echo -e "File size: ${BOLD}$DB_SIZE${NC}"
  echo -e "Number of records: ${BOLD}$RECORD_COUNT${NC}"
  
  # Calculate records per second
  if [ "$RECORD_COUNT" -gt 0 ]; then
    RECORDS_PER_SEC=$(echo "scale=2; $RECORD_COUNT / 30" | bc)
    echo -e "Records per second: ${BOLD}$RECORDS_PER_SEC${NC}"
  fi
  
  # Show a sample of the data
  echo -e "\n${YELLOW}Sample data (first 5 records):${NC}"
  sqlite3 data/sensor_data.db "SELECT * FROM sensor_readings LIMIT 5" 2>/dev/null || echo "Unable to query database"
  
  echo -e "\n${GREEN}${BOLD}TEST PASSED:${NC} Container is working properly and writing to the mounted volume."
else
  echo -e "${RED}${BOLD}ERROR:${NC} Database file was not created at ${BOLD}data/sensor_data.db${NC}"
  echo -e "${RED}Contents of data directory:${NC}"
  safe_ls data/
  echo -e "\n${RED}Check container logs for errors:${NC}"
  docker logs "$(docker ps -lq)" 2>&1 || echo "Unable to get container logs"
  echo -e "\n${RED}${BOLD}TEST FAILED:${NC} Container did not create the expected database file."
  exit 1
fi 