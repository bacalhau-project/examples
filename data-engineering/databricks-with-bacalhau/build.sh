#!/bin/bash
# Build script for Databricks-Bacalhau pipeline components

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[BUILD]${NC} $1"
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

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Default registry (can be overridden by environment variable)
REGISTRY="${DOCKER_REGISTRY:-ghcr.io}"
REGISTRY_PREFIX="${DOCKER_REGISTRY_PREFIX:-bacalhau-project}"

# Parse command line arguments
COMPONENT=""
VERSION=""
NO_CACHE=""
PUSH="true"  # Always push by default
AUTO_VERSION="true"

# Check if first argument is a component name (for backwards compatibility)
if [[ $# -gt 0 ]] && [[ "$1" != "--"* ]]; then
    COMPONENT="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --component)
            COMPONENT="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            AUTO_VERSION="false"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --push)
            PUSH="true"
            shift
            ;;
        --no-push)
            PUSH="false"
            shift
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --registry-prefix)
            REGISTRY_PREFIX="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [COMPONENT] [OPTIONS]"
            echo "       $0 --component COMPONENT [OPTIONS]"
            echo ""
            echo "Components:"
            echo "  databricks-uploader   Build the databricks-uploader image"
            echo "  pipeline-manager      Build the pipeline-manager image"
            echo "  all                   Build all images (default)"
            echo ""
            echo "Options:"
            echo "  --version VERSION     Docker image version tag \
(default: auto-increment)"
            echo "  --no-cache           Build without Docker cache"
            echo "  --no-push            Don't push to registry (default: push)"
            echo "  --registry REGISTRY   Docker registry \
(default: ghcr.io)"
            echo "  --registry-prefix PREFIX  Registry prefix \
(default: bacalhau-project)"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Build and push all"
            echo "  $0 databricks-uploader          # Build and push uploader"
            echo "  $0 all --no-push                # Build without pushing"
            echo "  $0 databricks-uploader --version v2.0.0  # Specific version"
            echo ""
            echo "Default Behavior:"
            echo "  - Auto-increments minor version (v1.0.0 -> v1.1.0)"
            echo "  - Pushes to ghcr.io/bacalhau-project by default"
            echo "  - Use --no-push to build locally only"
            echo ""
            echo "Environment Variables:"
            echo "  DOCKER_REGISTRY        Override registry (default: ghcr.io)"
            echo "  DOCKER_REGISTRY_PREFIX Override prefix \
(default: bacalhau-project)"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Default to building all if no component specified
if [ -z "$COMPONENT" ]; then
    COMPONENT="all"
fi

# Function to get next version
get_next_version() {
    local image_name=$1
    local full_name="$image_name"
    
    if [ -n "$REGISTRY" ]; then
        if [ -n "$REGISTRY_PREFIX" ]; then
            full_name="${REGISTRY}/${REGISTRY_PREFIX}/${image_name}"
        else
            full_name="${REGISTRY}/${image_name}"
        fi
    fi
    
    # Get latest version from registry
    local latest_tag=$(docker images --format "{{.Tag}}" "$full_name" | \
        grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | \
        sort -V | tail -1)
    
    if [ -z "$latest_tag" ]; then
        # No version found, start with v1.0.0
        echo "v1.0.0"
    else
        # Parse version and increment minor
        local version="${latest_tag#v}"
        local major=$(echo "$version" | cut -d. -f1)
        local minor=$(echo "$version" | cut -d. -f2)
        local patch=$(echo "$version" | cut -d. -f3)
        
        # Increment minor version
        minor=$((minor + 1))
        echo "v${major}.${minor}.0"
    fi
}

# Auto-determine version if not specified
if [ "$AUTO_VERSION" == "true" ] && [ -z "$VERSION" ]; then
    print_info "Auto-determining version..."
    # We'll determine version per component in the build functions
    VERSION="auto"
fi

# Function to build Docker image
build_image() {
    local name=$1
    local context=$2
    local dockerfile=$3
    
    # Determine version if auto
    local build_version="$VERSION"
    if [ "$VERSION" == "auto" ]; then
        build_version=$(get_next_version "$name")
        print_info "Using version: $build_version"
    elif [ -z "$build_version" ]; then
        build_version="latest"
    fi
    
    # Determine full image name with registry
    local full_name="$name"
    if [ -n "$REGISTRY" ]; then
        if [ -n "$REGISTRY_PREFIX" ]; then
            full_name="${REGISTRY}/${REGISTRY_PREFIX}/${name}"
        else
            full_name="${REGISTRY}/${name}"
        fi
    elif [ -n "$REGISTRY_PREFIX" ]; then
        full_name="${REGISTRY_PREFIX}/${name}"
    fi
    
    print_status "Building $full_name:$build_version..."
    
    if [ ! -f "$dockerfile" ]; then
        print_error "Dockerfile not found: $dockerfile"
        return 1
    fi
    
    # Build with both local and registry tags
    local build_args=""
    if [ "$build_version" != "latest" ]; then
        build_args="-t $name:$build_version -t $full_name:$build_version"
    fi
    
    docker build $NO_CACHE \
        -t "$name:latest" \
        -t "$full_name:latest" \
        $build_args \
        -f "$dockerfile" \
        "$context"
    
    if [ $? -eq 0 ]; then
        print_status "Successfully built $name:$build_version"
        
        if [ "$PUSH" == "true" ]; then
            if [ "$full_name" != "$name" ]; then
                print_status "Pushing $full_name to registry..."
                docker push "$full_name:latest"
                if [ "$build_version" != "latest" ]; then
                    docker push "$full_name:$build_version"
                fi
                print_success "Pushed to registry: $full_name:$build_version"
            else
                print_warning "No registry configured for push"
                print_info "Using default: ghcr.io/bacalhau-project"
            fi
        else
            print_info "Skipping push (use --push to enable)"
        fi
        
        # Show how to test the built image
        echo ""
        print_success "Build complete! To test the image, run:"
        echo ""
        if [ "$name" == "databricks-uploader" ]; then
            echo -e "${GREEN}# Run databricks-uploader locally:${NC}"
            echo "docker run --rm \\"
            echo "  --name databricks-uploader-test \\"
            echo "  -v \$(pwd)/databricks-s3-uploader-config.yaml:/app/config.yaml:ro \\"
            echo "  -v \$(pwd)/sample-sensor/data/sensor_data.db:/app/sensor_data.db:ro \\"
            echo "  -v \$(pwd)/credentials:/bacalhau_data/credentials:ro \\"
            echo "  -v \$(pwd)/databricks-uploader/state:/app/state \\"
            echo "  -v \$(pwd)/logs:/app/logs \\"
            echo "  -e AWS_ACCESS_KEY_ID=\${AWS_ACCESS_KEY_ID} \\"
            echo "  -e AWS_SECRET_ACCESS_KEY=\${AWS_SECRET_ACCESS_KEY} \\"
            echo "  -e AWS_REGION=\${AWS_REGION:-us-west-2} \\"
            echo "  $full_name:$build_version"
            echo ""
            echo -e "${GREEN}# Or run interactively with bash:${NC}"
            echo "docker run --rm -it \\"
            echo "  --name databricks-uploader-debug \\"
            echo "  -v \$(pwd)/databricks-s3-uploader-config.yaml:/app/config.yaml:ro \\"
            echo "  -v \$(pwd)/sample-sensor/data/sensor_data.db:/app/sensor_data.db:ro \\"
            echo "  -v \$(pwd)/credentials:/bacalhau_data/credentials:ro \\"
            echo "  -v \$(pwd)/databricks-uploader/state:/app/state \\"
            echo "  -v \$(pwd)/logs:/app/logs \\"
            echo "  -e AWS_ACCESS_KEY_ID=\${AWS_ACCESS_KEY_ID} \\"
            echo "  -e AWS_SECRET_ACCESS_KEY=\${AWS_SECRET_ACCESS_KEY} \\"
            echo "  -e AWS_REGION=\${AWS_REGION:-us-west-2} \\"
            echo "  --entrypoint /bin/bash \\"
            echo "  $full_name:$build_version"
            echo ""
            echo -e "${GREEN}# Or run with docker-compose:${NC}"
            echo "./docker-run-helper.sh start-all"
        elif [ "$name" == "pipeline-manager" ]; then
            echo -e "${GREEN}# Pipeline-manager is a CLI tool for managing pipeline state${NC}"
            echo -e "${YELLOW}# IMPORTANT: Must share state directory with databricks-uploader${NC}"
            echo ""
            echo -e "${GREEN}# Get current pipeline configuration:${NC}"
            echo "docker run --rm \\"
            echo "  -v \$(pwd)/databricks-uploader/state:/state \\"
            echo "  $full_name:$build_version \\"
            echo "  --db /state/pipeline_config.db get"
            echo ""
            echo -e "${GREEN}# Set pipeline type (raw/schematized/filtered/aggregated):${NC}"
            echo "docker run --rm \\"
            echo "  -v \$(pwd)/databricks-uploader/state:/state \\"
            echo "  $full_name:$build_version \\"
            echo "  --db /state/pipeline_config.db set schematized"
            echo ""
            echo -e "${GREEN}# Show pipeline history:${NC}"
            echo "docker run --rm \\"
            echo "  -v \$(pwd)/databricks-uploader/state:/state \\"
            echo "  $full_name:$build_version \\"
            echo "  --db /state/pipeline_config.db history"
            echo ""
            echo -e "${GREEN}# Monitor pipeline changes:${NC}"
            echo "docker run --rm \\"
            echo "  -v \$(pwd)/databricks-uploader/state:/state \\"
            echo "  $full_name:$build_version \\"
            echo "  --db /state/pipeline_config.db monitor"
        fi
        echo ""
    else
        print_error "Failed to build $name"
        return 1
    fi
}

# Build databricks-uploader
build_databricks_uploader() {
    print_status "Building databricks-uploader component..."
    build_image "databricks-uploader" \
        "./databricks-uploader" \
        "./databricks-uploader/Dockerfile"
}

# Build pipeline-manager
build_pipeline_manager() {
    print_status "Building pipeline-manager component..."
    
    # Check if Dockerfile exists, if not create a basic one
    if [ ! -f "./pipeline-manager/Dockerfile" ]; then
        print_warning "Creating Dockerfile for pipeline-manager..."
        cat > "./pipeline-manager/Dockerfile" << 'DOCKERFILE'
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy application files
COPY . .

# Install Python dependencies
RUN uv venv && uv pip install -r requirements.txt || true

# Run the pipeline controller
CMD ["uv", "run", "pipeline_controller.py"]
DOCKERFILE
    fi
    
    build_image "pipeline-manager" \
        "./pipeline-manager" \
        "./pipeline-manager/Dockerfile"
}

# Main build logic
case $COMPONENT in
    databricks-uploader)
        build_databricks_uploader
        ;;
    pipeline-manager)
        build_pipeline_manager
        ;;
    all)
        print_status "Building all components..."
        build_databricks_uploader
        build_pipeline_manager
        print_status "All components built successfully!"
        ;;
    *)
        print_error "Unknown component: $COMPONENT"
        print_error "Valid components: databricks-uploader, pipeline-manager, all"
        exit 1
        ;;
esac

# Show built images
print_status "Docker images built:"
docker images | grep -E "(databricks-uploader|pipeline-manager)" | \
    grep -E "(latest|$VERSION)"