#!/bin/bash

# Test Autoloader with production credentials to replicate production deployment
# This ensures local testing matches exactly what will happen in production

set -e

# Default values
PREFIX=""
REGION="us-west-2"
# Determine credentials directory based on where script is run from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CREDENTIALS_DIR="${PROJECT_ROOT}/credentials"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --credentials-dir)
            CREDENTIALS_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --prefix PREFIX [--region REGION] [--credentials-dir DIR]"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$PREFIX" ]; then
    echo "Error: --prefix is required"
    echo "Usage: $0 --prefix PREFIX [--region REGION] [--credentials-dir DIR]"
    exit 1
fi

PROD_ENV_FILE="${CREDENTIALS_DIR}/${PREFIX}-production.env"

echo "============================================="
echo "🧪 Testing Autoloader with Production Credentials"
echo "============================================="
echo "Prefix: $PREFIX"
echo "Region: $REGION"
echo "Credentials: $PROD_ENV_FILE"
echo ""

# Check if production credentials exist
if [ ! -f "$PROD_ENV_FILE" ]; then
    echo "❌ Production credentials not found: $PROD_ENV_FILE"
    echo "Run create-production-credentials.sh first:"
    echo "  ./scripts/create-production-credentials.sh --prefix $PREFIX --region $REGION"
    exit 1
fi

# Clear any existing AWS environment variables to ensure we use production credentials
echo "🧹 Clearing existing AWS environment variables..."
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY  
unset AWS_SESSION_TOKEN
unset AWS_DEFAULT_REGION
unset AWS_PROFILE

# Source production credentials
echo "🔑 Loading production credentials..."
source "$PROD_ENV_FILE"

# Verify credentials are loaded
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "❌ Failed to load production credentials from $PROD_ENV_FILE"
    exit 1
fi

echo "✅ Production credentials loaded:"
echo "  Access Key: ${AWS_ACCESS_KEY_ID:0:10}***"
echo "  Region: $AWS_DEFAULT_REGION"

# Test AWS access
echo ""
echo "🔍 Testing AWS access with production credentials..."
IDENTITY=$(aws sts get-caller-identity --query Arn --output text --no-cli-pager 2>/dev/null || echo "FAILED")
if [[ "$IDENTITY" == "FAILED" ]]; then
    echo "❌ Cannot assume production credentials"
    exit 1
else
    echo "✅ Using identity: $IDENTITY"
fi

# Test S3 bucket access
echo ""
echo "📁 Testing S3 bucket access..."
SCENARIOS=("raw" "schematized" "filtered" "emergency" "checkpoints")
ALL_ACCESSIBLE=true

for scenario in "${SCENARIOS[@]}"; do
    bucket_var="S3_BUCKET_$(echo ${scenario} | tr '[:lower:]' '[:upper:]')"
    bucket_name=$(eval echo \$${bucket_var})
    
    if [ -z "$bucket_name" ]; then
        echo "  ❌ $bucket_var not set in environment"
        ALL_ACCESSIBLE=false
        continue
    fi
    
    if aws s3 --no-cli-pager ls "s3://${bucket_name}" >/dev/null 2>&1; then
        echo "  ✅ $bucket_name - accessible"
    else
        echo "  ❌ $bucket_name - not accessible"
        ALL_ACCESSIBLE=false
    fi
done

if [ "$ALL_ACCESSIBLE" != true ]; then
    echo ""
    echo "❌ Some S3 buckets are not accessible. Check permissions."
    exit 1
fi

# Navigate to databricks-uploader directory
echo ""
echo "📂 Navigating to databricks-uploader directory..."
DATABRICKS_UPLOADER_DIR="${PROJECT_ROOT}/databricks-uploader"
cd "$DATABRICKS_UPLOADER_DIR" || {
    echo "❌ Cannot find databricks-uploader directory at: $DATABRICKS_UPLOADER_DIR"
    exit 1
}

# Test autoloader status with production credentials
echo ""
echo "⚡ Testing Autoloader status with production credentials..."
if uv run -s autoloader_main.py status; then
    echo "✅ Autoloader status check successful with production credentials"
else
    echo "❌ Autoloader status check failed"
    exit 1
fi

# Test basic autoloader functionality
echo ""
echo "🧪 Testing basic Autoloader functionality..."

# Create test data if it doesn't exist
if [ ! -f "sensor_data.db" ]; then
    echo "📊 Creating test data..."
    if ! python create_test_sensor_data.py; then
        echo "❌ Failed to create test data"
        exit 1
    fi
fi

# Test data processing with production credentials
echo "📈 Testing data processing with production credentials..."
if uv run -s autoloader_main.py process --db-path sensor_data.db; then
    echo "✅ Data processing successful with production credentials"
else
    echo "❌ Data processing failed"
    exit 1
fi

# Final status check
echo ""
echo "🔍 Final status check..."
if uv run -s autoloader_main.py status; then
    echo "✅ Final status check successful"
else
    echo "❌ Final status check failed"
    exit 1
fi

echo ""
echo "============================================="
echo "✅ Production Credentials Test Complete!"
echo "============================================="
echo ""
echo "🎯 Summary:"
echo "  • Production credentials work correctly"
echo "  • All S3 buckets are accessible"
echo "  • Autoloader pipeline functions properly"
echo "  • Data processing completed successfully"
echo ""
echo "🚀 Ready for production deployment!"
echo ""
echo "📦 To deploy to production nodes:"
echo "  1. Copy credentials/${PREFIX}-production.env to each node"
echo "  2. Source the environment file on each node"
echo "  3. Run the autoloader commands on each node"
echo ""
echo "💡 This test replicates exactly what will happen in production."
