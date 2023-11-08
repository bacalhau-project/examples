
bacalhau serve \
  --node-type requester,compute \
  --job-selection-data-locality anywhere \
  --swarm-port 1235 \
  --api-port 1234 \
  --peer none \
  --private-internal-ipfs=true \
  --job-selection-accept-networked \
