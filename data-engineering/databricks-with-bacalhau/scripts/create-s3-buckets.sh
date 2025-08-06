#!/bin/bash
# Create S3 buckets for Databricks pipeline using AWS SSO credentials

set -e

# Configuration
S3_BUCKET_PREFIX="${S3_BUCKET_PREFIX:-expanso}"
AWS_REGION="${AWS_REGION:-us-west-2}"

echo "Creating S3 Buckets for Databricks Pipeline"
echo "==========================================="
echo "Bucket Prefix: $S3_BUCKET_PREFIX"
echo "AWS Region: $AWS_REGION"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "Error: AWS CLI not configured or SSO session expired"
    echo "Please run: aws sso login"
    exit 1
fi

echo "AWS Identity:"
aws sts get-caller-identity --output table
echo ""

# Buckets to create
BUCKETS=(
    "${S3_BUCKET_PREFIX}-databricks-ingestion-${AWS_REGION}"
    "${S3_BUCKET_PREFIX}-databricks-validated-${AWS_REGION}"
    "${S3_BUCKET_PREFIX}-databricks-enriched-${AWS_REGION}"
    "${S3_BUCKET_PREFIX}-databricks-aggregated-${AWS_REGION}"
    "${S3_BUCKET_PREFIX}-databricks-checkpoints-${AWS_REGION}"
    "${S3_BUCKET_PREFIX}-databricks-metadata-${AWS_REGION}"
)

# Create buckets
echo "Creating buckets..."
for bucket in "${BUCKETS[@]}"; do
    echo -n "  Creating $bucket... "
    
    if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
        echo "already exists"
    else
        if aws s3api create-bucket \
            --bucket "$bucket" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION" 2>/dev/null; then
            echo "✓ created"
            
            # Enable versioning
            aws s3api put-bucket-versioning \
                --bucket "$bucket" \
                --versioning-configuration Status=Enabled
            
            # Enable encryption
            aws s3api put-bucket-encryption \
                --bucket "$bucket" \
                --server-side-encryption-configuration '{
                    "Rules": [{
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }]
                }'
        else
            echo "✗ failed"
        fi
    fi
done

# Create folder structure
echo -e "\nCreating folder structure..."
FOLDERS=(
    "${S3_BUCKET_PREFIX}-databricks-ingestion-${AWS_REGION}/ingestion/"
    "${S3_BUCKET_PREFIX}-databricks-validated-${AWS_REGION}/validated/"
    "${S3_BUCKET_PREFIX}-databricks-enriched-${AWS_REGION}/enriched/"
    "${S3_BUCKET_PREFIX}-databricks-aggregated-${AWS_REGION}/aggregated/"
)

for folder in "${FOLDERS[@]}"; do
    echo -n "  Creating folder s3://$folder... "
    if echo "" | aws s3 cp - "s3://$folder.keep" 2>/dev/null; then
        echo "✓"
    else
        echo "✗"
    fi
done

# List created buckets
echo -e "\nCreated buckets:"
aws s3 ls | grep "${S3_BUCKET_PREFIX}-databricks" | awk '{print "  - " $3}'

echo -e "\n✓ S3 bucket creation complete!"
echo ""
echo "Next steps:"
echo "1. The IAM role 'databricks-unity-catalog-expanso-role' needs access to these buckets"
echo "2. Update the storage credential in Databricks to use these buckets"
echo "3. Create external locations in Databricks"