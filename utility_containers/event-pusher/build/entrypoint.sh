#!/bin/sh
set -e

# Check if config.yaml exists
if [ ! -f "/config.yaml" ]; then
    echo "Error: /config.yaml not found"
    exit 1
fi

# Run the event pusher
exec /event-pusher 