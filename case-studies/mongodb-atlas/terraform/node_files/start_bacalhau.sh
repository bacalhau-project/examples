#!/bin/bash
# shellcheck disable=SC1091,SC2312,SC2155
set -euo pipefail
IFS=$'\n\t'

# Set the EXTERNAL_IP in case we need to declare this node as our orchestrator
EXTERNAL_IP=$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)

echo "${EXTERNAL_IP}"

# Initial setting of the isOrchestrator variable
isOrchestrator=true

# if the file /etc/bacalhau-bootstrap exists, infer that this node is a compute node
if [[ -f /etc/bacalhau-bootstrap ]]; then
  isOrchestrator=false
else
  echo -n "${EXTERNAL_IP}" > /etc/bacalhau-bootstrap
fi

labels="orchestrator-ip=${EXTERNAL_IP}"

# If /etc/bacalhau-node-info exists, then load the variables from it
if [[ -f /etc/bacalhau-node-info ]]; then
  # shellcheck disable=SC1090
  . /etc/bacalhau-node-info
fi

# If REGION is set, then we can assume all labels are set, and we should add it to the labels
if [[ -n "${REGION}" ]]; then
  labels="${labels},region=${REGION},zone=${ZONE},appname=${APPNAME}"
fi

if [[ "$isOrchestrator" == "true" ]]; then
    echo "isOrchestrator is set."
    bacalhau serve --node-type requester
else
    ORCHESTRATOR_IP=$(cat /etc/bacalhau-bootstrap)
    echo "isOrchestrator is not set."
    bacalhau serve --node-type=compute --orchestrators="nats://${ORCHESTRATOR_IP}:4222" --labels "${labels}" --job-selection-accept-networked=true
fi