#!/bin/bash
# /scripts/startup.sh

# Function to get instance metadata using IMDSv2
get_instance_metadata() {
    # Get IMDSv2 token
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    if [ -z "$TOKEN" ]; then
        echo "Error: Failed to get IMDSv2 token"
        return 1
    fi

    # Get all instance metadata in one call
    local metadata=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
        http://169.254.169.254/latest/dynamic/instance-identity/document)
    
    if [ -z "$metadata" ]; then
        echo "Error: Failed to get instance metadata"
        return 1
    fi

    # Parse the JSON response
    REGION=$(echo "$metadata" | grep -oP '"region"\s*:\s*"\K[^"]+')
    ZONE=$(echo "$metadata" | grep -oP '"availabilityZone"\s*:\s*"\K[^"]+')
    INSTANCE_ID=$(echo "$metadata" | grep -oP '"instanceId"\s*:\s*"\K[^"]+')
    INSTANCE_TYPE=$(echo "$metadata" | grep -oP '"instanceType"\s*:\s*"\K[^"]+')
    PRIVATE_IP=$(echo "$metadata" | grep -oP '"privateIp"\s*:\s*"\K[^"]+')
    
    # Get public IP separately as it's not in the document
    PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
        http://169.254.169.254/latest/meta-data/public-ipv4)

    return 0
}

# Function to fetch a parameter from SSM and exit on failure
fetch_parameter() {
  local param_name="$1"
  local output_file="$2"
  local max_retries=5
  local retry_count=0
  
  if ! get_instance_metadata; then
    echo "Error: Failed to get instance metadata"
    exit 1
  fi
  AWS_REGION=$REGION
  if [ -z "$AWS_REGION" ]; then
    echo "Error: Failed to fetch AWS region from instance metadata."
    exit 1
  fi

  while [ $retry_count -lt $max_retries ]; do
    echo "Attempt $((retry_count + 1)) of $max_retries: Fetching $param_name from SSM Parameter Store..."
    if aws ssm get-parameter --name "$param_name" --query "Parameter.Value" --output text --region "$AWS_REGION" > "$output_file"; then
      echo "$param_name written to $output_file."
      return 0
    fi
    retry_count=$((retry_count + 1))
    if [ $retry_count -lt $max_retries ]; then
      sleep $((retry_count * 5))
    fi
  done
  
  echo "Error: Failed to fetch $param_name after $max_retries attempts."
  return 1
}

# Populate node info
echo "Populating node info..."
# Get instance metadata
if ! get_instance_metadata; then
    echo "Error: Failed to get instance metadata"
    exit 1
fi

# Only write node info if we have the basic metadata
if [ ! -z "$REGION" ] && [ ! -z "$INSTANCE_ID" ]; then
cat <<EOF | sudo tee /etc/node-info
REGION=$REGION
ZONE=$ZONE
ARCH=$(uname -m)
CPUS=$(nproc)
MEMORY=$(grep MemTotal /proc/meminfo | awk '{print $2}')
INSTANCE_ID=$INSTANCE_ID
INSTANCE_TYPE=$INSTANCE_TYPE
PUBLIC_IP=$PUBLIC_IP
PRIVATE_IP=$PRIVATE_IP
HOSTNAME=$(hostname)
EOF
else
    echo "Error: Failed to fetch required metadata. Node info file not created."
    exit 1
fi

# Fetch configurations from SSM
# Ensure directories exist
sudo mkdir -p /bacalhau_node
sudo mkdir -p /etc/bacalhau

# Fetch configurations
# Create temporary file first to avoid mkdir interpreting it as a directory
fetch_parameter "/bacalhau/ORCHESTRATOR_CONFIG" "/tmp/orchestrator-config.yaml"
sudo mv "/tmp/orchestrator-config.yaml" "/bacalhau_node/orchestrator-config.yaml"

fetch_parameter "/bacalhau/DOCKER_COMPOSE" "/tmp/docker-compose.yaml"
sudo mv "/tmp/docker-compose.yaml" "/bacalhau_node/docker-compose.yaml"

# Start Docker Compose if both files exist
if [ -f "/bacalhau_node/orchestrator-config.yaml" ] && [ -f "/bacalhau_node/docker-compose.yaml" ]; then
  echo "Starting Docker Compose..."
  sudo docker-compose -f /bacalhau_node/docker-compose.yaml up -d
else
  echo "Warning: Required configuration files not found. Docker Compose not started."
  exit 1
fi