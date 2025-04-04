#!/bin/bash

#
# synchronize sqlite from all sensors to FerretDB
#

# get Ferret node public IP

cd setting-up-bacalhau-network-aws-ec2-instance
export FERRET_PUBLIC_IP=$(uv run ./deploy_instances.py --action=list --format=json | jq -r '.[] | select(.detailed_status == "ferretdb_node").public_ip')
cd ../

export MONGODB_URI="mongodb://username:password@"${FERRET_PUBLIC_IP}":27017"
echo $MONGODB_URI

bacalhau job run jobs/run_sensor_logs_syncer.yaml --template-vars "code=$(cat scripts/sqlite_syncer.py | base64 -w0),loop_code=$(cat scripts/sync_loop_script.sh | base64 -w0),mongodb_uri=${MONGODB_URI}"

