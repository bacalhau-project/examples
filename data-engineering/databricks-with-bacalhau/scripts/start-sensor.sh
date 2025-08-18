#!/usr/bin/env bash

# Simple sensor start script - no fancy features, just run the container

# Colors for output
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print Docker image version info
print_docker_version_info() {
    local image="$1"
    
    echo -e "${BLUE}[INFO]${NC} ===== Docker Image Version Info ====="
    
    # Get image digest and ID
    local image_id=$(docker images --no-trunc --quiet "$image" | head -1)
    local short_id=$(docker images --quiet "$image" | head -1)
    
    if [ -n "$image_id" ]; then
        echo -e "${BLUE}[INFO]${NC} Image ID: $short_id (full: ${image_id:7:19}...)"
        
        # Get image details
        local created=$(docker inspect "$image" --format='{{.Created}}' 2>/dev/null || echo "unknown")
        local digest=$(docker inspect "$image" --format='{{.RepoDigests}}' 2>/dev/null | grep -o 'sha256:[a-f0-9]*' | head -1 || echo "unknown")
        
        echo -e "${BLUE}[INFO]${NC} Created: $created"
        echo -e "${BLUE}[INFO]${NC} Digest: ${digest:-unknown}"
        
        # Try to get labels with version info
        local version=$(docker inspect "$image" --format='{{.Config.Labels.version}}' 2>/dev/null || echo "")
        local git_commit=$(docker inspect "$image" --format='{{.Config.Labels.git_commit}}' 2>/dev/null || echo "")
        local build_date=$(docker inspect "$image" --format='{{.Config.Labels.build_date}}' 2>/dev/null || echo "")
        
        [ -n "$version" ] && [ "$version" != "<no value>" ] && echo -e "${BLUE}[INFO]${NC} Version Label: $version"
        [ -n "$git_commit" ] && [ "$git_commit" != "<no value>" ] && echo -e "${BLUE}[INFO]${NC} Git Commit: $git_commit"
        [ -n "$build_date" ] && [ "$build_date" != "<no value>" ] && echo -e "${BLUE}[INFO]${NC} Build Date: $build_date"
    fi
    
    echo -e "${BLUE}[INFO]${NC} ======================================"
    echo ""
}

# Stop any existing sensor container
docker stop sensor-log-generator 2>/dev/null || true
docker rm sensor-log-generator 2>/dev/null || true

# Print version info for the image we're about to run
print_docker_version_info "ghcr.io/bacalhau-project/sensor-log-generator:latest"

# Print the Docker command for reference
echo "Docker command to run sensor:"
echo ""
echo "docker run --rm \\"
echo "  --name sensor-log-generator \\"
echo "  -v \"$(pwd)/sample-sensor/data\":/app/data \\"
echo "  -v \"$(pwd)/sample-sensor\":/app/config \\"
echo "  -e CONFIG_FILE=/app/config/sensor-config.yaml \\"
echo "  -e IDENTITY_FILE=/app/config/identity.json \\"
echo "  -p 8080:8080 \\"
echo "  ghcr.io/bacalhau-project/sensor-log-generator:latest"
echo ""

# Run the sensor container
docker run --rm \
  --name sensor-log-generator \
  -v "$(pwd)/sample-sensor/data":/app/data \
  -v "$(pwd)/sample-sensor":/app/config \
  -e CONFIG_FILE=/app/config/sensor-config.yaml \
  -e IDENTITY_FILE=/app/config/identity.json \
  -p 8080:8080 \
  ghcr.io/bacalhau-project/sensor-log-generator:latest