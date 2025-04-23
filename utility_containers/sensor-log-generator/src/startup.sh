#!/bin/sh

# Check if required environment variables are set
if [ -z "$CONFIG_FILE" ]; then
    echo "Error: CONFIG_FILE environment variable is not set"
    exit 1
fi

if [ -z "$IDENTITY_FILE" ]; then
    echo "Error: IDENTITY_FILE environment variable is not set"
    exit 1
fi

# Ensure the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Ensure the identity file exists
if [ ! -f "$IDENTITY_FILE" ]; then
    echo "Error: Identity file not found at $IDENTITY_FILE"
    exit 1
fi

# Run the application with the environment variables
exec uv run -s main.py "$@" 