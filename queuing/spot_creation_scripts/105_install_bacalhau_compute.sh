#!/usr/bin/env bash

set -euo pipefail

BACALHAU_COMPUTE_SH="/root/bacalhau_compute.sh"

cat << 'EOF' > "${BACALHAU_COMPUTE_SH}"
#!/usr/bin/env bash

set -euo pipefail

LOG_FILE="/var/log/bacalhau_compute_start.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Source the configuration file
if [ -f /etc/node-config ]; then
    # shellcheck disable=SC1091
    source /etc/node-config
else
    log "Error: /etc/node-config file not found."
    exit 1
fi

check_orchestrators() {
    if [ -z "${ORCHESTRATORS:-}" ]; then
        log "Error: ORCHESTRATORS environment variable is not set."
        exit 1
    fi
}

set_bacalhau_config_settings() {
    bacalhau config set  node.compute.controlplanesettings.resourceupdatefrequency 1s
}

start_bacalhau() {
    log "Starting Bacalhau compute node..."

    # Get the instance's private DNS name
    HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/local-hostname)
    IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

    # Construct LABELS from EC2 information
    LABELS="EC2_INSTANCE_FAMILY=${EC2_INSTANCE_FAMILY:-unknown},EC2_VCPU_COUNT=${EC2_VCPU_COUNT:-unknown},EC2_MEMORY_GB=${EC2_MEMORY_GB:-unknown},EC2_DISK_GB=${EC2_DISK_GB:-unknown},ORCHESTRATORS=${ORCHESTRATORS},HOSTNAME=${HOSTNAME},IP=${IP}"

    if [ -n "${TOKEN:-}" ]; then
        ORCHESTRATORS="${TOKEN}@${ORCHESTRATORS}"
    fi

    # Start Bacalhau
    /usr/local/bin/bacalhau serve \
        --node-type compute \
        --orchestrators "${ORCHESTRATORS}" \
        --labels "${LABELS}" \
        --job-selection-accept-networked \
        >> "${LOG_FILE}" 2>&1 &

    local PID=$!
    log "Bacalhau compute node started with PID ${PID}"
    log "Labels: ${LABELS}"
}

stop_bacalhau() {
    log "Stopping Bacalhau compute node..."
    pkill -f "bacalhau serve" || true
    log "Bacalhau compute node stopped"
}

# Main execution
main() {
    local cmd="${1:-}"

    case "${cmd}" in
        start)
            check_orchestrators
            set_bacalhau_config_settings
            start_bacalhau
            ;;
        stop)
            stop_bacalhau
            ;;
        restart)
            stop_bacalhau
            sleep 2
            check_orchestrators
            set_bacalhau_config_settings
            start_bacalhau
            ;;
        *)
            echo "Usage: $0 {start|stop|restart}"
            exit 1
            ;;
    esac
}

main "$@"
EOF

chmod +x "${BACALHAU_COMPUTE_SH}"

echo "Bacalhau compute service script has been created at ${BACALHAU_COMPUTE_SH}"