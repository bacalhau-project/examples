#!/usr/bin/env bash

# Include functions from install_uv.sh
source install_uv.sh

# Include functions from logging.sh
source logging.sh

# Set the BACALHAU_INSTALL_ID
# If not set, use a default value
BACALHAU_INSTALL_ID=${BACALHAU_INSTALL_ID:-"BACA14A0-4222-EEEE-8EEE-EEEEEEEEEEEE"}

log_info() {
    log "INFO" "$1"
}

log_success() {
    log "SUCCESS" "$1"
}

log_error() {
    log "ERROR" "$1"
}


ensure_jq_installed() {
    if ! command -v jq &> /dev/null; then
        log_error "JQ is not installed, please install it manually."
        exit 1
    else
        log_info "jq is installed."
    fi
}

ensure_jq_installed

# Replace the last 12 characters of the BACALHAU_INSTALL_ID with random 12 characters
BACALHAU_INSTALL_ID=$(echo "${BACALHAU_INSTALL_ID}" | \
    python3 -c "
import sys
import uuid

id = sys.stdin.read().strip()
new_id = id[:-12] + uuid.uuid4().hex[:12]
print(new_id)
")

# Download to a temporary file
TEMP_SCRIPT=$(mktemp)
if ! curl --fail --silent --show-error --tlsv1.2 --proto "=https" \
"https://get.bacalhau.org/install.sh?dl=${BACALHAU_INSTALL_ID}" \
--output "${TEMP_SCRIPT}"; then
    echo "Failed to download installation script"
    rm -f "${TEMP_SCRIPT}"
    exit 1
fi

# Execute the verified script
sudo bash "${TEMP_SCRIPT}"
rm -f "${TEMP_SCRIPT}"

