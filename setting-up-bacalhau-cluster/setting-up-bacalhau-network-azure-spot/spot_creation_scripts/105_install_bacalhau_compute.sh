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
    bacalhau config set Compute.Heartbeat.ResourceUpdateInterval=1s
}

start_bacalhau() {
    log "Starting Bacalhau compute node..."

    # Fetch instance metadata from Azure
    HOSTNAME=$(curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance/compute/name?api-version=2021-02-01&format=text")
    PUBLIC_IP=$(curl -s "ifconfig.me")
    PRIVATE_IP=$(curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/privateIpAddress?api-version=2021-02-01&format=text")

    IP=${PUBLIC_IP:-$PRIVATE_IP}

    VM_SIZE=$(curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance/compute/vmSize?api-version=2021-02-01&format=text")
    VCPU_COUNT=$(nproc)
    MEMORY=$(free -h | awk '/Mem:/ {print $2}')
    DISK_GB=$(df -h | grep "/dev/root" | awk '{print $2}')

    LABELS="AZURE_VM_SIZE=${VM_SIZE},AZURE_VCPU_COUNT=${VCPU_COUNT},AZURE_MEMORY=${MEMORY},AZURE_DISK_GB=${DISK_GB},ORCHESTRATORS=${ORCHESTRATORS},HOSTNAME=${HOSTNAME},IP=${IP}"

    if [ -n "${TOKEN:-}" ]; then
        ORCHESTRATORS="${TOKEN}@${ORCHESTRATORS}"
    fi

    # Start Bacalhau
    /usr/local/bin/bacalhau serve \
        -c /etc/bacalhau-config.yaml \
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