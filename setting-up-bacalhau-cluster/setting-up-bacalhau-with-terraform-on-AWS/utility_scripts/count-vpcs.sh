#!/bin/bash

# Get all available AWS regions
REGIONS=$(aws ec2 describe-regions --query 'Regions[*].RegionName' --output text)

# Initialize total VPC count
TOTAL_VPCS=0

# Quota code for VPCs per region
QUOTA_CODE="L-F678F1CE"

# Iterate through each region
for REGION in $REGIONS; do
    echo "Checking region: $REGION"
    
    # Get the number of VPCs in the region
    VPC_COUNT=$(aws ec2 describe-vpcs --region $REGION --query 'Vpcs[*].VpcId' --output text | wc -w)
    
    # Add to the total count
    TOTAL_VPCS=$((TOTAL_VPCS + VPC_COUNT))
    
    # Get the VPC quota for the region
    QUOTA=$(aws service-quotas get-service-quota \
        --service-code ec2 \
        --quota-code $QUOTA_CODE \
        --region $REGION \
        --query 'Quota.Value' --output text)
    
    echo "VPCs in $REGION: $VPC_COUNT (Quota: $QUOTA)"
done

echo "Total VPCs across all regions: $TOTAL_VPCS"
