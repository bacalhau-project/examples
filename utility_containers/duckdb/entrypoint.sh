#!/bin/bash
set -eo pipefail  # Exit on error

# Add error handling for invalid SQL
if ! duckdb -c "SELECT 1;" > /dev/null 2>&1; then
    echo "Error: DuckDB installation appears broken"
    exit 1
fi

DUCKDB_FLAGS=()

# If first argument doesn't start with -, treat it as a query and add -c
if [[ $# -gt 0 && "$1" != -* ]]; then
    DUCKDB_FLAGS+=("-c" "$1")
    shift
    DUCKDB_FLAGS+=("$@")
else
    DUCKDB_FLAGS+=("$@")
fi

# Execute duckdb with all flags
exec duckdb "${DUCKDB_FLAGS[@]}"