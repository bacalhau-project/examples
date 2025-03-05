#!/bin/bash

# Function to delete all resources in a VPC
delete_vpc_resources() {
    local VPC_ID=$1
    local REGION=$2

    echo "Deleting resources in VPC: $VPC_ID (Region: $REGION)"

    # Delete subnets
    SUBNETS=$(aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[].SubnetId" --output text)
    for SUBNET in $SUBNETS; do
        echo "Deleting subnet: $SUBNET"
        aws ec2 delete-subnet --subnet-id $SUBNET --region $REGION
    done

    # Delete internet gateways
    IGW=$(aws ec2 describe-internet-gateways --region $REGION --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query "InternetGateways[].InternetGatewayId" --output text)
    for GATEWAY in $IGW; do
        echo "Detaching and deleting internet gateway: $GATEWAY"
        aws ec2 detach-internet-gateway --internet-gateway-id $GATEWAY --vpc-id $VPC_ID --region $REGION
        aws ec2 delete-internet-gateway --internet-gateway-id $GATEWAY --region $REGION
    done

    # Delete route tables (except the main route table)
    ROUTE_TABLES=$(aws ec2 describe-route-tables --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "RouteTables[?Associations[?Main==\`false\`]].RouteTableId" --output text)
    for ROUTE_TABLE in $ROUTE_TABLES; do
        echo "Deleting route table: $ROUTE_TABLE"
        aws ec2 delete-route-table --route-table-id $ROUTE_TABLE --region $REGION
    done

    # Delete security groups (except the default security group)
    SECURITY_GROUPS=$(aws ec2 describe-security-groups --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "SecurityGroups[?GroupName!='default'].GroupId" --output text)
    for SG in $SECURITY_GROUPS; do
        echo "Deleting security group: $SG"
        aws ec2 delete-security-group --group-id $SG --region $REGION > /dev/null
    done

    # Delete network interfaces
    NETWORK_INTERFACES=$(aws ec2 describe-network-interfaces --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "NetworkInterfaces[].NetworkInterfaceId" --output text)
    for NETWORK_INTERFACE in $NETWORK_INTERFACES; do
        echo "Deleting network interface: $NETWORK_INTERFACE"
        aws ec2 delete-network-interface --network-interface-id $NETWORK_INTERFACE --region $REGION
    done

    echo "All resources in VPC $VPC_ID have been deleted."
}

# Get all available regions
REGIONS=$(aws ec2 describe-regions --query "Regions[].RegionName" --output text)

# Loop through each region
for REGION in $REGIONS; do
    echo "Checking region: $REGION"

    # Get the VPC IDs with the name "SpotInstanceVPC"
    VPC_IDS=$(aws ec2 describe-vpcs --region $REGION --filters "Name=tag:Name,Values=SpotInstanceVPC" --query "Vpcs[].VpcId" --output text)

    if [ -n "$VPC_IDS" ]; then
        for VPC_ID in $VPC_IDS; do
            echo "Found VPC with name 'SpotInstanceVPC' in region $REGION with ID: $VPC_ID"

            # Delete all resources inside the VPC
            delete_vpc_resources $VPC_ID $REGION

            # Delete the VPC
            echo "Deleting VPC: $VPC_ID"
            aws ec2 delete-vpc --vpc-id $VPC_ID --region $REGION
            echo "Deleted VPC with ID: $VPC_ID in region $REGION"
        done
    else
        echo "No VPC named 'SpotInstanceVPC' found in region $REGION"
    fi
done