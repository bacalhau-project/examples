#!/bin/bash
# Run script for Databricks-Bacalhau pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[RUN]${NC} $1"
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

# Default values
MODE="local"
COMPONENT=""
ENV_FILE=".env"
DETACH=""
FOLLOW_LOGS=""
PULL_LATEST="true"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --component)
            COMPONENT="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --detach|-d)
            DETACH="-d"
            shift
            ;;
        --follow-logs|-f)
            FOLLOW_LOGS="true"
            shift
            ;;
        --no-pull)
            PULL_LATEST="false"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --mode MODE         Run mode: local, docker, bacalhau \
(default: local)"
            echo "  --component NAME    Component to run: uploader, \
pipeline-manager, sensor, all"
            echo "  --env-file FILE     Environment file (default: .env)"
            echo "  --detach, -d        Run in detached mode (Docker only)"
            echo "  --follow-logs, -f   Follow logs after starting"
            echo "  --no-pull           Don't pull latest images (Docker mode)"
            echo "  --help              Show this help message"
            echo ""
            echo "Note: Docker mode always pulls latest images unless --no-pull is used"
            echo ""
            echo "Examples:"
            echo "  # Run sensor locally to generate data:"
            echo "  $0 --mode local --component sensor"
            echo ""
            echo "  # Run uploader locally (reads from sensor DB):"
            echo "  $0 --mode local --component uploader"
            echo ""
            echo "  # Check/change pipeline configuration locally:"
            echo "  $0 --mode local --component pipeline-manager"
            echo ""
            echo "  # Run everything in Docker:"
            echo "  $0 --mode docker --component all -d"
            echo ""
            echo "  # Run uploader on Bacalhau:"
            echo "  $0 --mode bacalhau --component uploader"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    print_error "Environment file not found: $ENV_FILE"
    print_info "Copy .env.example to .env and configure it"
    exit 1
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

# Function to run uploader locally
run_uploader_local() {
    print_status "Running databricks-uploader locally..."
    
    # Check for required files
    if [ ! -f "databricks-s3-uploader-config.yaml" ]; then
        print_error "Config file not found: databricks-s3-uploader-config.yaml"
        exit 1
    fi
    
    if [ ! -f "sample-sensor/data/sensor_data.db" ]; then
        print_warning "Sensor database not found. Run sensor first:"
        print_info "./run.sh --mode local --component sensor"
        exit 1
    fi
    
    # Source AWS credentials if available
    if [ -f "credentials/expanso-s3-env.sh" ]; then
        print_info "Loading AWS credentials from credentials/expanso-s3-env.sh"
        source credentials/expanso-s3-env.sh
    elif [ -f "credentials/expanso-s3-credentials" ]; then
        print_info "Loading AWS credentials from credentials/expanso-s3-credentials"
        source credentials/expanso-s3-credentials
    else
        print_warning "No credentials file found in credentials/"
        print_info "Expecting AWS credentials in environment variables"
    fi
    
    # Check if AWS credentials are set
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        print_error "AWS credentials not found!"
        print_info "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        print_info "Or create credentials/expanso-s3-env.sh with:"
        echo "  export AWS_ACCESS_KEY_ID=your-key-id"
        echo "  export AWS_SECRET_ACCESS_KEY=your-secret-key"
        echo "  export AWS_REGION=us-west-2"
        exit 1
    fi
    
    print_info "Using config: databricks-s3-uploader-config.yaml"
    print_info "Using database: sample-sensor/data/sensor_data.db"
    print_info "State directory: databricks-uploader/state"
    print_info "AWS Region: ${AWS_REGION:-us-west-2}"
    
    # Create a temporary config file with local paths
    print_info "Creating local config with correct paths..."
    TEMP_CONFIG="/tmp/databricks-uploader-local-$$.yaml"
    sed 's|/app/sensor_data.db|../sample-sensor/data/sensor_data.db|g' \
        databricks-s3-uploader-config.yaml > "$TEMP_CONFIG"
    
    print_status "Starting uploader..."
    cd databricks-uploader
    AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    AWS_REGION="${AWS_REGION:-us-west-2}" \
    uv run -s sqlite_to_databricks_uploader.py \
        --config "$TEMP_CONFIG"
    
    # Clean up temp config on exit
    trap "rm -f $TEMP_CONFIG" EXIT
}

# Function to run uploader in Docker
run_uploader_docker() {
    print_status "Running databricks-uploader in Docker..."
    
    # Pull latest image if enabled
    if [ "$PULL_LATEST" == "true" ]; then
        print_info "Pulling latest databricks-uploader image..."
        docker pull ghcr.io/bacalhau-project/databricks-uploader:latest || {
            print_warning "Could not pull from registry, using local image..."
            if ! docker images | grep -q "databricks-uploader"; then
                print_warning "Image not found locally, building..."
                ./build.sh databricks-uploader
            fi
        }
    else
        print_info "Using local databricks-uploader image (pull disabled)"
    fi
    
    # Stop existing container if running
    docker stop databricks-uploader 2>/dev/null || true
    docker rm databricks-uploader 2>/dev/null || true
    
    print_status "Starting databricks-uploader container..."
    docker run $DETACH \
        --name databricks-uploader \
        -v "$(pwd)/databricks-s3-uploader-config.yaml:/app/config.yaml:ro" \
        -v "$(pwd)/sample-sensor/data/sensor_data.db:/app/sensor_data.db:ro" \
        -v "$(pwd)/credentials:/bacalhau_data/credentials:ro" \
        -v "$(pwd)/databricks-uploader/state:/app/state" \
        -v "$(pwd)/logs:/app/logs" \
        -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
        -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
        -e AWS_REGION="${AWS_REGION:-us-west-2}" \
        ghcr.io/bacalhau-project/databricks-uploader:latest
    
    if [ "$FOLLOW_LOGS" == "true" ] && [ -n "$DETACH" ]; then
        docker logs -f databricks-uploader
    fi
}

# Function to run uploader on Bacalhau
run_uploader_bacalhau() {
    print_status "Submitting databricks-uploader job to Bacalhau..."
    
    # Check if job spec exists
    if [ ! -f "jobs/databricks-uploader-job.yaml" ]; then
        print_error "Bacalhau job spec not found: \
jobs/databricks-uploader-job.yaml"
        exit 1
    fi
    
    # Submit job
    bacalhau job run jobs/databricks-uploader-job.yaml
}

# Function to run pipeline manager locally
run_pipeline_manager_local() {
    print_status "Pipeline-manager is a CLI tool..."
    
    # Ensure state directory exists
    mkdir -p databricks-uploader/state
    
    DB_PATH="databricks-uploader/state/pipeline_config.db"
    
    # Show current configuration
    print_info "Current pipeline configuration:"
    cd pipeline-manager
    uv run -s pipeline_controller.py --db "../$DB_PATH" get
    
    echo ""
    print_info "Available commands:"
    echo "  Get current:  cd pipeline-manager && uv run -s pipeline_controller.py \\"
    echo "                --db ../$DB_PATH get"
    echo ""
    echo "  Set type:     cd pipeline-manager && uv run -s pipeline_controller.py \\"
    echo "                --db ../$DB_PATH set <type>"
    echo ""
    echo "  Show history: cd pipeline-manager && uv run -s pipeline_controller.py \\"
    echo "                --db ../$DB_PATH history"
    echo ""
    echo "  Monitor:      cd pipeline-manager && uv run -s pipeline_controller.py \\"
    echo "                --db ../$DB_PATH monitor"
    echo ""
    echo "Pipeline types: raw, schematized, aggregated, emergency, regional"
}

# Function to run pipeline manager in Docker
run_pipeline_manager_docker() {
    print_status "Pipeline-manager is a CLI tool, not a service..."
    
    # Pull latest image if enabled
    if [ "$PULL_LATEST" == "true" ]; then
        print_info "Pulling latest pipeline-manager image..."
        docker pull ghcr.io/bacalhau-project/pipeline-manager:latest || {
            print_warning "Could not pull from registry, using local image..."
            if ! docker images | grep -q "pipeline-manager"; then
                print_warning "Image not found locally, building..."
                ./build.sh pipeline-manager
            fi
        }
    else
        print_info "Using local pipeline-manager image (pull disabled)"
    fi
    
    print_info "Showing current pipeline configuration:"
    docker run --rm \
        -v "$(pwd)/databricks-uploader/state:/state" \
        ghcr.io/bacalhau-project/pipeline-manager:latest \
        --db /state/pipeline_config.db get
    
    echo ""
    print_info "To change pipeline type, run:"
    echo "docker run --rm \\"
    echo "  -v \$(pwd)/databricks-uploader/state:/state \\"
    echo "  ghcr.io/bacalhau-project/pipeline-manager:latest \\"
    echo "  --db /state/pipeline_config.db set <type>"
    echo ""
    echo "Available types: raw, schematized, aggregated, emergency, regional"
}

# Function to run sensor simulator
run_sensor() {
    print_status "Running sensor simulator..."
    
    # Always cleanup existing sensor container first
    if docker ps -a | grep -q sensor-log-generator; then
        print_warning "Cleaning up existing sensor container..."
        docker stop sensor-log-generator 2>/dev/null || true
        docker rm sensor-log-generator 2>/dev/null || true
    fi
    
    if [ "$MODE" == "local" ]; then
        ./scripts/start-sensor-local.sh
    else
        # Pull latest sensor image if enabled
        if [ "$PULL_LATEST" == "true" ]; then
            print_info "Pulling latest sensor-log-generator image..."
            docker pull ghcr.io/bacalhau-project/sensor-log-generator:latest || {
                print_warning "Could not pull sensor image from registry"
            }
        fi
        ./scripts/start-sensor.sh
    fi
}

# Function to check dependencies
check_dependencies() {
    local deps_missing=false
    
    case $MODE in
        local)
            if ! command -v uv &> /dev/null; then
                print_error "uv is not installed"
                print_info "Install with: curl -LsSf \
https://astral.sh/uv/install.sh | sh"
                deps_missing=true
            fi
            ;;
        docker)
            if ! command -v docker &> /dev/null; then
                print_error "Docker is not installed"
                deps_missing=true
            fi
            ;;
        bacalhau)
            if ! command -v bacalhau &> /dev/null; then
                print_error "Bacalhau is not installed"
                print_info "Install from: https://docs.bacalhau.org/getting-started/installation"
                deps_missing=true
            fi
            ;;
    esac
    
    if [ "$deps_missing" == "true" ]; then
        exit 1
    fi
}

# Main execution
check_dependencies

case $COMPONENT in
    uploader)
        case $MODE in
            local)
                run_uploader_local
                ;;
            docker)
                run_uploader_docker
                ;;
            bacalhau)
                run_uploader_bacalhau
                ;;
            *)
                print_error "Unknown mode: $MODE"
                exit 1
                ;;
        esac
        ;;
    pipeline-manager)
        case $MODE in
            local)
                run_pipeline_manager_local
                ;;
            docker)
                run_pipeline_manager_docker
                ;;
            *)
                print_error "Pipeline manager only supports local and docker modes"
                exit 1
                ;;
        esac
        ;;
    sensor)
        run_sensor
        ;;
    all)
        if [ "$MODE" == "docker" ]; then
            print_status "Starting all components in Docker..."
            ./docker-run-helper.sh start-all
        else
            print_error "Mode 'all' only supported with --mode docker"
            exit 1
        fi
        ;;
    *)
        print_error "Unknown component: $COMPONENT"
        print_error "Valid components: uploader, pipeline-manager, sensor, all"
        exit 1
        ;;
esac