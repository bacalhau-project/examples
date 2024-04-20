#!/usr/bin/env bash

# Get host private IP and export as an environment variable PRIVATEIP to bacalhau-node-info
PRIVATE_IP=$(ip addr | awk '/inet/ && /10\./ {split($2, ip, "/"); print ip[1]}')
if [ -z "$PRIVATE_IP" ]; then
    echo "Private IP not found"
else
    echo "export PRIVATE_IP=${PRIVATE_IP}" >> /node/config/bacalhau-node-info
fi

source /node/config/bacalhau-node-info

# Start the container
VERSION="$(cat /node/VERSION)" \
docker compose -f /node/docker-compose.yml up -d

TIMEOUT=120

# Wait until container responds ok on localhost:14041/ok - After 30 seconds, post a message to logs and exit
for i in $(seq 1 $TIMEOUT); do
    if curl -s localhost:14041/ok; then
        echo "Container started successfully"
        break
    fi
    sleep 1
    if [ $i -eq $TIMEOUT ]; then
        echo "Container did not start successfully"
        exit 1
    fi
done

# Wait until /opt/bacalhau/config.yaml contains "node:" and then copy it to /node/config/node-config.yaml
for ((i=1; i<=$TIMEOUT; i++)); do
    if grep -q "node:" /opt/bacalhau/config.yaml; then
        echo "Config file found"
        cp /opt/bacalhau/config.yaml /node/config/node-config.yaml
        break
    fi
    sleep 1
    if [ $i -eq $TIMEOUT ]; then
        echo "Config file not found"
        exit 1
    fi
done

chmod 444 /node/config/node-config.yaml

# Ping itsadash.work/update_sites with a json of the form {"site": "site_name", "ip": "ip_address"}
echo "Pinging itsadash.work/update ..."
PRIVATEIP=$(ip addr | awk '/inet/ && /10\./ {split($2, ip, "/"); print ip[1]}')
export PRIVATEIP
curl -X POST -H "Content-Type: application/json" -d "{\"site\": \"${SITEURL}\", \"TOKEN\": \"${TOKEN}\", \"SERVERIP\": \"${PRIVATEIP}\"  }" http://itsadash.work/update