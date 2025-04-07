#!/bin/bash

# get Ferret node public IP

cd setting-up-bacalhau-network-aws-ec2-instance
export FERRET_PUBLIC_IP=$(uv run ./deploy_instances.py --action=list --format=json | jq -r '.[] | select(.detailed_status == "ferretdb_node").public_ip')
cd ../

export MONGODB_URI="mongodb://username:password@"${FERRET_PUBLIC_IP}":27017"
echo $MONGODB_URI

bacalhau job run jobs/clean_sensor_logs_data_job.yaml --template-vars "code=$(cat scripts/cleanup_mongodb.py | base64 -w0),mongodb_uri=${MONGODB_URI}"
