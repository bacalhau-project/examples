#!/bin/bash
# Update IAM role to access all expanso-databricks buckets

set -e

# Configuration
IAM_ROLE_NAME="databricks-unity-catalog-expanso-role"
AWS_REGION="us-west-2"
S3_BUCKET_PREFIX="expanso-databricks"

echo "Updating IAM Role: $IAM_ROLE_NAME"
echo "=================================================="

# Create the new policy document
cat > /tmp/databricks-s3-policy.json << EOF
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
                "s3:GetBucketLocation"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET_PREFIX}-*",
                "arn:aws:s3:::${S3_BUCKET_PREFIX}-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListAllMyBuckets"
            ],
            "Resource": "*"
        }
    ]
}
EOF

echo "Policy document created"

# Check if the policy already exists
POLICY_NAME="${IAM_ROLE_NAME}-s3-access"
EXISTING_POLICY=$(aws iam list-role-policies --role-name $IAM_ROLE_NAME --query "PolicyNames[?contains(@, '$POLICY_NAME')]" --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_POLICY" ]; then
    echo "Updating existing policy: $POLICY_NAME"
    aws iam delete-role-policy --role-name $IAM_ROLE_NAME --policy-name $POLICY_NAME
fi

# Attach the new policy
echo "Attaching new policy..."
aws iam put-role-policy \
    --role-name $IAM_ROLE_NAME \
    --policy-name $POLICY_NAME \
    --policy-document file:///tmp/databricks-s3-policy.json

echo "✓ Policy attached successfully"

# List all buckets that will be accessible
echo -e "\nBuckets accessible by this role:"
aws s3 ls | grep $S3_BUCKET_PREFIX | awk '{print "  - " $3}'

# Clean up
rm -f /tmp/databricks-s3-policy.json

echo -e "\n✓ IAM role updated successfully!"
echo "Note: It may take 1-2 minutes for AWS to propagate the changes."