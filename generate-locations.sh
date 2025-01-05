#!/bin/bash

# Output file
OUTPUT_FILE="locations.yaml"

# Initialize YAML file
echo "# Auto-generated locations configuration" > $OUTPUT_FILE

# Get all available regions
REGIONS=$(aws ec2 describe-regions --query "Regions[].RegionName" --output text)

for REGION in $REGIONS; do
    # Get the latest Ubuntu 22.04 AMI
    AMI=$(aws ec2 describe-images \
        --region $REGION \
        --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --output text)
    
    # Get the first availability zone
    ZONE=$(aws ec2 describe-availability-zones \
        --region $REGION \
        --query "AvailabilityZones[0].ZoneName" \
        --output text)
    
    # Default node count based on region
    if [[ $REGION == "us-west-2" ]]; then
        NODE_COUNT=3
    elif [[ $REGION == "us-east-1" ]]; then
        NODE_COUNT=2
    elif [[ $REGION == "ap-northeast-1" ]]; then
        NODE_COUNT=1
    elif [[ $REGION == "eu-north-1" ]]; then
        NODE_COUNT=1
    elif [[ $REGION == "me-central-1" ]]; then
        NODE_COUNT=3
    else
        NODE_COUNT=1
    fi

    # Append to YAML file
    echo "- $REGION:" >> $OUTPUT_FILE
    echo "    region: $REGION" >> $OUTPUT_FILE
    echo "    zone: $ZONE" >> $OUTPUT_FILE
    echo "    instance_type: t3.medium" >> $OUTPUT_FILE
    echo "    instance_ami: $AMI" >> $OUTPUT_FILE
    echo "    node_count: $NODE_COUNT" >> $OUTPUT_FILE
done

echo "Generated locations.yaml successfully!"
