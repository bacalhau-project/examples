#!/usr/bin/env bash
# Quick setup script with authentication checks

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "DATABRICKS + S3 QUICK SETUP"
echo "=========================================="
echo

# Step 1: Check environment file
echo -e "${BLUE}Step 1: Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Please create .env file with required variables."
    exit 1
fi

source .env
echo -e "${GREEN}✓ Environment file loaded${NC}"
echo

# Step 2: Check AWS authentication
echo -e "${BLUE}Step 2: Checking AWS authentication...${NC}"
if ! aws sts get-caller-identity --no-paginate &>/dev/null; then
    echo -e "${YELLOW}AWS authentication required!${NC}"
    echo
    echo "Please authenticate using AWS SSO:"
    echo "  aws sso login"
    echo
    echo -e "${YELLOW}After authenticating, run this script again.${NC}"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --no-paginate)
echo -e "${GREEN}✓ AWS authenticated (Account: $ACCOUNT_ID)${NC}"
echo

# Step 3: Check Databricks connection
echo -e "${BLUE}Step 3: Testing Databricks connection...${NC}"
if ! uv run -s test-databricks-connection.py > /tmp/databricks-test.log 2>&1; then
    cat /tmp/databricks-test.log
    echo
    echo -e "${RED}ERROR: Databricks connection failed!${NC}"
    echo
    echo "To fix:"
    echo "1. Go to Databricks UI > User Settings > Developer > Access tokens"
    echo "2. Generate a new personal access token"
    echo "3. Update DATABRICKS_TOKEN in your .env file"
    echo "4. Run this script again"
    exit 1
fi
echo -e "${GREEN}✓ Databricks connection successful${NC}"
echo

# Step 4: Check if S3 buckets exist
echo -e "${BLUE}Step 4: Checking S3 buckets...${NC}"
BUCKETS_EXIST=true
for bucket_type in raw schematized filtered emergency; do
    BUCKET_NAME="${S3_BUCKET_PREFIX}-databricks-${bucket_type}-${S3_REGION}"
    if aws s3 ls "s3://${BUCKET_NAME}" --no-paginate &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} ${BUCKET_NAME}"
    else
        echo -e "  ${YELLOW}✗${NC} ${BUCKET_NAME} (not found)"
        BUCKETS_EXIST=false
    fi
done

if [ "$BUCKETS_EXIST" = false ]; then
    echo
    echo -e "${YELLOW}Some S3 buckets are missing.${NC}"
    echo -n "Would you like to create them now? (y/N) "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Creating S3 buckets..."
        cd scripts
        uv run -s create-s3-buckets.sh \
            --prefix "$S3_BUCKET_PREFIX" \
            --region "$S3_REGION" \
            --create-folders
        cd ..
    else
        echo "Please create S3 buckets before proceeding."
        exit 1
    fi
fi
echo

# Step 5: Run the main setup
echo -e "${BLUE}Step 5: Running Databricks S3 access setup...${NC}"
echo
echo "This will:"
echo "1. Generate IAM role configuration"
echo "2. Create IAM role in AWS"
echo "3. Guide you through Databricks credential creation"
echo "4. Set up external locations and tables"
echo
echo -n "Continue? (y/N) "
read -r response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Run the main setup script
./setup-databricks-s3-access.sh

echo
echo -e "${GREEN}=========================================="
echo "✓ QUICK SETUP COMPLETE!"
echo "==========================================${NC}"