#!/bin/bash

# Script to manage the unified log processor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
CONFIG_FILE="${PROJECT_ROOT}/bigquery-exporter/config.yaml"
PROCESSOR_FILE="${PROJECT_ROOT}/bigquery-exporter/log_processor_unified.py"
JOB_YAML="${PROJECT_ROOT}/bigquery_export_unified.yaml"

function print_usage() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  run [mode]        - Run the processor with specified mode (raw/schematized/sanitized/aggregated)"
    echo "  update-config     - Update configuration interactively"
    echo "  deploy            - Deploy to Bacalhau"
    echo "  status [job-id]   - Check job status"
    echo "  logs [job-id]     - Get job logs"
    echo "  test              - Test locally with sample data"
    echo ""
    echo "Examples:"
    echo "  $0 run sanitized"
    echo "  $0 deploy"
    echo "  $0 status j-12345"
}

function update_config() {
    echo -e "${GREEN}Updating configuration...${NC}"
    
    # Read current config
    if [ -f "$CONFIG_FILE" ]; then
        current_mode=$(yq '.pipeline_mode' "$CONFIG_FILE")
        current_interval=$(yq '.check_interval' "$CONFIG_FILE")
        current_chunk=$(yq '.chunk_size' "$CONFIG_FILE")
        current_project=$(yq '.project_id' "$CONFIG_FILE")
        current_creds=$(yq '.credentials_path' "$CONFIG_FILE")
        current_inputs=$(yq '.input_paths[]' "$CONFIG_FILE" | tr '\n' ' ')
    else
        current_mode="raw"
        current_interval="30"
        current_chunk="500000"
        current_project="bq-2501151036"
        current_creds="/var/log/app/log_uploader_credentials.json"
        current_inputs="/var/log/app/access.log"
    fi
    
    # Get new values
    echo "Current pipeline mode: $current_mode"
    echo -n "New pipeline mode [raw/schematized/sanitized/aggregated] (press enter to keep current): "
    read new_mode
    new_mode=${new_mode:-$current_mode}
    
    echo "Current check interval: $current_interval seconds"
    echo -n "New check interval in seconds (press enter to keep current): "
    read new_interval
    new_interval=${new_interval:-$current_interval}
    
    echo "Current chunk size: $current_chunk"
    echo -n "New chunk size (press enter to keep current): "
    read new_chunk
    new_chunk=${new_chunk:-$current_chunk}
    
    echo "Current project ID: $current_project"
    echo -n "New project ID (press enter to keep current): "
    read new_project
    new_project=${new_project:-$current_project}
    
    echo "Current credentials path: $current_creds"
    echo -n "New credentials path (press enter to keep current): "
    read new_creds
    new_creds=${new_creds:-$current_creds}
    
    echo "Current input paths: $current_inputs"
    echo -n "New input paths (space-separated, press enter to keep current): "
    read new_inputs
    new_inputs=${new_inputs:-$current_inputs}
    
    # Update config as YAML
    cat > "$CONFIG_FILE" <<EOF
pipeline_mode: $new_mode
chunk_size: $new_chunk
max_retries: 20
base_retry_delay: 1
max_retry_delay: 60
check_interval: $new_interval
project_id: $new_project
dataset: ${DATASET:-log_analytics}
credentials_path: $new_creds
input_paths:
$(echo "$new_inputs" | tr ' ' '\n' | sed 's/^/  - /')
tables:
  raw: raw_logs
  schematized: log_results
  sanitized: log_results
  aggregated: log_aggregates
  emergency: emergency_logs
node_id: bacalhau-node
metadata:
  region: ${REGION:-us-central1}
  provider: gcp
  hostname: bacalhau-cluster
EOF
    
    echo -e "${GREEN}Configuration updated!${NC}"
    cat "$CONFIG_FILE"
}

function run_mode() {
    local mode=$1
    
    if [ -z "$mode" ]; then
        echo -e "${RED}Error: Mode not specified${NC}"
        echo "Usage: $0 run [raw|schematized|sanitized|aggregated]"
        exit 1
    fi
    
    # Update config with new mode
    yq eval ".pipeline_mode = \"$mode\"" -i "$CONFIG_FILE"
    
    echo -e "${GREEN}Running processor in $mode mode...${NC}"
    
    # Check environment
    if [ -z "$PROJECT_ID" ]; then
        echo -e "${RED}Error: PROJECT_ID not set${NC}"
        exit 1
    fi
    
    if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo -e "${RED}Error: GOOGLE_APPLICATION_CREDENTIALS not set${NC}"
        exit 1
    fi
    
    # Run processor
    CONFIG_PATH="$CONFIG_FILE" python "$PROCESSOR_FILE"
}

function deploy() {
    echo -e "${GREEN}Deploying to Bacalhau...${NC}"
    
    # Check if config exists
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}Config file not found, creating one...${NC}"
        update_config
    fi
    
    # First, upload the config file
    echo -e "${YELLOW}Uploading configuration file...${NC}"
    "$SCRIPT_DIR/upload_config.sh" "$CONFIG_FILE"
    
    # Wait a moment for the config to be available
    sleep 2
    
    # Base64 encode the Python script
    PYTHON_B64=$(base64 < "$PROCESSOR_FILE" | tr -d '\n')
    
    # Run Bacalhau job
    echo -e "${YELLOW}Running unified processor job...${NC}"
    bacalhau job run "$JOB_YAML" \
        --template-vars="python_file_b64=$PYTHON_B64"
}

function test_local() {
    echo -e "${GREEN}Testing locally...${NC}"
    
    # Create test data if it doesn't exist
    TEST_DIR="/tmp/test_logs"
    mkdir -p "$TEST_DIR"
    
    if [ ! -f "$TEST_DIR/test.log" ]; then
        echo "Creating test log data..."
        cat > "$TEST_DIR/test.log" <<'EOF'
192.168.1.100 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/start.html" "Mozilla/4.08 [en] (Win98; I ;Nav)"
10.0.0.1 - - [10/Oct/2000:13:55:37 -0700] "GET /index.html HTTP/1.1" 404 208 "-" "Mozilla/5.0"
172.16.0.5 - alice [10/Oct/2000:13:55:38 -0700] "POST /api/data HTTP/1.1" 500 1234 "http://app.example.com" "Chrome/91.0"
192.168.1.100 - frank [10/Oct/2000:13:56:36 -0700] "GET /images/logo.png HTTP/1.0" 304 0 "http://www.example.com/" "Mozilla/4.08 [en] (Win98; I ;Nav)"
EOF
    fi
    
    # Update config to use test directory
    CONFIG_COPY="/tmp/test_config.json"
    cp "$CONFIG_FILE" "$CONFIG_COPY"
    
    # Run with test data
    echo "Running processor with test data..."
    CONFIG_PATH="$CONFIG_COPY" python "$PROCESSOR_FILE" &
    PID=$!
    
    # Let it run for a bit
    sleep 10
    
    # Kill the processor
    kill $PID 2>/dev/null || true
    
    echo -e "${GREEN}Test completed!${NC}"
}

function check_status() {
    local job_id=$1
    
    if [ -z "$job_id" ]; then
        echo -e "${RED}Error: Job ID not specified${NC}"
        echo "Usage: $0 status <job-id>"
        exit 1
    fi
    
    bacalhau job describe "$job_id"
}

function get_logs() {
    local job_id=$1
    
    if [ -z "$job_id" ]; then
        echo -e "${RED}Error: Job ID not specified${NC}"
        echo "Usage: $0 logs <job-id>"
        exit 1
    fi
    
    bacalhau logs "$job_id"
}

# Main command processing
case "$1" in
    run)
        run_mode "$2"
        ;;
    update-config)
        update_config
        ;;
    deploy)
        deploy
        ;;
    status)
        check_status "$2"
        ;;
    logs)
        get_logs "$2"
        ;;
    test)
        test_local
        ;;
    *)
        print_usage
        exit 1
        ;;
esac