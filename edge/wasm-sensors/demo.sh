#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
REPLICAS=${REPLICAS:-3}

# Helper functions
print_step() {
    echo -e "\n${YELLOW}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_usage() {
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  start_network          Start the Bacalhau network"
    echo "  stop_network          Stop the Bacalhau network"
    echo "  stop_all_jobs        Stop all running jobs"
    echo "  disconnect_region    Disconnect a specific region"
    echo "  reconnect_region     Reconnect a specific region"
    echo "  status               Show current status"
    echo
    echo "Options:"
    echo "  --interactive        Run in interactive menu mode"
    echo "  --help              Show this help message"
    echo
    echo "Examples:"
    echo "  $0 start_network"
    echo "  $0 stop_network"
    echo "  $0 disconnect_region eu"
}

# Get running job IDs for a specific region
get_running_jobs() {
    local region=$1
    bacalhau job list --labels "sqs-publisher=$region" --limit 100 --output json | \
    jq -r '.[] | select(.State.StateType != "Completed" and .State.StateType != "Stopped" and .State.StateType != "Failed") | .ID'
}

# Ensure we're in the right directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Step functions
start_network() {
    print_step "Starting Bacalhau network..."
    cd network
    docker compose down
    docker compose up -d
    cd ..
    print_success "Network started"
}

stop_network() {
    print_step "Stopping Bacalhau network..."
    cd network
    docker compose down
    cd ..
    print_success "Network stopped"
}

stop_all_jobs() {
    print_step "Stopping all jobs"
    for region in "us" "eu" "as"; do
        local jobs=$(get_running_jobs "$region")
        if [ ! -z "$jobs" ]; then
            print_info "Stopping jobs for $region region"
            echo "$jobs" | while read -r job_id; do
                print_info "Stopping job $job_id"
                bacalhau job stop --quiet "$job_id" >/dev/null 2>&1
            done
        fi
    done
    print_success "All jobs stopped"
}

disconnect_region() {
    local region=$1
    if [ -z "$region" ]; then
        read -p "Enter region to disconnect (us/eu/as): " region
    fi
    print_step "Disconnecting $region region"
    docker compose -f network/docker-compose.yml stop "edge-$region"
    print_success "$region region disconnected"
}

reconnect_region() {
    local region=$1
    if [ -z "$region" ]; then
        read -p "Enter region to reconnect (us/eu/as): " region
    fi
    print_step "Reconnecting $region region"
    docker compose -f network/docker-compose.yml start "edge-$region"
    print_success "$region region reconnected"
}

show_menu() {
    echo -e "\n${BLUE}Available commands:${NC}"
    echo "1) Start network"
    echo "2) Stop network"
    echo "3) Stop all jobs"
    echo "4) Disconnect region"
    echo "5) Reconnect region"
    echo "q) Quit"
    echo
}

# Handle command line arguments
if [ $# -eq 0 ] || [ "$1" = "--help" ]; then
    print_usage
    exit 0
fi

if [ "$1" = "--interactive" ]; then
    # Interactive mode
    while true; do
        show_menu
        read -p "Enter command number: " cmd
        echo

        case $cmd in
            1) start_network ;;
            2) stop_network ;;
            3) stop_all_jobs ;;
            4) 
                read -p "Enter region to disconnect (us/eu/as): " region
                disconnect_region "$region" 
                ;;
            5) 
                read -p "Enter region to reconnect (us/eu/as): " region
                reconnect_region "$region" 
                ;;
            q|Q) 
                print_info "Exiting..."
                exit 0
                ;;
            *)
                print_error "Invalid command"
                ;;
        esac

        echo
        read -p "Press Enter to continue..."
    done
else
    # Direct command mode
    case "$1" in
        start_network) start_network ;;
        stop_network) stop_network ;;
        stop_all_jobs) stop_all_jobs ;;
        disconnect_region) disconnect_region "$2" ;;
        reconnect_region) reconnect_region "$2" ;;
        *)
            print_error "Unknown command: $1"
            print_usage
            exit 1
            ;;
    esac
fi 