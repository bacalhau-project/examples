#!/bin/bash
PORT=${2:-"80"}
if [ "$1" = "update" ]; then
    echo "Updating database..."
    curl -s "http://localhost:${PORT}/updateDB"
    echo "Done."
elif [ "$1" = "reset" ]; then
    echo "Resetting database..."
    curl -X POST "http://localhost:${PORT}/resetDB"
    echo "Done."
else
    echo "Usage: $0 update|reset"
    exit 1
fi