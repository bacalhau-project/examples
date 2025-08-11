#!/bin/bash
# Simple script to set pipeline type directly in the database

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DB_PATH="databricks-uploader/state/pipeline_config.db"
PIPELINE_TYPE="${1:-}"

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ️${NC} $1"
}

# Check if pipeline type is provided
if [ -z "$PIPELINE_TYPE" ]; then
    echo "Usage: $0 <pipeline_type>"
    echo ""
    echo "Available pipeline types:"
    echo "  - raw (default)"
    echo "  - validated"
    echo "  - enriched"
    echo "  - aggregated"
    echo ""
    echo "Current pipeline configuration:"
    sqlite3 "$DB_PATH" "SELECT printf('  Pipeline: %s (created: %s)', pipeline_type, created_at) FROM pipeline_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1;" 2>/dev/null || echo "  No active pipeline configured"
    exit 1
fi

# Validate pipeline type
case "$PIPELINE_TYPE" in
    raw|validated|enriched|aggregated)
        ;;
    *)
        print_error "Invalid pipeline type: $PIPELINE_TYPE"
        echo "Valid types: raw, validated, enriched, aggregated"
        exit 1
        ;;
esac

# Update the pipeline configuration
print_info "Setting pipeline type to: $PIPELINE_TYPE"

# Deactivate current config and insert new one
sqlite3 "$DB_PATH" << EOF
BEGIN TRANSACTION;
UPDATE pipeline_config SET is_active = 0;
INSERT INTO pipeline_config (pipeline_type, created_at, created_by, is_active)
VALUES ('$PIPELINE_TYPE', datetime('now'), 'set-pipeline.sh', 1);
COMMIT;
EOF

if [ $? -eq 0 ]; then
    print_success "Pipeline updated to: $PIPELINE_TYPE"
    
    # Show the update
    echo ""
    echo "Current configuration:"
    sqlite3 "$DB_PATH" << EOF
.mode column
.headers on
SELECT 
    pipeline_type as "Pipeline Type",
    created_at as "Updated At",
    created_by as "Updated By"
FROM pipeline_config 
WHERE is_active = 1;
EOF
else
    print_error "Failed to update pipeline"
    exit 1
fi