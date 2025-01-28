#!/bin/bash
# build-ami.sh
set -e

source ./aws-spot-env.sh

echo "Building new AMI using Packer..."

# Initialize Packer
packer init .

# Build the AMI with variables
packer build \
  -var "aws_region=${AWS_REGION}" \
  -var "ami_name=${CUSTOM_AMI_NAME}" \
  -var "ami_description=${CUSTOM_AMI_DESCRIPTION}" \
  -var "instance_type=${INSTANCE_TYPE}" \
  .

# Extract the AMI ID from the manifest
NEW_AMI_ID=$(jq -r '.builds[-1].artifact_id | split(":")[1]' manifest.json)

# Update the environment file with the new AMI ID
sed -i.bak "s/export CONFIGURED_AMI_ID=.*/export CONFIGURED_AMI_ID=\"$NEW_AMI_ID\"/" aws-spot-env.sh

echo "New AMI built with ID: $NEW_AMI_ID"
echo "Environment file updated with new AMI ID"
echo "You can now run ./launch-spot-instances.sh to launch instances with this AMI"