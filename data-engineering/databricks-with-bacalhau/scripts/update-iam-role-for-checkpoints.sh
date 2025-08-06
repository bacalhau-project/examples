#!/bin/bash

# Update IAM role to include checkpoints bucket access

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get values from saved configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="${SCRIPT_DIR}/databricks-credential-values.json"

if [ ! -f "$VALUES_FILE" ]; then
    echo -e "${RED}ERROR: databricks-credential-values.json not found!${NC}"
    echo "Please run setup-databricks-credentials.py first."
    exit 1
fi

# Extract values
ROLE_NAME=$(jq -r '.role_name' "$VALUES_FILE")
AWS_ACCOUNT_ID=$(jq -r '.aws_account_id' "$VALUES_FILE")

# Get prefix and region from environment or use defaults
PREFIX="${S3_BUCKET_PREFIX:-expanso}"
REGION="${S3_REGION:-us-west-2}"

# If not in environment, try to extract from bucket names in the existing policy
if [ "$PREFIX" = "expanso" ] && [ -f "$VALUES_FILE" ]; then
    # Try to extract from existing bucket ARNs in the permissions policy
    BUCKET_ARN=$(jq -r '.permissions_policy.Statement[0].Resource // ""' "$VALUES_FILE" 2>/dev/null)
    if [[ "$BUCKET_ARN" =~ arn:aws:s3:::([^-]+)-databricks-([^-]+)-([^/]+) ]]; then
        PREFIX="${BASH_REMATCH[1]}"
        REGION="${BASH_REMATCH[3]}"
    fi
fi

echo "Updating IAM role to include checkpoints bucket..."
echo "Role: $ROLE_NAME"
echo "Prefix: $PREFIX"
echo "Region: $REGION"

# Create updated policy document
POLICY_NAME="${ROLE_NAME}-policy"
POLICY_FILE="${SCRIPT_DIR}/updated-permissions-policy.json"

cat > "$POLICY_FILE" << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetLifecycleConfiguration",
                "s3:PutLifecycleConfiguration"
            ],
            "Resource": [
                "arn:aws:s3:::${PREFIX}-databricks-ingestion-${REGION}/*",
                "arn:aws:s3:::${PREFIX}-databricks-ingestion-${REGION}",
                "arn:aws:s3:::${PREFIX}-databricks-validated-${REGION}/*",
                "arn:aws:s3:::${PREFIX}-databricks-validated-${REGION}",
                "arn:aws:s3:::${PREFIX}-databricks-enriched-${REGION}/*",
                "arn:aws:s3:::${PREFIX}-databricks-enriched-${REGION}",
                "arn:aws:s3:::${PREFIX}-databricks-aggregated-${REGION}/*",
                "arn:aws:s3:::${PREFIX}-databricks-aggregated-${REGION}",
                "arn:aws:s3:::${PREFIX}-databricks-checkpoints-${REGION}/*",
                "arn:aws:s3:::${PREFIX}-databricks-checkpoints-${REGION}",
                "arn:aws:s3:::${PREFIX}-databricks-metadata-${REGION}/*",
                "arn:aws:s3:::${PREFIX}-databricks-metadata-${REGION}"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Resource": [
                "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
            ]
        }
    ]
}
EOF

# Create new policy version
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "Creating new policy version..."
aws iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document "file://$POLICY_FILE" \
    --set-as-default \
    --no-cli-pager

echo -e "${GREEN}✓ IAM policy updated successfully!${NC}"

# Clean up
rm -f "$POLICY_FILE"

echo ""
echo "Next steps:"
echo "1. Wait a few minutes for IAM changes to propagate"
echo "2. Re-run: uv run -s setup-databricks-external-locations.py"
echo "3. The checkpoints external location should now be created successfully"