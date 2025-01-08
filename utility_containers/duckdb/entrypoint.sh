#!/bin/sh
# Check if the QUERY environment variable is set
if [ -z "$QUERY" ]; then
  echo "Error: QUERY environment variable is not set."
  echo "Usage: docker run -e QUERY='your SQL query here' [other options]"
  exit 1
fi

# Execute the query using DuckDB
./duckdb -c "$QUERY"