#!/bin/bash
# prepare_credentials.sh - Helper script to prepare credentials for deployment
# Run this on your local machine to prepare the service account key

set -e

echo "BigQuery Credentials Preparation Script"
echo "======================================"

# Check if service account file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-service-account-key.json>"
    echo ""
    echo "Example: $0 ~/Downloads/my-project-bigquery-sa.json"
    exit 1
fi

SERVICE_ACCOUNT_FILE="$1"

# Verify file exists
if [ ! -f "$SERVICE_ACCOUNT_FILE" ]; then
    echo "Error: Service account file not found: $SERVICE_ACCOUNT_FILE"
    exit 1
fi

# Verify it's valid JSON
if ! jq empty "$SERVICE_ACCOUNT_FILE" 2>/dev/null; then
    echo "Error: Invalid JSON in service account file"
    exit 1
fi

# Extract project ID from service account file
PROJECT_ID=$(jq -r '.project_id' "$SERVICE_ACCOUNT_FILE")
if [ "$PROJECT_ID" == "null" ] || [ -z "$PROJECT_ID" ]; then
    echo "Error: Could not extract project_id from service account file"
    exit 1
fi

echo "Project ID: $PROJECT_ID"

# Base64 encode the service account key
# macOS and Linux have different base64 syntax
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    SERVICE_ACCOUNT_KEY_BASE64=$(base64 -i "$SERVICE_ACCOUNT_FILE" | tr -d '\n')
else
    # Linux
    SERVICE_ACCOUNT_KEY_BASE64=$(base64 -w 0 "$SERVICE_ACCOUNT_FILE" 2>/dev/null || base64 "$SERVICE_ACCOUNT_FILE" | tr -d '\n')
fi

# Create deployment configuration
cat > bigquery_deployment_config.sh << EOF
#!/bin/bash
# Auto-generated BigQuery deployment configuration
# Generated on: $(date)

export PROJECT_ID="$PROJECT_ID"
export DATASET="sensor_analytics"
export SERVICE_ACCOUNT_KEY_BASE64="$SERVICE_ACCOUNT_KEY_BASE64"
export DOCKER_IMAGE="ghcr.io/bacalhau-project/bigquery-uploader-sqlite:latest"
export REGION="us-central1"
EOF

chmod 600 bigquery_deployment_config.sh

echo ""
echo "Configuration saved to: bigquery_deployment_config.sh"
echo ""
echo "To use this configuration:"
echo "1. Copy bigquery_deployment_config.sh to your deployment server"
echo "2. Source it before running the setup script:"
echo "   source bigquery_deployment_config.sh"
echo "   ./setup_bigquery_sensor_pipeline.sh"
echo ""
echo "Security note: The bigquery_deployment_config.sh file contains sensitive credentials."
echo "Ensure it is properly secured and deleted after use."

# Optionally test the credentials
echo ""
read -p "Would you like to test the credentials now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Testing credentials..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    cp "$SERVICE_ACCOUNT_FILE" "$TEMP_DIR/creds.json"
    
    # Test with gcloud
    docker run --rm \
        -v "$TEMP_DIR/creds.json:/tmp/creds.json:ro" \
        -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/creds.json \
        google/cloud-sdk:alpine \
        sh -c "gcloud auth activate-service-account --key-file=/tmp/creds.json && \
               gcloud config set project $PROJECT_ID && \
               bq ls" && echo "✓ Credentials test successful!" || echo "✗ Credentials test failed!"
    
    # Cleanup
    rm -rf "$TEMP_DIR"
fi

echo ""
echo "Next steps:"
echo "1. Review and modify DATASET and REGION in bigquery_deployment_config.sh if needed"
echo "2. Copy the configuration to your deployment server"
echo "3. Run the setup script on the deployment server"