"""
AWS client module provides safe boto3 client interactions with proper error handling.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, TypeVar, cast

import boto3
import botocore.config
import botocore.exceptions

# Type variable for generic return types
T = TypeVar('T')

# Configure logging
logger = logging.getLogger(__name__)

# Default timeout for AWS API calls
DEFAULT_API_TIMEOUT = 30  # seconds


class AWSClientError(Exception):
    """Base exception for AWS client errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.original_error = original_error
        super().__init__(message)


class AWSTimeoutError(AWSClientError):
    """Exception raised when an AWS API call times out."""
    
    def __init__(self, message: str, operation: str, region: str, 
                 timeout: int, original_error: Optional[Exception] = None):
        self.operation = operation
        self.region = region
        self.timeout = timeout
        super().__init__(
            f"{message} (Operation: {operation}, Region: {region}, Timeout: {timeout}s)", 
            original_error
        )


class AWSCredentialError(AWSClientError):
    """Exception raised when AWS credentials are invalid or expired."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, original_error)


class AWSResourceError(AWSClientError):
    """Exception raised when an AWS resource operation fails."""
    
    def __init__(self, message: str, resource_type: str, original_error: Optional[Exception] = None):
        self.resource_type = resource_type
        super().__init__(
            f"{message} (Resource Type: {resource_type})", 
            original_error
        )


def get_boto3_client(service_name: str, region: str, timeout: int = DEFAULT_API_TIMEOUT) -> Any:
    """
    Get a configured boto3 client with proper timeout and retry settings.
    
    Args:
        service_name: AWS service name (e.g., 'ec2', 's3')
        region: AWS region name
        timeout: Timeout for API calls in seconds
        
    Returns:
        Configured boto3 client
        
    Raises:
        AWSClientError: On client creation failure
    """
    try:
        logger.debug(f"Creating {service_name} client for region {region} with timeout={timeout}s")
        
        # Configure client with timeout and retry settings
        config = botocore.config.Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={"max_attempts": 3, "mode": "standard"},
        )
        
        # Create the client
        client = boto3.client(service_name, region_name=region, config=config)
        logger.debug(f"Successfully created {service_name} client for {region}")
        return client
        
    except botocore.exceptions.ClientError as e:
        error_code = getattr(e.response.get('Error', {}), 'Code', 'UnknownError')
        error_msg = getattr(e.response.get('Error', {}), 'Message', str(e))
        
        if any(code in error_code for code in ('ExpiredToken', 'InvalidToken')):
            logger.error(f"AWS credential error: {error_code} - {error_msg}")
            raise AWSCredentialError(
                "AWS credentials have expired or are invalid. Try running 'aws sso login'.",
                original_error=e
            )
        
        logger.error(f"Error creating {service_name} client for {region}: {error_code} - {error_msg}")
        raise AWSClientError(f"Failed to create {service_name} client in {region}: {error_msg}", e)
    
    except Exception as e:
        logger.error(f"Unexpected error creating {service_name} client for {region}: {str(e)}")
        raise AWSClientError(f"Unexpected error creating {service_name} client: {str(e)}", e)


async def safe_aws_call(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Execute an AWS API call safely with proper timeout and error handling.
    
    Args:
        func: AWS API function to call
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result from the AWS API call
        
    Raises:
        AWSTimeoutError: If the API call times out
        AWSCredentialError: If credentials are invalid
        AWSClientError: For other AWS API errors
    """
    # Extract region from function's __self__ if it's available
    region = getattr(func.__self__, 'meta', {}).get('region_name', 'unknown') 
    operation = func.__name__
    timeout = kwargs.pop('timeout', DEFAULT_API_TIMEOUT)
    
    try:
        logger.debug(f"Executing AWS operation {operation} in region {region}")
        
        # Execute the API call in a separate thread with timeout
        result = await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs), 
            timeout=timeout
        )
        
        return cast(T, result)
        
    except asyncio.TimeoutError as e:
        logger.error(f"AWS operation {operation} timed out after {timeout}s in region {region}")
        
        # Check for SSO credential issues
        if "describe_instances" in operation:
            logger.error("Timeout may be due to SSO credential issues. Try running 'aws sso login'.")
        
        raise AWSTimeoutError(
            "AWS API call timed out",
            operation=operation,
            region=region,
            timeout=timeout,
            original_error=e
        )
        
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'UnknownError')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(f"AWS operation {operation} failed: {error_code} - {error_msg}")
        
        # Handle credential errors
        if any(code in error_code for code in ('ExpiredToken', 'InvalidToken')):
            logger.error("AWS credentials have expired. Try running 'aws sso login'.")
            raise AWSCredentialError(
                "AWS credentials have expired or are invalid. Try running 'aws sso login'.",
                original_error=e
            )
            
        # Handle resource-specific errors
        if 'NotFound' in error_code:
            resource_type = error_code.replace('NotFound', '')
            raise AWSResourceError(
                f"AWS resource not found: {error_msg}",
                resource_type=resource_type,
                original_error=e
            )
            
        # Handle other client errors
        raise AWSClientError(
            f"AWS operation {operation} failed: {error_code} - {error_msg}",
            original_error=e
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in AWS operation {operation}: {str(e)}")
        raise AWSClientError(f"Unexpected error in AWS operation {operation}: {str(e)}", e)