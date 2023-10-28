#!/bin/bash
# shellcheck disable=SC1091,SC2312,SC2155
set -euo pipefail
IFS=$'\n\t'

# we start with none as the default ("none" prevents the node connecting to our default bootstrap list)
export CONNECT_PEER="none"

# Special case - get tailscale address if any
# If the tailscale0 address exists in the command ip
export TAILSCALE_ADDRESS=$(ip -4 a l tailscale0 | awk '/inet/ {print $2}' | cut -d/ -f1)

# if TAILSCALE_ADDRESS is set, use it to populate the CONNECT_PEER variable
if [[ -n "${TAILSCALE_ADDRESS}" ]]; then
  export BACALHAU_PREFERRED_ADDRESS="${TAILSCALE_ADDRESS}"
fi

# if the file /etc/bacalhau-bootstrap exists, use it to populate the CONNECT_PEER variable
if [[ -f /etc/bacalhau-bootstrap ]]; then
  # shellcheck disable=SC1090
  source /etc/bacalhau-bootstrap
  CONNECT_PEER="${BACALHAU_NODE_LIBP2P_PEERCONNECT}"
fi

# If /etc/bacalhau-node-info exists, then load the variables from it
if [[ -f /etc/bacalhau-node-info ]]; then
  # shellcheck disable=SC1090
  . /etc/bacalhau-node-info
fi

labels="ip=${TAILSCALE_ADDRESS}"

# If REGION is set, then we can assume all labels are set, and we should add it to the labels
if [[ -n "${REGION}" ]]; then
  labels="${labels},region=${REGION},zone=${ZONE},appname=${APPNAME}"
fi

bacalhau serve \
  --node-type requester,compute \
  --job-selection-data-locality anywhere \
  --swarm-port 1235 \
  --api-port 1234 \
  --peer "${CONNECT_PEER}" \
  --private-internal-ipfs=true \
  --allow-listed-local-paths '/db' \
  --allow-listed-local-paths '/var/log/logs_to_process/**' \
  --job-selection-accept-networked \
  --labels "${labels}"