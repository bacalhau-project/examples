#!/bin/bash
# Docker helper utilities for Databricks-Bacalhau pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[DOCKER]${NC} $1"
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
ENV_FILE=".env"
NETWORK_NAME="databricks-pipeline"

# Parse command line arguments
COMMAND="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --network)
            NETWORK_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 COMMAND [OPTIONS]"
            echo ""
            echo "Commands:"
            echo "  start-all           Start all containers"
            echo "  stop-all            Stop all containers"
            echo "  restart-all         Restart all containers"
            echo "  status              Show container status"
            echo "  logs                Show logs from all containers"
            echo "  clean               Remove all containers and volumes"
            echo "  network-create      Create Docker network"
            echo "  network-remove      Remove Docker network"
            echo "  exec                Execute command in container"
            echo "  shell               Open shell in container"
            echo ""
            echo "Options:"
            echo "  --env-file FILE     Environment file (default: .env)"
            echo "  --network NAME      Docker network name \
(default: databricks-pipeline)"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

# Function to create Docker network
create_network() {
    if ! docker network ls | grep -q "$NETWORK_NAME"; then
        print_status "Creating Docker network: $NETWORK_NAME"
        docker network create "$NETWORK_NAME"
    else
        print_info "Network $NETWORK_NAME already exists"
    fi
}

# Function to remove Docker network
remove_network() {
    if docker network ls | grep -q "$NETWORK_NAME"; then
        print_status "Removing Docker network: $NETWORK_NAME"
        docker network rm "$NETWORK_NAME" || \
            print_warning "Could not remove network (containers may still be connected)"
    fi
}

# Function to start all containers
start_all() {
    print_status "Starting all containers..."
    
    # Create network if it doesn't exist
    create_network
    
    # Check if images exist, build if not
    if ! docker images | grep -q "databricks-uploader"; then
        print_warning "Building databricks-uploader image..."
        ./build.sh --component databricks-uploader
    fi
    
    if ! docker images | grep -q "pipeline-manager"; then
        print_warning "Building pipeline-manager image..."
        ./build.sh --component pipeline-manager
    fi
    
    # Start databricks-uploader
    print_status "Starting databricks-uploader..."
    docker run -d \
        --name databricks-uploader \
        --network "$NETWORK_NAME" \
        --env-file "$ENV_FILE" \
        -v "$(pwd)/databricks-uploader/data:/app/data" \
        -v "$(pwd)/logs:/app/logs" \
        --restart unless-stopped \
        databricks-uploader:latest
    
    # Start pipeline-manager using docker-compose
    print_status "Starting pipeline-manager..."
    cd pipeline-manager
    docker-compose up -d
    cd ..
    
    print_status "All containers started successfully!"
    show_status
}

# Function to stop all containers
stop_all() {
    print_status "Stopping all containers..."
    
    # Stop databricks-uploader
    docker stop databricks-uploader 2>/dev/null || \
        print_warning "databricks-uploader not running"
    
    # Stop pipeline-manager
    cd pipeline-manager 2>/dev/null && docker-compose down || \
        print_warning "pipeline-manager not running"
    cd ..
    
    print_status "All containers stopped"
}

# Function to restart all containers
restart_all() {
    print_status "Restarting all containers..."
    stop_all
    sleep 2
    start_all
}

# Function to show container status
show_status() {
    print_status "Container Status:"
    echo ""
    echo "Container Name          Status          Ports"
    echo "---------------------------------------------------"
    
    # Check databricks-uploader
    if docker ps -a | grep -q databricks-uploader; then
        status=$(docker inspect databricks-uploader --format='{{.State.Status}}')
        echo "databricks-uploader     $status"
    else
        echo "databricks-uploader     not created"
    fi
    
    # Check pipeline-manager
    if docker ps -a | grep -q pipeline-manager; then
        status=$(docker inspect pipeline-manager --format='{{.State.Status}}')
        ports=$(docker port pipeline-manager 2>/dev/null || echo "none")
        echo "pipeline-manager        $status         $ports"
    else
        echo "pipeline-manager        not created"
    fi
    
    echo ""
    
    # Show resource usage
    if docker ps -q | grep -E "(databricks-uploader|pipeline-manager)"; then
        print_info "Resource Usage:"
        docker stats --no-stream \
            $(docker ps --filter "name=databricks-uploader" \
                       --filter "name=pipeline-manager" -q) 2>/dev/null || true
    fi
}

# Function to show logs
show_logs() {
    local container="$1"
    local follow="$2"
    
    if [ -z "$container" ]; then
        # Show logs from all containers
        print_status "Showing logs from all containers..."
        
        if [ "$follow" == "-f" ]; then
            # Follow logs from all containers
            docker logs -f databricks-uploader 2>/dev/null &
            docker logs -f pipeline-manager 2>/dev/null &
            wait
        else
            # Show recent logs
            echo -e "\n${BLUE}=== databricks-uploader logs ===${NC}"
            docker logs --tail 50 databricks-uploader 2>/dev/null || \
                print_warning "No logs for databricks-uploader"
            
            echo -e "\n${BLUE}=== pipeline-manager logs ===${NC}"
            docker logs --tail 50 pipeline-manager 2>/dev/null || \
                print_warning "No logs for pipeline-manager"
        fi
    else
        # Show logs from specific container
        if [ "$follow" == "-f" ]; then
            docker logs -f "$container"
        else
            docker logs --tail 100 "$container"
        fi
    fi
}

# Function to clean up containers and volumes
clean_all() {
    print_warning "This will remove all containers and volumes. Continue? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Cleaning up containers and volumes..."
        
        # Stop and remove containers
        docker stop databricks-uploader pipeline-manager 2>/dev/null || true
        docker rm databricks-uploader pipeline-manager 2>/dev/null || true
        
        # Remove volumes
        docker volume prune -f
        
        # Remove network
        remove_network
        
        print_status "Cleanup complete"
    else
        print_info "Cleanup cancelled"
    fi
}

# Function to execute command in container
exec_container() {
    local container="$1"
    shift
    local cmd="$@"
    
    if [ -z "$container" ]; then
        print_error "Container name required"
        echo "Usage: $0 exec CONTAINER COMMAND"
        exit 1
    fi
    
    if [ -z "$cmd" ]; then
        print_error "Command required"
        exit 1
    fi
    
    print_status "Executing in $container: $cmd"
    docker exec -it "$container" $cmd
}

# Function to open shell in container
shell_container() {
    local container="$1"
    
    if [ -z "$container" ]; then
        print_error "Container name required"
        echo "Usage: $0 shell CONTAINER"
        echo "Available containers: databricks-uploader, pipeline-manager"
        exit 1
    fi
    
    print_status "Opening shell in $container..."
    docker exec -it "$container" /bin/bash || \
        docker exec -it "$container" /bin/sh
}

# Main execution
case $COMMAND in
    start-all)
        start_all
        ;;
    stop-all)
        stop_all
        ;;
    restart-all)
        restart_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$@"
        ;;
    clean)
        clean_all
        ;;
    network-create)
        create_network
        ;;
    network-remove)
        remove_network
        ;;
    exec)
        exec_container "$@"
        ;;
    shell)
        shell_container "$@"
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo "Run '$0 --help' for usage information"
        exit 1
        ;;
esac