#!/bin/bash
# Run the Auto Loader demo without using Databricks UI

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running Auto Loader Demo (No UI Required)${NC}"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found. Please run from project root.${NC}"
    exit 1
fi

# Step 1: Upload and run the setup notebook
echo -e "\n${GREEN}Step 1: Uploading and running Auto Loader setup notebook${NC}"

cd scripts
# Get SQL warehouse ID from environment
WAREHOUSE_ID=$(grep DATABRICKS_HTTP_PATH ../.env | cut -d'/' -f6)

if [ -n "$WAREHOUSE_ID" ]; then
    echo "Using SQL warehouse: $WAREHOUSE_ID"
    uv run -s upload-and-run-notebook.py \
        --notebook ../databricks-notebooks/01-setup-autoloader-demo.py \
        --workspace-path /Shared/demos/autoloader/setup-autoloader-demo \
        --run \
        --warehouse-id $WAREHOUSE_ID \
        --wait
else
    echo "No SQL warehouse found, using job cluster"
    uv run -s upload-and-run-notebook.py \
        --notebook ../databricks-notebooks/01-setup-autoloader-demo.py \
        --workspace-path /Shared/demos/autoloader/setup-autoloader-demo \
        --run \
        --wait
fi

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to run setup notebook${NC}"
    exit 1
fi

# Step 2: Create some test data
echo -e "\n${GREEN}Step 2: Creating test sensor data${NC}"
cd ../databricks-uploader

# Create test data if it doesn't exist
if [ ! -f "sensor_data.db" ]; then
    uv run -s create_test_sensor_data.py
fi

# Step 3: Upload test data to S3
echo -e "\n${GREEN}Step 3: Uploading test data to S3${NC}"
uv run -s test-upload.py

# Step 4: Query results
echo -e "\n${GREEN}Step 4: Checking results in Databricks${NC}"
cd ../scripts

# Wait a bit for Auto Loader to process
echo "Waiting 30 seconds for Auto Loader to process files..."
sleep 30

# Query the ingestion table
uv run -s run-databricks-sql.py --query "
SELECT 
    COUNT(*) as record_count,
    MIN(_ingested_at) as first_record,
    MAX(_ingested_at) as last_record,
    COUNT(DISTINCT sensor_id) as unique_sensors
FROM expanso-databricks-workspace.sensor_readings.sensor_readings_ingestion
WHERE _ingested_at >= current_timestamp() - INTERVAL 5 MINUTES
"

echo -e "\n${GREEN}✅ Demo setup complete!${NC}"
echo -e "\n${YELLOW}What just happened:${NC}"
echo "1. Uploaded and ran the Auto Loader setup notebook"
echo "2. Created tables and started Auto Loader streams"
echo "3. Generated and uploaded test sensor data to S3"
echo "4. Auto Loader processed the files automatically"
echo "5. Queried results to verify data was ingested"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Upload more data: cd databricks-uploader && uv run -s test-upload.py"
echo "2. Query results: cd scripts && uv run -s run-databricks-sql.py -q 'SELECT * FROM sensor_readings_ingestion LIMIT 10'"
echo "3. Run teardown: uv run -s upload-and-run-notebook.py -n ../databricks-notebooks/02-teardown-autoloader-demo.py -r"

echo -e "\n${YELLOW}View in Databricks UI (optional):${NC}"
echo "Notebook: https://your-workspace.databricks.com/#workspace/Shared/demos/autoloader/setup-autoloader-demo"
echo "SQL Editor: https://your-workspace.databricks.com/sql/editor"