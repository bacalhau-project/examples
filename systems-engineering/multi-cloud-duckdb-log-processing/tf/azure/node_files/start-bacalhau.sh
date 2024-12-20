#!/bin/bash
# shellcheck disable=SC1091,SC2312,SC2155
set -euo pipefail
IFS=$'\n\t'

# we start with none as the default ("none" prevents the node connecting to our default bootstrap list)
export CONNECT_PEER="none"

# If /etc/bacalhau/orchestrator-config.yaml exists, use it to populate the CONNECT_PEER variable
if [[ -f /etc/bacalhau/orchestrator-config.yaml ]]; then
  # shellcheck disable=SC1090
  source /etc/bacalhau/orchestrator-config.yaml
  CONNECT_PEER="${BACALHAU_NODE_LIBP2P_PEERCONNECT}"
fi

# If /etc/bacalhau-node-info exists, then load the variables from it
if [[ -f /etc/bacalhau-node-info ]]; then
  # shellcheck disable=SC1090
  . /etc/bacalhau-node-info
fi

# If REGION is set, then we can assume all labels are set, and we should add it to the labels
labels="region=${REGION},zone=${ZONE},appname=${APPNAME}"

bacalhau serve \
  --node-type requester,compute \
  --job-selection-data-locality anywhere \
  --swarm-port 1235 \
  --api-port 1234 \
  --peer "${CONNECT_PEER}" \
  --private-internal-ipfs=true \
  --allow-listed-local-paths '/var/log/logs_to_process/**' \
  --job-selection-accept-networked \
  --labels "${labels}"
