#!/bin/bash

set -e

# This script uploads tar.gz data to IPFS via Estuary from a directory

if [ -z "$TOKEN" ]; then
    echo "TOKEN is not set, please export your Estuary API token as TOKEN"
    exit 1
fi

if [ -z "$1" ]; then
    echo "Please provide a directory to upload"
    exit 1
fi

# Find all tar.gz files in the directory
for i in $(seq 0 10000 20000000); do
    FILE="$1/output_$i.tar.gz"
    if [ -f "$FILE" ]; then
        echo "Uploading $FILE"
        curl \
            -s -D - \
            --max-time 20 \
            --retry 5 \
            -X POST https://upload.estuary.tech/content/add \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: multipart/form-data" -F "data=@$FILE"
    fi
done

# List all of the pins ready to be used in a collection
curl -s -X GET https://api.estuary.tech/pinning/pins\?limit\=200 -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" | jq -r '.results[] | .requestid + ", " + .pin.name + ", " + .pin.cid'
