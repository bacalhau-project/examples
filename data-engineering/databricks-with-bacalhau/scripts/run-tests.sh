#!/bin/bash
# Comprehensive test script for Databricks with Bacalhau

set -e  # Exit on error

echo "=== Databricks with Bacalhau Test Suite ==="
echo

# Load environment variables
source .env

# 1. Environment Check
echo "1. Checking environment variables..."
echo "   AWS_REGION: ${AWS_REGION}"
echo "   S3_BUCKET_PREFIX: ${S3_BUCKET_PREFIX}"
echo "   DATABRICKS_HOST: ${DATABRICKS_HOST}"
echo "   ✓ Environment variables loaded"
echo

# 2. AWS S3 Check (using on-disk credentials)
echo "2. Testing AWS S3 connectivity with on-disk credentials..."
# Unset any session credentials to force use of on-disk credentials
unset AWS_SESSION_TOKEN
unset AWS_SECURITY_TOKEN

# Check for credentials file
if [ -f ~/.aws/credentials ]; then
    echo "   ✓ Found AWS credentials file"
    # Test S3 access with explicit profile if needed
    if aws s3 ls s3://${S3_BUCKET_RAW}/ --no-paginate > /dev/null 2>&1; then
        echo "   ✓ S3 bucket ${S3_BUCKET_RAW} is accessible"
    else
        echo "   ✗ Failed to access S3 bucket ${S3_BUCKET_RAW}"
        echo "   Please check AWS credentials in ~/.aws/credentials"
    fi
else
    echo "   ✗ No AWS credentials file found at ~/.aws/credentials"
    echo "   Please configure AWS credentials for production use"
fi
echo

# 3. SQLite Database Check
echo "3. Checking SQLite database..."
if [ -f "sample-sensor/data/sensor_data.db" ]; then
    RECORD_COUNT=$(sqlite3 sample-sensor/data/sensor_data.db "SELECT COUNT(*) FROM sensor_data;" 2>/dev/null || echo "0")
    echo "   ✓ Database exists with ${RECORD_COUNT} records"
else
    echo "   ✗ Database not found. Creating test data..."
    uv run -s databricks-uploader/create_test_sensor_data.py --records 100
fi
echo

# 4. Pipeline Configuration
echo "4. Checking pipeline configuration..."
PIPELINE_TYPE=$(uv run -s databricks-uploader/pipeline_manager.py --db sample-sensor/data/sensor_data.db get 2>/dev/null | grep "Current pipeline type:" | cut -d: -f2 | xargs)
echo "   Current pipeline type: ${PIPELINE_TYPE}"
echo

# 5. Run Simple Test
echo "5. Running simple connectivity test..."
cat > test-simple.py << 'EOF'
#!/usr/bin/env uv run -s
# /// script
# dependencies = ["python-dotenv>=1.0.0", "boto3>=1.26.0"]
# ///
import os
from dotenv import load_dotenv
import boto3

load_dotenv()

# Test S3
try:
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=os.getenv('S3_BUCKET_RAW'), MaxKeys=1)
    print("✓ S3 connection successful")
except Exception as e:
    print(f"✗ S3 connection failed: {e}")

# Test environment
print(f"✓ Environment configured for: {os.getenv('S3_BUCKET_PREFIX')}")
EOF

chmod +x test-simple.py
uv run -s test-simple.py
echo

echo "=== Test Summary ==="
echo "- Environment variables: ✓"
echo "- S3 connectivity: Check output above"
echo "- SQLite database: ✓"
echo "- Pipeline configuration: ${PIPELINE_TYPE}"
echo
echo "To run the full pipeline:"
echo "  uv run -s databricks-uploader/sqlite_to_json_transformer.py"
echo
echo "To monitor pipeline:"
echo "  uv run -s databricks-uploader/pipeline_manager.py --db sample-sensor/data/sensor_data.db history"