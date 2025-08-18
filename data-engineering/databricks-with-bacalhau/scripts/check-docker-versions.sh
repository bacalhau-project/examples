#!/usr/bin/env bash
# Script to check Docker image versions for all components

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_image_info() {
    local image="$1"
    local component_name="$2"
    
    print_header "$component_name"
    
    # Check if image exists locally
    if docker images --quiet "$image" | head -1 | grep -q .; then
        echo -e "${GREEN}✓${NC} Image found locally"
        
        # Get image details
        local image_id=$(docker images --no-trunc --quiet "$image" | head -1)
        local short_id=$(docker images --quiet "$image" | head -1)
        local created=$(docker inspect "$image" --format='{{.Created}}' 2>/dev/null || echo "unknown")
        local digest=$(docker inspect "$image" --format='{{.RepoDigests}}' 2>/dev/null | \
                       grep -o 'sha256:[a-f0-9]*' | head -1 || echo "unknown")
        local size=$(docker images "$image" --format "{{.Size}}" | head -1)
        
        echo -e "${BLUE}Image:${NC} $image"
        echo -e "${BLUE}ID:${NC} $short_id (${image_id:7:19}...)"
        echo -e "${BLUE}Size:${NC} $size"
        echo -e "${BLUE}Created:${NC} $created"
        echo -e "${BLUE}Digest:${NC} ${digest:-unknown}"
        
        # Try to get labels with version info
        local version=$(docker inspect "$image" \
                       --format='{{.Config.Labels.version}}' 2>/dev/null || echo "")
        local git_commit=$(docker inspect "$image" \
                          --format='{{.Config.Labels.git_commit}}' 2>/dev/null || echo "")
        local build_date=$(docker inspect "$image" \
                          --format='{{.Config.Labels.build_date}}' 2>/dev/null || echo "")
        
        if [ -n "$version" ] && [ "$version" != "<no value>" ]; then
            echo -e "${BLUE}Version:${NC} $version"
        fi
        if [ -n "$git_commit" ] && [ "$git_commit" != "<no value>" ]; then
            echo -e "${BLUE}Git Commit:${NC} $git_commit"
        fi
        if [ -n "$build_date" ] && [ "$build_date" != "<no value>" ]; then
            echo -e "${BLUE}Build Date:${NC} $build_date"
        fi
        
        # Check if running
        local container_name="${component_name//-uploader/}"
        container_name="${container_name//-manager/}"
        if docker ps --format "{{.Names}}" | grep -q "^${container_name}"; then
            echo -e "${GREEN}● Container is running${NC}"
            local uptime=$(docker ps --format "{{.Status}}" \
                          --filter "name=${container_name}" | head -1)
            echo -e "${BLUE}Uptime:${NC} $uptime"
        else
            echo -e "${YELLOW}○ Container is not running${NC}"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Image not found locally"
        echo -e "${BLUE}Image:${NC} $image"
        echo ""
        echo "Pull with: docker pull $image"
    fi
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Docker is not installed or not in PATH"
    exit 1
fi

# Main header
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Docker Image Version Check for Databricks Pipeline        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"

# Check each component
print_image_info \
    "ghcr.io/bacalhau-project/sensor-log-generator:latest" \
    "sensor-log-generator"

print_image_info \
    "ghcr.io/bacalhau-project/databricks-uploader:latest" \
    "databricks-uploader"

print_image_info \
    "ghcr.io/bacalhau-project/pipeline-manager:latest" \
    "pipeline-manager"

# Check for local build tag
print_header "Local Build Information"
if [ -f ".latest-image-tag" ]; then
    local_tag=$(cat .latest-image-tag)
    echo -e "${BLUE}Local Build Tag:${NC} $local_tag"
else
    echo -e "${YELLOW}No local build tag file found${NC}"
fi

# Show git info if in a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo ""
    echo -e "${BLUE}Current Git Branch:${NC} $(git branch --show-current 2>/dev/null || echo 'unknown')"
    echo -e "${BLUE}Current Git Commit:${NC} $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        echo -e "${YELLOW}⚠ Uncommitted changes in repository${NC}"
    fi
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Summary
echo -e "${GREEN}Quick Commands:${NC}"
echo "  Pull all images:  docker pull ghcr.io/bacalhau-project/sensor-log-generator:latest && \\"
echo "                    docker pull ghcr.io/bacalhau-project/databricks-uploader:latest && \\"
echo "                    docker pull ghcr.io/bacalhau-project/pipeline-manager:latest"
echo ""
echo "  Run sensor:       ./run.sh --mode docker --component sensor"
echo "  Run uploader:     ./run.sh --mode docker --component uploader"
echo ""