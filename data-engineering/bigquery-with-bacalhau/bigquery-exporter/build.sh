#!/bin/bash

# Build script for bigquery-uploader Docker image

set -e

# Configuration
IMAGE_NAME="${IMAGE_NAME:-bigquery-uploader}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to read value from config.yaml using yq
read_config_value() {
    local key="$1"
    local config_file="${CONFIG_FILE:-../demo-network/files/config.yaml}"

    if ! command -v yq >/dev/null 2>&1; then
        echo "[ERROR] yq is required but not installed. Please install yq (https://mikefarah.gitbook.io/yq/) and try again."
        exit 1
    fi

    if [[ -f "$config_file" ]]; then
        yq -r ".\"$key\"" "$config_file"
    fi
}

# Function to test Docker connectivity
test_docker_connectivity() {
    print_info "Testing Docker daemon connectivity..."
    if ! docker version >/dev/null 2>&1; then
        print_error "Cannot connect to Docker daemon. Is Docker running?"
        return 1
    fi

    # Test pulling a small image
    print_info "Testing Docker Hub connectivity..."
    if ! docker pull hello-world:latest >/dev/null 2>&1; then
        print_warning "Cannot pull from Docker Hub. Trying alternative registry..."
        # You might want to configure a mirror here
        return 1
    fi

    return 0
}

# Parse command line arguments
CONFIG_FILE=""
SKIP_CONNECTIVITY_CHECK="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --platform)
            PLATFORM="--platform $2"
            shift 2
            ;;
        --push)
            PUSH_IMAGE="true"
            shift
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --skip-connectivity-check)
            SKIP_CONNECTIVITY_CHECK="true"
            shift
            ;;
        --simple)
            USE_SIMPLE_DOCKERFILE="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --name NAME        Docker image name (default: bigquery-uploader)"
            echo "  --tag TAG          Docker image tag (default: latest)"
            echo "  --registry REGISTRY Registry URL (e.g., docker.io/username)"
            echo "  --no-cache         Build without using cache"
            echo "  --platform PLATFORM Build for specific platform (e.g., linux/amd64)"
            echo "  --push             Push image to registry after building"
            echo "  --config FILE      Path to config.yaml to read settings from"
            echo "  --skip-connectivity-check Skip Docker connectivity test"
            echo "  --simple           Use simple Dockerfile (better for connectivity issues)"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Set default config file if not specified
if [[ -z "$CONFIG_FILE" ]]; then
    if [[ -f "../demo-network/files/config.yaml" ]]; then
        CONFIG_FILE="../demo-network/files/config.yaml"
    elif [[ -f "config.yaml" ]]; then
        CONFIG_FILE="config.yaml"
    fi
fi

# Read values from config.yaml if available
if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
    print_info "Reading configuration from: $CONFIG_FILE"

    # Read project_id and use it in image tag if not specified
    PROJECT_ID=$(read_config_value "project_id")
    if [[ -n "$PROJECT_ID" && "$IMAGE_TAG" == "latest" ]]; then
        IMAGE_TAG="${PROJECT_ID}-latest"
        print_info "Using project-specific tag: $IMAGE_TAG"
    fi

    # Display some key configuration values
    DATASET=$(read_config_value "dataset")
    NODE_ID=$(read_config_value "node_id")
    PIPELINE_MODE=$(read_config_value "pipeline_mode")

    if [[ -n "$PIPELINE_MODE" ]]; then
        print_info "Pipeline mode: $PIPELINE_MODE"
    fi
    if [[ -n "$NODE_ID" ]]; then
        print_info "Node ID: $NODE_ID"
    fi
fi

# Construct full image name
if [[ -n "$REGISTRY" ]]; then
    FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
fi

# Test Docker connectivity unless skipped
if [[ "$SKIP_CONNECTIVITY_CHECK" != "true" ]]; then
    if ! test_docker_connectivity; then
        print_warning "Docker connectivity issues detected"
        print_info "You can skip this check with --skip-connectivity-check"
        print_info "If you're behind a proxy, configure Docker to use it"
        echo ""
    fi
fi

# Check if required files exist
print_info "Checking required files..."

if [[ ! -f "Dockerfile" ]]; then
    print_error "Dockerfile not found in current directory"
    exit 1
fi

if [[ ! -f "bigquery_uploader.py" ]]; then
    print_error "bigquery_uploader.py not found in current directory"
    exit 1
fi

if [[ ! -f "requirements.txt" ]]; then
    print_error "requirements.txt not found in current directory"
    exit 1
fi

print_info "All required files found"

# Fix potential Docker connectivity issues
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Choose Dockerfile based on options
if [[ "$USE_SIMPLE_DOCKERFILE" == "true" ]]; then
    DOCKERFILE="Dockerfile.simple"
    print_info "Using simple Dockerfile for better compatibility"
else
    DOCKERFILE="Dockerfile"
fi

# Build the Docker image
print_info "Building Docker image: ${FULL_IMAGE_NAME}"
print_info "Build options: ${NO_CACHE} ${PLATFORM}"
print_info "Using Dockerfile: ${DOCKERFILE}"

# Add build arguments from config if available
BUILD_ARGS=""
if [[ -n "$PROJECT_ID" ]]; then
    BUILD_ARGS="$BUILD_ARGS --build-arg PROJECT_ID=$PROJECT_ID"
fi
if [[ -n "$DATASET" ]]; then
    BUILD_ARGS="$BUILD_ARGS --build-arg DATASET=$DATASET"
fi

docker build \
    ${NO_CACHE} \
    ${PLATFORM} \
    ${BUILD_ARGS} \
    --pull \
    -t "${FULL_IMAGE_NAME}" \
    -f "${DOCKERFILE}" \
    . 2>&1 | tee build.log

if [[ $? -eq 0 ]]; then
    print_info "Docker image built successfully: ${FULL_IMAGE_NAME}"

    # Show image details
    echo ""
    print_info "Image details:"
    docker images "${FULL_IMAGE_NAME}"

    # Push image if requested
    if [[ "$PUSH_IMAGE" == "true" ]]; then
        if [[ -z "$REGISTRY" ]]; then
            print_error "Registry must be specified to push image"
            exit 1
        fi
        print_info "Pushing image to registry..."
        docker push "${FULL_IMAGE_NAME}"
        if [[ $? -eq 0 ]]; then
            print_info "Image pushed successfully"
        else
            print_error "Failed to push image"
            exit 1
        fi
    fi

    echo ""
    print_info "To run the container:"
    echo "docker run \\"
    echo "  -e CONFIG_FILE=/app/config.yaml \\"

    # Add config-specific environment variables if available
    if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
        CREDENTIALS_PATH=$(read_config_value "credentials_path")
        if [[ -n "$CREDENTIALS_PATH" ]]; then
            echo "  -e GOOGLE_APPLICATION_CREDENTIALS=$CREDENTIALS_PATH \\"
        else
            echo "  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \\"
        fi

        if [[ -n "$PROJECT_ID" ]]; then
            echo "  -e PROJECT_ID=$PROJECT_ID \\"
        fi

        echo "  -v $CONFIG_FILE:/app/config.yaml:ro \\"
    else
        echo "  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \\"
        echo "  -e PROJECT_ID=your-project-id \\"
        echo "  -v /path/to/config.yaml:/app/config.yaml:ro \\"
    fi

    echo "  -v /path/to/credentials.json:/app/credentials.json:ro \\"
    echo "  -v /path/to/logs:/bacalhau_data:ro \\"
    echo "  ${FULL_IMAGE_NAME}"

    # Add example with actual paths from config
    if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
        echo ""
        print_info "Example with your config:"
        echo "docker run \\"
        echo "  -e CONFIG_FILE=/app/config.yaml \\"
        if [[ -n "$CREDENTIALS_PATH" ]]; then
            echo "  -e GOOGLE_APPLICATION_CREDENTIALS=$CREDENTIALS_PATH \\"
        fi
        if [[ -n "$PROJECT_ID" ]]; then
            echo "  -e PROJECT_ID=$PROJECT_ID \\"
        fi
        echo "  -v $(realpath $CONFIG_FILE):/app/config.yaml:ro \\"
        echo "  -v /path/to/your/credentials.json:$CREDENTIALS_PATH:ro \\"

        # Extract input paths
        INPUT_PATH=$(grep -A1 "input_paths:" "$CONFIG_FILE" | tail -1 | sed 's/.*- //' | tr -d '"')
        if [[ -n "$INPUT_PATH" ]]; then
            LOG_DIR=$(dirname "$INPUT_PATH")
            echo "  -v /path/to/your/logs:$LOG_DIR:ro \\"
        fi

        echo "  ${FULL_IMAGE_NAME}"
    fi
else
    print_error "Docker build failed"

    # Check for common error patterns
    if grep -q "failed to resolve source metadata" build.log 2>/dev/null; then
        print_error "Network connectivity issue detected"
        echo ""
        print_info "Try these solutions:"
        echo "1. Use simple Dockerfile: $0 --simple"
        echo "2. Check Docker proxy settings"
        echo "3. Restart Docker daemon"
        echo "4. Try: docker pull python:3.11-slim"
    elif grep -q "no space left on device" build.log 2>/dev/null; then
        print_error "Insufficient disk space"
        echo ""
        print_info "Free up disk space:"
        echo "1. Remove unused Docker images: docker image prune -a"
        echo "2. Remove unused containers: docker container prune"
        echo "3. Check disk usage: df -h"
    fi

    # General troubleshooting tips
    echo ""
    print_info "General troubleshooting tips:"
    echo "1. Check Docker daemon is running: docker version"
    echo "2. Try simple Dockerfile: $0 --simple"
    echo "3. Try pulling base image manually: docker pull python:3.11-slim"
    echo "4. Check for proxy settings if behind corporate firewall"
    echo "5. Try building with --no-cache option"
    echo "6. Check build log: cat build.log"

    exit 1
fi
