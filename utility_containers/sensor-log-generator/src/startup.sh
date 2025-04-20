#!/bin/sh

# Clean up old database files if they exist
if [ -f /app/data/sensor_data.db ]; then
    echo "Removing old database file"
    rm -f /app/data/sensor_data.db*
fi

# Run the application
exec uv run -s main.py "$@" 