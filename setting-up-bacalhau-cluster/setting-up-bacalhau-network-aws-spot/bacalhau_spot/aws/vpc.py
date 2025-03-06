"""
VPC and network resources management module.

This module provides functions for creating and managing AWS VPC and related
network resources (subnets, internet gateways, route tables, security groups).
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

import botocore.exceptions

from .client import AWSClientError, AWSResourceError, get_boto3_client, safe_aws_call

# Configure logger
logger = logging.getLogger(__name__)


async def create_vpc_if_not_exists(
    region: str,
    vpc_name: str,
    filter_tag_name: str,
    filter_tag_value: str,
    creator_value: str,
    cidr_block: str = "10.0.0.0/16",
) -> str:
    """
    Create a VPC if it doesn't exist, or return the ID of an existing one.
    
    Args:
        region: AWS region
        vpc_name: Name for the VPC
        filter_tag_name: Tag name for filtering
        filter_tag_value: Tag value for filtering
        creator_value: Value for the CreatedBy tag
        cidr_block: CIDR block for the VPC
        
    Returns:
        VPC ID
        
    Raises:
        AWSClientError: If VPC creation fails
    """
    ec2 = get_boto3_client("ec2", region)
    
    try:
        # Check if a VPC with the specified tags already exists
        vpcs = await safe_aws_call(
            ec2.describe_vpcs,
            Filters=[
                {"Name": "tag:Name", "Values": [vpc_name]},
                {"Name": f"tag:{filter_tag_name}", "Values": [filter_tag_value]},
            ],
        )
        
        if vpcs["Vpcs"]:
            # Use the first matching VPC
            vpc_id = vpcs["Vpcs"][0]["VpcId"]
            logger.info(f"Using existing VPC {vpc_id} in {region}")
            return vpc_id
        
        # Create a new VPC
        logger.info(f"Creating new VPC in {region} with CIDR {cidr_block}")
        vpc = await safe_aws_call(ec2.create_vpc, CidrBlock=cidr_block)
        vpc_id = vpc["Vpc"]["VpcId"]
        
        # Tag the VPC
        await safe_aws_call(
            ec2.create_tags,
            Resources=[vpc_id],
            Tags=[
                {"Key": "Name", "Value": vpc_name},
                {"Key": filter_tag_name, "Value": filter_tag_value},
                {"Key": "CreatedBy", "Value": creator_value},
            ],
        )
        
        # Enable DNS support and hostnames
        await safe_aws_call(
            ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsHostnames={"Value": True}
        )
        await safe_aws_call(
            ec2.modify_vpc_attribute, VpcId=vpc_id, EnableDnsSupport={"Value": True}
        )
        
        logger.info(f"Created VPC {vpc_id} in {region}")
        return vpc_id
        
    except AWSClientError:
        logger.error(f"Failed to create VPC in {region}")
        raise


async def create_subnet(
    region: str,
    vpc_id: str,
    zone: str,
    resource_prefix: str,
    filter_tag_name: str,
    filter_tag_value: str,
    creator_value: str,
    cidr_block: Optional[str] = None,
) -> str:
    """
    Create a subnet in the specified VPC and availability zone.
    
    Args:
        region: AWS region
        vpc_id: VPC ID
        zone: Availability zone
        resource_prefix: Prefix for resource names
        filter_tag_name: Tag name for filtering
        filter_tag_value: Tag value for filtering
        creator_value: Value for the CreatedBy tag
        cidr_block: CIDR block for the subnet (optional)
        
    Returns:
        Subnet ID
        
    Raises:
        AWSClientError: If subnet creation fails
    """
    ec2 = get_boto3_client("ec2", region)
    
    try:
        # Check if a subnet already exists in the specified zone
        existing_subnets = await safe_aws_call(
            ec2.describe_subnets,
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "availability-zone", "Values": [zone]},
                {"Name": f"tag:{filter_tag_name}", "Values": [filter_tag_value]},
            ],
        )
        
        if existing_subnets["Subnets"]:
            # Use the first matching subnet
            subnet_id = existing_subnets["Subnets"][0]["SubnetId"]
            logger.info(f"Using existing subnet {subnet_id} in {zone}")
            return subnet_id
        
        # Try different CIDR blocks until we find one that works
        cidr_base_prefix = "10.0."
        cidr_base_suffix = ".0/24"
        
        # If CIDR block is provided, try it first
        if cidr_block:
            try:
                subnet = await safe_aws_call(
                    ec2.create_subnet,
                    VpcId=vpc_id,
                    CidrBlock=cidr_block,
                    AvailabilityZone=zone,
                )
                
                subnet_id = subnet["Subnet"]["SubnetId"]
                logger.info(f"Created subnet {subnet_id} in {zone} with CIDR {cidr_block}")
                
                # Tag the subnet
                await safe_aws_call(
                    ec2.create_tags,
                    Resources=[subnet_id],
                    Tags=[
                        {"Key": "Name", "Value": f"{resource_prefix}-Subnet-{zone}"},
                        {"Key": filter_tag_name, "Value": filter_tag_value},
                        {"Key": "CreatedBy", "Value": creator_value},
                        {"Key": "Zone", "Value": zone},
                    ],
                )
                
                return subnet_id
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] != "InvalidSubnet.Conflict":
                    raise AWSClientError(f"Failed to create subnet in {zone}: {str(e)}", e)
        
        # Try different CIDR blocks
        for i in range(256):
            try:
                cidr = f"{cidr_base_prefix}{i}{cidr_base_suffix}"
                logger.debug(f"Trying to create subnet in {zone} with CIDR {cidr}")
                
                subnet = await safe_aws_call(
                    ec2.create_subnet,
                    VpcId=vpc_id,
                    CidrBlock=cidr,
                    AvailabilityZone=zone,
                )
                
                subnet_id = subnet["Subnet"]["SubnetId"]
                logger.info(f"Created subnet {subnet_id} in {zone} with CIDR {cidr}")
                
                # Tag the subnet
                await safe_aws_call(
                    ec2.create_tags,
                    Resources=[subnet_id],
                    Tags=[
                        {"Key": "Name", "Value": f"{resource_prefix}-Subnet-{zone}"},
                        {"Key": filter_tag_name, "Value": filter_tag_value},
                        {"Key": "CreatedBy", "Value": creator_value},
                        {"Key": "Zone", "Value": zone},
                    ],
                )
                
                return subnet_id
                
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "InvalidSubnet.Conflict":
                    # This CIDR is already in use, try the next one
                    continue
                else:
                    # Re-raise other errors
                    raise AWSClientError(f"Failed to create subnet in {zone}: {str(e)}", e)
        
        # If we've tried all CIDRs and none worked, raise an error
        raise AWSResourceError(
            f"Unable to create subnet in {zone}. All CIDR blocks are in use.",
            resource_type="subnet"
        )
        
    except AWSClientError:
        logger.error(f"Failed to create subnet in {zone}")
        raise


async def create_internet_gateway(
    region: str,
    vpc_id: str,
    resource_prefix: str,
    filter_tag_name: str,
    filter_tag_value: str,
    creator_value: str,
) -> str:
    """
    Create an internet gateway and attach it to the VPC.
    
    Args:
        region: AWS region
        vpc_id: VPC ID
        resource_prefix: Prefix for resource names
        filter_tag_name: Tag name for filtering
        filter_tag_value: Tag value for filtering
        creator_value: Value for the CreatedBy tag
        
    Returns:
        Internet gateway ID
        
    Raises:
        AWSClientError: If internet gateway creation or attachment fails
    """
    ec2 = get_boto3_client("ec2", region)
    
    try:
        # Check if an internet gateway is already attached to the VPC
        igws = await safe_aws_call(
            ec2.describe_internet_gateways,
            Filters=[
                {"Name": "attachment.vpc-id", "Values": [vpc_id]},
                {"Name": f"tag:{filter_tag_name}", "Values": [filter_tag_value]},
            ],
        )
        
        if igws["InternetGateways"]:
            # Use the first matching internet gateway
            igw_id = igws["InternetGateways"][0]["InternetGatewayId"]
            logger.info(f"Using existing internet gateway {igw_id} for VPC {vpc_id}")
            return igw_id
        
        # Check for any internet gateway attached to the VPC (even if not tagged)
        all_igws = await safe_aws_call(
            ec2.describe_internet_gateways,
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
        )
        
        if all_igws["InternetGateways"]:
            # Use the first attached internet gateway and tag it
            igw_id = all_igws["InternetGateways"][0]["InternetGatewayId"]
            logger.info(f"Found attached internet gateway {igw_id} for VPC {vpc_id}, tagging it")
            
            await safe_aws_call(
                ec2.create_tags,
                Resources=[igw_id],
                Tags=[
                    {"Key": "Name", "Value": f"{resource_prefix}-IGW"},
                    {"Key": filter_tag_name, "Value": filter_tag_value},
                    {"Key": "CreatedBy", "Value": creator_value},
                ],
            )
            
            return igw_id
        
        # Create a new internet gateway
        logger.info(f"Creating new internet gateway for VPC {vpc_id}")
        igw = await safe_aws_call(ec2.create_internet_gateway)
        igw_id = igw["InternetGateway"]["InternetGatewayId"]
        
        # Tag the internet gateway
        await safe_aws_call(
            ec2.create_tags,
            Resources=[igw_id],
            Tags=[
                {"Key": "Name", "Value": f"{resource_prefix}-IGW"},
                {"Key": filter_tag_name, "Value": filter_tag_value},
                {"Key": "CreatedBy", "Value": creator_value},
            ],
        )
        
        # Attach the internet gateway to the VPC
        try:
            await safe_aws_call(
                ec2.attach_internet_gateway, InternetGatewayId=igw_id, VpcId=vpc_id
            )
            logger.info(f"Attached internet gateway {igw_id} to VPC {vpc_id}")
            
        except Exception as e:
            # If attachment fails, delete the internet gateway and check if another one was created
            logger.error(f"Failed to attach internet gateway {igw_id} to VPC {vpc_id}: {str(e)}")
            
            try:
                await safe_aws_call(ec2.delete_internet_gateway, InternetGatewayId=igw_id)
            except Exception as delete_error:
                logger.error(f"Failed to delete internet gateway {igw_id}: {str(delete_error)}")
            
            # Check if another internet gateway was attached concurrently
            try:
                concurrent_igws = await safe_aws_call(
                    ec2.describe_internet_gateways,
                    Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
                )
                
                if concurrent_igws["InternetGateways"]:
                    # Use and tag the concurrent internet gateway
                    concurrent_igw_id = concurrent_igws["InternetGateways"][0]["InternetGatewayId"]
                    logger.info(f"Using concurrently created internet gateway {concurrent_igw_id}")
                    
                    await safe_aws_call(
                        ec2.create_tags,
                        Resources=[concurrent_igw_id],
                        Tags=[
                            {"Key": "Name", "Value": f"{resource_prefix}-IGW"},
                            {"Key": filter_tag_name, "Value": filter_tag_value},
                            {"Key": "CreatedBy", "Value": creator_value},
                        ],
                    )
                    
                    return concurrent_igw_id
                
            except Exception as check_error:
                logger.error(f"Failed to check for concurrent internet gateways: {str(check_error)}")
            
            # Re-raise the original error
            raise AWSClientError(f"Failed to attach internet gateway to VPC {vpc_id}", e)
        
        return igw_id
        
    except AWSClientError:
        logger.error(f"Failed to create or attach internet gateway for VPC {vpc_id}")
        raise


async def create_route_table(
    region: str,
    vpc_id: str,
    igw_id: str,
    resource_prefix: str,
    filter_tag_name: str,
    filter_tag_value: str,
    creator_value: str,
) -> str:
    """
    Create a route table with a route to the internet gateway.
    
    Args:
        region: AWS region
        vpc_id: VPC ID
        igw_id: Internet gateway ID
        resource_prefix: Prefix for resource names
        filter_tag_name: Tag name for filtering
        filter_tag_value: Tag value for filtering
        creator_value: Value for the CreatedBy tag
        
    Returns:
        Route table ID
        
    Raises:
        AWSClientError: If route table creation or route creation fails
    """
    ec2 = get_boto3_client("ec2", region)
    
    try:
        # Check if a tagged route table already exists for the VPC
        tagged_route_tables = await safe_aws_call(
            ec2.describe_route_tables,
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": f"tag:{filter_tag_name}", "Values": [filter_tag_value]},
            ],
        )
        
        if tagged_route_tables["RouteTables"]:
            # Use the first matching route table
            route_table_id = tagged_route_tables["RouteTables"][0]["RouteTableId"]
            routes = tagged_route_tables["RouteTables"][0].get("Routes", [])
            
            # Ensure it has the internet gateway route
            if not any(route.get("GatewayId") == igw_id for route in routes):
                await safe_aws_call(
                    ec2.create_route,
                    RouteTableId=route_table_id,
                    DestinationCidrBlock="0.0.0.0/0",
                    GatewayId=igw_id,
                )
                logger.info(f"Added route to internet gateway {igw_id} in route table {route_table_id}")
                
            logger.info(f"Using existing route table {route_table_id} for VPC {vpc_id}")
            return route_table_id
        
        # Check for the main route table
        route_tables = await safe_aws_call(
            ec2.describe_route_tables,
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
        )
        
        for rt in route_tables["RouteTables"]:
            for association in rt.get("Associations", []):
                if association.get("Main", False):
                    # Use the main route table
                    route_table_id = rt["RouteTableId"]
                    routes = rt.get("Routes", [])
                    
                    # Tag the main route table
                    await safe_aws_call(
                        ec2.create_tags,
                        Resources=[route_table_id],
                        Tags=[
                            {"Key": "Name", "Value": f"{resource_prefix}-RouteTable"},
                            {"Key": filter_tag_name, "Value": filter_tag_value},
                            {"Key": "CreatedBy", "Value": creator_value},
                        ],
                    )
                    
                    # Add route to internet gateway if it doesn't exist
                    if not any(route.get("GatewayId") == igw_id for route in routes):
                        await safe_aws_call(
                            ec2.create_route,
                            RouteTableId=route_table_id,
                            DestinationCidrBlock="0.0.0.0/0",
                            GatewayId=igw_id,
                        )
                        logger.info(f"Added route to internet gateway {igw_id} in main route table {route_table_id}")
                        
                    logger.info(f"Using main route table {route_table_id} for VPC {vpc_id}")
                    return route_table_id
        
        # Create a new route table
        logger.info(f"Creating new route table for VPC {vpc_id}")
        route_table = await safe_aws_call(ec2.create_route_table, VpcId=vpc_id)
        route_table_id = route_table["RouteTable"]["RouteTableId"]
        
        # Tag the route table
        await safe_aws_call(
            ec2.create_tags,
            Resources=[route_table_id],
            Tags=[
                {"Key": "Name", "Value": f"{resource_prefix}-RouteTable"},
                {"Key": filter_tag_name, "Value": filter_tag_value},
                {"Key": "CreatedBy", "Value": creator_value},
            ],
        )
        
        # Add route to internet gateway
        await safe_aws_call(
            ec2.create_route,
            RouteTableId=route_table_id,
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=igw_id,
        )
        
        # Make it the main route table for the VPC
        await safe_aws_call(
            ec2.associate_route_table,
            RouteTableId=route_table_id,
            VpcId=vpc_id,
        )
        
        logger.info(f"Created route table {route_table_id} for VPC {vpc_id} with route to internet gateway {igw_id}")
        return route_table_id
        
    except AWSClientError:
        logger.error(f"Failed to create route table for VPC {vpc_id}")
        raise


async def associate_route_table(
    region: str, route_table_id: str, subnet_id: str
) -> None:
    """
    Associate a route table with a subnet.
    
    Args:
        region: AWS region
        route_table_id: Route table ID
        subnet_id: Subnet ID
        
    Raises:
        AWSClientError: If route table association fails
    """
    ec2 = get_boto3_client("ec2", region)
    
    try:
        await safe_aws_call(
            ec2.associate_route_table, RouteTableId=route_table_id, SubnetId=subnet_id
        )
        logger.info(f"Associated route table {route_table_id} with subnet {subnet_id}")
        
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "Resource.AlreadyAssociated":
            logger.info(f"Route table {route_table_id} already associated with subnet {subnet_id}")
        else:
            logger.error(f"Failed to associate route table {route_table_id} with subnet {subnet_id}: {str(e)}")
            raise AWSClientError(f"Failed to associate route table with subnet", e)


async def create_security_group(
    region: str,
    vpc_id: str,
    resource_prefix: str,
    filter_tag_name: str,
    filter_tag_value: str,
    creator_value: str,
) -> str:
    """
    Create a security group with rules for SSH and Bacalhau services.
    
    Args:
        region: AWS region
        vpc_id: VPC ID
        resource_prefix: Prefix for resource names
        filter_tag_name: Tag name for filtering
        filter_tag_value: Tag value for filtering
        creator_value: Value for the CreatedBy tag
        
    Returns:
        Security group ID
        
    Raises:
        AWSClientError: If security group creation or rule creation fails
    """
    ec2 = get_boto3_client("ec2", region)
    
    try:
        # Check for security groups with our tag
        tagged_security_groups = await safe_aws_call(
            ec2.describe_security_groups,
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": f"tag:{filter_tag_name}", "Values": [filter_tag_value]},
            ],
        )
        
        if tagged_security_groups["SecurityGroups"]:
            # Use the first matching security group
            sg_id = tagged_security_groups["SecurityGroups"][0]["GroupId"]
            logger.info(f"Using existing security group {sg_id} for VPC {vpc_id}")
            return sg_id
        
        # Check for security groups with our name
        security_groups = await safe_aws_call(
            ec2.describe_security_groups,
            Filters=[
                {"Name": "group-name", "Values": [f"{resource_prefix}SG"]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ],
        )
        
        if security_groups["SecurityGroups"]:
            # Use the first matching security group and tag it
            sg_id = security_groups["SecurityGroups"][0]["GroupId"]
            logger.info(f"Found security group {sg_id} with name {resource_prefix}SG, tagging it")
            
            await safe_aws_call(
                ec2.create_tags,
                Resources=[sg_id],
                Tags=[
                    {"Key": "Name", "Value": f"{resource_prefix}SG"},
                    {"Key": filter_tag_name, "Value": filter_tag_value},
                    {"Key": "CreatedBy", "Value": creator_value},
                ],
            )
            
            return sg_id
        
        # Create a new security group
        logger.info(f"Creating new security group for VPC {vpc_id}")
        security_group = await safe_aws_call(
            ec2.create_security_group,
            GroupName=f"{resource_prefix}SG",
            Description="Security group for Bacalhau Spot Instances",
            VpcId=vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [
                        {"Key": "Name", "Value": f"{resource_prefix}SG"},
                        {"Key": filter_tag_name, "Value": filter_tag_value},
                        {"Key": "CreatedBy", "Value": creator_value},
                    ],
                }
            ],
        )
        
        sg_id = security_group["GroupId"]
        logger.info(f"Created security group {sg_id} for VPC {vpc_id}")
        
        # Add ingress rules
        logger.info(f"Adding ingress rules to security group {sg_id}")
        await safe_aws_call(
            ec2.authorize_security_group_ingress,
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH access"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1234,
                    "ToPort": 1234,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Bacalhau health check"}
                    ],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 1235,
                    "ToPort": 1235,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Bacalhau service"}
                    ],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 6001,
                    "ToPort": 6001,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Bacalhau service"}
                    ],
                },
            ],
        )
        
        return sg_id
        
    except AWSClientError:
        logger.error(f"Failed to create security group for VPC {vpc_id}")
        raise


async def clean_up_vpc_resources(region: str, vpc_id: str) -> bool:
    """
    Clean up all resources associated with a VPC.
    
    Args:
        region: AWS region
        vpc_id: VPC ID
        
    Returns:
        True if cleanup was successful, False otherwise
    """
    ec2 = get_boto3_client("ec2", region)
    
    # Helper function to update status log
    async def update_status(message: str) -> None:
        logger.info(message)
    
    try:
        # First check if the VPC exists
        try:
            vpc_response = await safe_aws_call(
                ec2.describe_vpcs,
                VpcIds=[vpc_id],
            )
            if not vpc_response.get("Vpcs"):
                logger.info(f"VPC {vpc_id} not found - already deleted")
                return True
                
        except botocore.exceptions.ClientError as e:
            if "InvalidVpcID.NotFound" in str(e):
                logger.info(f"VPC {vpc_id} not found - already deleted")
                return True
            else:
                raise
    
        # 1. Find and delete NAT Gateways
        await update_status(f"Looking for NAT gateways in VPC {vpc_id}")
        try:
            nat_gateways = await safe_aws_call(
                ec2.describe_nat_gateways,
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
            )
            
            nat_count = 0
            for nat in nat_gateways.get("NatGateways", []):
                nat_count += 1
                nat_id = nat.get("NatGatewayId")
                await update_status(f"Deleting NAT gateway {nat_id}")
                
                try:
                    await safe_aws_call(
                        ec2.delete_nat_gateway,
                        NatGatewayId=nat_id,
                    )
                    logger.info(f"NAT gateway {nat_id} deletion initiated")
                    
                except Exception as e:
                    logger.warning(f"Error deleting NAT gateway {nat_id}: {str(e)}")
                    
            if nat_count == 0:
                await update_status(f"No NAT gateways found in VPC {vpc_id}")
            elif nat_count > 0:
                # Wait for NAT gateways to start deleting
                await update_status(f"Waiting for {nat_count} NAT gateways to start deleting")
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.warning(f"Error checking for NAT gateways: {str(e)}")
    
        # 2. Release Elastic IPs
        await update_status(f"Looking for Elastic IPs in VPC {vpc_id}")
        try:
            eips = await safe_aws_call(ec2.describe_addresses)
            
            eip_count = 0
            for eip in eips.get("Addresses", []):
                # Check if EIP has tags matching our filter
                has_matching_tag = False
                if "Tags" in eip:
                    for tag in eip["Tags"]:
                        if tag["Key"] == "ManagedBy" and tag["Value"] == "SpotInstanceScript":
                            has_matching_tag = True
                            break
                            
                if has_matching_tag or "Tags" not in eip:
                    allocation_id = eip.get("AllocationId")
                    if allocation_id:
                        eip_count += 1
                        await update_status(f"Releasing Elastic IP {allocation_id}")
                        
                        try:
                            await safe_aws_call(
                                ec2.release_address,
                                AllocationId=allocation_id,
                            )
                            logger.info(f"Released Elastic IP {allocation_id}")
                            
                        except Exception as e:
                            logger.warning(f"Error releasing Elastic IP {allocation_id}: {str(e)}")
                            
            if eip_count == 0:
                await update_status(f"No Elastic IPs found for VPC {vpc_id}")
                
        except Exception as e:
            logger.warning(f"Error checking for Elastic IPs: {str(e)}")
    
        # 3. Delete Network Interfaces
        await update_status(f"Looking for network interfaces in VPC {vpc_id}")
        try:
            eni_response = await safe_aws_call(
                ec2.describe_network_interfaces,
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
            )
            
            eni_count = 0
            for eni in eni_response.get("NetworkInterfaces", []):
                eni_count += 1
                eni_id = eni.get("NetworkInterfaceId")
                
                # Skip attached interfaces
                if eni.get("Status") == "in-use":
                    await update_status(f"Skipping attached network interface {eni_id}")
                    continue
                    
                await update_status(f"Deleting network interface {eni_id}")
                try:
                    await safe_aws_call(
                        ec2.delete_network_interface,
                        NetworkInterfaceId=eni_id,
                    )
                    logger.info(f"Deleted network interface {eni_id}")
                    
                except Exception as e:
                    logger.warning(f"Error deleting network interface {eni_id}: {str(e)}")
                    
            if eni_count == 0:
                await update_status(f"No available network interfaces found in VPC {vpc_id}")
                
        except Exception as e:
            logger.warning(f"Error checking for network interfaces: {str(e)}")
    
        # 4. Delete Security Groups
        await update_status(f"Looking for security groups in VPC {vpc_id}")
        try:
            sgs = await safe_aws_call(
                ec2.describe_security_groups,
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "tag:ManagedBy", "Values": ["SpotInstanceScript"]},
                ],
            )
            
            # If no tagged security groups found, try all non-default ones
            if not sgs["SecurityGroups"]:
                sgs = await safe_aws_call(
                    ec2.describe_security_groups,
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
                )
                
            sg_count = 0
            for sg in sgs["SecurityGroups"]:
                if sg["GroupName"] != "default":
                    sg_count += 1
                    sg_id = sg["GroupId"]
                    await update_status(f"Deleting security group {sg_id} ({sg['GroupName']})")
                    
                    try:
                        await safe_aws_call(ec2.delete_security_group, GroupId=sg_id)
                        logger.info(f"Deleted security group {sg_id}")
                        
                    except Exception as e:
                        logger.warning(f"Error deleting security group {sg_id}: {str(e)}")
                        
            if sg_count == 0:
                await update_status(f"No non-default security groups found in VPC {vpc_id}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up security groups: {str(e)}")
    
        # 5. Delete Subnets
        await update_status(f"Looking for subnets in VPC {vpc_id}")
        try:
            subnets = await safe_aws_call(
                ec2.describe_subnets,
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
            )
            
            subnet_count = 0
            for subnet in subnets["Subnets"]:
                subnet_count += 1
                subnet_id = subnet["SubnetId"]
                await update_status(f"Deleting subnet {subnet_id}")
                
                try:
                    await safe_aws_call(ec2.delete_subnet, SubnetId=subnet_id)
                    logger.info(f"Deleted subnet {subnet_id}")
                    
                except Exception as e:
                    logger.warning(f"Error deleting subnet {subnet_id}: {str(e)}")
                    
            if subnet_count == 0:
                await update_status(f"No subnets found in VPC {vpc_id}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up subnets: {str(e)}")
    
        # 6. Delete Route Tables
        await update_status(f"Looking for route tables in VPC {vpc_id}")
        try:
            rts = await safe_aws_call(
                ec2.describe_route_tables,
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
            )
            
            rt_count = 0
            for rt in rts["RouteTables"]:
                # Skip main route tables
                if any(assoc.get("Main", False) for assoc in rt.get("Associations", [])):
                    continue
                    
                rt_count += 1
                rt_id = rt["RouteTableId"]
                
                # First disassociate any subnets
                for assoc in rt.get("Associations", []):
                    if "AssociationId" in assoc:
                        assoc_id = assoc["AssociationId"]
                        await update_status(f"Disassociating route table {rt_id} association {assoc_id}")
                        
                        try:
                            await safe_aws_call(
                                ec2.disassociate_route_table,
                                AssociationId=assoc_id,
                            )
                            logger.info(f"Disassociated route table association {assoc_id}")
                            
                        except Exception as e:
                            logger.warning(f"Error disassociating route table {assoc_id}: {str(e)}")
                            
                # Now delete the route table
                await update_status(f"Deleting route table {rt_id}")
                try:
                    await safe_aws_call(
                        ec2.delete_route_table,
                        RouteTableId=rt_id,
                    )
                    logger.info(f"Deleted route table {rt_id}")
                    
                except Exception as e:
                    logger.warning(f"Error deleting route table {rt_id}: {str(e)}")
                    
            if rt_count == 0:
                await update_status(f"No non-main route tables found in VPC {vpc_id}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up route tables: {str(e)}")
    
        # 7. Detach and Delete Internet Gateways
        await update_status(f"Looking for internet gateways attached to VPC {vpc_id}")
        try:
            igws = await safe_aws_call(
                ec2.describe_internet_gateways,
                Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}],
            )
            
            igw_count = 0
            for igw in igws["InternetGateways"]:
                igw_count += 1
                igw_id = igw["InternetGatewayId"]
                
                # First detach
                await update_status(f"Detaching internet gateway {igw_id}")
                try:
                    await safe_aws_call(
                        ec2.detach_internet_gateway,
                        InternetGatewayId=igw_id,
                        VpcId=vpc_id,
                    )
                    logger.info(f"Detached internet gateway {igw_id}")
                    
                except Exception as e:
                    logger.warning(f"Error detaching internet gateway {igw_id}: {str(e)}")
                    continue  # Skip deletion if detach fails
                    
                # Then delete
                await update_status(f"Deleting internet gateway {igw_id}")
                try:
                    await safe_aws_call(
                        ec2.delete_internet_gateway,
                        InternetGatewayId=igw_id,
                    )
                    logger.info(f"Deleted internet gateway {igw_id}")
                    
                except Exception as e:
                    logger.warning(f"Error deleting internet gateway {igw_id}: {str(e)}")
                    
            if igw_count == 0:
                await update_status(f"No internet gateways found attached to VPC {vpc_id}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up internet gateways: {str(e)}")
    
        # 8. Finally delete the VPC itself
        await update_status(f"Deleting VPC {vpc_id}")
        try:
            await safe_aws_call(ec2.delete_vpc, VpcId=vpc_id)
            await update_status(f"VPC {vpc_id} successfully deleted")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting VPC {vpc_id}: {str(e)}")
            await update_status(f"Failed to delete VPC {vpc_id}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error cleaning up VPC {vpc_id}: {str(e)}")
        return False