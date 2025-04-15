#!/bin/bash

# This script generates docker-compose.yml with multiple sensors per city
# Uses pre-built images instead of building in the compose file
# Standard Docker Compose format with individual containers (no Swarm mode)

# Configuration
OUTPUT_FILE="docker-compose.yml"
CITIES_FILE="config/cities.txt"
SENSOR_CONFIG="config/sensor-config.yaml"
SENSORS_PER_CITY=${SENSORS_PER_CITY:-5}    # Can be overridden with environment variable
MAX_CITIES=${MAX_CITIES:-5}                # Can be overridden with environment variable

# Mode parameter is no longer used, but kept for backward compatibility
MODE=${1:-standard}   # Default to standard mode even if param provided

# Check if cities file exists
if [ ! -f "$CITIES_FILE" ]; then
  echo "Error: Cities file $CITIES_FILE not found."
  exit 1
fi

# Check if sensor config file exists
if [ ! -f "$SENSOR_CONFIG" ]; then
  echo "Error: Sensor configuration file $SENSOR_CONFIG not found."
  exit 1
fi

# Start with the header
cat > $OUTPUT_FILE << EOF
version: '3.8'

services:
EOF

# Read cities file
CITIES=$(head -n $MAX_CITIES "$CITIES_FILE")

# Process each city
for CITY in $CITIES; do
  # Normalize city name for use as container name (remove spaces, special chars)
  NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:upper:]' '[:lower:]')
  
  # Add individual services for each sensor
  for ((i=1; i<=$SENSORS_PER_CITY; i++)); do
    # Create a unique sensor ID including the city code and sensor number
    CITY_CODE=$(echo "$NORMALIZED_CITY" | cut -c1-3 | tr '[:lower:]' '[:upper:]')
    SENSOR_ID="${CITY_CODE}_SENSOR$(printf "%03d" $i)"
    
    # Calculate temperature, vibration, and voltage means based on city and sensor index
    # This is just an example to create some variation - adjust as needed
    TEMP_OFFSET=$(( ($(echo "$NORMALIZED_CITY" | cksum | cut -d' ' -f1) % 10) - 5 ))
    VIBRATION_OFFSET=$(echo "scale=2; (($i * 0.1) + 0.5)" | bc)
    VOLTAGE_FLUCTUATION=$(echo "scale=2; (($i * 0.05) + 0.1)" | bc)
    
    cat >> $OUTPUT_FILE << EOF
  # Sensor ${i} for ${CITY}
  sensor-${NORMALIZED_CITY}-${i}:
    image: ghcr.io/bacalhau-project/sensor-log-generator:latest
    container_name: sensor-${NORMALIZED_CITY}-${i}
    environment:
      - SENSOR_LOCATION=${CITY}
      - SENSOR_ID=${SENSOR_ID}
      # Environment variables that override sensor-config.yaml settings
      - READINGS_PER_SECOND=${READINGS_PER_SECOND:-1}
      - ANOMALY_PROBABILITY=${ANOMALY_PROBABILITY:-0.05}
      - TEMPERATURE_MEAN=${TEMPERATURE_MEAN:-65.0}
      - VIBRATION_MEAN=${VIBRATION_MEAN:-2.5}
      - VOLTAGE_MEAN=${VOLTAGE_MEAN:-12.0}
    volumes:
      - ./data/${NORMALIZED_CITY}/${i}:/app/data
      - ./config/sensor-config.yaml:/app/config/sensor-config.yaml
    restart: unless-stopped
    command: ["uv", "run", "-s", "main.py", "--config", "/app/config/sensor-config.yaml"]

EOF
  done
  
  # Add uploader for this city - always use pre-built image
  # First create dependency list as a string
  depends_list=""
  for ((i=1; i<=$SENSORS_PER_CITY; i++)); do
    if [ $i -eq 1 ]; then
      # First item doesn't need a newline
      depends_list="      - sensor-${NORMALIZED_CITY}-${i}"
    else
      # Add properly indented items
      depends_list="${depends_list}
      - sensor-${NORMALIZED_CITY}-${i}"
    fi
  done
  
  # Set default uploader values, but allow override via environment variables
  UPLOAD_INTERVAL=${UPLOAD_INTERVAL:-30}
  ARCHIVE_FORMAT=${ARCHIVE_FORMAT:-"Parquet"}
  CONFIG_FILE=${CONFIG_FILE:-"config.yaml"}
  
  cat >> $OUTPUT_FILE << EOF
  # Uploader for ${CITY}
  uploader-${NORMALIZED_CITY}:
    image: ghcr.io/bacalhau-project/cosmos-uploader:latest
    container_name: uploader-${NORMALIZED_CITY}
    depends_on:
${depends_list}
    environment:
      - DOTNET_ENVIRONMENT=${DOTNET_ENVIRONMENT:-Production}
      - SENSOR_REGION=${CITY}
      - UPLOAD_INTERVAL=${UPLOAD_INTERVAL}
      - ARCHIVE_FORMAT=${ARCHIVE_FORMAT}
      - COSMOS_ENDPOINT=${COSMOS_ENDPOINT}
      - COSMOS_KEY=${COSMOS_KEY}
      - COSMOS_DATABASE=${COSMOS_DATABASE:-SensorData}
      - COSMOS_CONTAINER=${COSMOS_CONTAINER:-SensorReadings}
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./archive/${NORMALIZED_CITY}:/app/archive
    command: ["--config", "/app/config/${CONFIG_FILE}", "--sqlite", "/app/data", "--continuous", "--interval", "${UPLOAD_INTERVAL}", "--archive-path", "/app/archive"]
    restart: unless-stopped

EOF
done

# Add volumes section for persistent storage
cat >> $OUTPUT_FILE << EOF
volumes:
EOF

# Add volumes for each city
for CITY in $CITIES; do
  NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:upper:]' '[:lower:]')
  cat >> $OUTPUT_FILE << EOF
  ${NORMALIZED_CITY}_data:
    driver: local
  ${NORMALIZED_CITY}_archive:
    driver: local
EOF
done

# Count the number of services
NUM_SENSORS=$(($(echo "$CITIES" | wc -l) * SENSORS_PER_CITY))
NUM_SERVICES=$((NUM_SENSORS + $(echo "$CITIES" | wc -l)))  # Individual sensor services + one uploader per city
echo "Generated $OUTPUT_FILE with $NUM_SENSORS sensors across $(echo "$CITIES" | wc -l | tr -d ' ') cities ($NUM_SERVICES total services)."
echo "Configuration uses standard Docker Compose with immutable pre-built images."
echo "Each city has $SENSORS_PER_CITY sensors and 1 dedicated uploader."