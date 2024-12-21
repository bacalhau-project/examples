#!/usr/bin/env bash

set -euo pipefail

RUN_BACALHAU_SH="/root/run_bacalhau.sh"

cat << 'EOF' > "${RUN_BACALHAU_SH}"
#!/usr/bin/env bash

set -euo pipefail

# Log files
LOG_FILE="/var/log/bacalhau_start.log"
DEBUG_LOG_FILE="/var/log/bacalhau_start_debug.log"

# Ensure log files are writable
touch "$LOG_FILE" "$DEBUG_LOG_FILE"
chmod 666 "$LOG_FILE" "$DEBUG_LOG_FILE"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_debug() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$DEBUG_LOG_FILE"
}

log_error() {
    echo "[ERROR][$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE" >> "$DEBUG_LOG_FILE"
}

# Source the configuration file
if [ -f /etc/node-config ]; then
    # shellcheck disable=SC1091
    source /etc/node-config
else
    log_error "Node configuration file not found at /etc/node-config"
    exit 1
fi

# Function to get labels from node config
get_labels() {
    local labels=""
    while IFS= read -r line
    do
        # Skip empty lines and lines starting with TOKEN
        [[ -z "$line" || "$line" =~ ^TOKEN ]] && continue

        # Extract variable name and value
        var_name=$(echo "$line" | cut -d'=' -f1)
        var_value=${!var_name}

        # Remove any quotes from the value
        var_value=$(echo "$var_value" | tr -d '\"')

        # Append to labels string
        labels="${labels:+$labels,}${var_name}=${var_value}"
    done < /etc/node-config

    echo "$labels"
}

check_env_vars() {
    local required_vars=("NODE_TYPE" "ORCHESTRATORS")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Required environment variable $var is not set"
            return 1
        fi
    done
    return 0
}

start_bacalhau() {
    log "Starting Bacalhau..."

    # Get labels from configuration
    LABELS=$(get_labels)

    # Validate environment
    if ! check_env_vars; then
        log_error "Environment validation failed"
        return 1
    fi

    # Log environment for debugging
    log_debug "Environment:"
    log_debug "NODE_TYPE: ${NODE_TYPE}"
    log_debug "ORCHESTRATORS: ${ORCHESTRATORS}"
    log_debug "LABELS: ${LABELS}"

    if [ -n "${TOKEN:-}" ]; then
        ORCHESTRATORS="${TOKEN}@${ORCHESTRATORS}"
    fi

    # Start Bacalhau with verbose logging
    /usr/local/bin/bacalhau serve \
        --node-type "${NODE_TYPE}" \
        --orchestrators "${ORCHESTRATORS}" \
        --labels "${LABELS}" \
        --log-level debug \
        >> "${LOG_FILE}" 2>&1

    local exit_code=$?
    log_debug "Bacalhau exit code: ${exit_code}"

    return ${exit_code}
}

stop_bacalhau() {
    log "Stopping Bacalhau worker node..."
    pkill -f "bacalhau serve" || true
    log "Bacalhau worker node stopped"
}

# Main execution
main() {
    local cmd="${1:-}"

    case "${cmd}" in
        start)
            start_bacalhau
            exit $?
            ;;
        stop)
            stop_bacalhau
            ;;
        restart)
            stop_bacalhau
            sleep 2
            start_bacalhau
            exit $?
            ;;
        *)
            log_error "Usage: $0 {start|stop|restart}"
            exit 1
            ;;
    esac
}

main "$@"
EOF

chmod +x "${RUN_BACALHAU_SH}"

echo "Bacalhau service script has been created at ${RUN_BACALHAU_SH}"