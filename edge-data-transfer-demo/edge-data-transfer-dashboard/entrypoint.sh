#!/bin/sh
set -e

# Check Bacalhau status
echo "Checking Bacalhau status..."
if ! /usr/local/bin/bacalhau node list; then
    echo "Error: Failed to connect to Bacalhau"
    exit 1
fi

# Start the Next.js application
echo "Starting Next.js application..."
exec /usr/local/bin/npm run start -- -H 0.0.0.0
