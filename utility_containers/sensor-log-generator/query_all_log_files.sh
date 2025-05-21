#!/usr/bin/env bash

# Give me a simple command that will go to all log files
# in 'docker ps' that are running "sensor-log-generator image"
# and execute "sqlite3 /app/data/sensor_data.db" "select * from sensor_readings limit 2";

# Get all running container IDs
CONTAINER_IDS=$(docker ps -q)

# Iterate through each container ID
for CONTAINER_ID in $CONTAINER_IDS; do
    # Get the container name
    CONTAINER_NAME=$(docker ps --format "{{.Names}}" --filter "id=$CONTAINER_ID")
    
    # Define a temporary local path for the database file
    TEMP_DB_PATH="/tmp/sensor_data_${CONTAINER_ID}.db"

    # Copy the database file from the container to the host
    echo "Copying database from $CONTAINER_NAME ($CONTAINER_ID) to $TEMP_DB_PATH..."
    docker cp "${CONTAINER_ID}:/app/data/sensor_data.db" "$TEMP_DB_PATH"

    if [ -f "$TEMP_DB_PATH" ]; then
        echo "Querying database for $CONTAINER_NAME ($CONTAINER_ID)..."
        # Execute the SQLite query on the local copy
        sqlite3 "$TEMP_DB_PATH" "select id, timestamp, sensor_id, latitude, longitude from sensor_readings limit 2;"
        
        # Clean up the temporary database file
        rm "$TEMP_DB_PATH"
    else
        echo "Failed to copy database from $CONTAINER_NAME ($CONTAINER_ID)."
    fi
    echo "---"
done
