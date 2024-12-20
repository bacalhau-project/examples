#!/usr/bin/env bash

export NUMBER_OF_JOBS=${NUMBER_OF_JOBS:-10000}
export TIME_BETWEEN_JOBS=${TIME_BETWEEN_JOBS:-30}
export JOBS_PER_BATCH=${JOBS_PER_BATCH:-20}

for ((i=1; i<=NUMBER_OF_JOBS; i++)); do
    echo -n "$(date +"%Y-%m-%d %H:%M:%S") - "
    bacalhau job run --wait=false --id-only stress_job.yaml | tr -d '\n'
    echo ""
    # If mod 5, then wait 30 seconds
    if [ $((i % JOBS_PER_BATCH)) -eq 0 ]; then
        sleep "$TIME_BETWEEN_JOBS" 
    fi
done

