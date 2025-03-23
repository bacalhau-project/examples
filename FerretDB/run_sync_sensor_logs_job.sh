#!/bin/bash

# get Ferret node public IP
(
cd setting-up-bacalhau-network-aws-spot
export FERRET_PUBLIC_IP=$(./deploy_spot.py --action=list --format=json | jq -r '.[] | select(.detailed_status == "ferretdb_node").public_ip')
)
export MONGODB_URI="mongodb://username:password@${FERRET_PUBLIC_IP}:27017"

bacalhau job run sync_sensor_logs_job.yaml --template-vars "code=$(cat sqlite_syncer.py | base64 -w0)" --template-vars "MONGODB_URI=${MONGODB_URI}"
