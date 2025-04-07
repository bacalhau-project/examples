#!/usr/bin/bash

FLAG_FILE="/tmp/sync_stop_flag"

while true; do
    if [ -f "$FLAG_FILE" ]; then
        echo "Stop flag detected. Exiting."
        exit 0
    fi

    /app/data/sync.py

    sleep 5
done
