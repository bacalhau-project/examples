#!/bin/bash
set -euo pipefail

# Required environment variables
: "${NODE_TYPE:?Required}"
: "${ORCHESTRATORS:?Required}"

# Optional environment variables with defaults
: "${LABELS:=}"
: "${TOKEN:=}"

if [ -n "$TOKEN" ]; then
    ORCHESTRATORS="${TOKEN}@${ORCHESTRATORS}"
fi

exec bacalhau serve \
    --node-type "$NODE_TYPE" \
    --orchestrators "$ORCHESTRATORS" \
    ${LABELS:+--labels "$LABELS"} \
    --log-level info
