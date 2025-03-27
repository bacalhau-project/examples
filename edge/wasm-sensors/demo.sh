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
PROXY_URL=${PROXY_URL:-"http://bacalhau-edge-sqs-proxy-1:9090"}

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
    echo "  deploy_all            Deploy to all regions"
    echo "  deploy_us             Deploy to US region"
    echo "  deploy_eu             Deploy to EU region"
    echo "  deploy_as             Deploy to AS region"
    echo "  deploy_interactive    Deploy with interactive configuration"
    echo "  deploy               Deploy with raw configuration"
    echo "  stop_all_jobs        Stop all running jobs"
    echo "  deploy_new_config    Deploy with new configuration"
    echo "  disconnect_region    Disconnect a specific region"
    echo "  reconnect_region     Reconnect a specific region"
    echo "  status               Show current status"
    echo
    echo "Options:"
    echo "  --interactive        Run in interactive menu mode"
    echo "  --help              Show this help message"
    echo
    echo "Environment variables:"
    echo "  PROXY_URL           SQS proxy URL (default: http://bacalhau-edge-sqs-proxy-1:9090)"
    echo
    echo "Examples:"
    echo "  $0 start_network"
    echo "  $0 stop_network"
    echo "  $0 deploy_us"
    echo "  $0 deploy_interactive"
    echo "  $0 --interactive"
    echo "  PROXY_URL=http://custom-proxy:9090 $0 deploy_us"
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

# Common deploy function
deploy() {
    if [ -z "$1" ]; then
        print_error "Region is required"
        print_usage
        exit 1
    fi

    local region=$1
    local color=${2:-"#FF0000"}  # Default to red if not provided
    local emoji=${3:-"0"}        # Default to 0 if not provided
    local interval=${4:-5}       # Default to 5 seconds if not provided

    print_step "Deploying to $region region"

    # Stop existing job if it exists
    local existing_jobs=$(get_running_jobs "$region")
    if [ ! -z "$existing_jobs" ]; then
        echo "$existing_jobs" | while read -r job_id; do
            bacalhau job stop --quiet "$job_id" >/dev/null 2>&1
        done
    fi

    # Get current Unix timestamp
    local submission_time=$(date +%s)

    # Deploy new job
    local job_id=$(bacalhau job run \
        --wait=false \
        --id-only \
        -V proxy="$PROXY_URL" \
        -V color="$color" \
        -V emoji="$emoji" \
        -V interval="$interval" \
        -V region="$region" \
        -V submission_time="$submission_time" \
        jobs/sqs-publisher.yaml)
    
    print_success "$region region deployed"
    print_info "To check job status, run: "
    echo -e "bacalhau job describe $job_id"
}

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

deploy_us() {
    # Red color and rocket emoji 🚀
    deploy "us" "#FF0000" "0"
}

deploy_eu() {
    # Blue color and satellite emoji 📡
    deploy "eu" "#0000FF" "1"
}

deploy_as() {
    # Green color and light bulb emoji 💡
    deploy "as" "#00FF00" "2"
}

deploy_all() {
    print_step "Deploying to all regions"
    deploy_us
    deploy_eu
    deploy_as
    print_success "All regions deployed"
}

deploy_interactive() {
    read -p "Enter region (us/eu/as): " region
    read -p "Enter color (hex or -1 for random): " color
    read -p "Enter emoji index (-1 for random): " emoji
    read -p "Enter interval in seconds (default 5): " interval
    interval=${interval:-5}
    
    deploy "$region" "$color" "$emoji" "$interval"
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
    echo "3) Deploy to all regions"
    echo "4) Deploy to US region"
    echo "5) Deploy to EU region"
    echo "6) Deploy to AS region"
    echo "7) Deploy interactive configuration"
    echo "8) Deploy with raw configuration"
    echo "9) Stop all jobs"
    echo "10) Disconnect region"
    echo "11) Reconnect region"
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
            3) deploy_all ;;
            4) deploy_us ;;
            5) deploy_eu ;;
            6) deploy_as ;;
            7) deploy_interactive ;;
            8) deploy "$2" "$3" "$4" ;;
            9) stop_all_jobs ;;
            10) disconnect_region ;;
            11) reconnect_region ;;
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
        deploy_all) deploy_all ;;
        deploy_us) deploy_us ;;
        deploy_eu) deploy_eu ;;
        deploy_as) deploy_as ;;
        deploy_interactive) deploy_interactive ;;
        deploy) deploy "$2" "$3" "$4" ;;
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