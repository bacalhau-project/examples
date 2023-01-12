#!/bin/bash

# Compresses the directories created by process.sh
# Usage: ./compress.sh /mnt/disks/ethereum/ethereum-etl
# This will compress all the directories in the dir

cd $1
for i in $(seq 0 10000 20000000); do
    if [ -d "output_$i" ]; then
        sudo tar cfz output_$i.tar.gz output_$i
    fi
done
