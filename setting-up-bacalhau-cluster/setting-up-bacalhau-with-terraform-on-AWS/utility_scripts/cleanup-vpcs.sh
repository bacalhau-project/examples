#!/bin/bash

# Get all VPC IDs
VPC_IDS=$(aws ec2 describe-vpcs --query 'Vpcs[*].VpcId' --output text)

for VPC_ID in $VPC_IDS; do
    echo "Checking VPC $VPC_ID"

    # Check for associated resources
    SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[*].SubnetId' --output text)
    INSTANCES=$(aws ec2 describe-instances --filters "Name=vpc-id,Values=$VPC_ID" --query 'Reservations[*].Instances[*].InstanceId' --output text)
    IGW=$(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query 'InternetGateways[*].InternetGatewayId' --output text)
    NAT=$(aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" --query 'NatGateways[*].NatGatewayId' --output text)
    ROUTE_TABLES=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --query 'RouteTables[*].RouteTableId' --output text)
    ACLS=$(aws ec2 describe-network-acls --filters "Name=vpc-id,Values=$VPC_ID" --query 'NetworkAcls[*].NetworkAclId' --output text)
    ENDPOINTS=$(aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VPC_ID" --query 'VpcEndpoints[*].VpcEndpointId' --output text)
    PEERING=$(aws ec2 describe-vpc-peering-connections --filters "Name=requester-vpc-info.vpc-id,Values=$VPC_ID" --query 'VpcPeeringConnections[*].VpcPeeringConnectionId' --output text)

    if [ -z "$SUBNETS" ] && [ -z "$INSTANCES" ] && [ -z "$IGW" ] && [ -z "$NAT" ] && [ -z "$ROUTE_TABLES" ] && [ -z "$ACLS" ] && [ -z "$ENDPOINTS" ] && [ -z "$PEERING" ]; then
        echo "Deleting VPC $VPC_ID"
        aws ec2 delete-vpc --vpc-id $VPC_ID
    else
        echo "VPC $VPC_ID is in use, skipping..."
    fi
done
