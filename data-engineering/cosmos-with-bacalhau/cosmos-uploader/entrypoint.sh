#!/bin/bash
set -e

# Default values
CONFIG_PATH=${CONFIG_PATH:-"/tmp/config.yaml"}
INPUT_FILE=${INPUT_FILE:-"/var/log/app/access.log"}
CHUNK_SIZE=${CHUNK_SIZE:-500000}
BATCH_SIZE=${BATCH_SIZE:-1000}
MAX_WORKERS=${MAX_WORKERS:-10}
CLEAN_MODE=${CLEAN_MODE:-false}

# Check if we need to decode the config file from base64
if [ -n "$CONFIG_FILE_B64" ]; then
    echo "Decoding config file from base64..."
    echo "$CONFIG_FILE_B64" | base64 -d > "$CONFIG_PATH"
fi

# Check if we need to decode the Python file from base64
if [ -n "$PYTHON_FILE_B64" ]; then
    echo "Decoding Python file from base64..."
    echo "$PYTHON_FILE_B64" | base64 -d > /tmp/process.py
    SCRIPT_PATH="/tmp/process.py"
else
    # Determine which script to run based on CLEAN_MODE
    if [ "$CLEAN_MODE" = "true" ]; then
        SCRIPT_PATH="/app/log_process_cosmos_clean.py"
    else
        SCRIPT_PATH="/app/log_process_cosmos.py"
    fi
fi

# Print configuration
echo "Configuration:"
echo "  CONFIG_PATH: $CONFIG_PATH"
echo "  INPUT_FILE: $INPUT_FILE"
echo "  CHUNK_SIZE: $CHUNK_SIZE"
echo "  BATCH_SIZE: $BATCH_SIZE"
echo "  MAX_WORKERS: $MAX_WORKERS"
echo "  CLEAN_MODE: $CLEAN_MODE"
echo "  SCRIPT_PATH: $SCRIPT_PATH"

# Run the script
echo "Starting log processing..."
python "$SCRIPT_PATH" \
    --config "$CONFIG_PATH" \
    --input "$INPUT_FILE" \
    --chunk-size "$CHUNK_SIZE" \
    --batch-size "$BATCH_SIZE" \
    --max-workers "$MAX_WORKERS"

# Exit with the script's exit code
exit $? 