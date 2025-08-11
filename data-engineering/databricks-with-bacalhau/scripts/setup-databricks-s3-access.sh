#!/usr/bin/env bash
# Complete setup script for Databricks S3 access

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "DATABRICKS S3 ACCESS SETUP"
echo "=========================================="
echo

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Please create .env file with required variables."
    exit 1
fi

# Source environment variables
source .env

# Check AWS authentication first
echo -e "${BLUE}Checking AWS authentication...${NC}"
if ! aws sts get-caller-identity --no-paginate &>/dev/null; then
    echo -e "${YELLOW}AWS authentication required!${NC}"
    echo
    echo "Would you like to authenticate now? (y/N) "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        ./aws-sso-login.sh
        echo
    else
        echo
        echo -e "${RED}ERROR: AWS authentication required!${NC}"
        echo "Please run: aws sso login"
        echo "Then run this script again."
        exit 1
    fi
fi

# Verify authentication succeeded
if aws sts get-caller-identity --no-paginate &>/dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --no-paginate)
    echo -e "${GREEN}✓ AWS authenticated (Account: $ACCOUNT_ID)${NC}"
else
    echo -e "${RED}ERROR: AWS authentication failed${NC}"
    exit 1
fi
echo

# Verify required variables
REQUIRED_VARS=(
    "DATABRICKS_HOST"
    "DATABRICKS_HTTP_PATH"
    "DATABRICKS_TOKEN"
    "S3_BUCKET_PREFIX"
    "S3_REGION"
)

echo "Checking environment variables..."
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo -e "${RED}ERROR: $var is not set in .env${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} $var"
done
echo

# Test Databricks connection first
echo -e "${BLUE}Testing Databricks connection...${NC}"
if ! uv run -s test-databricks-connection.py; then
    echo
    echo -e "${RED}ERROR: Databricks connection test failed!${NC}"
    echo "Please fix the connection issues before proceeding."
    exit 1
fi
echo

# Step 1: Generate credential values
echo -e "${BLUE}Step 1: Generating credential values...${NC}"
cd scripts
uv run -s setup-databricks-credentials.py
cd ..
echo

# Step 2: Create IAM role
echo -e "${BLUE}Step 2: Creating IAM role in AWS...${NC}"
./scripts/create-databricks-iam-role.sh
echo

# Step 3: Wait for user to create credential in Databricks
echo -e "${YELLOW}=========================================="
echo "ACTION REQUIRED:"
echo "==========================================${NC}"
echo
echo "Please complete these steps in Databricks UI:"
echo
echo "1. Go to: ${DATABRICKS_HOST}"
echo "2. Navigate to: Data > Storage Credentials"
echo "3. Click 'Create credential'"
echo "4. Copy and paste the values shown above"
echo "5. Click 'Create'"
echo
echo -e "${YELLOW}Press ENTER when you have created the credential...${NC}"
read -r

# Step 4: Set up external locations
echo -e "${BLUE}Step 4: Setting up external locations and tables...${NC}"
cd scripts
uv run -s setup-databricks-external-locations.py
cd ..
echo

# Step 5: Test the setup
echo -e "${BLUE}Step 5: Testing the setup...${NC}"
echo

# Create a test file
TEST_FILE="/tmp/test-sensor-data.json"
cat > "$TEST_FILE" << EOF
{"id": 1, "sensor_id": "test-001", "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S)Z", "temperature": 22.5, "humidity": 45.0, "pressure": 1013.25, "battery_level": 85.0, "signal_strength": -45, "location_lat": 37.7749, "location_lon": -122.4194, "firmware_version": "1.0.0", "error_count": 0, "last_maintenance": "2024-01-01T00:00:00Z", "status": "active", "data_quality": "good"}
EOF

# Upload test file to raw bucket
RAW_BUCKET="${S3_BUCKET_PREFIX}-databricks-raw-${S3_REGION}"
echo "Uploading test file to S3..."
aws s3 cp "$TEST_FILE" "s3://${RAW_BUCKET}/test-sensor-data.json" --no-paginate

# Clean up
rm -f "$TEST_FILE"

echo
echo -e "${GREEN}=========================================="
echo "✓ SETUP COMPLETE!"
echo "==========================================${NC}"
echo
echo "What's been configured:"
echo "  - IAM role with S3 permissions"
echo "  - Databricks storage credential"
echo "  - External locations for all S3 buckets"
echo "  - Delta tables for each data type"
echo "  - Test file uploaded to raw bucket"
echo
echo "Next steps:"
echo "1. Start the uploader:"
echo "   ./start-databricks-uploader.sh"
echo
echo "2. Import and run the Auto Loader notebook:"
echo "   databricks-notebooks/autoloader-simple.py"
echo
echo "3. Query your data:"
echo "   SELECT * FROM ${DATABRICKS_DATABASE}.sensor_readings_raw LIMIT 10;"
echo