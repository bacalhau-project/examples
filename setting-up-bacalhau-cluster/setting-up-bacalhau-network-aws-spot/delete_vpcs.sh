#!/bin/bash
set -o pipefail

# Add AWS CLI wrapper function with improved error handling and timeouts
aws_with_timeout() {
    # Default timeout is 30 seconds
    local timeout=30
    if [[ "$1" == "--timeout" ]]; then
        timeout="$2"
        shift 2
    fi
    
    # Save the command for logging
    local cmd=("$@")
    
    # Use timeout command to enforce time limit
    timeout --foreground "$timeout" aws "${cmd[@]}" 2>&1
    local status=$?
    
    # Return the exit status
    return $status
}

# Function to verify AWS credentials are valid
verify_aws_credentials() {
    echo "Verifying AWS credentials..."
    
    # Try a simple API call that requires valid credentials
    local result=$(aws sts get-caller-identity 2>&1)
    local status=$?
    
    if [ $status -ne 0 ]; then
        echo "Error: AWS credentials verification failed"
        
        # Check for specific error patterns
        if [[ "$result" == *"Token"*"expired"* ]]; then
            echo "AWS token has expired. Please refresh your credentials."
            echo "Try running: 'aws sso login' or refresh your credentials in your AWS config."
        elif [[ "$result" == *"AccessDenied"* ]] || [[ "$result" == *"NotAuthorized"* ]]; then
            echo "You don't have sufficient permissions to access AWS resources."
        else
            echo "AWS credentials error: $result"
        fi
        
        return 1
    fi
    
    echo "AWS credentials verified successfully."
    return 0
}

# Run credential verification unless --skip-credential-check is provided
SKIP_AWS_CHECK=false
if [[ "$1" == "--skip-credential-check" ]]; then
    SKIP_AWS_CHECK=true
    shift
fi

if [ "$SKIP_AWS_CHECK" = false ]; then
    verify_aws_credentials
    if [ $? -ne 0 ]; then
        echo "Exiting due to credential verification failure."
        exit 1
    fi
fi

# Function to terminate instances in a VPC
terminate_vpc_instances() {
    local VPC_ID=$1
    local REGION=$2

    echo "Terminating instances in VPC: $VPC_ID (Region: $REGION)"
    
    # Find and terminate all instances in the VPC
    INSTANCES=$(aws ec2 describe-instances --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query "Reservations[].Instances[].InstanceId" --output text --no-cli-pager)
    if [ -n "$INSTANCES" ]; then
        echo "Found instances to terminate: $INSTANCES"
        aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCES > /dev/null
        
        echo "Waiting for instances to terminate..."
        aws ec2 wait instance-terminated --region $REGION --instance-ids $INSTANCES
    fi
}

# Function to list all dependencies of a VPC
list_vpc_dependencies() {
    local VPC_ID=$1
    local REGION=$2

    echo "Detailed dependencies for VPC: $VPC_ID (Region: $REGION)"
    
    # List instances with more details
    echo "Instances:"
    aws ec2 describe-instances --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "Reservations[].Instances[].[InstanceId,State.Name,InstanceType,SubnetId,Tags[?Key=='Name'].Value|[0]]" \
        --output table --no-cli-pager

    # List NAT Gateways with more details
    echo "NAT Gateways:"
    aws ec2 describe-nat-gateways --region $REGION --filter "Name=vpc-id,Values=$VPC_ID" \
        --query "NatGateways[].[NatGatewayId,State,SubnetId,NatGatewayAddresses[0].AllocationId]" \
        --output table --no-cli-pager

    # List Network Interfaces with more details
    echo "Network Interfaces (ENIs):"
    aws ec2 describe-network-interfaces --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "NetworkInterfaces[].[NetworkInterfaceId,Status,Description,SubnetId,OwnerId,RequesterManaged,InterfaceType]" \
        --output table --no-cli-pager

    # List Subnets with more details
    echo "Subnets:"
    aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "Subnets[].[SubnetId,CidrBlock,AvailabilityZone,MapPublicIpOnLaunch]" \
        --output table --no-cli-pager

    # List Route Tables with associations
    echo "Route Tables and Associations:"
    aws ec2 describe-route-tables --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "RouteTables[].[RouteTableId,Associations[].{SubnetId:SubnetId,Main:Main}]" \
        --output table --no-cli-pager

    # List Security Groups with more details
    echo "Security Groups:"
    aws ec2 describe-security-groups --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[].[GroupId,GroupName,Description]" \
        --output table --no-cli-pager

    # List Load Balancers with more details
    echo "Load Balancers:"
    aws elbv2 describe-load-balancers --region $REGION --query "LoadBalancers[?VpcId=='$VPC_ID'].[LoadBalancerArn,DNSName,State.Code,Type]" \
        --output table --no-cli-pager 2>/dev/null || true

    # List Transit Gateway Attachments with more details
    echo "Transit Gateway Attachments:"
    aws ec2 describe-transit-gateway-vpc-attachments --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "TransitGatewayVpcAttachments[].[TransitGatewayAttachmentId,State,TransitGatewayId]" \
        --output table --no-cli-pager 2>/dev/null || true

    # List VPC Endpoints with more details
    echo "VPC Endpoints:"
    aws ec2 describe-vpc-endpoints --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "VpcEndpoints[].[VpcEndpointId,VpcEndpointType,State,ServiceName]" \
        --output table --no-cli-pager

    # List VPC Peering Connections
    echo "VPC Peering Connections:"
    aws ec2 describe-vpc-peering-connections --region $REGION \
        --filters "Name=requester-vpc-info.vpc-id,Values=$VPC_ID" "Name=accepter-vpc-info.vpc-id,Values=$VPC_ID" \
        --query "VpcPeeringConnections[].[VpcPeeringConnectionId,Status.Code,RequesterVpcInfo.VpcId,AccepterVpcInfo.VpcId]" \
        --output table --no-cli-pager

    # List any attached VPN Gateways
    echo "VPN Gateways:"
    aws ec2 describe-vpn-gateways --region $REGION --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
        --query "VpnGateways[].[VpnGatewayId,State,Type]" \
        --output table --no-cli-pager
}

# Function to clean up security group rules
cleanup_security_group_rules() {
    local VPC_ID=$1
    local REGION=$2

    echo "Cleaning up security group rules for VPC: $VPC_ID"
    
    # Get all security groups in the VPC
    local GROUPS=$(aws ec2 describe-security-groups --region $REGION \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query 'SecurityGroups[*].GroupId' --output text --no-cli-pager)

    for GROUP_ID in $GROUPS; do
        echo "Cleaning rules for security group: $GROUP_ID"
        
        # Remove all ingress rules using the older API method if describe-security-group-rules fails
        local INGRESS=""
        INGRESS=$(aws ec2 describe-security-group-rules --region $REGION \
            --filters "Name=group-id,Values=$GROUP_ID" "Name=is-egress,Values=false" \
            --query 'SecurityGroupRules[*].SecurityGroupRuleId' --output text --no-cli-pager 2>/dev/null) || true

        if [ ! -z "$INGRESS" ]; then
            echo "Removing ingress rules: $INGRESS"
            for RULE_ID in $INGRESS; do
                aws ec2 revoke-security-group-rules --region $REGION \
                    --group-id $GROUP_ID \
                    --security-group-rule-ids $RULE_ID > /dev/null 2>&1 || true
            done
        else
            # Fallback to the older method
            aws ec2 revoke-security-group-ingress --region $REGION --group-id $GROUP_ID \
                --ip-permissions '[{"IpProtocol": "-1", "FromPort": -1, "ToPort": -1, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]' > /dev/null 2>&1 || true
        fi

        # Remove all egress rules using the older API method if describe-security-group-rules fails
        local EGRESS=""
        EGRESS=$(aws ec2 describe-security-group-rules --region $REGION \
            --filters "Name=group-id,Values=$GROUP_ID" "Name=is-egress,Values=true" \
            --query 'SecurityGroupRules[*].SecurityGroupRuleId' --output text --no-cli-pager 2>/dev/null) || true
        
        if [ ! -z "$EGRESS" ]; then
            echo "Removing egress rules: $EGRESS"
            for RULE_ID in $EGRESS; do
                aws ec2 revoke-security-group-rules --region $REGION \
                    --group-id $GROUP_ID \
                    --security-group-rule-ids $RULE_ID > /dev/null 2>&1 || true
            done
        else
            # Fallback to the older method
            aws ec2 revoke-security-group-egress --region $REGION --group-id $GROUP_ID \
                --ip-permissions '[{"IpProtocol": "-1", "FromPort": -1, "ToPort": -1, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]' > /dev/null 2>&1 || true
        fi
    done
}

# Function to delete all resources in a VPC
delete_vpc_resources() {
    local VPC_ID=$1
    local REGION=$2

    echo "Deleting resources in VPC: $VPC_ID (Region: $REGION)"
    
    # First list all dependencies
    list_vpc_dependencies "$VPC_ID" "$REGION"
    
    # Clean up all security group rules first
    cleanup_security_group_rules "$VPC_ID" "$REGION"

    # First terminate any running instances
    terminate_vpc_instances "$VPC_ID" "$REGION"

    # Delete Load Balancers
    LBS=$(aws elbv2 describe-load-balancers --region $REGION --query "LoadBalancers[?VpcId=='$VPC_ID'].LoadBalancerArn" --output text --no-cli-pager 2>/dev/null || echo "")
    for LB in $LBS; do
        echo "Deleting Load Balancer: $LB"
        aws elbv2 delete-load-balancer --region $REGION --load-balancer-arn $LB > /dev/null 2>&1 || true
    done
    
    # Delete Transit Gateway Attachments
    TGW_ATTACHMENTS=$(aws ec2 describe-transit-gateway-vpc-attachments --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "TransitGatewayVpcAttachments[].TransitGatewayAttachmentId" --output text --no-cli-pager 2>/dev/null || echo "")
    for TGW in $TGW_ATTACHMENTS; do
        echo "Deleting Transit Gateway Attachment: $TGW"
        aws ec2 delete-transit-gateway-vpc-attachment --region $REGION --transit-gateway-attachment-id $TGW --force > /dev/null 2>&1 || true
    done

    # Delete VPC Endpoints
    ENDPOINTS=$(aws ec2 describe-vpc-endpoints --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "VpcEndpoints[].VpcEndpointId" --output text --no-cli-pager)
    for ENDPOINT in $ENDPOINTS; do
        echo "Deleting VPC Endpoint: $ENDPOINT"
        aws ec2 delete-vpc-endpoints --region $REGION --vpc-endpoint-ids $ENDPOINT > /dev/null 2>&1 || true
    done

    # Delete NAT Gateways
    NAT_GATEWAYS=$(aws ec2 describe-nat-gateways --region $REGION --filter "Name=vpc-id,Values=$VPC_ID" --query "NatGateways[?State!='deleted'].NatGatewayId" --output text --no-cli-pager)
    for NAT in $NAT_GATEWAYS; do
        echo "Deleting NAT Gateway: $NAT"
        aws ec2 delete-nat-gateway --region $REGION --nat-gateway-id $NAT > /dev/null 2>&1 || true
    done

    if [ -n "$NAT_GATEWAYS" ]; then
        echo "Waiting for NAT Gateways to delete..."
        sleep 30  # Give some time for NAT Gateway deletion to start
    fi

    # Delete Network Interfaces
    NETWORK_INTERFACES=$(aws ec2 describe-network-interfaces --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "NetworkInterfaces[].NetworkInterfaceId" --output text --no-cli-pager)
    for ENI in $NETWORK_INTERFACES; do
        echo "Deleting network interface: $ENI"
        # Try to detach first if attached
        ATTACHMENT_ID=$(aws ec2 describe-network-interfaces --region $REGION --network-interface-ids $ENI --query "NetworkInterfaces[].Attachment.AttachmentId" --output text --no-cli-pager)
        if [ -n "$ATTACHMENT_ID" ]; then
            aws ec2 detach-network-interface --region $REGION --attachment-id $ATTACHMENT_ID --force > /dev/null
            sleep 5  # Give it time to detach
        fi
        aws ec2 delete-network-interface --region $REGION --network-interface-id $ENI > /dev/null 2>&1 || true
    done

    # Delete internet gateways
    IGW=$(aws ec2 describe-internet-gateways --region $REGION --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query "InternetGateways[].InternetGatewayId" --output text --no-cli-pager)
    for GATEWAY in $IGW; do
        echo "Detaching and deleting internet gateway: $GATEWAY"
        aws ec2 detach-internet-gateway --region $REGION --internet-gateway-id $GATEWAY --vpc-id $VPC_ID > /dev/null 2>&1 || true
        aws ec2 delete-internet-gateway --region $REGION --internet-gateway-id $GATEWAY > /dev/null 2>&1 || true
    done

    # Better handling for security groups - list all non-default security groups
    SECURITY_GROUPS=$(aws ec2 describe-security-groups --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "SecurityGroups[?GroupName!='default'].GroupId" --output text --no-cli-pager)
    
    for SG in $SECURITY_GROUPS; do
        echo "Handling security group: $SG"
        
        # First get a detailed view of all security group rules
        echo "Getting rules for security group: $SG"
        
        # Try the newer security-group-rules API first
        INGRESS_RULES=$(aws ec2 describe-security-group-rules --region $REGION --filters "Name=group-id,Values=$SG" "Name=is-egress,Values=false" --query "SecurityGroupRules[].SecurityGroupRuleId" --output text --no-cli-pager 2>/dev/null || echo "")
        EGRESS_RULES=$(aws ec2 describe-security-group-rules --region $REGION --filters "Name=group-id,Values=$SG" "Name=is-egress,Values=true" --query "SecurityGroupRules[].SecurityGroupRuleId" --output text --no-cli-pager 2>/dev/null || echo "")
        
        # New API - revoke by rule ID if we have rule IDs
        if [ -n "$INGRESS_RULES" ]; then
            echo "Removing ingress rules by ID from security group: $SG"
            for RULE_ID in $INGRESS_RULES; do
                echo "  Removing ingress rule: $RULE_ID"
                aws ec2 revoke-security-group-rules --region $REGION --group-id $SG --security-group-rule-ids "$RULE_ID" > /dev/null 2>&1 || true
            done
        else
            # Fallback to older method - get all ingress rules
            SG_DETAIL=$(aws ec2 describe-security-groups --region $REGION --group-ids $SG --query "SecurityGroups[0].IpPermissions" --output json --no-cli-pager 2>/dev/null || echo "[]")
            if [ "$SG_DETAIL" != "[]" ] && [ "$SG_DETAIL" != "" ]; then
                echo "Removing all ingress rules from security group: $SG (legacy method)"
                # Write the permissions to a temporary file
                TMP_FILE=$(mktemp)
                echo "$SG_DETAIL" > "$TMP_FILE"
                # Use the file as input to revoke-security-group-ingress
                aws ec2 revoke-security-group-ingress --region $REGION --group-id $SG --ip-permissions file://$TMP_FILE > /dev/null 2>&1 || true
                rm "$TMP_FILE"
            fi
        fi
        
        # New API - revoke egress by rule ID
        if [ -n "$EGRESS_RULES" ]; then
            echo "Removing egress rules by ID from security group: $SG"
            for RULE_ID in $EGRESS_RULES; do
                echo "  Removing egress rule: $RULE_ID"
                aws ec2 revoke-security-group-rules --region $REGION --group-id $SG --security-group-rule-ids "$RULE_ID" > /dev/null 2>&1 || true
            done
        else
            # Fallback to older method - get all egress rules
            SG_EGRESS_DETAIL=$(aws ec2 describe-security-groups --region $REGION --group-ids $SG --query "SecurityGroups[0].IpPermissionsEgress" --output json --no-cli-pager 2>/dev/null || echo "[]")
            if [ "$SG_EGRESS_DETAIL" != "[]" ] && [ "$SG_EGRESS_DETAIL" != "" ]; then
                echo "Removing all egress rules from security group: $SG (legacy method)"
                # Write the permissions to a temporary file
                TMP_EGRESS_FILE=$(mktemp)
                echo "$SG_EGRESS_DETAIL" > "$TMP_EGRESS_FILE"
                # Use the file as input to revoke-security-group-egress
                aws ec2 revoke-security-group-egress --region $REGION --group-id $SG --ip-permissions file://$TMP_EGRESS_FILE > /dev/null 2>&1 || true
                rm "$TMP_EGRESS_FILE"
            fi
        fi
        
        # Wait a moment for rule deletions to propagate
        sleep 2
    done
    
    # Now delete the security groups
    for SG in $SECURITY_GROUPS; do
        echo "Deleting security group: $SG"
        # Try up to 3 times to delete the security group
        for i in {1..3}; do
            aws ec2 delete-security-group --region $REGION --group-id $SG > /dev/null 2>&1 && {
                echo "  Successfully deleted security group: $SG"
                break
            } || {
                echo "  Retry $i: Failed to delete security group: $SG - checking dependencies"
                # Double-check there are really no rules left
                aws ec2 revoke-security-group-ingress --region $REGION --group-id $SG --protocol all --port all --cidr 0.0.0.0/0 > /dev/null 2>&1 || true
                aws ec2 revoke-security-group-egress --region $REGION --group-id $SG --protocol all --port all --cidr 0.0.0.0/0 > /dev/null 2>&1 || true
                
                if [ $i -eq 3 ]; then
                    echo "  WARNING: Failed to delete security group after 3 attempts: $SG"
                else
                    sleep 5
                fi
            }
        done
    done

    # Wait for any NAT Gateway deletions to complete
    NAT_GATEWAYS=$(aws ec2 describe-nat-gateways --region $REGION --filter "Name=vpc-id,Values=$VPC_ID" --query "NatGateways[?State!='deleted'].NatGatewayId" --output text --no-cli-pager)
    if [ ! -z "$NAT_GATEWAYS" ]; then
        echo "Waiting for NAT Gateways to be deleted..."
        while true; do
            PENDING_NATS=$(aws ec2 describe-nat-gateways --region $REGION --filter "Name=vpc-id,Values=$VPC_ID" --query "NatGateways[?State!='deleted'].NatGatewayId" --output text --no-cli-pager)
            if [ -z "$PENDING_NATS" ]; then
                break
            fi
            echo "Still waiting for NAT Gateways to be deleted..."
            sleep 10
        done
    fi

    # Delete subnets
    SUBNETS=$(aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[].SubnetId" --output text --no-cli-pager)
    for SUBNET in $SUBNETS; do
        echo "Deleting subnet: $SUBNET"
        aws ec2 delete-subnet --region $REGION --subnet-id $SUBNET > /dev/null 2>&1 || true
    done

    # Delete ALL route tables (both custom and main) - handle main route table differently
    # Get all route tables in the VPC
    ROUTE_TABLES=$(aws ec2 describe-route-tables --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "RouteTables[].RouteTableId" --output text --no-cli-pager)
    
    for RT in $ROUTE_TABLES; do
        echo "Processing route table: $RT"
        
        # Check if it's the main route table
        IS_MAIN=$(aws ec2 describe-route-tables --region $REGION --route-table-ids $RT --query "RouteTables[].Associations[?Main==\`true\`]" --output text --no-cli-pager)
        
        # First, delete all routes in the route table (except local routes which cannot be deleted)
        # Handle IPv4 routes - Fix for "list index out of range" by checking for specific key existence
        ROUTES=$(aws ec2 describe-route-tables --region $REGION --route-table-ids $RT --query "RouteTables[0].Routes[?GatewayId!='local' && contains(keys(@), 'DestinationCidrBlock')].DestinationCidrBlock" --output text --no-cli-pager)
        
        # Only process if we have routes
        if [ -n "$ROUTES" ]; then
            for ROUTE in $ROUTES; do
                echo "Deleting IPv4 route to $ROUTE from route table $RT"
                aws ec2 delete-route --region $REGION --route-table-id $RT --destination-cidr-block "$ROUTE" > /dev/null 2>&1 || true
            done
        fi
        
        # Handle IPv6 routes separately
        IPV6_ROUTES=$(aws ec2 describe-route-tables --region $REGION --route-table-ids $RT --query "RouteTables[0].Routes[?GatewayId!='local' && contains(keys(@), 'DestinationIpv6CidrBlock')].DestinationIpv6CidrBlock" --output text --no-cli-pager 2>/dev/null || echo "")
        
        if [ -n "$IPV6_ROUTES" ]; then
            for ROUTE in $IPV6_ROUTES; do
                echo "Deleting IPv6 route to $ROUTE from route table $RT"
                aws ec2 delete-route --region $REGION --route-table-id $RT --destination-ipv6-cidr-block "$ROUTE" > /dev/null 2>&1 || true
            done
        fi
        
        # Get the association IDs for this route table with safer query that handles empty results
        ASSOC_IDS=$(aws ec2 describe-route-tables --region $REGION --route-table-ids $RT --query "RouteTables[0].Associations[?RouteTableAssociationId!=null].RouteTableAssociationId" --output text --no-cli-pager)
        
        if [ -n "$ASSOC_IDS" ]; then
            for ASSOC in $ASSOC_IDS; do
                # Skip if this is a main association (cannot be disassociated)
                IS_MAIN_ASSOC=$(aws ec2 describe-route-tables --region $REGION --route-table-ids $RT --query "RouteTables[0].Associations[?RouteTableAssociationId=='$ASSOC'].Main" --output text --no-cli-pager)
                
                if [ "$IS_MAIN_ASSOC" != "True" ] && [ "$IS_MAIN_ASSOC" != "true" ]; then
                    echo "Disassociating route table association: $ASSOC"
                    aws ec2 disassociate-route-table --region $REGION --association-id $ASSOC > /dev/null 2>&1 || true
                else
                    echo "Skipping main route table association $ASSOC (cannot be disassociated)"
                fi
            done
        fi
        
        # Only try to delete non-main route tables
        if [ -z "$IS_MAIN" ]; then
            echo "Deleting route table: $RT"
            aws ec2 delete-route-table --region $REGION --route-table-id $RT > /dev/null 2>&1 || true
        else
            echo "Skipping deletion of main route table $RT (will be deleted with VPC)"
        fi
    done

    echo "All resources in VPC $VPC_ID have been deleted."
}

# Get all available regions - use timeout to prevent hanging
echo "Retrieving available AWS regions..."
REGIONS=$(aws_with_timeout --timeout 15 ec2 describe-regions --query "Regions[].RegionName" --output text --no-cli-pager)

if [ -z "$REGIONS" ]; then
    echo "ERROR: Failed to retrieve AWS regions. Check your AWS credentials and network connection."
    exit 1
fi

# Loop through each region
for REGION in $REGIONS; do
    echo "Checking region: $REGION"

    # Get the VPC IDs with our naming patterns - use timeout to prevent hanging
    VPC_IDS=$(aws_with_timeout --timeout 15 ec2 describe-vpcs --region $REGION --filters "Name=tag:Name,Values=SpotInstance-*,SpotInstanceVPC" --query "Vpcs[].VpcId" --output text --no-cli-pager)

    if [ -n "$VPC_IDS" ]; then
        for VPC_ID in $VPC_IDS; do
            echo "Found VPC with name 'SpotInstanceVPC' in region $REGION with ID: $VPC_ID"

            # Delete all resources inside the VPC
            delete_vpc_resources $VPC_ID $REGION

            # Delete the VPC with retries
            echo "Deleting VPC: $VPC_ID"
            MAX_RETRIES=3
            RETRY_COUNT=0
            VPC_DELETED=false
            
            while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$VPC_DELETED" = "false" ]; do
                # Check if there are any dependencies left
                echo "Checking for remaining dependencies in VPC: $VPC_ID"
                
                # Verify no instances
                INSTANCES=$(aws ec2 describe-instances --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query "Reservations[].Instances[].InstanceId" --output text --no-cli-pager)
                
                # Verify no NAT gateways
                NAT_GATEWAYS=$(aws ec2 describe-nat-gateways --region $REGION --filter "Name=vpc-id,Values=$VPC_ID" --query "NatGateways[?State!='deleted'].NatGatewayId" --output text --no-cli-pager)
                
                # Verify no ENIs except the default ones
                NETWORK_INTERFACES=$(aws ec2 describe-network-interfaces --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "NetworkInterfaces[].NetworkInterfaceId" --output text --no-cli-pager)
                
                # List all remaining dependencies
                if [ -n "$INSTANCES" ] || [ -n "$NAT_GATEWAYS" ] || [ -n "$NETWORK_INTERFACES" ]; then
                    echo "Found remaining dependencies in VPC $VPC_ID:"
                    [ -n "$INSTANCES" ] && echo " - Instances: $INSTANCES"
                    [ -n "$NAT_GATEWAYS" ] && echo " - NAT Gateways: $NAT_GATEWAYS"
                    [ -n "$NETWORK_INTERFACES" ] && echo " - Network Interfaces: $NETWORK_INTERFACES"
                    
                    # Try to cleanup remaining resources
                    echo "Attempting to force cleanup of remaining resources..."
                    
                    # Force terminate any instances
                    if [ -n "$INSTANCES" ]; then
                        echo "Force terminating instances: $INSTANCES"
                        aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCES > /dev/null 2>&1 || true
                        sleep 10
                    fi
                    
                    # Force delete network interfaces
                    if [ -n "$NETWORK_INTERFACES" ]; then
                        for ENI in $NETWORK_INTERFACES; do
                            echo "Force detaching network interface: $ENI"
                            ATTACHMENT=$(aws ec2 describe-network-interfaces --region $REGION --network-interface-ids $ENI --query "NetworkInterfaces[].Attachment.AttachmentId" --output text --no-cli-pager 2>/dev/null || echo "")
                            if [ -n "$ATTACHMENT" ]; then
                                aws ec2 detach-network-interface --region $REGION --attachment-id $ATTACHMENT --force > /dev/null 2>&1 || true
                                sleep 2
                            fi
                            
                            echo "Force deleting network interface: $ENI"
                            aws ec2 delete-network-interface --region $REGION --network-interface-id $ENI > /dev/null 2>&1 || true
                        done
                    fi
                    
                    sleep 10
                fi
                
                # Try to delete the VPC
                echo "Attempt $((RETRY_COUNT+1)) to delete VPC: $VPC_ID"
                if aws ec2 delete-vpc --vpc-id $VPC_ID --region $REGION > /dev/null 2>&1; then
                    echo "Successfully deleted VPC with ID: $VPC_ID in region $REGION"
                    VPC_DELETED=true
                    break
                else
                    echo "Failed to delete VPC. Retrying in 10 seconds..."
                    RETRY_COUNT=$((RETRY_COUNT+1))
                    sleep 10
                fi
            done
            
            if [ "$VPC_DELETED" = "false" ]; then
                echo "WARNING: Failed to delete VPC $VPC_ID in region $REGION after $MAX_RETRIES attempts."
                echo "You may need to manually check for remaining dependencies in the AWS Console."
            fi
        done
    else
        echo "No matching VPCs found in region $REGION"
    fi
done