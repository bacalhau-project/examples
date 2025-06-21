#!/bin/bash
set -e

if [ ! -z "$PYTHON_FILE_B64" ]; then
    echo "Decoding base64 Python file..."
    echo "$PYTHON_FILE_B64" | base64 -d > /tmp/script.py
    SCRIPT_PATH="/tmp/script.py"
elif [ ! -z "$PYTHON_FILE" ]; then
    echo "Using provided Python file..."
    echo "$PYTHON_FILE" > /tmp/script.py
    SCRIPT_PATH="/tmp/script.py"
else
    echo "Error: Neither PYTHON_FILE_B64 nor PYTHON_FILE environment variables are set"
    exit 1
fi

# Make the script executable
chmod +x "$SCRIPT_PATH"

# Execute the Python script with any additional arguments
exec python "$SCRIPT_PATH" "$@" 