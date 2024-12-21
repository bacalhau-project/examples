#!/bin/bash
set -euo pipefail

export PATH="$PATH:/usr/local/go/bin"

# Logging functions (for improved debugging)
log() {
    local level="${1^^}"
    local message="$2"
    local color=""
    
    case "$level" in
        INFO)
            color="\033[0;34m"  # Blue
        ;;
        SUCCESS)
            color="\033[0;32m"  # Green
        ;;
        ERROR)
            color="\033[0;31m"  # Red
        ;;
        *)
            color="\033[0m"     # No color
        ;;
    esac
    
    echo -e "${color}[$level] $message"
}

# Start Bacalhau with the config (if it exists) and our combined labels
CONFIG_FILE="${BACALHAU_CONFIG_PATH:-/etc/bacalhau/config.yaml}"
if [ -f "$CONFIG_FILE" ]; then
    log "INFO" "Found config file, using: $CONFIG_FILE"
else
    log "WARNING" "No config file at $CONFIG_FILE – continuing without it."
fi

# Function to get a config value from the current Bacalhau config
get_config_value() {
    local key="$1"
    bacalhau config list "$CONFIG_FILE" --output json | jq -r ".[] | select(.Key == \"$key\") | .Value"
}

# Gather Bacalhau config
DATA_DIR=$(get_config_value "DataDir")
ALLOWED_PATHS=$(get_config_value "Compute.AllowListedLocalPaths")
COMPUTE_ORCHESTRATORS=$(get_config_value "Compute.Orchestrators")
ACCEPT_NETWORKED=$(get_config_value "JobAdmissionControl.AcceptNetworkedJobs")

# Gather container resources (cgroup-based)
MEMORY_LIMIT="$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo "unlimited")"
CPU_QUOTA="$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || echo "unlimited")"
CPU_PERIOD="$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null || echo "unknown")"
HOSTNAME="$(hostname)"

# Build an array of labels
LABELS=(
    "DataDir=$DATA_DIR"
    "JobAdmissionControl.AcceptNetworkedJobs=$ACCEPT_NETWORKED"
    "Compute.AllowListedLocalPaths=$ALLOWED_PATHS"
    "Compute.Orchestrators=$COMPUTE_ORCHESTRATORS"
    "memory_limit=$MEMORY_LIMIT"
    "cpu_quota=$CPU_QUOTA"
    "cpu_period=$CPU_PERIOD"
    "hostname=$HOSTNAME"
)

# Parse extra labels from /etc/node-info if present
if [ -f "/etc/node-info" ]; then
    log "INFO" "Reading additional labels from /etc/node-info..."
    while IFS='=' read -r key val; do
        # Skip lines without proper key-value pairs
        if [[ -n "$key" && -n "$val" ]]; then
            LABELS+=("$key=$val")
        fi
    done < /etc/node-info
else
    log "INFO" "No /etc/node-info found, proceeding without node info labels."
fi

# Convert the array of labels to a single comma-separated string
LABELS_STRING="$(IFS=,; echo "${LABELS[*]}")"

log "INFO" "Launching Bacalhau with labels: $LABELS_STRING"
bacalhau serve \
    --config "$CONFIG_FILE" \
    -c Logging.Level=info \
    -c Labels="$LABELS_STRING"

log "INFO" "Bacalhau server started. Press Ctrl+C to exit or let the container run."

