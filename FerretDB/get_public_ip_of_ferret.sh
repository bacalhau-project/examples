#!/bin/bash

(
cd setting-up-bacalhau-network-aws-spot
export FERRET_PUBLIC_IP=$(./deploy_spot.py --action=list --format=json | jq -r '.[] | select(.detailed_status == "ferretdb_node").public_ip')
echo $FERRET_PUBLIC_IP
)
