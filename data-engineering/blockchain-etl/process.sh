#!/bin/bash

# Process x blocks of data from ethereum
# Usage: ./process.sh 1000000 1999999 /mnt/disks/ethereum/ethereum-etl
# This will process blocks 1000000 to 1999999 in 10,000 block chunks and save to the dir

# Note: We can't do this in one go because it's too much data

# set -e # Don't set -e, because ethereumetl repeatedly fails and needs to retry.

if [ "$#" -ne 3 ]; then
    echo "Illegal number of parameters. E.g. ./process.sh 1000000 1999999 /dir"
    exit 1
fi

for i in $(seq $1 10000 $2); do 
    sudo ethereumetl export_all --start $i --end $(expr $i + 9999)  --provider-uri file:///mnt/disks/ethereum/geth.ipc -o $3/output_$i; 
done

# Assert that all the directories are actually there, since ethereumetl is unreliable
for i in $(seq $1 10000 $2); do 
    if [ ! -d "$3/output_$i" ]; then
        echo "Directory $3/output_$i does not exist"
        exit 1
    fi
done
