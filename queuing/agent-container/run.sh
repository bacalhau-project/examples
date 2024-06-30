#!/usr/bin/env bash

if [ -z "$BACALHAU_NODE_NETWORK_ORCHESTRATORS" ]; then
    echo "BACALHAU_NODE_NETWORK_ORCHESTRATORS is not set"
    exit 1
fi

bacalhau serve --node-type=compute \
               --labels hostname="$(hostname)" \
               --orchestrators="${BACALHAU_NODE_NETWORK_ORCHESTRATORS}"