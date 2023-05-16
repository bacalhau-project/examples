#!/bin/bash
# shellcheck disable=SC1091,SC2312
set -euo pipefail
IFS=$'\n\t'

# mount the disk - wait for /dev/sdb to exist
# NB: do not reformat the disk if we can't mount it, unlike the initial
# install/upgrade script!
while [[ ! -e /dev/sdb ]]; do
  sleep 1
  echo "waiting for /dev/sdb to exist"
done
# mount /dev/sdb at /data
mkdir -p /data
mount /dev/sdb /data || true

function getMultiaddress() {
  echo -n "/ip4/${1}/tcp/${BACALHAU_PORT}/p2p/${2}"
}

# we start with none as the default ("none" prevents the node connecting to our default bootstrap list)
export CONNECT_PEER="none"

# If the file /node/node-is-rally-point exists, then we are the rally point
if [[ ! -f /node/variables ]]; then
  # we are the rally point, so we can connect to the default bootstrap list
  CONNECT_PEER="/ip4/"
fi

bacalhau serve \
  --node-type requester,compute \
  --job-selection-data-locality anywhere \
  --job-selection-accept-networked \
  --job-selection-probe-exec "${BACALHAU_PROBE_EXEC}" \
  --swarm-port "${BACALHAU_PORT}" \
  --api-port 1234 \
  --peer "${CONNECT_PEER}" \
  --private-internal-ipfs=false \
  --labels owner=bacalhau
