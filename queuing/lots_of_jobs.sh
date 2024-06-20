#!/usr/bin/env bash

export NUMBER_OF_JOBS=${NUMBER_OF_JOBS:-1000}

for ((i=1; i<=NUMBER_OF_JOBS; i++)); do
    echo -n "$(date +"%Y-%m-%d %H:%M:%S") - "
    bacalhau job run --id-only --wait=0 stress_job.yaml | tr -d '\n'
    echo ""
    # If mod 5, then wait 30 seconds
    if [ $((i % 10)) -eq 0 ]; then
        sleep 30
    fi
done

