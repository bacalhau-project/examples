#!/bin/bash
set -e

# Simple wrapper script for the CosmosDB query tool
# This script forwards all arguments to the Python-based query tool

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
QUERY_SCRIPT="$SCRIPT_DIR/cosmos-uploader/query.py"

if [ ! -f "$QUERY_SCRIPT" ]; then
  echo "Error: Query script not found at $QUERY_SCRIPT"
  exit 1
fi

# Execute with uv run
exec uv run -s "$QUERY_SCRIPT" "$@"