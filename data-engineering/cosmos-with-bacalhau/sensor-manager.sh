#!/usr/bin/env bash

# Sensor Manager - Unified script for managing all aspects of sensor simulation and Cosmos DB
# Combines functionality from multiple scripts into a single command-line interface

# Ensure BASH version is 4 or higher
if [ ${BASH_VERSINFO[0]} -lt 4 ]; then
  echo "Error: This script requires Bash version 4 or higher."
  echo "Current version: $BASH_VERSION"
  exit 1
fi

# Set up colors for terminal output
setup_colors() {
  # Set to 1 to enable colors, 0 to disable
  local colors_enabled=1
  
  # Check if we should disable colors
  if [[ -n "$NO_COLORS" || "$TERM" == "dumb" || "$TERM" == "" ]]; then
    colors_enabled=0
  fi
  
  # Check if stdout is a terminal
  if [[ ! -t 1 ]]; then
    colors_enabled=0
  fi
  
  # Define the color codes
  if [[ $colors_enabled -eq 1 ]]; then
    # Use echo with -e flag to enable interpretation of backslash escapes
    RESET=$(echo -e "\033[0m")
    BOLD=$(echo -e "\033[1m")
    GREEN=$(echo -e "\033[32m")
    YELLOW=$(echo -e "\033[33m")
    BLUE=$(echo -e "\033[34m")
    CYAN=$(echo -e "\033[36m")
    RED=$(echo -e "\033[31m")
  else
    # No colors
    RESET=""
    BOLD=""
    GREEN=""
    YELLOW=""
    BLUE=""
    CYAN=""
    RED=""
  fi
  
  export RESET BOLD GREEN YELLOW BLUE CYAN RED
}

# Initialize colors
setup_colors

# Global variables
PROJ_VERSION="1.0.0"
CURRENT_PROJECT_NAME=""

###########################################
# COMMON UTILITY FUNCTIONS
###########################################

function load_env_file() {
  # Source CosmosDB connection details if .env file exists
  if [ -f ".env" ]; then
    echo "Loading configuration from .env file..."
    source .env
  else
    echo "Warning: No .env file found. Using default values and environment variables."
  fi
}

function check_cosmos_credentials() {
  # Check required environment variables
  if [ -z "$COSMOS_ENDPOINT" ] || [ -z "$COSMOS_KEY" ]; then
    echo -e "${RED}Error: COSMOS_ENDPOINT and COSMOS_KEY environment variables must be set.${RESET}"
    echo "You can create a .env file with these variables or set them manually."
    exit 1
  fi
}

function cleanup_containers() {
  echo "Cleaning up existing containers..."
  docker rm -f $(docker ps -a -q --filter "name=sensor" --filter "name=uploader") 2>/dev/null || true
  echo "Removing Docker Compose state files..."
  rm -f .current-project-name .swarm-mode 2>/dev/null || true
}

function is_container_running() {
  local container=$1
  docker ps --format '{{.Names}}' | grep -q "^$container$"
  return $?
}

function count_files() {
  local dir=$1
  local pattern=$2
  if [ -d "$dir" ]; then
    find "$dir" -name "$pattern" | wc -l
  else
    echo "0"
  fi
}

function latest_file() {
  local dir=$1
  local pattern=$2
  if [ -d "$dir" ]; then
    find "$dir" -name "$pattern" -type f -printf "%T@ %p\n" 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-
  else
    echo "none"
  fi
}

function get_file_time() {
  local file=$1
  if [ -f "$file" ]; then
    stat -c "%y" "$file" 2>/dev/null || stat -f "%Sm" "$file" 2>/dev/null
  else
    echo "N/A"
  fi
}

###########################################
# COMMAND: BUILD - Build the uploader image
###########################################

function build_uploader() {
  # Process flags if any
  local TAG=""
  local NO_TAG=false
  
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      --tag)
        TAG="$2"
        shift 2
        ;;
      --no-tag)
        NO_TAG=true
        shift
        ;;
      *)
        echo "Unknown parameter for build: $1"
        echo "Usage: $0 build [--tag VERSION] [--no-tag]"
        exit 1
        ;;
    esac
  done
  
  # Generate tag if not provided
  if [ -z "$TAG" ] && [ "$NO_TAG" = false ]; then
    TIMESTAMP=$(date +%Y%m%d%H%M%S)
    TAG="v$TIMESTAMP"
  fi
  
  echo -e "${BOLD}Building CosmosUploader image${RESET}"
  if [ "$NO_TAG" = false ]; then
    echo "Using tag: $TAG"
  fi
  
  # Check if we need to create a backup of the entrypoint.sh
  if [ ! -f "cosmos-uploader/entrypoint.sh.original" ] && [ -f "cosmos-uploader/entrypoint.sh" ]; then
    cp cosmos-uploader/entrypoint.sh cosmos-uploader/entrypoint.sh.original
  fi
  
  # Run the build script in the cosmos-uploader directory
  cd cosmos-uploader
  
  if [ "$NO_TAG" = false ]; then
    # Build with timestamp tag
    ./build.sh --tag "$TAG"
    
    # Tag as latest if it's not already tagged as latest
    docker tag cosmos-uploader:$TAG cosmos-uploader:latest
    
    echo "Build completed:"
    echo "  - cosmos-uploader:$TAG"
    echo "  - cosmos-uploader:latest"
    
    # Return to original directory
    cd ..
    
    # Update docker-compose.yml to use the tagged version if it exists
    if [ -f "docker-compose.yml" ]; then
      sed -i.bak "s|cosmos-uploader:.*|cosmos-uploader:$TAG|g" docker-compose.yml
      rm -f docker-compose.yml.bak
      echo "Updated docker-compose.yml to use tagged image: cosmos-uploader:$TAG"
    fi
  else
    # Build without tagging
    ./build.sh 
    echo "Build completed: cosmos-uploader:latest"
    # Return to original directory
    cd ..
  fi
  
  return 0
}

###########################################
# COMMAND: START - Start sensor simulation
###########################################

function start_sensors() {
  # Parse command line arguments
  local REBUILD=true
  PROJECT_NAME="cosmos-sensors-$(date +%Y%m%d%H%M%S)"
  SENSOR_CONFIG_FILE="config/sensor-config.yaml"
  
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      --no-rebuild)
        REBUILD=false
        shift
        ;;
      --project-name)
        PROJECT_NAME="$2"
        shift 2
        ;;
      --no-diagnostics)
        NO_DIAGNOSTICS=true
        shift
        ;;
      --sensor-config)
        SENSOR_CONFIG_FILE="$2"
        shift 2
        ;;
      *)
        echo "Unknown parameter for start: $1"
        echo "Usage: $0 start [--no-rebuild] [--project-name NAME] [--no-diagnostics] [--sensor-config PATH]"
        exit 1
        ;;
    esac
  done

  # Step 1: Cleanup - Stop and remove existing containers
  echo -e "${BOLD}Step 1: Cleaning up existing containers...${RESET}"
  cleanup_containers

  # Step 2: Set default configuration values
  export SENSORS_PER_CITY=${SENSORS_PER_CITY:-3}
  export MAX_CITIES=${MAX_CITIES:-3}
  export READINGS_PER_SECOND=${READINGS_PER_SECOND:-1}
  export ANOMALY_PROBABILITY=${ANOMALY_PROBABILITY:-0.05}
  export UPLOAD_INTERVAL=${UPLOAD_INTERVAL:-30}
  export ARCHIVE_FORMAT=${ARCHIVE_FORMAT:-"Parquet"}
  # CONFIG_FILE is the path of the config file relative to the /app/config directory in the container
  # This will be used as: /app/config/${CONFIG_FILE} in the container
  # Do not include any leading slashes or "config/" in this value
  export CONFIG_FILE=${CONFIG_FILE:-"config.yaml"}

  # Load environment variables
  load_env_file
  
  # Check Cosmos credentials
  check_cosmos_credentials

  # Step 4: Build the uploader image with versioning if needed
  if [ "$REBUILD" = true ]; then
    echo -e "${BOLD}Step 3: Building Cosmos Uploader image with versioning...${RESET}"
    build_uploader
  else
    echo -e "${BOLD}Step 3: Skipping rebuild as requested...${RESET}"
  fi

  # Step 5: Generate Docker Compose configuration
  echo -e "${BOLD}Step 4: Generating docker-compose.yml with sensors using configuration file...${RESET}"
  
  # Make the generate script executable
  chmod +x ./generate-multi-sensor-compose.sh
  
  # Check if the sensor config file exists
  SENSOR_CONFIG_FILE="config/sensor-config.yaml"
  if [ ! -f "$SENSOR_CONFIG_FILE" ]; then
    echo -e "${YELLOW}Warning: Sensor configuration file not found at $SENSOR_CONFIG_FILE${RESET}"
    echo "Using default configuration instead."
  else
    echo -e "${GREEN}Using sensor configuration from $SENSOR_CONFIG_FILE${RESET}"
    
    # Export the sensor config file path for use in the generation script
    export SENSOR_CONFIG_FILE
  fi
  
  # Generate the docker-compose.yml file with the multi-region test configuration
  echo -e "${GREEN}Generating multi-region test configuration with dedicated sensors and uploaders per region${RESET}"
  ./generate-multi-sensor-compose.sh
  
  echo -e "${YELLOW}NOTE: Using TEST configuration with multiple regions - not for production use${RESET}"
  
  # Get the list of cities and sensors per city
  CITIES_FILE="config/cities.txt"
  CITIES=$(head -n $MAX_CITIES "$CITIES_FILE")

  # Step 6: Clean up existing data directories
  echo -e "${BOLD}Step 6: Setting up data directories...${RESET}"
  
  # Clean up existing directories and create fresh ones
  echo "Cleaning up old data..."
  rm -rf ./data/*
  rm -rf ./archive/*
  
  # Clean up Docker networks
  echo "Cleaning up Docker networks..."
  docker network prune -f
  
  # Create base data and archive directories for replicas to use
  echo "Creating shared data directories..."
  mkdir -p "./data"
  mkdir -p "./archive"
  
  echo -e "${GREEN}✅ Data directories prepared for replica deployment${RESET}"

  # Step 7: Check if Docker is running
  if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${RESET}"
    exit 1
  fi

  # Configure Docker Compose commands
  COMPOSE_CMD="docker-compose -p $PROJECT_NAME"
  
  # Display project information
  echo -e "${BOLD}Using project name: ${CYAN}$PROJECT_NAME${RESET}"
  echo "Mode: Standard Docker Compose"
  
  if [ "$REBUILD" = true ]; then
    echo "Images have been freshly built"
  else
    echo "Using existing images"
  fi
  
  # Save project name to a file for later use
  echo "$PROJECT_NAME" > .current-project-name
  CURRENT_PROJECT_NAME="$PROJECT_NAME"

  # Step 8: Verify Docker Compose configuration
  echo -e "${BOLD}Step 8: Verifying docker-compose.yml configuration...${RESET}"
  echo "Using CONFIG_FILE=$CONFIG_FILE"
  
  # Check if the config file exists
  if [ ! -f "config/$CONFIG_FILE" ]; then
    echo -e "${RED}WARNING: Config file config/$CONFIG_FILE does not exist!${RESET}"
    echo "This may cause containers to fail on startup."
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Aborting startup."
      exit 1
    fi
  else
    echo -e "${GREEN}Config file found. Ready to start containers.${RESET}"
  fi
  
  # Step 9: Start the containers
  echo -e "${BOLD}Step 9: Starting containers for all cities...${RESET}"
  $COMPOSE_CMD up -d
  
  # Wait for containers to start up
  echo "Waiting for containers to start up..."
  sleep 5
  
  # Get container count
  CONTAINER_COUNT=$($COMPOSE_CMD ps | grep -c "Up" || echo 0)
  
  # Count the total number of sensors
  NUM_SENSORS=$(($(echo "$CITIES" | wc -l) * SENSORS_PER_CITY))
  
  # Display status
  echo "===================================================="
  echo "                   STARTUP COMPLETE                 "
  echo "===================================================="
  echo -e "${GREEN}✅ Running $NUM_SENSORS sensors across $(echo "$CITIES" | wc -l | tr -d ' ') cities.${RESET}"
  echo -e "${GREEN}✅ Project name: $PROJECT_NAME${RESET}"
  echo -e "${GREEN}✅ Each city has $SENSORS_PER_CITY sensors and 1 dedicated uploader${RESET}"
  echo ""
  echo "USEFUL COMMANDS:"
  echo "* View logs: $0 logs [service-name...]"
  echo "* Stop all: $0 stop"
  echo "* Diagnostics: $0 diagnostics"
  echo "* Query SQLite: $0 query [--all | <city> [<sensor>]]"
  echo "* Monitor: $0 monitor [--plain]"
  echo ""
  echo "DATA LOCATIONS:"
  echo "- ./data/{city}/{sensor-number}/sensor_data.db"
  echo "- ./archive/{city}/{region}_{sensor-id}_{timestamp}.parquet"
  echo "===================================================="
  
  # Display container status
  echo "Current container status:"
  $COMPOSE_CMD ps
  
  # Step 9: Run diagnostics
  if [ "$NO_DIAGNOSTICS" != true ]; then
    echo -e "${BOLD}Step 9: Running initial diagnostics...${RESET}"
    sleep 10  # Give containers a bit more time to initialize
    run_diagnostics
  fi
}

###########################################
# COMMAND: STOP - Stop all running containers
###########################################

function stop_sensors() {
  echo -e "${BOLD}Stopping all containers...${RESET}"
  
  # Parse arguments
  local NO_PROMPT=false
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      --no-prompt)
        NO_PROMPT=true
        shift
        ;;
      *)
        echo "Unknown parameter for stop: $1"
        echo "Usage: $0 stop [--no-prompt]"
        exit 1
        ;;
    esac
  done
  
  # Check if we have current project name saved
  if [ -f ".current-project-name" ]; then
    PROJECT_NAME=$(cat .current-project-name)
    echo "Using saved project name: $PROJECT_NAME"
    COMPOSE_CMD="docker-compose -p $PROJECT_NAME"
  else
    echo "No project name found, using default docker-compose"
    COMPOSE_CMD="docker-compose"
  fi
  
  # Check if docker-compose.yml exists
  if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found. Nothing to stop.${RESET}"
    exit 1
  fi
  
  # Stop all containers using docker-compose
  $COMPOSE_CMD down
  
  echo -e "${GREEN}All containers stopped.${RESET}"
  
  # Ask if user wants to delete the project file, unless --no-prompt is used
  if [ "$NO_PROMPT" = false ]; then
    read -p "Remove project reference? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      rm -f .current-project-name
      echo "Project reference removed."
    fi
  fi
}

###########################################
# COMMAND: CLEAN - Delete all data from Cosmos DB
###########################################

function clean_cosmos() {
  echo -e "${BOLD}Starting Cosmos DB data cleanup...${RESET}"
  
  # Parse command line arguments
  local DRY_RUN=false
  local CONFIRM=false
  local CONFIG_PATH="config/${CONFIG_FILE:-config.yaml}"
  
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --yes)
        CONFIRM=true
        shift
        ;;
      --config)
        CONFIG_PATH="$2"
        if [ ! -f "$CONFIG_PATH" ]; then
          echo -e "${RED}Error: Config file not found at $CONFIG_PATH${RESET}"
          exit 1
        fi
        shift 2
        ;;
      *)
        echo "Unknown parameter for clean: $1"
        echo "Usage: $0 clean [--dry-run] [--yes] [--config PATH]"
        exit 1
        ;;
    esac
  done
  
  # Load environment variables
  load_env_file
  
  # Check Cosmos credentials
  check_cosmos_credentials
  
  # Set default database and container if not provided
  export COSMOS_DATABASE=${COSMOS_DATABASE:-SensorData}
  export COSMOS_CONTAINER=${COSMOS_CONTAINER:-SensorReadings}
  
  echo -e "${CYAN}Will clean data from database '${COSMOS_DATABASE}' and container '${COSMOS_CONTAINER}'${RESET}"
  
  # Confirm unless --yes was provided
  if [ "$CONFIRM" != true ]; then
    echo -e "${YELLOW}This will DELETE ALL DATA in the specified container.${RESET}"
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Canceling cleanup operation."
      exit 0
    fi
  fi
  
  # Build the command with appropriate options
  cmd_options=""
  if [ "$DRY_RUN" = true ]; then
    cmd_options="$cmd_options --dry-run"
  fi
  
  # Always pass the config file - this is the main change to read credentials from config
  cmd_options="$cmd_options --config $CONFIG_PATH"
  
  echo -e "${CYAN}Executing: utility_scripts/bulk_delete_cosmos.py $cmd_options${RESET}"
  
  # Run Python bulk delete script with uv run -s
  utility_scripts/bulk_delete_cosmos.py $cmd_options || {
    echo -e "${RED}Error: Failed to run bulk delete script.${RESET}"
    echo "Make sure uv is installed and azure-cosmos package is available."
    echo "Run: uv pip install azure-cosmos pyyaml"
    exit 1
  }
  
  if [ "$DRY_RUN" = false ]; then
    echo ""
    echo -e "${GREEN}Bulk deletion completed! The container has been emptied but preserved.${RESET}"
    echo "New data will be uploaded as sensors continue to run."
  fi
}

###########################################
# COMMAND: FORCE-CLEANUP - Remove all containers
###########################################

function force_cleanup() {
  echo -e "${BOLD}Force removing all sensor and uploader containers...${RESET}"
  
  # Find all sensor and uploader container IDs
  CONTAINER_IDS=$(docker ps -a -q --filter "name=sensor" --filter "name=uploader")
  
  if [ -z "$CONTAINER_IDS" ]; then
    echo "No containers found to remove."
  else
    # Remove containers
    docker rm -f $CONTAINER_IDS
    echo "Removed containers with IDs: $CONTAINER_IDS"
  fi
  
  # Remove any old project references
  rm -f .current-project-name
  rm -f .swarm-mode
  
  echo -e "${GREEN}Cleanup complete!${RESET}"
  echo "You can now run '$0 start' to start fresh containers."
}

###########################################
# COMMAND: QUERY - Query SQLite databases
###########################################

function query_db() {
  local db_path="$1"
  local city="$2"
  local sensor="$3"
  
  echo "======================="
  echo "Database: $db_path"
  echo "City: $city, Sensor: $sensor"
  echo "======================="
  
  # Check if file exists
  if [ ! -f "$db_path" ]; then
    echo -e "${YELLOW}⚠️ Database file not found${RESET}"
    return
  fi
  
  # Check file size
  file_size=$(du -h "$db_path" | awk '{print $1}')
  echo "File size: $file_size"
  
  # Run SQLite query to get table info
  echo -e "\nTable schema:"
  sqlite3 "$db_path" ".schema"
  
  # Run SQLite query to get row count
  row_count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM sensor_readings")
  echo -e "\nTotal records: $row_count"
  
  # Run SQLite query to get sample data
  echo -e "\nSample records:"
  sqlite3 "$db_path" "SELECT id, sensor_id, timestamp, temperature, location FROM sensor_readings LIMIT 5;"
  
  # Check for sensor_id values 
  echo -e "\nUnique sensor_id values:"
  sqlite3 "$db_path" "SELECT DISTINCT sensor_id FROM sensor_readings;"
  
  # Check location values
  echo -e "\nUnique location values:"
  sqlite3 "$db_path" "SELECT DISTINCT location FROM sensor_readings;"
  
  echo ""
}

function run_query() {
  # Parse command line options
  if [ "$1" == "--all" ]; then
    # Query all databases found in the data directory
    echo -e "${BOLD}Querying all SQLite databases in the data directory...${RESET}"
    echo ""
    
    # Find all sensor_data.db files in the data directory
    DB_FILES=$(find ./data -name "sensor_data.db")
    
    if [ -z "$DB_FILES" ]; then
      echo -e "${YELLOW}No database files found. Make sure the sensors have generated data.${RESET}"
      return
    fi
    
    # Process each database file
    for DB_PATH in $DB_FILES; do
      # Extract sensor information from the path if possible
      SENSOR_ID=$(sqlite3 "$DB_PATH" "SELECT DISTINCT sensor_id FROM sensor_readings LIMIT 1;" 2>/dev/null || echo "Unknown")
      LOCATION=$(sqlite3 "$DB_PATH" "SELECT DISTINCT location FROM sensor_readings LIMIT 1;" 2>/dev/null || echo "Unknown")
      
      query_db "$DB_PATH" "$LOCATION" "$SENSOR_ID"
    done
  elif [ "$1" == "--list" ]; then
    # List all sensors found in the databases
    echo -e "${BOLD}Listing all sensors with data:${RESET}"
    echo ""
    
    # Find all sensor_data.db files
    DB_FILES=$(find ./data -name "sensor_data.db")
    
    if [ -z "$DB_FILES" ]; then
      echo -e "${YELLOW}No database files found. Make sure the sensors have generated data.${RESET}"
      return
    fi
    
    echo -e "${CYAN}%-30s %-30s %-30s${RESET}" "DATABASE PATH" "SENSOR ID" "LOCATION"
    echo "---------------------------------------------------------------------------------"
    
    # Process each database file
    for DB_PATH in $DB_FILES; do
      # Extract sensor information
      SENSOR_ID=$(sqlite3 "$DB_PATH" "SELECT DISTINCT sensor_id FROM sensor_readings LIMIT 1;" 2>/dev/null || echo "Unknown")
      LOCATION=$(sqlite3 "$DB_PATH" "SELECT DISTINCT location FROM sensor_readings LIMIT 1;" 2>/dev/null || echo "Unknown")
      
      printf "%-30s %-30s %-30s\n" "$DB_PATH" "$SENSOR_ID" "$LOCATION"
    done
  elif [ -n "$1" ]; then
    # Try to find a database with the specified sensor ID
    SENSOR_ID="$1"
    echo -e "${BOLD}Searching for sensor with ID: $SENSOR_ID${RESET}"
    echo ""
    
    # Find all sensor_data.db files
    DB_FILES=$(find ./data -name "sensor_data.db")
    
    if [ -z "$DB_FILES" ]; then
      echo -e "${YELLOW}No database files found. Make sure the sensors have generated data.${RESET}"
      return
    fi
    
    # Try to find the specified sensor ID
    FOUND=false
    for DB_PATH in $DB_FILES; do
      # Check if this database contains the requested sensor ID
      FOUND_ID=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sensor_readings WHERE sensor_id LIKE '%$SENSOR_ID%' LIMIT 1;" 2>/dev/null)
      
      if [ "$FOUND_ID" -gt 0 ]; then
        LOCATION=$(sqlite3 "$DB_PATH" "SELECT DISTINCT location FROM sensor_readings WHERE sensor_id LIKE '%$SENSOR_ID%' LIMIT 1;" 2>/dev/null)
        echo -e "${GREEN}Found sensor $SENSOR_ID in database: $DB_PATH${RESET}"
        query_db "$DB_PATH" "$LOCATION" "$SENSOR_ID"
        FOUND=true
        break
      fi
    done
    
    if [ "$FOUND" = false ]; then
      echo -e "${YELLOW}No database found for sensor ID: $SENSOR_ID${RESET}"
      echo "Available sensors:"
      run_query --list
    fi
  else
    # Show usage
    echo "Usage: $0 query [--all | --list | <sensor_id>]"
    echo ""
    echo "Examples:"
    echo "  $0 query --all                  # Query all databases"
    echo "  $0 query --list                 # List all available sensors"
    echo "  $0 query AMS_SENSOR001          # Query specific sensor by ID"
    echo ""
  fi
}

###########################################
# COMMAND: LOGS - View container logs
###########################################

function view_logs() {
  # Check if we have current project name saved
  if [ -f ".current-project-name" ]; then
    PROJECT_NAME=$(cat .current-project-name)
    echo "Viewing logs for project: $PROJECT_NAME"
  else
    PROJECT_NAME=""
    echo "No project name found, using default docker-compose"
  fi
  
  echo "Press Ctrl+C to exit"
  echo "---------------------------------------------"
  
  # If no arguments are provided, show logs for all containers
  if [ $# -eq 0 ]; then
    # Standard docker-compose logs
    if [ -n "$PROJECT_NAME" ]; then
      docker compose -p "$PROJECT_NAME" logs -f
    else
      docker compose logs -f
    fi
  else
    # Standard docker-compose logs for specific services
    if [ -n "$PROJECT_NAME" ]; then
      docker compose -p "$PROJECT_NAME" logs -f "$@"
    else
      docker compose logs -f "$@"
    fi
  fi
}

###########################################
# COMMAND: DIAGNOSTICS - Run diagnostics
###########################################

function run_diagnostics() {
  # Check if Docker is running
  if ! docker ps >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${RESET}"
    exit 1
  fi
  
  # Check for running containers
  echo -e "${BOLD}Checking running containers...${RESET}"
  echo ""
  
  echo -e "${CYAN}🧪 SENSOR CONTAINERS:${RESET}"
  docker ps --filter "name=sensor" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
  SENSOR_COUNT=$(docker ps --filter "name=sensor" -q | wc -l | tr -d ' ')
  echo "Total sensor containers: $SENSOR_COUNT"
  echo ""
  
  echo -e "${CYAN}🧪 UPLOADER CONTAINERS:${RESET}"
  docker ps --filter "name=uploader" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
  UPLOADER_COUNT=$(docker ps --filter "name=uploader" -q | wc -l | tr -d ' ')
  echo "Total uploader containers: $UPLOADER_COUNT"
  echo ""
  
  # Check images
  echo -e "${CYAN}🧪 COSMOS UPLOADER IMAGES:${RESET}"
  docker images "cosmos-uploader*" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}"
  echo ""
  
  # Check uploader logs
  echo -e "${CYAN}🧪 CHECKING LOGS FROM UPLOADER CONTAINERS:${RESET}"
  echo "Showing last 10 lines from the uploader container..."
  echo ""
  
  UPLOADER_CONTAINER=$(docker ps --filter "name=uploader" -q | head -1)
  if [ -n "$UPLOADER_CONTAINER" ]; then
    container_name=$(docker inspect --format='{{.Name}}' $UPLOADER_CONTAINER | sed 's/\///')
    echo -e "${YELLOW}=== $container_name ===${RESET}"
    docker logs $UPLOADER_CONTAINER --tail 20 | grep -i 'sensor' | tail -n 10
  else
    echo -e "${YELLOW}No uploader container found running${RESET}"
  fi
  echo ""
  
  # Check sensor logs (sample from a few replica containers)
  echo -e "${CYAN}🧪 CHECKING LOGS FROM SENSOR CONTAINERS:${RESET}"
  echo "Showing last 10 lines from a few sensor replicas..."
  echo ""
  
  SENSOR_CONTAINERS=$(docker ps --filter "name=sensor" -q | head -3)
  if [ -n "$SENSOR_CONTAINERS" ]; then
    for container in $SENSOR_CONTAINERS; do
      container_name=$(docker inspect --format='{{.Name}}' $container | sed 's/\///')
      echo -e "${YELLOW}=== $container_name ===${RESET}"
      docker logs $container --tail 10
      echo ""
    done
  else
    echo -e "${YELLOW}No sensor containers found running${RESET}"
  fi
  
  # Check SQLite databases
  echo -e "${CYAN}🧪 CHECKING SQLITE DATABASES:${RESET}"
  echo "Looking for databases in data directory..."
  echo ""
  
  find ./data -name "sensor_data.db" | while read db; do
    echo "Database: $db"
    # Check if file exists and has data
    if [ -f "$db" ]; then
      size=$(du -h "$db" | cut -f1)
      
      # First check if sqlite3 is available
      if ! command -v sqlite3 &> /dev/null; then
        echo "  - Size: $size"
        echo "  - Records: ${YELLOW}sqlite3 command not available${RESET}"
        continue
      fi
      
      # Check if the file is a valid SQLite database
      if ! sqlite3 "$db" ".tables" &> /dev/null; then
        echo "  - Size: $size"
        echo "  - Records: ${YELLOW}Not a valid SQLite database or still initializing${RESET}"
        continue
      fi
      
      # Check if the sensor_readings table exists
      if ! sqlite3 "$db" ".tables" 2>/dev/null | grep -q "sensor_readings"; then
        echo "  - Size: $size"
        echo "  - Records: ${YELLOW}Table 'sensor_readings' not found${RESET}"
        continue
      fi
      
      # Now try to count the records
      count=$(sqlite3 "$db" "SELECT COUNT(*) FROM sensor_readings" 2>/dev/null || echo "${RED}Error accessing table${RESET}")
      
      echo "  - Size: $size"
      if [[ "$count" =~ ^[0-9]+$ ]]; then
        if [ "$count" -eq 0 ]; then
          echo "  - Records: ${YELLOW}0 (empty)${RESET}"
        else
          echo "  - Records: ${GREEN}$count${RESET}"
        fi
      else
        echo "  - Records: $count"
      fi
    else
      echo "  - ${RED}Not found or empty${RESET}"
    fi
  done
  
  echo ""
  echo -e "${BOLD}📊 DIAGNOSTIC SUMMARY:${RESET}"
  echo "- Sensor containers: $SENSOR_COUNT"
  echo "- Uploader containers: $UPLOADER_COUNT"
  echo ""
  echo "Next steps:"
  echo "1. Check if the correct sensor IDs appear in the logs"
  echo "2. Run '$0 query --all' to check database contents"
  echo "3. Verify if all sensor IDs are appearing in Cosmos DB"
}

###########################################
# COMMAND: MONITOR - Monitor uploads
###########################################

function run_monitor() {
  local USE_COLOR=1
  
  # Check if colors should be disabled
  if [[ "$1" == "--plain" || "$TERM" == "dumb" || -n "$NO_COLOR" ]]; then
    USE_COLOR=0
  fi
  
  # Set terminal colors (only if enabled)
  if [[ $USE_COLOR -eq 0 ]]; then
    # No colors
    RESET=""
    BOLD=""
    GREEN=""
    YELLOW=""
    BLUE=""
    CYAN=""
    RED=""
  fi
  
  # Print header
  # Only clear if not using watch (watch does its own clearing)
  if [ -z "$WATCH_EXEC" ]; then
    clear
  fi
  
  echo -e "${BOLD}SENSOR DATA MONITORING${RESET} - $(date)"
  echo -e "${CYAN}Checking data for sensor replicas...${RESET}"
  echo
  
  # Get container stats
  SENSOR_CONTAINERS=$(docker ps --filter "name=sensor" -q)
  SENSOR_COUNT=$(echo "$SENSOR_CONTAINERS" | wc -l | tr -d ' ')
  if [ -z "$SENSOR_CONTAINERS" ]; then
    SENSOR_COUNT=0
  fi
  
  UPLOADER_CONTAINER=$(docker ps --filter "name=uploader" -q | head -1)
  if [ -n "$UPLOADER_CONTAINER" ]; then
    UPLOADER_STATUS="${GREEN}RUNNING${RESET}"
  else
    UPLOADER_STATUS="${RED}STOPPED${RESET}"
  fi
  
  # Print container summary
  echo -e "${BOLD}CONTAINER STATUS:${RESET}"
  echo -e "Sensor Replicas: $SENSOR_COUNT"
  echo -e "Uploader Status: $UPLOADER_STATUS"
  echo
  
  # Check for SQLite databases
  echo -e "${BOLD}DATABASE STATUS:${RESET}"
  DB_FILES=$(find ./data -name "sensor_data.db")
  DB_COUNT=$(echo "$DB_FILES" | wc -l | tr -d ' ')
  if [ -z "$DB_FILES" ]; then
    DB_COUNT=0
  fi
  
  echo -e "SQLite Databases: $DB_COUNT"
  
  # Check archive files
  ARCHIVE_FILES=$(find ./archive -name "*.parquet")
  ARCHIVE_COUNT=$(echo "$ARCHIVE_FILES" | wc -l | tr -d ' ')
  if [ -z "$ARCHIVE_FILES" ]; then
    ARCHIVE_COUNT=0
  fi
  
  echo -e "Archive Files: $ARCHIVE_COUNT"
  echo
  
  # Show active sensors from databases
  echo -e "${BOLD}ACTIVE SENSORS:${RESET}"
  echo
  
  if [ "$DB_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No database files found yet. Sensors may still be initializing.${RESET}"
  else
    # Print table header
    printf "${BOLD}%-25s %-25s %-15s %-15s${RESET}\n" "SENSOR ID" "LOCATION" "DB SIZE" "READINGS"
    echo "--------------------------------------------------------------------------------"
    
    # Check each database file (limit to 10 for display purposes)
    count=0
    for DB_PATH in $DB_FILES; do
      # Skip if we've already shown 10 files
      ((count++))
      if [ $count -gt 10 ]; then
        echo "... and $(($DB_COUNT - 10)) more database files ..."
        break
      fi
      
      # Get database size
      DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
      
      # Get sensor information
      SENSOR_ID=$(sqlite3 "$DB_PATH" "SELECT DISTINCT sensor_id FROM sensor_readings LIMIT 1;" 2>/dev/null || echo "Unknown")
      LOCATION=$(sqlite3 "$DB_PATH" "SELECT DISTINCT location FROM sensor_readings LIMIT 1;" 2>/dev/null || echo "Unknown")
      READING_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "0")
      
      # Print row
      printf "%-25s %-25s %-15s %-15s\n" \
        "$SENSOR_ID" "$LOCATION" "$DB_SIZE" "$READING_COUNT"
    done
  fi
  
  echo
  
  # Show recent archive files
  echo -e "${BOLD}RECENT ARCHIVES:${RESET}"
  echo
  
  if [ "$ARCHIVE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No archive files found yet. May need to wait for the uploader cycle.${RESET}"
  else
    # Print table header
    printf "${BOLD}%-60s %-25s${RESET}\n" "ARCHIVE FILE" "CREATION TIME"
    echo "--------------------------------------------------------------------------------"
    
    # List the 5 most recent archive files
    find ./archive -name "*.parquet" -type f -printf "%T@ %T+ %p\n" 2>/dev/null | \
      sort -nr | head -5 | while read timestamp timestr filepath; do
        filename=$(basename "$filepath")
        printf "%-60s %-25s\n" "$filename" "$(echo $timestr | cut -d'+' -f1)"
      done
  fi
  
  echo
  echo -e "${CYAN}TIP:${RESET} Run with 'watch' for real-time updates: ${BOLD}watch -n 5 $0 monitor${RESET}"
  echo -e "${CYAN}TIP:${RESET} For more details: ${BOLD}$0 query --list${RESET} or ${BOLD}$0 diagnostics${RESET}"
}

###########################################
# COMMAND: RESET - Reset services with fixed config
###########################################

function reset_services() {
  local NO_DIAGNOSTICS=false
  local SENSOR_CONFIG_FILE="config/sensor-config.yaml"
  
  # Parse arguments
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      --no-diagnostics)
        NO_DIAGNOSTICS=true
        shift
        ;;
      --sensor-config)
        SENSOR_CONFIG_FILE="$2"
        shift 2
        ;;
      *)
        echo "Unknown parameter for reset: $1"
        echo "Usage: $0 reset [--no-diagnostics] [--sensor-config PATH]"
        exit 1
        ;;
    esac
  done

  echo "Resetting services with configuration from $SENSOR_CONFIG_FILE..."
  
  # Step 1: Stop all services
  echo "Step 1: Stopping all services..."
  stop_sensors --no-prompt
  
  # Step 2: Ensure Dockerfile has the proper entrypoint wrapper
  echo "Step 2: Ensuring Dockerfile has the proper entrypoint wrapper..."
  fix_dockerfile 2>/dev/null || echo "Skipping Dockerfile fix (function not available)."
  
  # Step 3: Rebuild the image
  echo "Step 3: Rebuilding the Docker image with fixed entrypoint..."
  build_uploader --no-tag
  
  # Step 4: Check if the sensor config file exists
  if [ ! -f "$SENSOR_CONFIG_FILE" ]; then
    echo -e "${YELLOW}Warning: Sensor configuration file not found at $SENSOR_CONFIG_FILE${RESET}"
    echo "Using default configuration instead."
  else
    echo -e "${GREEN}Using sensor configuration from $SENSOR_CONFIG_FILE${RESET}"
    # Export the sensor config file path for use in the generation script
    export SENSOR_CONFIG_FILE
  fi
  
  # Step 5: Regenerate the Docker Compose file
  echo "Step 5: Recreating Docker Compose file with multi-region test configuration..."
  chmod +x ./generate-multi-sensor-compose.sh
  ./generate-multi-sensor-compose.sh
  
  echo -e "${YELLOW}NOTE: Using TEST configuration with multiple regions - not for production use${RESET}"
  
  # Step 6: Start all services
  echo "Step 6: Starting all services with configuration..."
  docker-compose up -d
  
  echo "Services reset complete. Check their status with:"
  echo "docker-compose ps"
  
  # Step 7: Run diagnostics if requested
  if [ "$NO_DIAGNOSTICS" != "true" ]; then
    echo "Step 7: Running diagnostics..."
    sleep 10  # Give containers a bit more time to initialize
    run_diagnostics
  fi
}

###########################################
# COMMAND: VERSION - Show version
###########################################

function show_version() {
  echo "Sensor Manager v$PROJ_VERSION"
  echo "Copyright (c) 2023-2025 Bacalhau Project"
}

###########################################
# COMMAND: HELP - Display usage information
###########################################

function show_help() {
  echo "Sensor Manager v$PROJ_VERSION - Unified script for managing all aspects of sensor simulation and Cosmos DB"
  echo ""
  echo "USAGE:"
  echo "  $0 <command> [options]"
  echo ""
  echo "COMMANDS:"
  echo "  start       Start sensor simulation with configuration"
  echo "  stop        Stop all running containers"
  echo "  reset       Reset services with fixed configuration"
  echo "  clean       Delete all data from Cosmos DB"
  echo "  build       Build the CosmosUploader image"
  echo "  logs        View logs from running containers"
  echo "  query       Query SQLite databases"
  echo "  diagnostics Run system diagnostics"
  echo "  monitor     Monitor sensors and uploads"
  echo "  cleanup     Force clean all containers"
  echo "  version     Show version information"
  echo "  help        Show this help message"
  echo ""
  echo "CONFIGURATION:"
  echo "  Configuration can be set via environment variables, either directly or in a .env file."
  echo "  See .env.template for available options."
  echo ""
  echo "COMMAND DETAILS:"
  echo "  start [--no-rebuild] [--project-name NAME] [--no-diagnostics] [--sensor-config PATH]"
  echo "      Starts sensor simulation with configuration"
  echo ""
  echo "  stop [--no-prompt]"
  echo "      Stops all running containers"
  echo ""
  echo "  reset [--no-diagnostics] [--sensor-config PATH]"
  echo "      Resets services with configuration (stops, regenerates config, starts)"
  echo ""
  echo "  clean [--dry-run] [--yes] [--config PATH]"
  echo "      Deletes all data from Cosmos DB using the bulk delete utility script"
  echo ""
  echo "  build [--tag VERSION] [--no-tag]"
  echo "      Builds the CosmosUploader image"
  echo ""
  echo "  logs [service-name...]"
  echo "      Views logs from running containers"
  echo ""
  echo "  query [--all | <city> [<sensor>]]"
  echo "      Queries SQLite databases"
  echo ""
  echo "  monitor [--plain]"
  echo "      Monitors sensor status and data uploads"
  echo ""
  echo "EXAMPLES:"
  echo "  $0 start                                       # Start with default configuration"
  echo "  $0 start --sensor-config config/custom.yaml   # Start with custom sensor configuration"
  echo "  SENSORS_PER_CITY=10 $0 start                   # Start with 10 sensors per city"
  echo "  $0 monitor --plain                             # Monitor without colors"
  echo "  $0 clean --dry-run                             # Show what would be deleted, without deleting"
  echo "  $0 query Amsterdam 1                           # Check SQLite database for Amsterdam sensor 1"
  echo "  $0 build --tag v1.0.0                          # Build with a specific tag"
  echo ""
  echo "See docs/using-configuration.md for detailed configuration information."
}

###########################################
# MAIN COMMAND DISPATCHER
###########################################

# Main command dispatcher
command=$1
shift # Remove the command from the arguments

case $command in
  start)
    start_sensors "$@"
    ;;
  stop)
    stop_sensors "$@"
    ;;
  reset)
    reset_services "$@"
    ;;
  clean)
    clean_cosmos "$@"
    ;;
  build)
    build_uploader "$@"
    ;;
  logs)
    if type view_logs &>/dev/null; then
      view_logs "$@"
    else
      echo "Viewing logs for containers..."
      if [ -f ".current-project-name" ]; then
        PROJECT_NAME=$(cat .current-project-name)
        echo "Using project name: $PROJECT_NAME"
        docker compose -p "$PROJECT_NAME" logs -f "$@"
      else
        docker compose logs -f "$@"
      fi
    fi
    ;;
  query)
    run_query "$@"
    ;;
  diagnostics)
    run_diagnostics "$@"
    ;;
  monitor)
    run_monitor "$@"
    ;;
  cleanup)
    force_cleanup "$@"
    ;;
  version)
    show_version
    ;;
  help|--help|-h)
    show_help
    ;;
  "")
    echo "Error: No command specified."
    show_help
    exit 1
    ;;
  *)
    echo "Error: Unknown command '$command'."
    show_help
    exit 1
    ;;
esac