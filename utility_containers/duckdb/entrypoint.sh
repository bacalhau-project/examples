#!/bin/sh

FINAL_QUERY=""

# If QUERY_B64 is set, decode it and use as query
if [ -n "$QUERY_B64" ]; then
    FINAL_QUERY=$(echo "$QUERY_B64" | base64 -d)
# Otherwise if QUERY is set, use it directly
elif [ -n "$QUERY" ]; then
    FINAL_QUERY="$QUERY"
# If neither is set, show usage help
else
    echo "Error: Neither QUERY nor QUERY_B64 environment variable is set."
    echo "Usage: docker run with either:"
    echo "  -e QUERY='your SQL query here'"
    echo "  -e QUERY_B64='your base64 encoded SQL query here'"
    echo "[other options]"
    exit 1
fi

echo "Running query: $FINAL_QUERY"
./duckdb -c "$FINAL_QUERY"