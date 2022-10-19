#!/bin/bash
source /gunicorn/set_env.sh

if [ "$1" = "update" ]; then
    echo "Updating database..."
    curl -s "http://localhost/updateDB"
    echo "Done."
elif [ "$1" = "reset" ]; then
    echo "Resetting database..."
    curl -s "http://localhost/resetDB?key=${SQLITE_KEY}"
    echo "Done."
else
    echo "Usage: $0 update|reset"
    exit 1
fi