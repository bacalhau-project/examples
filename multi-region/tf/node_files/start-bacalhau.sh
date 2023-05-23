#!/bin/bash
# shellcheck disable=SC1091,SC2312,SC2155
set -euo pipefail
IFS=$'\n\t'

# we start with none as the default ("none" prevents the node connecting to our default bootstrap list)
export CONNECT_PEER="none"

# Special case - get tailscale address if any
export TAILSCALE_ADDRESS=$(ip -4 a l tailscale0 | awk '/inet/ {print $2}' | cut -d/ -f1)

# if TAILSCALE_ADDRESS is set, use it to populate the CONNECT_PEER variable
if [[ -n "${TAILSCALE_ADDRESS}" ]]; then
  export BACALHAU_PREFERRED_ADDRESS="${TAILSCALE_ADDRESS}"
fi

# if the file /etc/bacalhau-bootstrap exists, use it to populate the CONNECT_PEER variable
if [[ -f /etc/bacalhau-bootstrap ]]; then
  # shellcheck disable=SC1090
  source /etc/bacalhau-bootstrap
  CONNECT_PEER="${BACALHAU_PEER_CONNECT}"
fi

bacalhau serve \
  --node-type requester,compute \
  --job-selection-data-locality anywhere \
  --swarm-port 1235 \
  --api-port 1234 \
  --peer "${CONNECT_PEER}" \
  --private-internal-ipfs=true