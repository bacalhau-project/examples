#!/bin/bash

# Test S3 access permissions for the current AWS user
# This helps diagnose what permissions you have

# Disable AWS CLI pager
export AWS_PAGER=""

echo "Testing S3 Access Permissions"
echo "============================="
echo ""

# Get current user identity
echo "Current AWS Identity:"
aws sts get-caller-identity || {
    echo "❌ Cannot get AWS identity. Check your credentials."
    exit 1
}
echo ""

# Test bucket prefix
PREFIX="${1:-expanso}"
REGION="${2:-us-west-2}"

echo "Testing access to buckets with prefix: ${PREFIX}"
echo "Region: ${REGION}"
echo ""

# Test operations
SCENARIOS=("raw" "schematized" "aggregated" "emergency" "regional")

for scenario in "${SCENARIOS[@]}"; do
    bucket_name="${PREFIX}-databricks-${scenario}-${REGION}"
    echo "Testing bucket: ${bucket_name}"
    
    # Test 1: List bucket
    echo -n "  List bucket: "
    if aws s3 ls "s3://${bucket_name}" >/dev/null 2>&1; then
        echo "✅ OK"
    else
        echo "❌ Failed"
    fi
    
    # Test 2: Write object
    echo -n "  Write object: "
    TEST_FILE="test-${RANDOM}.txt"
    if echo "test content" | aws s3 cp - "s3://${bucket_name}/${TEST_FILE}" >/dev/null 2>&1; then
        echo "✅ OK"
        
        # Test 3: Read object (only if write succeeded)
        echo -n "  Read object: "
        if aws s3 cp "s3://${bucket_name}/${TEST_FILE}" - >/dev/null 2>&1; then
            echo "✅ OK"
        else
            echo "❌ Failed"
        fi
        
        # Clean up test file
        aws s3 rm "s3://${bucket_name}/${TEST_FILE}" >/dev/null 2>&1
    else
        echo "❌ Failed"
        echo "  Read object: ⚠️  Skipped (no test file)"
    fi
    
    echo ""
done

echo "Permission Summary:"
echo "==================="
echo ""
echo "If you see failures above, you may need:"
echo "1. s3:ListBucket permission for listing"
echo "2. s3:PutObject permission for writing"
echo "3. s3:GetObject permission for reading"
echo ""
echo "For bucket creation/configuration, you also need:"
echo "- s3:CreateBucket"
echo "- s3:PutBucketVersioning"
echo "- s3:PutBucketEncryption"
echo "- s3:PutBucketTagging"
echo "- s3:PutLifecycleConfiguration"