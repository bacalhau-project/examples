#!/bin/bash
# shellcheck disable=SC1091,SC2312,SC2155
set -euo pipefail
IFS=$'\n\t'

# we start with none as the default ("none" prevents the node connecting to our default bootstrap list)
export CONNECT_PEER="none"

# Special case - get tailscale address if any
# If the tailscale0 address exists in the command ip
# Get internal IP address from the first result that starts with 10.
export IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -E '^10\.' | head -n 1)

if [[ -n "${IP}" ]]; then
    export BACALHAU_PREFERRED_ADDRESS="${IP}"
fi

# export BACALHAU_NODE_CLIENTAPI_HOST=10.128.0.2
# export BACALHAU_NODE_CLIENTAPI_PORT=1234
# export BACALHAU_NODE_NETWORK_TYPE=nats
# export BACALHAU_NODE_NETWORK_ORCHESTRATORS=nats://bL8wVBTqu1bnERh6q_dBVN7tB0YTZmxBlTMH0Q-tQUw@10.128.0.2:4222
# export BACALHAU_NODE_IPFS_SWARMADDRESSES=/ip4/10.128.0.2/tcp/41347/p2p/QmVm4R3Fp2ZkiFrYeLYYVRAXkVr9WSU325AWD4HuMLGMkk


# if the file /etc/bacalhau-bootstrap exists
if [[ -f /etc/bacalhau-bootstrap ]]; then
    # shellcheck disable=SC1090
    source /etc/bacalhau-bootstrap
fi

# If /etc/bacalhau-node-info exists, then load the variables from it
if [[ -f /etc/bacalhau-node-info ]]; then
    # shellcheck disable=SC1090
    . /etc/bacalhau-node-info
fi

labels="ip=${IP}"

# If REGION is set, then we can assume all labels are set, and we should add it to the labels
if [[ -n "${REGION}" ]]; then
    labels="${labels},region=${REGION},zone=${ZONE},appname=${APPNAME}"
fi

bacalhau serve \
--node-type=compute \
--network="${BACALHAU_NODE_NETWORK_TYPE}" \
--orchestrators="${BACALHAU_NODE_NETWORK_ORCHESTRATORS}" \
--private-internal-ipfs \
--ipfs-swarm-addrs="${BACALHAU_NODE_IPFS_SWARMADDRESSES}" \
--allow-listed-local-paths="${ABSOLUTE_LOCAL_PATH}:rw" \
--job-selection-data-locality anywhere \
--swarm-port 1235 \
--api-port 1234 \
--peer "${CONNECT_PEER}" \
--job-selection-accept-networked \
--labels "${labels}"
