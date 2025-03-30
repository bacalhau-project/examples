#!/bin/bash
#
# Bacalhau Network Demo Script
#
# This script manages a Bacalhau distributed computing network with edge nodes in multiple regions.
# It provides functionality to start/stop the network, disconnect/reconnect regions, and manage jobs.
#
# Key features:
# - Sequential provisioning of edge nodes to prevent overwhelming the orchestrator
# - Controlled reconnection of regions for fault tolerance testing
# - Preservation of container and node identities during disconnection/reconnection
#

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
REPLICAS=${REPLICAS:-3}            # Default number of replicas if not specified
US_REPLICAS=${US_REPLICAS:-$REPLICAS}     # US region can be overridden separately
EU_REPLICAS=${EU_REPLICAS:-$REPLICAS}     # EU region can be overridden separately
AS_REPLICAS=${AS_REPLICAS:-$REPLICAS}     # AS region can be overridden separately

# Timing for sequential operations (milliseconds)
# - Provisioning needs a small delay to prevent overwhelming the orchestrator's registration process
# - Reconnection uses a different delay as restarting is typically faster than initial creation
MS_BETWEEN_NODES=${MS_BETWEEN_NODES:-100}          # Default delay for node provisioning
MS_BETWEEN_RECONNECT=${MS_BETWEEN_RECONNECT:-250}  # Default delay for node reconnection (higher as starting existing containers is much faster than creating new ones)

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

# Sleep for milliseconds
ms_sleep() {
  local ms=$1
  sleep $(echo "scale=3; $ms/1000" | bc)
}

print_usage() {
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  start_network        Start the Bacalhau network (with sequential provisioning)"
    echo "  stop_network         Stop the Bacalhau network"
    echo "  stop_all_jobs        Stop all running jobs"
    echo "  disconnect_region    Disconnect a specific region"
    echo "  reconnect_region     Reconnect a specific region (with sequential restart)"
    echo "  status               Show current status"
    echo
    echo "Options:"
    echo "  --interactive        Run in interactive menu mode"
    echo "  --help               Show this help message"
    echo
    echo "Environment variables:"
    echo "  REPLICAS             Default number of replicas for all regions (default: 3)"
    echo "  US_REPLICAS          Number of replicas for US region"
    echo "  EU_REPLICAS          Number of replicas for EU region"
    echo "  AS_REPLICAS          Number of replicas for AS region"
    echo "  MS_BETWEEN_NODES     Milliseconds to wait between node startups (default: 100)"
    echo "  MS_BETWEEN_RECONNECT Milliseconds to wait between node reconnections (default: 250)"
    echo
    echo "Examples:"
    echo "  $0 start_network"
    echo "  REPLICAS=10 $0 start_network"
    echo "  US_REPLICAS=5 EU_REPLICAS=8 AS_REPLICAS=7 $0 start_network"
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

# Show progress indicator for sequential provisioning
show_progress() {
  local region=$1
  local current=$2
  local total=$3

  local percent=$((current * 100 / total))
  printf "\r${BLUE}[%s] Provisioning: %3d%% (%d/%d nodes)${NC}" "$region" "$percent" "$current" "$total"
}

# Provision nodes for a region sequentially
provision_region() {
  local region=$1
  local node_count=$2

  print_step "Provisioning $region region ($node_count nodes)"

  # We provision nodes sequentially (one at a time) for two important reasons:
  # 1. To prevent overwhelming the orchestrator with many simultaneous registration requests,
  #    which can cause connection failures or timeout issues in large deployments
  # 2. To allow for graceful node registration, especially important when running many nodes
  #    on the same host where resource contention could occur during startup

  for i in $(seq 1 $node_count); do
    # Scale up by one node at a time
    # This is much gentler on the orchestrator than starting all nodes at once
    docker compose -f network/docker-compose.yml up -d --scale edge-$region=$i edge-$region &>/dev/null

    # Show progress
    show_progress $region $i $node_count

    # Wait before provisioning the next node to allow time for registration
    # This delay is critical to ensure each node fully registers before the next one starts
    if [ $i -lt $node_count ]; then
      ms_sleep $MS_BETWEEN_NODES
    fi
  done

  echo
  print_success "$region region fully provisioned"
}

start_network() {
    print_step "Starting Bacalhau network with sequential node provisioning"

    # Clean up existing network
    cd network
    docker compose down

    # Start core services first
    # We always start orchestrator and web services before edge nodes
    print_info "Starting core services..."
    docker compose up -d orchestrator web-services sqs-proxy sqs-puller

    # Wait for orchestrator to be healthy
    # This is critical - we must have a running orchestrator before any edge nodes start
    print_info "Waiting for orchestrator readiness..."
    until docker compose exec orchestrator bacalhau agent alive &>/dev/null; do
      printf "."
      sleep 2
    done
    echo
    print_success "Orchestrator ready"

    # Calculate total nodes
    TOTAL_NODES=$((US_REPLICAS + EU_REPLICAS + AS_REPLICAS))
    print_info "Total target: $TOTAL_NODES nodes across all regions"

    # Provision each region sequentially
    # The order (US, EU, AS) matters if you're demonstrating geographic distribution
    cd ..
    provision_region "us" $US_REPLICAS
    provision_region "eu" $EU_REPLICAS
    provision_region "as" $AS_REPLICAS

    # Show summary
    print_step "Deployment Complete"
    echo "   ┌─────────────────────────────────┐"
    echo "   │ Region │ Nodes │   Percentage   │"
    echo "   ├─────────────────────────────────┤"
    printf "   │ US     │ %5d │ %6.1f%%        │\n" $US_REPLICAS $(echo "scale=1; $US_REPLICAS*100/$TOTAL_NODES" | bc)
    printf "   │ EU     │ %5d │ %6.1f%%        │\n" $EU_REPLICAS $(echo "scale=1; $EU_REPLICAS*100/$TOTAL_NODES" | bc)
    printf "   │ AS     │ %5d │ %6.1f%%        │\n" $AS_REPLICAS $(echo "scale=1; $AS_REPLICAS*100/$TOTAL_NODES" | bc)
    echo "   ├─────────────────────────────────┤"
    printf "   │ TOTAL  │ %5d │ 100.0%%        │\n" $TOTAL_NODES
    echo "   └─────────────────────────────────┘"

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

    # We use 'docker compose stop' instead of 'down' for a critical reason:
    # - 'stop' preserves the containers in a stopped state, maintaining their identity
    # - This allows us to restart the exact same containers later with the same node IDs
    # - Maintaining node identity is important for the Bacalhau network to recognize
    #   returning nodes rather than treating them as completely new nodes
    print_info "Stopping all edge-$region containers..."
    docker compose -f network/docker-compose.yml stop edge-$region

    # Count how many containers were stopped
    local container_count=$(docker ps -a -q --filter "name=edge-${region}" --filter "status=exited" | wc -l)
    print_success "$region region disconnected ($container_count containers)"
}

reconnect_region() {
    local region=$1
    if [ -z "$region" ]; then
        read -p "Enter region to reconnect (us/eu/as): " region
    fi

    print_step "Reconnecting $region region with sequential restart"

    # Find all stopped containers for this region
    local container_ids=($(docker ps -a -q --filter "name=edge-${region}" --filter "status=exited"))
    local total_containers=${#container_ids[@]}

    if [ $total_containers -eq 0 ]; then
        print_error "No stopped containers found for $region region"
        return 1
    fi

    print_info "Found $total_containers stopped containers for $region region"

    # We restart containers one-by-one rather than using 'docker-compose up --scale' for several reasons:
    # 1. We want to preserve each container's exact identity and node ID
    # 2. Sequential restart prevents overwhelming the orchestrator with simultaneous reconnections
    # 3. We can show a precise progress indicator
    # 4. This approach maintains the distributed system's state more accurately

    # Start containers one by one
    local current=0
    for container_id in "${container_ids[@]}"; do
        current=$((current + 1))

        # Start this specific container
        # Using 'docker start' maintains the container's identity, including its
        # hostname, environment variables, and most importantly, its Bacalhau node ID
        docker start "$container_id" &>/dev/null

        # Show progress
        printf "\r${BLUE}[$region] Restarting: %3d%% (%d/%d containers)${NC}" \
            $((current * 100 / total_containers)) $current $total_containers

        # Wait between container starts
        # The delay is higher for reconnection than initial provisioning because:
        # 1. Starting existing containers is much faster than creating new ones
        # 2. We need to ensure each node properly reconnects to the orchestrator
        if [ $current -lt $total_containers ]; then
            ms_sleep $MS_BETWEEN_RECONNECT  # Using the reconnection-specific delay
        fi
    done

    echo
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