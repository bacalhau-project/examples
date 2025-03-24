#!/bin/bash
set -e

if [ ! -z "$FILE_CONTENTS_B64" ]; then
    echo "Decoding base64 file contents..."
    echo "$FILE_CONTENTS_B64" | base64 -d > /tmp/file.sh
    FILE_PATH="/tmp/file.sh"
elif [ ! -z "$FILE_PATH" ]; then
    echo "Using provided file path..."
    FILE_PATH="/tmp/file.sh"
else
    echo "Error: Neither FILE_CONTENTS_B64 nor FILE_PATH environment variables are set"
    exit 1
fi

# Make the script executable
chmod +x "$FILE_PATH"

# Execute the script with any additional arguments
exec uv run -s "$FILE_PATH" "$@" 