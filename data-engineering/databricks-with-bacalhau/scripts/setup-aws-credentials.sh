#!/bin/bash
# Setup AWS credentials for production use (not SSO)

echo "=== AWS Credentials Setup ==="
echo
echo "This script helps configure AWS credentials for production use."
echo "These credentials will be stored on disk (not SSO session-based)."
echo

# Check if credentials already exist
if [ -f ~/.aws/credentials ]; then
    echo "⚠️  AWS credentials file already exists at ~/.aws/credentials"
    echo "   Current profiles:"
    grep '^\[' ~/.aws/credentials | tr -d '[]' | sed 's/^/   - /'
    echo
    read -p "Do you want to add/update credentials? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting without changes."
        exit 0
    fi
fi

# Create AWS directory if it doesn't exist
mkdir -p ~/.aws

# Get credentials from environment or prompt
if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Using credentials from environment variables..."
    ACCESS_KEY=$AWS_ACCESS_KEY_ID
    SECRET_KEY=$AWS_SECRET_ACCESS_KEY
else
    echo "Please enter your AWS credentials:"
    read -p "AWS Access Key ID: " ACCESS_KEY
    read -s -p "AWS Secret Access Key: " SECRET_KEY
    echo
fi

# Get profile name
read -p "Profile name (default: databricks-pipeline): " PROFILE_NAME
PROFILE_NAME=${PROFILE_NAME:-databricks-pipeline}

# Write credentials
echo "" >> ~/.aws/credentials
echo "[$PROFILE_NAME]" >> ~/.aws/credentials
echo "aws_access_key_id = $ACCESS_KEY" >> ~/.aws/credentials
echo "aws_secret_access_key = $SECRET_KEY" >> ~/.aws/credentials

# Write config
cat >> ~/.aws/config << EOF

[profile $PROFILE_NAME]
region = ${AWS_REGION:-us-west-2}
output = json
EOF

echo
echo "✅ AWS credentials configured for profile: $PROFILE_NAME"
echo
echo "To use these credentials:"
echo "  export AWS_PROFILE=$PROFILE_NAME"
echo
echo "Or add to your .env file:"
echo "  AWS_PROFILE=$PROFILE_NAME"
echo
echo "Test with:"
echo "  AWS_PROFILE=$PROFILE_NAME aws s3 ls s3://${S3_BUCKET_RAW}/ --no-paginate"