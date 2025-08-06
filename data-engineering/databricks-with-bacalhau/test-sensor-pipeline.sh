#!/bin/bash

# Test script to verify the sensor and pipeline are working
# Run from the main databricks-with-bacalhau directory

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Testing Databricks S3 Pipeline${NC}"
echo "================================="

# Check database exists
if [ -f "sample-sensor/data/sensor_data.db" ]; then
    echo -e "${GREEN}✓ Database exists${NC}"
    
    # Check recent data
    LATEST=$(sqlite3 sample-sensor/data/sensor_data.db "SELECT MAX(timestamp) FROM sensor_readings" 2>/dev/null || echo "none")
    COUNT=$(sqlite3 sample-sensor/data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings" 2>/dev/null || echo "0")
    
    echo "  Latest timestamp: $LATEST"
    echo "  Total records: $COUNT"
else
    echo -e "${RED}✗ Database not found${NC}"
    echo "  Run ./start-sensor-local.sh to start generating data"
fi

echo ""

# Check upload state
if [ -f "sample-sensor/data/sensor_data.db" ]; then
    echo -e "${GREEN}Upload State:${NC}"
    # Check if upload_state table exists
    TABLE_EXISTS=$(sqlite3 sample-sensor/data/sensor_data.db "SELECT name FROM sqlite_master WHERE type='table' AND name='upload_state'" 2>/dev/null || echo "")
    
    if [ -n "$TABLE_EXISTS" ]; then
        sqlite3 sample-sensor/data/sensor_data.db -header -column \
            "SELECT table_name, scenario, last_timestamp, 
                    datetime(last_upload_at, 'localtime') as last_upload 
             FROM upload_state ORDER BY last_upload_at DESC LIMIT 5" 2>/dev/null || echo "  No upload state found"
    else
        echo "  Upload state table not yet created"
    fi
fi

echo ""

# Check AWS credentials
echo -e "${GREEN}AWS Configuration:${NC}"
if [ -n "$AWS_SESSION_TOKEN" ]; then
    echo "  ✓ Session token is set"
    echo "  ✓ Temporary credentials configured"
elif [ -n "$AWS_ACCESS_KEY_ID" ]; then
    echo "  ✓ Access key is set"
    echo "  ⚠ Using permanent credentials (consider using session tokens)"
else
    echo "  ✗ No AWS credentials configured"
    echo "  Run: source set-environment.sh"
fi

echo ""

# Check S3 buckets
echo -e "${GREEN}S3 Buckets:${NC}"
if [ -n "$AWS_ACCESS_KEY_ID" ] || [ -n "$AWS_SESSION_TOKEN" ]; then
    # Try to list buckets
    BUCKETS=$(aws s3 ls 2>/dev/null | grep -E "expanso-databricks-(raw|schematized|aggregated|emergency|regional)" || echo "")
    if [ -n "$BUCKETS" ]; then
        echo "$BUCKETS" | while read -r line; do
            echo "  ✓ $line"
        done
    else
        echo "  ⚠ No Databricks buckets found"
        echo "  Run: scripts/create-s3-buckets-admin.sh"
    fi
else
    echo "  Cannot check - AWS credentials not configured"
fi

echo ""
echo -e "${GREEN}Quick Commands:${NC}"
echo "  Start sensor:       ./start-sensor-local.sh"
echo "  Run uploader once:  uv run -s databricks-uploader/sqlite_to_s3_uploader.py --config databricks-uploader-config.yaml --once"
echo "  Run continuous:     uv run -s databricks-uploader/sqlite_to_s3_uploader.py --config databricks-uploader-config.yaml"
echo "  View state:         uv run -s databricks-uploader/upload_state_manager.py --db sample-sensor/data/sensor_data.db list"
echo "  Set pipeline:       uv run -s pipeline-manager/pipeline_controller.py --db sample-sensor/data/sensor_data.db set raw"
echo "  Monitor uploads:    watch -n 5 './test-sensor-pipeline.sh'"