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
      *)
        echo "Unknown parameter for start: $1"
        echo "Usage: $0 start [--no-rebuild] [--project-name NAME] [--no-diagnostics]"
        exit 1
        ;;
    esac
  done

  # Step 1: Cleanup - Stop and remove existing containers
  echo -e "${BOLD}Step 1: Cleaning up existing containers...${RESET}"
  cleanup_containers

  # Step 2: Set default configuration values
  export SENSORS_PER_CITY=${SENSORS_PER_CITY:-5}
  export MAX_CITIES=${MAX_CITIES:-5}
  export READINGS_PER_SECOND=${READINGS_PER_SECOND:-1}
  export ANOMALY_PROBABILITY=${ANOMALY_PROBABILITY:-0.05}
  export UPLOAD_INTERVAL=${UPLOAD_INTERVAL:-30}
  export ARCHIVE_FORMAT=${ARCHIVE_FORMAT:-"Parquet"}
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
  echo -e "${BOLD}Step 4: Generating docker-compose.yml with multiple sensors per city...${RESET}"
  
  # Make the generate script executable
  chmod +x ./generate-multi-sensor-compose.sh
  
  # Generate the docker-compose.yml file with multiple sensors per city
  ./generate-multi-sensor-compose.sh
  
  # Get the list of cities and sensors per city
  CITIES_FILE="config/cities.txt"
  CITIES=$(head -n $MAX_CITIES "$CITIES_FILE")

  # Step 6: Clean up existing data directories
  echo -e "${BOLD}Step 6: Cleaning up old data directories...${RESET}"
  rm -rf ./data/*
  rm -rf ./archive/*
  
  # Create data and archive directories for each city with sensor-specific subdirectories
  for CITY in $CITIES; do
    # Normalize city name
    NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:upper:]' '[:lower:]')
    
    echo "Creating directories for $CITY..."
    mkdir -p "./archive/$NORMALIZED_CITY"
    
    # Create directories for each sensor replica in this city
    for ((i=1; i<=$SENSORS_PER_CITY; i++)); do
      echo "  - Creating sensor directory: $NORMALIZED_CITY/$i"
      mkdir -p "./data/$NORMALIZED_CITY/$i"
    done
  done

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

  # Step 8: Start the containers
  echo -e "${BOLD}Step 8: Starting containers for all cities...${RESET}"
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
  local CONFIG_PATH="config/config.yaml"
  
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
  
  # Run Python bulk delete script
  python3 -c "
import os
from azure.cosmos import CosmosClient, PartitionKey

# Get Cosmos DB connection details from environment variables
endpoint = os.environ.get('COSMOS_ENDPOINT')
key = os.environ.get('COSMOS_KEY')
database_name = os.environ.get('COSMOS_DATABASE', 'SensorData')
container_name = os.environ.get('COSMOS_CONTAINER', 'SensorReadings')
dry_run = $([ "$DRY_RUN" = true ] && echo "True" || echo "False")

print(f'Connecting to Cosmos DB: {endpoint}')
print(f'Database: {database_name}')
print(f'Container: {container_name}')
if dry_run:
    print('DRY RUN MODE - No data will be deleted')

# Connect to Cosmos DB
client = CosmosClient(endpoint, key)
database = client.get_database_client(database_name)
container = database.get_container_client(container_name)

def clean_container():
    # First, get all the partition key values (cities)
    print('Finding all partition key values...')
    query = 'SELECT DISTINCT c.city FROM c'
    cities = list(container.query_items(query=query, enable_cross_partition_query=True))
    
    if not cities:
        print('No data found in the container.')
        return
    
    # For each city (partition key), call the bulk delete stored procedure
    total_deleted = 0
    cities_count = len(cities)
    print(f'Found {cities_count} partition key values. Starting deletion...')
    
    for i, city_record in enumerate(cities):
        city = city_record['city']
        partition_key = city
        
        try:
            if dry_run:
                # In dry run mode, just count the documents
                query = f'SELECT VALUE COUNT(1) FROM c WHERE c.city = \"{city}\"'
                count_results = list(container.query_items(
                    query=query,
                    enable_cross_partition_query=False,
                    partition_key=partition_key
                ))
                count = count_results[0] if count_results else 0
                print(f'Would delete {count} documents for city={city}')
                total_deleted += count
            else:
                # Execute the stored procedure with the partition key value
                result = container.scripts.execute_stored_procedure(
                    sproc='bulkDeleteSproc',
                    partition_key=partition_key,
                    params=[partition_key]
                )
                deleted = result.get('deleted', 0)
                total_deleted += deleted
                print(f'Processed partition {i+1}/{cities_count} (city={city}): Deleted {deleted} documents')
        except Exception as e:
            if 'Resource with name \\\'bulkDeleteSproc\\\' not found' in str(e):
                print(f'Stored procedure not found. Creating it first...')
                # Create the stored procedure and try again
                create_sproc()
                try:
                    if not dry_run:
                        result = container.scripts.execute_stored_procedure(
                            sproc='bulkDeleteSproc',
                            partition_key=partition_key,
                            params=[partition_key]
                        )
                        deleted = result.get('deleted', 0)
                        total_deleted += deleted
                        print(f'Processed partition {i+1}/{cities_count} (city={city}): Deleted {deleted} documents')
                except Exception as e2:
                    print(f'Error processing partition {city} after creating sproc: {str(e2)}')
            else:
                print(f'Error processing partition {city}: {str(e)}')
    
    print(f'Done. Total documents {"would be" if dry_run else ""} deleted: {total_deleted}')

# Create or update the bulk delete stored procedure
def create_sproc():
    sproc_body = '''
function bulkDeleteSproc(partitionKeyValue) {
    // Validate input
    if (!partitionKeyValue) {
        throw new Error('Partition key value must be provided');
    }
    
    // Query to get document IDs in this partition
    var query = 'SELECT c.id FROM c WHERE c.city = @city';
    var parameters = [{name: '@city', value: partitionKeyValue}];
    
    // Get document IDs for this partition
    var response = __.queryDocuments(__.getSelfLink(), query, parameters);
    
    // Initialize counter
    var deleted = 0;
    
    // Process the results and delete each document
    if (response.hasMoreResults) {
        while (response.hasMoreResults) {
            // Get a batch of results
            var batch = response.executeNext();
            for (var i = 0; i < batch.length; i++) {
                // Get document link and delete the document
                var docLink = __.getAltLink() + '/docs/' + batch[i].id;
                var deleted_result = __.deleteDocument(docLink, {});
                deleted++;
            }
        }
    }
    
    // Return the number of documents deleted
    return { deleted: deleted };
}
'''

    try:
        print(f'Creating bulk delete stored procedure...')
        container.scripts.create_stored_procedure(
            id='bulkDeleteSproc',
            body=sproc_body
        )
        print('Stored procedure created successfully.')
    except Exception as e:
        if 'Resource with specified id already exists' in str(e):
            print('Stored procedure already exists, replacing it...')
            container.scripts.replace_stored_procedure(
                id='bulkDeleteSproc',
                body=sproc_body
            )
            print('Stored procedure replaced successfully.')
        else:
            print(f'Error creating stored procedure: {str(e)}')
            exit(1)

# Create the sproc first
create_sproc()

# Run the cleanup
clean_container()
" || {
    echo -e "${RED}Error: Failed to run bulk delete script.${RESET}"
    echo "Make sure python3 and azure-cosmos are installed."
    echo "Run: pip install azure-cosmos pyyaml"
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
  # Get configuration
  CITIES_FILE="config/cities.txt"
  if [ ! -f "$CITIES_FILE" ]; then
    echo -e "${RED}Error: Cities file not found at $CITIES_FILE${RESET}"
    exit 1
  fi
  
  # Parse command line
  if [ "$1" == "--all" ]; then
    # Query all databases
    MAX_CITIES=5
    CITIES=$(head -n $MAX_CITIES "$CITIES_FILE")
    SENSORS_PER_CITY=5
    
    for CITY in $CITIES; do
      # Normalize city name
      NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:upper:]' '[:lower:]')
      
      # Check each sensor for this city
      for ((i=1; i<=$SENSORS_PER_CITY; i++)); do
        DB_PATH="./data/$NORMALIZED_CITY/$i/sensor_data.db"
        query_db "$DB_PATH" "$CITY" "$i"
      done
    done
  elif [ -n "$1" ] && [ -n "$2" ]; then
    # Query a specific database by city and sensor
    CITY="$1"
    SENSOR="$2"
    NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:lower:]')
    DB_PATH="./data/$NORMALIZED_CITY/$SENSOR/sensor_data.db"
    query_db "$DB_PATH" "$CITY" "$SENSOR"
  elif [ -n "$1" ]; then
    # Query all sensors for a specific city
    CITY="$1"
    SENSORS_PER_CITY=5
    NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:lower:]')
    
    for ((i=1; i<=$SENSORS_PER_CITY; i++)); do
      DB_PATH="./data/$NORMALIZED_CITY/$i/sensor_data.db"
      query_db "$DB_PATH" "$CITY" "$i"
    done
  else
    # Show usage
    echo "Usage: $0 query [--all | <city> [<sensor>]]"
    echo ""
    echo "Examples:"
    echo "  $0 query --all                  # Query all databases"
    echo "  $0 query Amsterdam              # Query all sensors for Amsterdam"
    echo "  $0 query Amsterdam 1            # Query Amsterdam sensor 1"
    echo ""
    echo "Available cities:"
    cat "$CITIES_FILE" | head -n 10 | while read -r city; do
      echo "  $city"
    done
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
  echo "Showing last 10 lines from each container..."
  echo ""
  
  for container in $(docker ps --filter "name=uploader" -q); do
    container_name=$(docker inspect --format='{{.Name}}' $container | sed 's/\///')
    echo -e "${YELLOW}=== $container_name ===${RESET}"
    docker logs $container --tail 20 | grep -i 'sensor' | tail -n 10
    echo ""
  done
  
  # Check SQLite databases
  echo -e "${CYAN}🧪 CHECKING SQLITE DATABASES:${RESET}"
  echo "Looking for databases in data directory..."
  echo ""
  
  find ./data -name "sensor_data.db" | while read db; do
    echo "Database: $db"
    # Check if file exists and has data
    if [ -f "$db" ]; then
      size=$(du -h "$db" | cut -f1)
      count=$(sqlite3 "$db" "SELECT COUNT(*) FROM sensor_readings 2>/dev/null" 2>/dev/null || echo "Error")
      echo "  - Size: $size"
      echo "  - Records: $count"
    else
      echo "  - Not found or empty"
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
  
  # Configuration
  MAX_CITIES=5
  SENSORS_PER_CITY=5
  CITIES_FILE="config/cities.txt"
  
  # Get the list of cities
  CITIES=$(head -n $MAX_CITIES "$CITIES_FILE" 2>/dev/null)
  if [ -z "$CITIES" ]; then
    echo -e "${RED}Error: Could not read cities from $CITIES_FILE${RESET}"
    exit 1
  fi
  
  # Print header
  # Only clear if not using watch (watch does its own clearing)
  if [ -z "$WATCH_EXEC" ]; then
    clear
  fi
  
  echo -e "${BOLD}SENSOR DATA MONITORING${RESET} - $(date)"
  echo -e "${CYAN}Checking data across all cities and sensors...${RESET}"
  echo
  
  # Print table header
  printf "${BOLD}%-15s %-15s %-10s %-10s %-25s %-8s${RESET}\n" "CITY" "SENSOR" "STATUS" "DB FILES" "LAST UPLOADED" "ARCHIVES"
  echo "------------------------------------------------------------------------------------------"
  
  # Counter for total stats
  TOTAL_SENSORS=0
  ACTIVE_SENSORS=0
  TOTAL_DB_FILES=0
  TOTAL_ARCHIVES=0
  
  # Process each city
  for CITY in $CITIES; do
    # Normalize city name
    NORMALIZED_CITY=$(echo "$CITY" | tr -d " " | tr -d "'" | tr -d "." | tr '[:upper:]' '[:lower:]')
    
    # Check each sensor for this city
    for ((i=1; i<=$SENSORS_PER_CITY; i++)); do
      # Create a unique sensor ID including the city code and sensor number
      CITY_CODE=$(echo "$NORMALIZED_CITY" | cut -c1-3 | tr '[:lower:]' '[:upper:]')
      SENSOR_ID="${CITY_CODE}_SENSOR$(printf "%03d" $i)"
      CONTAINER_NAME="sensor-${NORMALIZED_CITY}-${i}"
      
      # Check container status
      if is_container_running "$CONTAINER_NAME"; then
        STATUS="${GREEN}RUNNING${RESET}"
        ((ACTIVE_SENSORS++))
      else
        STATUS="${RED}STOPPED${RESET}"
      fi
      
      # Check database files
      DATA_DIR="./data/${NORMALIZED_CITY}/${i}"
      DB_COUNT=$(count_files "$DATA_DIR" "*.db")
      ((TOTAL_DB_FILES += DB_COUNT))
      
      # Check archive files for this sensor
      ARCHIVE_DIR="./archive/${NORMALIZED_CITY}"
      ARCHIVE_COUNT=$(count_files "$ARCHIVE_DIR" "*${SENSOR_ID}*.parquet")
      ((TOTAL_ARCHIVES += ARCHIVE_COUNT))
      
      # Get last archive file
      LAST_ARCHIVE=$(latest_file "$ARCHIVE_DIR" "*${SENSOR_ID}*.parquet")
      if [ "$LAST_ARCHIVE" != "none" ]; then
        LAST_UPLOAD_TIME=$(get_file_time "$LAST_ARCHIVE")
        # Truncate time if too long
        LAST_UPLOAD_TIME=$(echo "$LAST_UPLOAD_TIME" | cut -c 1-24)
      else
        LAST_UPLOAD_TIME="No archives yet"
      fi
      
      # Print row
      printf "%-15s ${YELLOW}%-15s${RESET} %-10s %-10s %-25s %-8s\n" \
        "$CITY" "$SENSOR_ID" "$STATUS" "$DB_COUNT" "$LAST_UPLOAD_TIME" "$ARCHIVE_COUNT"
      
      ((TOTAL_SENSORS++))
    done
    
    # Check uploader status
    UPLOADER_NAME="uploader-${NORMALIZED_CITY}"
    if is_container_running "$UPLOADER_NAME"; then
      UPLOADER_STATUS="${GREEN}RUNNING${RESET}"
    else
      UPLOADER_STATUS="${RED}STOPPED${RESET}"
    fi
    
    # Print uploader row with different formatting
    printf "${BLUE}%-15s %-15s${RESET} %-10s %-10s %-25s %-8s\n" \
      "$CITY" "UPLOADER" "$UPLOADER_STATUS" "-" "-" "-"
    
    # Add separator between cities
    echo "------------------------------------------------------------------------------------------"
  done
  
  # Print summary
  echo ""
  echo -e "${BOLD}SUMMARY:${RESET}"
  echo -e "Total Sensors: $TOTAL_SENSORS ($ACTIVE_SENSORS active)"
  echo -e "Total Database Files: $TOTAL_DB_FILES"
  echo -e "Total Archive Files: $TOTAL_ARCHIVES"
  echo ""
  echo -e "${CYAN}TIP:${RESET} Run with 'watch' for real-time updates: ${BOLD}watch -n 5 $0 monitor${RESET}"
}

###########################################
# COMMAND: RESET - Reset services with fixed config
###########################################

function reset_services() {
  echo "Resetting services with fixed configuration..."
  
  # Step 1: Stop all services
  echo "Step 1: Stopping all services..."
  stop_sensors --no-prompt
  
  # Step 2: Ensure Dockerfile has the proper entrypoint wrapper
  echo "Step 2: Ensuring Dockerfile has the proper entrypoint wrapper..."
  fix_dockerfile
  
  # Step 3: Rebuild the image
  echo "Step 3: Rebuilding the Docker image with fixed entrypoint..."
  build_uploader --no-tag
  
  # Step 4: Regenerate the Docker Compose file
  echo "Step 4: Recreating Docker Compose file with fixed format..."
  chmod +x ./generate-multi-sensor-compose.sh
  ./generate-multi-sensor-compose.sh
  
  # Step 5: Start all services
  echo "Step 5: Starting all services with fixed configuration..."
  docker-compose up -d
  
  echo "Services reset complete. Check their status with:"
  echo "docker-compose ps"
  
  # Step 6: Run diagnostics if requested
  if [ "$1" != "--no-diagnostics" ]; then
    echo "Step 6: Running diagnostics..."
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
  echo "  start [--no-rebuild] [--project-name NAME] [--no-diagnostics]"
  echo "      Starts sensor simulation with configuration"
  echo ""
  echo "  stop [--no-prompt]"
  echo "      Stops all running containers"
  echo ""
  echo "  reset [--no-diagnostics]"
  echo "      Resets services with fixed configuration (stops, regenerates config, starts)"
  echo ""
  echo "  clean [--dry-run] [--yes] [--config PATH]"
  echo "      Deletes all data from Cosmos DB"
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
  echo "  $0 start                           # Start with default configuration"
  echo "  SENSORS_PER_CITY=10 $0 start       # Start with 10 sensors per city"
  echo "  $0 monitor --plain                 # Monitor without colors"
  echo "  $0 clean --dry-run                 # Show what would be deleted, without deleting"
  echo "  $0 query Amsterdam 1               # Check SQLite database for Amsterdam sensor 1"
  echo "  $0 build --tag v1.0.0              # Build with a specific tag"
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