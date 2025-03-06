"""
Spot instance creation module.

This module provides functions for creating spot instances and managing
their lifecycle. It includes robust error handling and structured progress
reporting.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, cast, Any

import botocore.exceptions

from ..aws.client import (AWSClientError, AWSCredentialError, AWSResourceError, 
                        AWSTimeoutError, safe_aws_call, get_boto3_client)
from ..aws.vpc import (associate_route_table, create_internet_gateway,
                      create_route_table, create_security_group,
                      create_subnet, create_vpc_if_not_exists)
from ..config.config_manager import ConfigManager, get_config, ConfigError
from ..ui.console import (console, print_error, print_info, print_success,
                         print_warning, display_state)
from ..utils.models import (ErrorType, InstanceStatus, SpotInstanceStatus, 
                          OperationResult, RegionStatistics)

# Configure logger
logger = logging.getLogger(__name__)


class SpotCreationError(Exception):
    """Exception raised for errors during spot instance creation."""
    
    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN):
        self.error_type = error_type
        super().__init__(message)


async def get_user_data(config: ConfigManager) -> Optional[str]:
    """
    Get the user data for spot instances.
    
    Args:
        config: Configuration manager instance
        
    Returns:
        Base64-encoded user data string or None on error
    """
    try:
        # This is a placeholder - in a real implementation, you would
        # generate user data from templates in the config
        placeholder_user_data = "#!/bin/bash\necho 'Bacalhau Spot Instance Starting...'\n"
        encoded_user_data = base64.b64encode(placeholder_user_data.encode()).decode()
        
        logger.debug("Generated user data template")
        return encoded_user_data
        
    except Exception as e:
        logger.error(f"Error generating user data: {str(e)}", exc_info=True)
        return None


async def create_spot_instances(
    config_path: str = "config.yaml",
    timeout: int = 30,
    dry_run: bool = False,
) -> OperationResult:
    """
    Create spot instances according to the configuration.
    
    This function orchestrates the creation of spot instances across multiple AWS regions,
    handling network setup, spot request creation, and monitoring their fulfillment.
    
    Args:
        config_path: Path to the configuration file
        timeout: AWS API timeout in seconds
        dry_run: Show what would be done without making any changes
        
    Returns:
        Operation result object with success/failure status and details
    """
    # Set display task name and total
    display_state.task_name = "Creating Spot Instances"
    
    # Create operation result object
    result = OperationResult(action="create")
    
    try:
        # Load configuration
        config = get_config(config_path)
        
        # Get regions and total instances
        aws_regions = config.get_regions()
        total_instances = config.get_total_instances()
        display_state.task_total = total_instances
        
        if not aws_regions:
            raise ConfigError("No AWS regions configured")
            
        if total_instances <= 0:
            raise ConfigError("Total instances must be greater than 0")
        
        # Get tag settings
        tag_settings = config.get_tag_settings()
        filter_tag_name = tag_settings["filter_tag_name"]
        filter_tag_value = tag_settings["filter_tag_value"]
        creator_value = tag_settings["creator_value"]
        resource_prefix = tag_settings["resource_prefix"]
        vpc_name = tag_settings["vpc_name"]
        
        # Generate user data
        user_data = await get_user_data(config)
        if not user_data:
            raise SpotCreationError(
                "Failed to generate user data template", 
                ErrorType.CONFIG_ISSUES
            )
        
        # Log configuration
        logger.info(f"Creating spot instances in {len(aws_regions)} regions")
        logger.info(f"Total instances to create: {total_instances}")
        
        if dry_run:
            logger.info("DRY RUN MODE: No changes will be made")
            print_warning("DRY RUN MODE: No changes will be made")
            
        # Create instances in batches by region to avoid overwhelming the AWS API
        batch_size = 10  # Process 10 regions at a time
        region_batches = [
            aws_regions[i : i + batch_size]
            for i in range(0, len(aws_regions), batch_size)
        ]
        
        total_created = 0
        total_requested = 0
        
        # Track created instances by region
        creation_results = {}
        
        # Process each batch of regions
        for batch_num, region_batch in enumerate(region_batches, 1):
            logger.info(
                f"Processing batch {batch_num}/{len(region_batches)} with {len(region_batch)} regions"
            )
            
            # Calculate instances per region (distribute evenly if not specified)
            batch_total = 0
            region_instances = {}
            
            for region in region_batch:
                # Initialize region statistics
                if region not in creation_results:
                    creation_results[region] = RegionStatistics(region=region)
                
                # Get node count for this region
                node_count = config.get_node_count(region, default=1)
                region_instances[region] = node_count
                batch_total += node_count
                
            logger.info(f"Batch {batch_num} will create {batch_total} instances")
            
            # Create tasks for each region
            create_tasks = []
            for region in region_batch:
                node_count = region_instances[region]
                logger.info(f"Creating {node_count} instance(s) in region: {region}")
                
                create_tasks.append(
                    create_instances_in_region(
                        config=config,
                        region=region,
                        instances_to_create=node_count,
                        filter_tag_name=filter_tag_name,
                        filter_tag_value=filter_tag_value,
                        creator_value=creator_value,
                        resource_prefix=resource_prefix,
                        vpc_name=vpc_name,
                        user_data=user_data,
                        timeout=timeout,
                        dry_run=dry_run,
                    )
                )
                
            # Run tasks in parallel with proper error handling
            batch_results = []
            try:
                # Run all tasks and wait for them to complete
                batch_results = await asyncio.gather(*create_tasks, return_exceptions=True)
                
                # Process results, handling exceptions
                for i, res in enumerate(batch_results):
                    region = region_batch[i]
                    
                    if isinstance(res, Exception):
                        # Handle exception for this region
                        logger.error(f"Error creating instances in {region}: {str(res)}")
                        
                        # Set error type in display state
                        if isinstance(res, AWSCredentialError):
                            display_state.error_types["credential_issues"] = True
                        elif "capacity" in str(res).lower():
                            display_state.error_types["capacity_issues"] = True
                        elif "price" in str(res).lower():
                            display_state.error_types["price_issues"] = True
                        elif isinstance(res, ConfigError) or "configuration" in str(res).lower():
                            display_state.error_types["config_issues"] = True
                        elif "network" in str(res).lower():
                            display_state.error_types["network_issues"] = True
                            
                        # Update statistics for this region
                        creation_results[region].add_zone_stat(
                            zone="", 
                            total=region_instances[region],
                            failed=region_instances[region]
                        )
                        
                    else:
                        # Process successful result
                        instance_ids, instances_requested = res
                        
                        # Update counts
                        total_created += len(instance_ids)
                        total_requested += instances_requested
                        
                        # Add statistics for this region
                        # Note: detailed zone statistics are updated within create_instances_in_region
                        
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}", exc_info=True)
                
                # Don't re-raise - continue with next batch
                print_warning(f"Error in batch {batch_num}, continuing with remaining batches")
            
            # Wait for public IPs for this batch (but don't fail if we can't get them)
            if total_created > 0:
                logger.info(f"Waiting for public IPs for batch {batch_num}...")
                try:
                    await wait_for_batch_public_ips()
                except Exception as e:
                    logger.error(f"Error waiting for public IPs: {str(e)}", exc_info=True)
                    print_warning("Error waiting for public IPs, continuing...")
                
        # Log final results
        logger.info(
            f"All batches processed: requested {total_requested} instances, created {total_created} across all regions"
        )
        
        # Check if any instances were created
        instances_with_ip = sum(
            1 for status in display_state.all_statuses.values() if status.public_ip
        )
        
        if total_created > 0:
            # Save machine information to JSON
            try:
                save_result = await save_machines_to_json(operation="update")
                logger.info(f"Saved machine information to MACHINES.json: {save_result}")
            except Exception as e:
                logger.error(f"Error saving machine information: {str(e)}", exc_info=True)
                save_result = False
            
            # Build result summary
            result.result_summary = {
                "total_requested": total_requested,
                "total_created": total_created,
                "instances_with_ip": instances_with_ip,
                "success_rate": float(instances_with_ip) / float(total_requested) if total_requested > 0 else 0.0,
                "machines_saved": save_result,
                "regions": {
                    region: stats.to_dict() for region, stats in creation_results.items()
                },
            }
            
            # Check if we had partial success
            if instances_with_ip < total_requested:
                result.complete(success=True)
                print_warning(
                    f"Partial success: Created {instances_with_ip} of {total_requested} requested instances"
                )
            else:
                result.complete(success=True)
                print_success(f"Successfully created {instances_with_ip} instances")
                
        else:
            # No instances were created
            error_message = "No instances were created"
            logger.error(error_message)
            
            # Determine error type
            error_type = ErrorType.UNKNOWN
            for error_name, error_value in display_state.error_types.items():
                if error_value:
                    if error_name == "credential_issues":
                        error_type = ErrorType.CREDENTIAL_ISSUES
                    elif error_name == "capacity_issues":
                        error_type = ErrorType.CAPACITY_ISSUES
                    elif error_name == "price_issues":
                        error_type = ErrorType.PRICE_ISSUES
                    elif error_name == "config_issues":
                        error_type = ErrorType.CONFIG_ISSUES
                    elif error_name == "network_issues":
                        error_type = ErrorType.NETWORK_ISSUES
                    break
                    
            print_error(error_message, error_type)
            
            # Set error in result
            result.set_error(error_message, error_type)
            
            # Add summary information
            result.result_summary = {
                "total_requested": total_requested,
                "total_created": 0,
                "instances_with_ip": 0,
                "success_rate": 0.0,
                "error_type": error_type.value,
                "regions": {
                    region: stats.to_dict() for region, stats in creation_results.items()
                },
            }
            
        return result
        
    except ConfigError as e:
        logger.error(f"Configuration error: {str(e)}", exc_info=True)
        result.set_error(str(e), ErrorType.CONFIG_ISSUES)
        return result
        
    except SpotCreationError as e:
        logger.error(f"Spot creation error: {str(e)}", exc_info=True)
        result.set_error(str(e), e.error_type)
        return result
        
    except AWSCredentialError as e:
        logger.error(f"AWS credential error: {str(e)}", exc_info=True)
        result.set_error(str(e), ErrorType.CREDENTIAL_ISSUES)
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error creating spot instances: {str(e)}", exc_info=True)
        result.set_error(str(e))
        return result

async def create_instances_in_region(
    config: ConfigManager,
    region: str,
    instances_to_create: int,
    filter_tag_name: str,
    filter_tag_value: str,
    creator_value: str,
    resource_prefix: str,
    vpc_name: str,
    user_data: str,
    timeout: int = 30,
    dry_run: bool = False,
) -> Tuple[List[str], int]:
    """
    Create spot instances in a specific region.
    
    This function handles the creation of network resources (VPC, subnets, etc.)
    and spot instances in a specific AWS region.
    
    Args:
        config: Configuration manager
        region: AWS region
        instances_to_create: Number of instances to create
        filter_tag_name: Tag name for filtering resources
        filter_tag_value: Tag value for filtering resources
        creator_value: Value for the CreatedBy tag
        resource_prefix: Prefix for resource names
        vpc_name: Name for the VPC
        user_data: Base64-encoded user data for instances
        timeout: AWS API timeout in seconds
        dry_run: Show what would be done without making changes
        
    Returns:
        Tuple of (list of instance IDs, number of instances requested)
        
    Raises:
        AWSCredentialError: If AWS credentials are invalid
        AWSTimeoutError: If AWS API calls timeout
        AWSResourceError: If AWS resources can't be created
        SpotCreationError: If spot instances can't be created
    """
    # Track error types
    error_types = {
        "credential_issues": False,
        "capacity_issues": False,
        "price_issues": False,
        "config_issues": False,
    }
    
    # Get region configuration
    region_cfg = config.get_region_config(region)
    instance_type = region_cfg.get("machine_type", "t2.medium")
    
    # Get AWS EC2 client
    ec2 = get_boto3_client("ec2", region, timeout=timeout)
    
    # Create the VPC and network resources (or use existing ones)
    try:
        if dry_run:
            # In dry run mode, just log what would be done
            logger.info(f"DRY RUN: Would create or use existing VPC in {region}")
            vpc_id = "vpc-dryrun"
            subnet_id = "subnet-dryrun"
            security_group_id = "sg-dryrun"
            logger.info(f"DRY RUN: Would create spot instance in {region} with type {instance_type}")
            
            # Create a dummy instance status for display
            for i in range(instances_to_create):
                status = InstanceStatus(region=region, zone=f"{region}a", index=i)
                status.status = SpotInstanceStatus.REQUESTING
                status.detailed_status = f"DRY RUN: Would create {instance_type} instance"
                await display_state.add_status(status)
                
            # Return empty instance list but correct requested count
            return [], instances_to_create
            
        # Create or get existing VPC
        vpc_id = await create_vpc_if_not_exists(
            region=region,
            vpc_name=vpc_name,
            filter_tag_name=filter_tag_name,
            filter_tag_value=filter_tag_value,
            creator_value=creator_value,
        )
        
        # Get availability zones for this region
        zones = await get_availability_zones(ec2)
        
        # Create internet gateway
        igw_id = await create_internet_gateway(
            region=region,
            vpc_id=vpc_id,
            resource_prefix=resource_prefix,
            filter_tag_name=filter_tag_name,
            filter_tag_value=filter_tag_value,
            creator_value=creator_value,
        )
        
        # Create route table
        route_table_id = await create_route_table(
            region=region,
            vpc_id=vpc_id,
            igw_id=igw_id,
            resource_prefix=resource_prefix,
            filter_tag_name=filter_tag_name,
            filter_tag_value=filter_tag_value,
            creator_value=creator_value,
        )
        
        # Create security group
        security_group_id = await create_security_group(
            region=region,
            vpc_id=vpc_id,
            resource_prefix=resource_prefix,
            filter_tag_name=filter_tag_name,
            filter_tag_value=filter_tag_value,
            creator_value=creator_value,
        )
        
        # Now create the instances
        instance_ids = []
        
        for i in range(instances_to_create):
            # Choose availability zone (distribute evenly)
            zone = zones[i % len(zones)]
            
            # Create subnet with CIDR block based on index
            subnet_id = await create_subnet(
                region=region,
                vpc_id=vpc_id,
                zone=zone,
                resource_prefix=resource_prefix,
                filter_tag_name=filter_tag_name,
                filter_tag_value=filter_tag_value,
                creator_value=creator_value,
                cidr_block=f"10.0.{i}.0/24",
            )
            
            # Associate route table with subnet
            await associate_route_table(region, route_table_id, subnet_id)
            
            # Create instance status
            status = InstanceStatus(region=region, zone=zone, index=i)
            status.status = SpotInstanceStatus.REQUESTING
            status.detailed_status = f"Requesting {instance_type} spot instance"
            status.vpc_id = vpc_id
            await display_state.add_status(status)
            
            # Create a launch specification for the spot instance
            launch_spec = {
                "ImageId": config.get_image_for_region(region),
                "InstanceType": instance_type,
                "UserData": user_data,
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {"DeleteOnTermination": True},
                    }
                ],
                "NetworkInterfaces": [
                    {
                        "DeviceIndex": 0,
                        "AssociatePublicIpAddress": True,
                        "DeleteOnTermination": True,
                        "SubnetId": subnet_id,
                        "Groups": [security_group_id],
                    }
                ],
            }
            
            # Log request details
            logger.info(f"Requesting spot instance in {region}-{zone}")
            logger.info(f"  Instance type: {instance_type}")
            logger.info(f"  Image ID: {launch_spec['ImageId']}")
            
            # Update status
            status.detailed_status = "Submitting spot request to AWS"
            await display_state.add_status(status)
            
            # Create the spot request
            try:
                response = await safe_aws_call(
                    ec2.request_spot_instances,
                    InstanceCount=1,
                    Type="one-time",
                    InstanceInterruptionBehavior="terminate",
                    LaunchSpecification=launch_spec,
                    TagSpecifications=[
                        {
                            "ResourceType": "spot-instances-request",
                            "Tags": [
                                {
                                    "Key": "Name",
                                    "Value": f"{resource_prefix}-{region}-{zone}",
                                },
                                {"Key": filter_tag_name, "Value": filter_tag_value},
                            ],
                        },
                    ],
                )
                
                # Process spot request response
                if "SpotInstanceRequests" in response and response["SpotInstanceRequests"]:
                    request = response["SpotInstanceRequests"][0]
                    spot_request_id = request.get("SpotInstanceRequestId", "unknown")
                    status.spot_request_id = spot_request_id
                    
                    # Update status
                    status.status = SpotInstanceStatus.WAITING_FOR_FULFILLMENT
                    status.detailed_status = "Waiting for AWS to fulfill spot request"
                    await display_state.add_status(status)
                    
                    # Wait for spot request to be fulfilled
                    instance_id = await wait_for_spot_fulfillment(
                        ec2, spot_request_id, status, timeout=300
                    )
                    
                    if instance_id:
                        # Request was fulfilled
                        instance_ids.append(instance_id)
                        status.instance_id = instance_id
                        status.fulfilled = True
                        status.status = SpotInstanceStatus.FULFILLED
                        status.detailed_status = "Spot request fulfilled, tagging instance"
                        await display_state.add_status(status)
                        
                        # Tag the instance
                        await safe_aws_call(
                            ec2.create_tags,
                            Resources=[instance_id],
                            Tags=[
                                {
                                    "Key": "Name",
                                    "Value": f"{resource_prefix}-{region}-{zone}",
                                },
                                {"Key": filter_tag_name, "Value": filter_tag_value},
                                {"Key": "AZ", "Value": zone},
                                {"Key": "CreatedBy", "Value": creator_value},
                            ],
                        )
                        
                        # Try to get instance details
                        instance_details = await safe_aws_call(
                            ec2.describe_instances,
                            InstanceIds=[instance_id],
                        )
                        
                        # Extract public and private IPs
                        if (
                            instance_details
                            and "Reservations" in instance_details
                            and instance_details["Reservations"]
                        ):
                            instance = instance_details["Reservations"][0]["Instances"][0]
                            status.public_ip = instance.get("PublicIpAddress")
                            status.private_ip = instance.get("PrivateIpAddress")
                            
                        # Update status
                        status.status = SpotInstanceStatus.RUNNING
                        status.detailed_status = "Instance running"
                        await display_state.add_status(status)
                        
                    else:
                        # Request timed out or was not fulfilled
                        status.status = SpotInstanceStatus.FAILED
                        status.detailed_status = "Spot request was not fulfilled"
                        status.error_type = ErrorType.CAPACITY_ISSUES
                        error_types["capacity_issues"] = True
                        await display_state.add_status(status)
                        
                else:
                    # No spot request was created
                    status.status = SpotInstanceStatus.FAILED
                    status.detailed_status = "No spot request was created"
                    status.error_type = ErrorType.UNKNOWN
                    await display_state.add_status(status)
                    
            except AWSClientError as e:
                # Handle spot request errors
                logger.error(f"Error requesting spot instance in {region}-{zone}: {str(e)}")
                
                status.status = SpotInstanceStatus.FAILED
                status.detailed_status = f"Error: {str(e)}"
                
                # Categorize error types
                if isinstance(e, AWSCredentialError):
                    status.error_type = ErrorType.CREDENTIAL_ISSUES
                    error_types["credential_issues"] = True
                    display_state.error_types["credential_issues"] = True
                    raise  # Re-raise credential errors to abort the entire region
                    
                elif "capacity" in str(e).lower():
                    status.error_type = ErrorType.CAPACITY_ISSUES
                    error_types["capacity_issues"] = True
                    display_state.error_types["capacity_issues"] = True
                    
                elif "price" in str(e).lower():
                    status.error_type = ErrorType.PRICE_ISSUES
                    error_types["price_issues"] = True
                    display_state.error_types["price_issues"] = True
                    
                elif "invalid" in str(e).lower() or "configuration" in str(e).lower():
                    status.error_type = ErrorType.CONFIG_ISSUES
                    error_types["config_issues"] = True
                    display_state.error_types["config_issues"] = True
                    
                else:
                    status.error_type = ErrorType.UNKNOWN
                    
                await display_state.add_status(status)
                
        # Return created instances and requested count
        return instance_ids, instances_to_create
        
    except AWSCredentialError as e:
        # Handle credential errors
        display_state.error_types["credential_issues"] = True
        logger.error(f"AWS credential error in {region}: {str(e)}")
        raise
        
    except AWSTimeoutError as e:
        # Handle timeout errors
        display_state.error_types["network_issues"] = True
        logger.error(f"AWS timeout error in {region}: {str(e)}")
        raise SpotCreationError(
            f"AWS API timeout in region {region}: {str(e)}", 
            ErrorType.NETWORK_ISSUES
        )
        
    except AWSResourceError as e:
        # Handle resource errors
        display_state.error_types["config_issues"] = True
        logger.error(f"AWS resource error in {region}: {str(e)}")
        raise SpotCreationError(
            f"AWS resource error in region {region}: {str(e)}", 
            ErrorType.CONFIG_ISSUES
        )
        
    except Exception as e:
        # Handle any other errors
        logger.error(f"Error creating instances in {region}: {str(e)}", exc_info=True)
        
        # Try to categorize the error
        if "capacity" in str(e).lower():
            display_state.error_types["capacity_issues"] = True
            error_type = ErrorType.CAPACITY_ISSUES
        elif "price" in str(e).lower():
            display_state.error_types["price_issues"] = True
            error_type = ErrorType.PRICE_ISSUES
        elif "invalid" in str(e).lower() or "configuration" in str(e).lower():
            display_state.error_types["config_issues"] = True
            error_type = ErrorType.CONFIG_ISSUES
        elif "network" in str(e).lower() or "timeout" in str(e).lower():
            display_state.error_types["network_issues"] = True
            error_type = ErrorType.NETWORK_ISSUES
        else:
            error_type = ErrorType.UNKNOWN
            
        raise SpotCreationError(
            f"Error creating instances in region {region}: {str(e)}", 
            error_type
        )

async def create_spot_instances_json(
    config_path: str = "config.yaml",
    timeout: int = 30,
    dry_run: bool = False,
) -> Dict:
    """
    Create spot instances and return JSON-serializable results.
    
    Args:
        config_path: Path to the configuration file
        timeout: AWS API timeout in seconds
        dry_run: Show what would be done without making changes
        
    Returns:
        JSON-serializable result data
    """
    # Create spot instances
    result = await create_spot_instances(
        config_path=config_path,
        timeout=timeout,
        dry_run=dry_run,
    )
    
    # Convert to JSON-serializable format
    return result.to_dict()


# Second definition removed to prevent duplication


async def get_availability_zones(ec2: any) -> List[str]:
    """
    Get available zones in a region.
    
    Args:
        ec2: EC2 client
        
    Returns:
        List of availability zone names
        
    Raises:
        AWSClientError: If there's an issue with the AWS API call
    """
    try:
        response = await safe_aws_call(
            ec2.describe_availability_zones,
            Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}],
        )
        
        # Get all available zones
        zones = [zone["ZoneName"] for zone in response["AvailabilityZones"]]
        
        if not zones:
            logger.warning("No availability zones found, using region with 'a' suffix")
            # If no zones found, use the region name with 'a' suffix as a fallback
            region = ec2.meta.region_name if hasattr(ec2, 'meta') else "unknown"
            return [f"{region}a"]
            
        logger.info(f"Found {len(zones)} availability zones")
        return zones
        
    except Exception as e:
        logger.error(f"Error getting availability zones: {str(e)}", exc_info=True)
        # Return at least one zone to allow the process to continue
        region = ec2.meta.region_name if hasattr(ec2, 'meta') else "unknown"
        return [f"{region}a"]


async def wait_for_spot_fulfillment(
    ec2: any, spot_request_id: str, status: InstanceStatus, timeout: int = 300
) -> Optional[str]:
    """
    Wait for a spot request to be fulfilled.
    
    This function periodically polls the AWS API to check if a spot request
    has been fulfilled. It updates the status object as the request progresses.
    
    Args:
        ec2: EC2 client
        spot_request_id: Spot request ID
        status: Instance status object to update
        timeout: Timeout in seconds
        
    Returns:
        Instance ID if the request was fulfilled, None otherwise
        
    Raises:
        AWSClientError: If there's an issue with AWS API calls
    """
    # Record start time for timeout calculation
    start_time = time.time()
    poll_interval = 5  # seconds
    
    # Keep track of failures that indicate we should stop waiting
    fatal_failure_codes = [
        "price-too-low",
        "capacity-not-available",
        "capacity-oversubscribed",
        "capacity-unavailable",
        "constraint-not-fulfillable",
        "instance-terminated-by-price",
        "instance-terminated-capacity",
        "bad-parameters",
        "bad-instance-type",
        "service-not-supported",
    ]
    
    try:
        logger.info(f"Waiting for spot request {spot_request_id} to be fulfilled (timeout: {timeout}s)")
        
        # Update status initially
        status.detailed_status = "Waiting for spot request fulfillment"
        await display_state.add_status(status)
        
        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            
            try:
                # Get spot request status
                response = await safe_aws_call(
                    ec2.describe_spot_instance_requests,
                    SpotInstanceRequestIds=[spot_request_id],
                )
                
                # Process response
                if "SpotInstanceRequests" in response and response["SpotInstanceRequests"]:
                    request = response["SpotInstanceRequests"][0]
                    request_status = request.get("Status", {})
                    status_code = request_status.get("Code", "unknown")
                    status_message = request_status.get("Message", "No message")
                    
                    # Update status with current state
                    status.detailed_status = f"{status_code}: {status_message} (elapsed: {elapsed:.1f}s)"
                    await display_state.add_status(status)
                    
                    # Check for fatal failure codes that mean we should stop waiting
                    if status_code in fatal_failure_codes:
                        logger.error(f"Spot request {spot_request_id} failed: {status_code} - {status_message}")
                        
                        # Set error type based on status code
                        if "capacity" in status_code.lower() or "capacity" in status_message.lower():
                            status.error_type = ErrorType.CAPACITY_ISSUES
                            display_state.error_types["capacity_issues"] = True
                        elif "price" in status_code.lower() or "price" in status_message.lower():
                            status.error_type = ErrorType.PRICE_ISSUES
                            display_state.error_types["price_issues"] = True
                        elif "parameter" in status_code.lower() or "constraint" in status_code.lower():
                            status.error_type = ErrorType.CONFIG_ISSUES
                            display_state.error_types["config_issues"] = True
                            
                        status.status = SpotInstanceStatus.FAILED
                        await display_state.add_status(status)
                        return None
                        
                    # Check for success - instance ID is present
                    if "InstanceId" in request:
                        instance_id = request["InstanceId"]
                        logger.info(f"Spot request {spot_request_id} fulfilled with instance ID: {instance_id}")
                        return instance_id
                else:
                    # No spot request found - log warning but continue polling
                    logger.warning(f"No spot request found with ID {spot_request_id}")
                    status.detailed_status = f"No spot request found (elapsed: {elapsed:.1f}s)"
                    await display_state.add_status(status)
                    
            except AWSClientError as e:
                logger.error(f"Error checking spot request {spot_request_id}: {str(e)}")
                
                # Update status with error but continue polling
                status.detailed_status = f"Error checking status: {str(e)} (elapsed: {elapsed:.1f}s)"
                await display_state.add_status(status)
                
                # If it's a credential error, re-raise it
                if isinstance(e, AWSCredentialError):
                    status.error_type = ErrorType.CREDENTIAL_ISSUES
                    display_state.error_types["credential_issues"] = True
                    status.status = SpotInstanceStatus.FAILED
                    await display_state.add_status(status)
                    raise
                    
            # Wait before next poll
            await asyncio.sleep(poll_interval)
            
        # If we get here, we timed out
        elapsed = time.time() - start_time
        timeout_message = f"Timed out after {elapsed:.1f}s waiting for spot request {spot_request_id}"
        logger.warning(timeout_message)
        
        status.status = SpotInstanceStatus.TIMEOUT
        status.detailed_status = timeout_message
        status.error_type = ErrorType.CAPACITY_ISSUES
        display_state.error_types["capacity_issues"] = True
        await display_state.add_status(status)
        
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error waiting for spot request {spot_request_id}: {str(e)}", exc_info=True)
        
        status.status = SpotInstanceStatus.FAILED
        status.detailed_status = f"Unexpected error: {str(e)}"
        status.error_type = ErrorType.UNKNOWN
        await display_state.add_status(status)
        
        return None


async def wait_for_batch_public_ips() -> None:
    """
    Wait for public IPs for instances in a batch.
    
    This function finds instances without public IP addresses and polls
    the AWS API to get their IP addresses. It updates the status objects
    with the new IP addresses.
    
    Returns:
        None
    """
    # Find instances without IPs
    pending_instances = [
        status 
        for status in display_state.all_statuses.values()
        if status.instance_id and not status.public_ip
    ]
    
    if not pending_instances:
        logger.debug("No instances waiting for IPs")
        return
        
    # Group by region
    instances_by_region = {}
    for status in pending_instances:
        if status.region not in instances_by_region:
            instances_by_region[status.region] = []
        instances_by_region[status.region].append(status)
        
    # Poll for IPs in each region
    for region, statuses in instances_by_region.items():
        try:
            # Get instance IDs
            instance_ids = [
                status.instance_id for status in statuses 
                if status.instance_id
            ]
            
            if not instance_ids:
                continue
                
            # Create EC2 client
            ec2 = get_boto3_client("ec2", region)
            
            # Get instance details
            response = await safe_aws_call(
                ec2.describe_instances,
                InstanceIds=instance_ids,
            )
            
            # Process results
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    public_ip = instance.get("PublicIpAddress")
                    private_ip = instance.get("PrivateIpAddress")
                    
                    # Find the status object
                    for status in statuses:
                        if status.instance_id == instance_id:
                            # Update IPs
                            if public_ip and not status.public_ip:
                                status.public_ip = public_ip
                                status.detailed_status = "Public IP assigned"
                                await display_state.add_status(status)
                                
                            if private_ip:
                                status.private_ip = private_ip
                                await display_state.add_status(status)
                                
        except Exception as e:
            logger.error(f"Error getting IPs in {region}: {str(e)}")


async def save_machines_to_json(operation: str = "update") -> bool:
    """
    Save machine information to MACHINES.json.
    
    This function saves the current machine status information to a JSON file,
    which can be used to track the state of the cluster.
    
    Args:
        operation: Operation type ("update" or "delete")
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create temporary file
        temp_file = "MACHINES.json.tmp"
        
        # Load existing data if file exists
        existing_data = {}
        existing_machines = {}
        
        if os.path.exists("MACHINES.json"):
            try:
                with open("MACHINES.json", "r") as f:
                    existing_data = json.load(f)
                    existing_machines = existing_data.get("machines", {})
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in MACHINES.json, treating as empty")
                existing_data = {}
                existing_machines = {}
                
        # Convert all statuses to dictionary
        current_machines = {
            status.id: status.to_dict()
            for status in display_state.all_statuses.values()
        }
        
        if operation == "update":
            # Update existing machines with current ones
            machines_data = {**existing_machines, **current_machines}
            
            # Log operations
            new_count = len(set(current_machines.keys()) - set(existing_machines.keys()))
            updated_count = len(set(current_machines.keys()) & set(existing_machines.keys()))
            logger.info(f"Adding {new_count} new and updating {updated_count} existing machines")
            
        elif operation == "delete":
            # Remove current machines from existing ones
            machines_to_remove = set(current_machines.keys())
            machines_data = {
                k: v for k, v in existing_machines.items() if k not in machines_to_remove
            }
            
            # Log operation
            removed_count = len(machines_to_remove)
            logger.info(f"Removing {removed_count} machines from MACHINES.json")
            
        else:
            # Default to just using current machines
            machines_data = current_machines
            
        # Extract regions from the machines data
        regions = set()
        for machine_data in machines_data.values():
            if isinstance(machine_data, dict) and "region" in machine_data:
                region = machine_data["region"]
                if region:
                    regions.add(region)
                    
        # Prepare output data
        output_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "machines": machines_data,
            "total_count": len(machines_data),
            "regions": list(regions),
            "last_operation": operation,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        
        # Write to temporary file
        with open(temp_file, "w") as f:
            json.dump(output_data, indent=2, default=str, sort_keys=True, fp=f)
            f.flush()
            
        # Atomic rename
        os.replace(temp_file, "MACHINES.json")
        
        # Log success
        logger.info(f"Saved {len(machines_data)} machine records to MACHINES.json")
        return True
        
    except Exception as e:
        logger.error(f"Error saving machines to JSON: {str(e)}", exc_info=True)
        return False