#!/bin/bash

# Output file
OUTPUT_FILE="all_locations.yaml"

# Truncate the output file if it exists
truncate -s 0 $OUTPUT_FILE

# Initialize YAML file
echo "# Auto-generated locations configuration" > $OUTPUT_FILE
echo "# Using Amazon Linux 2023 AMIs" >> $OUTPUT_FILE

# Get all available regions
REGIONS=$(aws ec2 describe-regions --query "Regions[].RegionName" --output text)

for REGION in $REGIONS; do
    # Get the latest Amazon Linux 2023 AMI
    AMI=$(aws ec2 describe-images \
        --region "$REGION" \
        --owners amazon \
        --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --output text)
    
    # Skip if no AMI found
    if [ "$AMI" == "None" ] || [ -z "$AMI" ]; then
        echo "Skipping $REGION - No Amazon Linux 2023 AMI found"
        continue
    fi
    
    # Get the first availability zone
    ZONE=$(aws ec2 describe-availability-zones \
        --region $REGION \
        --query "AvailabilityZones[0].ZoneName" \
        --output text)
    
    # Skip if no availability zone found
    if [ "$ZONE" == "None" ] || [ -z "$ZONE" ]; then
        echo "Skipping $REGION - No availability zone found"
        continue
    fi
    
    # Append to YAML file
    REGION_BLOCK="- $REGION:"
    REGION_BLOCK="$REGION_BLOCK\n    region: $REGION"
    REGION_BLOCK="$REGION_BLOCK\n    zone: $ZONE"
    REGION_BLOCK="$REGION_BLOCK\n    instance_type: t3.medium"
    REGION_BLOCK="$REGION_BLOCK\n    instance_ami: $AMI"
    REGION_BLOCK="$REGION_BLOCK\n    node_count: 1"
    echo -e "$REGION_BLOCK" >> $OUTPUT_FILE
    echo -e "Added $REGION with AMI $AMI"
done

echo "Generated locations.yaml successfully!"
