#!/bin/bash

TIME_FORMAT="%Y-%m-%d %H:%M:%S"

# Initialize variables
START_TIME=""
END_TIME=$(date --utc +"${TIME_FORMAT}") # Default end time is now
LOG_PATH="/logs/**" # Default log path is all files in /logs, recursively
QUERY=""
OTHER_ARGS=()

# Function to convert relative time to absolute time
convert_time() {
    local input_time="$1"

    if [[ -z "$input_time" ]]; then
        echo "" # Return empty string if no input time
    elif [[ $input_time =~ ^([+-]?[0-9]+)[[:space:]]*(second|sec|minute|min|hour|hr|day|week|month|year)s?$ ]]; then
        date -d "$input_time" --utc +"${TIME_FORMAT}" # Relative time
    else
        echo "$input_time" # Fixed time format
    fi
}

# Decompress any .gz log files under /logs (and all subdirectories).
# The -k (or --keep) flag preserves the original .gz file;
# remove it if you want the .gz files deleted after decompression.
readarray -t gzfiles < <(find /logs -type f -name '*.gz')
count=0
for gzfile in "${gzfiles[@]}"; do
  gunzip -k "$gzfile" && ((count++))
done

echo "Decompressed $count file(s)."

echo "Starting analysis on uncompressed log files..."

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --start-time)
            START_TIME=$(convert_time "$2")
            shift
            ;;
        --end-time)
            END_TIME=$(convert_time "$2")
            shift
            ;;
        --log-path)
            LOG_PATH="$2"
            shift
            ;;
        --query)
            QUERY="$2"
            shift
            ;;
        *)
            OTHER_ARGS+=("$1") # Collect other arguments
            ;;
    esac
    shift
done

# Validate required parameters
if [[ -z "$QUERY" ]]; then
    echo "Error: Query is not set." >&2
    exit 1
fi

if [[ -z "$LOG_PATH" ]]; then
    echo "Error: Log path is not set." >&2
    exit 1
fi

# Check if QUERY contains a CTE
lowercase_query=$(echo "$QUERY" | tr '[:upper:]' '[:lower:]')
if [[ $lowercase_query =~ ^[[:space:]]*with[[:space:]] ]]; then
    echo "Error: The provided query contains a CTE, which is not supported in this context." >&2
    echo "Provided Query: $QUERY" >&2
    exit 1
fi

# Define the schema for nginx access logs
COLUMNS="{'time_local': 'TIMESTAMP_MS', 'remote_addr': 'STRING', 'remote_user': 'STRING', 'http_method': 'STRING', 'request': 'STRING', 'http_version': 'STRING', 'status': 'INTEGER', 'body_bytes_sent': 'INTEGER', 'http_referer': 'STRING', 'http_user_agent': 'STRING'}";

# Construct the DuckDB query
TIME_CONDITION=""
if [[ -n "$START_TIME" && -n "$END_TIME" ]]; then
    TIME_CONDITION="WHERE time_local BETWEEN '$START_TIME' AND '$END_TIME'"
elif [[ -n "$START_TIME" ]]; then
    TIME_CONDITION="WHERE time_local >= '$START_TIME'"
elif [[ -n "$END_TIME" ]]; then
    TIME_CONDITION="WHERE time_local <= '$END_TIME'"
fi

FULL_QUERY="
WITH logs AS (
    SELECT * FROM read_json(['$LOG_PATH'], columns=$COLUMNS, format='newline_delimited', ignore_errors=true)
    $TIME_CONDITION
)
$QUERY;
"

# Execute the DuckDB query
duckdb "${OTHER_ARGS[@]}" -c "$FULL_QUERY"
