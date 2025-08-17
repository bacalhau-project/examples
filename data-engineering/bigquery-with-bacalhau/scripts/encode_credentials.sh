#!/bin/bash
# encode_credentials.sh - Simple script to base64 encode credentials file

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-credentials-file>"
    echo ""
    echo "Example: $0 credentials.json"
    echo ""
    echo "This will output the base64-encoded content of the file"
    exit 1
fi

CREDENTIALS_FILE="$1"

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "Error: File not found: $CREDENTIALS_FILE" >&2
    exit 1
fi

# Base64 encode based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    base64 -i "$CREDENTIALS_FILE" | tr -d '\n'
else
    # Linux
    base64 -w 0 "$CREDENTIALS_FILE" 2>/dev/null || base64 "$CREDENTIALS_FILE" | tr -d '\n'
fi