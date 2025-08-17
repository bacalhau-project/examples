#!/bin/bash

# Docker connectivity test script
# This script helps diagnose Docker connectivity issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Check Docker installation
print_section "Docker Installation Check"
if command -v docker &> /dev/null; then
    print_info "Docker is installed"
    docker --version
else
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

# Check Docker daemon
print_section "Docker Daemon Check"
if docker version &> /dev/null; then
    print_info "Docker daemon is running"
    echo "Client:"
    docker version --format '  Version: {{.Client.Version}}'
    echo "Server:"
    docker version --format '  Version: {{.Server.Version}}'
else
    print_error "Cannot connect to Docker daemon"
    echo "Possible solutions:"
    echo "  1. Start Docker Desktop (if on Mac/Windows)"
    echo "  2. Run: sudo systemctl start docker (if on Linux)"
    echo "  3. Check if your user is in the docker group"
    exit 1
fi

# Check Docker Hub connectivity
print_section "Docker Hub Connectivity Check"
echo "Testing connection to Docker Hub..."

# Try different methods to test connectivity
REGISTRY_URL="https://registry-1.docker.io/v2/"
if curl -s -o /dev/null -w "%{http_code}" "$REGISTRY_URL" | grep -q "401"; then
    print_info "Successfully connected to Docker Hub (401 is expected without auth)"
else
    print_warning "Could not connect to Docker Hub directly"
fi

# Try pulling a small test image
print_section "Image Pull Test"
TEST_IMAGE="hello-world:latest"
echo "Attempting to pull test image: $TEST_IMAGE"

if docker pull "$TEST_IMAGE" 2>&1 | tee pull-test.log; then
    print_info "Successfully pulled test image"
    docker rmi "$TEST_IMAGE" > /dev/null 2>&1 || true
else
    print_error "Failed to pull test image"

    # Check for specific errors
    if grep -q "http: server gave HTTP response to HTTPS client" pull-test.log; then
        print_error "HTTP/HTTPS mismatch detected"
        echo ""
        echo "Possible solutions:"
        echo "  1. Check Docker proxy settings"
        echo "  2. Update Docker to latest version"
        echo "  3. Try setting DOCKER_BUILDKIT=0"
    elif grep -q "timeout" pull-test.log; then
        print_error "Connection timeout detected"
        echo ""
        echo "Possible solutions:"
        echo "  1. Check internet connection"
        echo "  2. Check firewall settings"
        echo "  3. Configure Docker to use a proxy if behind corporate firewall"
    fi
fi

# Check Docker proxy settings
print_section "Docker Proxy Configuration"
if docker info 2>/dev/null | grep -q "HTTP Proxy\|HTTPS Proxy"; then
    print_info "Docker proxy is configured:"
    docker info 2>/dev/null | grep -E "HTTP Proxy|HTTPS Proxy"
else
    print_info "No Docker proxy configured"
fi

# Check available disk space
print_section "Disk Space Check"
DOCKER_ROOT=$(docker info 2>/dev/null | grep "Docker Root Dir" | awk '{print $NF}')
if [ -n "$DOCKER_ROOT" ]; then
    df -h "$DOCKER_ROOT" | tail -1
else
    df -h /var/lib/docker 2>/dev/null || df -h .
fi

# Check Docker daemon configuration
print_section "Docker Daemon Configuration"
if [ -f /etc/docker/daemon.json ]; then
    print_info "Docker daemon configuration found:"
    cat /etc/docker/daemon.json | jq . 2>/dev/null || cat /etc/docker/daemon.json
elif [ -f ~/.docker/daemon.json ]; then
    print_info "User Docker daemon configuration found:"
    cat ~/.docker/daemon.json | jq . 2>/dev/null || cat ~/.docker/daemon.json
else
    print_info "No custom Docker daemon configuration found"
fi

# Test building a simple Dockerfile
print_section "Build Test"
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

cat > Dockerfile << 'EOF'
FROM alpine:latest
RUN echo "Build test successful"
EOF

echo "Testing Docker build with simple Dockerfile..."
if docker build -t test-build:latest . 2>&1 | tee build-test.log; then
    print_info "Docker build test successful"
    docker rmi test-build:latest > /dev/null 2>&1 || true
else
    print_error "Docker build test failed"
    cat build-test.log
fi

cd - > /dev/null
rm -rf "$TEMP_DIR"

# Summary
print_section "Summary"
echo "Docker connectivity test completed."
echo ""
echo "If you're experiencing issues:"
echo "1. Check the error messages above"
echo "2. Ensure Docker Desktop is running (Mac/Windows)"
echo "3. Try: docker logout && docker login"
echo "4. Check proxy settings if behind a corporate firewall"
echo "5. Update Docker to the latest version"
echo "6. Try building with: ./build.sh --simple --skip-connectivity-check"

# Clean up
rm -f pull-test.log build-test.log 2>/dev/null || true
