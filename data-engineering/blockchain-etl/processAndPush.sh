#!/bin/bash

# Process all the data from ethereum and push to Estuary
# Usage: ./processAndPush.sh 1000000 1999999 /mnt/disks/ethereum/ethereum-etl
# This will process blocks 1000000 to 1999999 in 10,000 block chunks, compress, and upload to Estuary

# set -e # Don't set -e, because ethereumetl repeatedly fails and needs to retry.

if [ "$#" -ne 3 ]; then
    echo "Illegal number of parameters. E.g. ./processAndPush.sh 1000000 1999999 /dir"
    exit 1
fi

if [ -z "$TOKEN" ]; then
    echo "TOKEN is not set, please export your Estuary API token as TOKEN"
    exit 1
fi

for i in $(seq $1 10000 $2); do
    echo "Processing block $i to $(expr $i + 9999) and saving to $3/output_$i"
    sudo ethereumetl export_all --start $i --end $(expr $i + 9999)  --provider-uri file:///mnt/disks/ethereum/geth.ipc -o $3/output_$i; 
    TAR_FILE="$3/output_$i.tar.gz"
    echo "Compressing $3/output_$i to $TAR_FILE"
    (cd $3 && sudo tar cfz output_$i.tar.gz output_$i)
    echo "Uploading $TAR_FILE"
    curl \
        -s -D - \
        --max-time 120 \
        --retry 5 \
        -X POST https://upload.estuary.tech/content/add \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: multipart/form-data" -F "data=@$TAR_FILE"
done
