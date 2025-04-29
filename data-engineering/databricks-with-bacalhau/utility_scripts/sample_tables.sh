#!/bin/bash

# Default config path
CONFIG_PATH="config.yaml"
if [ -n "$1" ]; then
    CONFIG_PATH="$1"
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Please install jq."
    exit 1
fi

# ANSI color codes for better formatting
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get tables from confirm_tables.py
TABLES=("raw_logs" "log_results" "log_aggregates" "emergency_logs")

echo -e "${BOLD}${BLUE}===== PostgreSQL Table Statistics =====${NC}"
echo

# First, get counts for all tables efficiently using metadata
echo -e "${BOLD}${YELLOW}Table Row Counts:${NC}"
echo -e "${BOLD}----------------------------------------${NC}"

# Use a metadata query to get row counts more efficiently
COUNT_QUERY="SELECT 
  relname as table_name,
  n_live_tup as row_count
FROM pg_stat_user_tables 
WHERE schemaname = 'log_analytics' 
  AND relname IN ('raw_logs', 'log_results', 'log_aggregates', 'emergency_logs')
ORDER BY relname;"

# Run the count query with JSON output
COUNT_RESULTS=$(uv run -s postgres-uploader/query.py --config "$CONFIG_PATH" --query "$COUNT_QUERY" --json)

# Extract counts using jq for each table
for TABLE in "${TABLES[@]}"; do
    # Use jq to extract the row count for this table, default to 0 if not found
    COUNT=$(echo "$COUNT_RESULTS" | jq -r ".[] | select(.table_name == \"$TABLE\") | .row_count // 0")
    printf "${GREEN}%-20s${NC} | ${BOLD}%s${NC}\n" "$TABLE" "$COUNT rows"
done
echo

# Now sample each table
echo -e "${BOLD}${YELLOW}Table Samples (10 rows each):${NC}"

for TABLE in "${TABLES[@]}"; do
    echo -e "${BOLD}${BLUE}=== $TABLE ===${NC}"
    
    # Get sample with JSON formatting
    SAMPLE_QUERY="SELECT * FROM log_analytics.$TABLE LIMIT 10;"
    SAMPLE_RESULT=$(uv run -s postgres-uploader/query.py --config "$CONFIG_PATH" --query "$SAMPLE_QUERY" --json)
    
    # Check if we got results
    if [[ $(echo "$SAMPLE_RESULT" | jq '. | length') -eq 0 ]]; then
        echo -e "${YELLOW}No Rows${NC}"
    else
        # Print column headers without excessive spacing
        echo "$SAMPLE_RESULT" | jq -r '.[0] | keys_unsorted | join("  ")'
        echo -e "${BOLD}----------------------------------------${NC}"
        
        # Print each row without excessive spacing
        echo "$SAMPLE_RESULT" | jq -r '.[] | [.[] | tostring] | join("  ")'
    fi
    
    echo -e "${BOLD}----------------------------------------${NC}"
    echo
done

echo -e "${BOLD}${BLUE}===== End of Report =====${NC}"