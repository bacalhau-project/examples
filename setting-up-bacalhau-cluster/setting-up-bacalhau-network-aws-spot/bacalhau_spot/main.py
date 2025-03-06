"""
Main entry point for the Bacalhau spot instance deployment tool.

This module provides the command-line interface and orchestrates the
deployment process.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import traceback
from typing import Dict, List, Optional

from .config.config_manager import ConfigError, get_config
from .ui.console import (console, display_state, print_error, print_info, print_success,
                        print_warning, setup_logging, start_display,
                        stop_display)
from .utils.models import ErrorType

# Configure logger
logger = logging.getLogger(__name__)


def print_architecture_mismatch_summary(result) -> None:
    """
    Print a detailed summary of architecture mismatch errors.
    
    Args:
        result: Operation result with error information
    """
    console.print("\n" + "=" * 80)
    console.print("ARCHITECTURE MISMATCH ERROR".center(80))
    console.print("=" * 80)
    
    console.print("\nYou are trying to use ARM instance types (t4g, a1, c6g, etc.) with x86_64 AMIs.")
    console.print("This is not compatible. You need to use ARM AMIs with ARM instances.")
    
    console.print("\nDetected mismatches:")
    mismatches = {}
    
    # Extract region and instance type info from error messages
    error_msg = str(result.error)
    if hasattr(result, 'region_errors') and result.region_errors:
        for region, error in result.region_errors.items():
            instance_type = error.get('instance_type', 'unknown')
            ami = error.get('ami', 'unknown')
            instance_arch = 'arm64' if any(x in instance_type for x in ['t4g', 'a1', 'c6g', 'm6g', 'r6g']) else 'x86_64'
            ami_arch = error.get('ami_arch', 'x86_64')
            
            if instance_arch != ami_arch:
                mismatches[region] = {
                    'instance_type': instance_type,
                    'instance_arch': instance_arch,
                    'ami': ami,
                    'ami_arch': ami_arch
                }
    
    if mismatches:
        for region, info in mismatches.items():
            console.print(f"  - Region: {region}")
            console.print(f"    Instance: {info['instance_type']} (Architecture: {info['instance_arch']})")
            console.print(f"    AMI: {info['ami']} (Architecture: {info['ami_arch']})")
            console.print()
    
    console.print("\nRECOMMENDED SOLUTIONS:")
    console.print("1. Use t3a.small instead of t4g.small (t3a is x86_64 and same price range)")
    console.print("2. OR update your config.yaml to use ARM64 AMIs (run util/get_ubuntu_amis.py)")
    console.print("3. OR run util/verify_config_architecture.py to validate your config")
    console.print("\nFor more information about ARM vs x86_64, see:")
    console.print("https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/processor-arch.html")
    console.print("=" * 80)


def print_detailed_error_summary(result) -> None:
    """
    Print a detailed summary of operation errors.
    
    Args:
        result: Operation result with error information
    """
    console.print("\n" + "=" * 80)
    console.print("OPERATION FAILED".center(80))
    console.print("=" * 80)
    
    console.print(f"\nError: {result.error}")
    
    if hasattr(result, 'region_errors') and result.region_errors:
        console.print("\nDetails by region:")
        for region, error in result.region_errors.items():
            error_msg = error.get('error', 'Unknown error')
            console.print(f"  - {region}: {error_msg}")
    
    console.print("\nCheck debug.log for more detailed information")
    console.print("=" * 80)


def print_success_summary(result) -> None:
    """
    Print a summary of successfully created instances.
    
    Args:
        result: Operation result with instance information
    """
    if not hasattr(result, 'instances') or not result.instances:
        console.print("\nNo instances were created.")
        return
        
    console.print("\n" + "=" * 80)
    console.print("INSTANCES CREATED SUCCESSFULLY".center(80))
    console.print("=" * 80)
    
    # Create a table of instances
    console.print(f"\nTotal instances created: {len(result.instances)}")
    
    header = "| {:<8} | {:<15} | {:<15} | {:<20} | {:<15} |".format(
        "Region", "Instance ID", "Instance Type", "Public IP", "Private IP"
    )
    separator = "-" * len(header)
    
    console.print(separator)
    console.print(header)
    console.print(separator)
    
    for instance in result.instances:
        console.print("| {:<8} | {:<15} | {:<15} | {:<20} | {:<15} |".format(
            instance.region,
            instance.instance_id[:15],
            instance.instance_type,
            instance.public_ip or "N/A",
            instance.private_ip or "N/A"
        ))
    
    console.print(separator)
    
    console.print("\nTo connect to instances, use SSH with your private key:")
    console.print("ssh -i /path/to/your/key.pem ubuntu@<public-ip>")
    
    console.print("\nBacalhau service should be started automatically on the instances.")
    console.print("Check status with: ssh -i /path/to/key.pem ubuntu@<public-ip> 'systemctl status bacalhau-startup'")
    console.print("=" * 80)


def print_instance_list_summary(result) -> None:
    """
    Print a summary of existing instances.
    
    Args:
        result: Operation result with instance information
    """
    if not hasattr(result, 'instances') or not result.instances:
        console.print("\nNo instances found.")
        return
        
    console.print("\n" + "=" * 80)
    console.print("CURRENT INSTANCES".center(80))
    console.print("=" * 80)
    
    # Create a table of instances
    console.print(f"\nTotal instances: {len(result.instances)}")
    
    header = "| {:<8} | {:<15} | {:<15} | {:<20} | {:<15} | {:<12} |".format(
        "Region", "Instance ID", "Instance Type", "Public IP", "Private IP", "Status"
    )
    separator = "-" * len(header)
    
    console.print(separator)
    console.print(header)
    console.print(separator)
    
    for instance in result.instances:
        console.print("| {:<8} | {:<15} | {:<15} | {:<20} | {:<15} | {:<12} |".format(
            instance.region,
            instance.instance_id[:15],
            instance.instance_type,
            instance.public_ip or "N/A",
            instance.private_ip or "N/A",
            instance.status
        ))
    
    console.print(separator)
    console.print("=" * 80)


def print_destroy_summary(result) -> None:
    """
    Print a summary of destroyed instances.
    
    Args:
        result: Operation result with destroyed instance information
    """
    console.print("\n" + "=" * 80)
    console.print("INSTANCE DESTRUCTION SUMMARY".center(80))
    console.print("=" * 80)
    
    if result.success:
        if hasattr(result, 'destroyed_count'):
            console.print(f"\nSuccessfully terminated {result.destroyed_count} instances")
        else:
            console.print("\nAll requested instances were terminated successfully")
    else:
        console.print(f"\nError: {result.error}")
        
        if hasattr(result, 'region_errors') and result.region_errors:
            console.print("\nErrors by region:")
            for region, error in result.region_errors.items():
                console.print(f"  - {region}: {error}")
    
    console.print("=" * 80)


def print_nuke_summary(result) -> None:
    """
    Print a summary of nuked resources.
    
    Args:
        result: Operation result with resource information
    """
    console.print("\n" + "=" * 80)
    console.print("AWS RESOURCE NUKE SUMMARY".center(80))
    console.print("=" * 80)
    
    if result.success:
        if hasattr(result, 'nuked_resources'):
            resources = result.nuked_resources
            console.print("\nDeleted resources:")
            
            if resources.get('instances', 0) > 0:
                console.print(f"  - EC2 Instances: {resources.get('instances', 0)}")
            if resources.get('spot_requests', 0) > 0:
                console.print(f"  - Spot Requests: {resources.get('spot_requests', 0)}")
            if resources.get('vpcs', 0) > 0:
                console.print(f"  - VPCs: {resources.get('vpcs', 0)}")
            if resources.get('security_groups', 0) > 0:
                console.print(f"  - Security Groups: {resources.get('security_groups', 0)}")
            if resources.get('subnets', 0) > 0:
                console.print(f"  - Subnets: {resources.get('subnets', 0)}")
            if resources.get('internet_gateways', 0) > 0:
                console.print(f"  - Internet Gateways: {resources.get('internet_gateways', 0)}")
            if resources.get('route_tables', 0) > 0:
                console.print(f"  - Route Tables: {resources.get('route_tables', 0)}")
                
            console.print("\nAll tagged resources have been deleted")
        else:
            console.print("\nAll requested resources were nuked successfully")
    else:
        console.print(f"\nError: {result.error}")
        
        if hasattr(result, 'region_errors') and result.region_errors:
            console.print("\nErrors by region:")
            for region, error in result.region_errors.items():
                console.print(f"  - {region}: {error}")
    
    console.print("=" * 80)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Manage Bacalhau spot instances across multiple AWS regions."
    )
    
    # Primary action to perform
    parser.add_argument(
        "action",
        choices=["create", "destroy", "list", "delete_disconnected_aws_nodes", "nuke"],
        help="Action to perform",
        nargs="?",
        default="list",
    )
    
    # Output format
    parser.add_argument(
        "--format",
        choices=["default", "json"],
        default="default",
        help="Output format",
    )
    
    # AWS API timeout
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="AWS API timeout in seconds",
    )
    
    # Verbose output
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug output",
    )
    
    # Force delete without confirmation
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force delete all resources without confirmation (for nuke action)",
    )
    
    # Configuration file
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file",
    )
    
    # Dry run mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making any changes",
    )
    
    # Debug mode - don't handle exceptions at this level
    parser.add_argument(
        "--debug",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden option for development
    )
    
    return parser.parse_args()


def handle_sigint(signum, frame):
    """
    Handle interrupt signal (Ctrl+C).
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info("Received interrupt signal, shutting down...")
    print_warning("Operation cancelled by user.")
    
    # Stop the display if it's running
    try:
        stop_display()
    except Exception:
        pass
    
    sys.exit(1)


async def main() -> None:
    """
    Main entry point for the application.
    
    This function initializes the application, parses command line arguments,
    and dispatches to the appropriate action handler.
    """
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, handle_sigint)
    
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging with appropriate verbosity
    setup_logging(
        verbose=args.verbose,
        log_file="debug.log",
        log_to_console=True,
    )
    
    # Log start of execution
    logger.info(f"Starting with action: {args.action}")
    logger.info(f"Using configuration file: {args.config}")
    
    try:
        # Load configuration
        config = get_config(args.config)
        
        # Validate configuration for current action
        await validate_config_for_action(config, args.action)
        
        # Dispatch to action handler based on format
        if args.format == "json":
            # JSON output format - no interactive UI
            await dispatch_action_json(args)
        else:
            # Default interactive UI
            await dispatch_action_interactive(args)
            
    except ConfigError as e:
        logger.error(f"Configuration error: {str(e)}")
        print_error(f"Configuration error: {str(e)}", ErrorType.CONFIG_ISSUES)
        raise RuntimeError(f"Configuration error: {str(e)}") if args.debug else None
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        print_error(f"Unexpected error: {str(e)}")
        raise e if args.debug else None
        
    finally:
        logger.info("Execution completed")


async def validate_config_for_action(config: any, action: str) -> None:
    """
    Validate configuration for the specified action.
    
    Args:
        config: Configuration manager
        action: Action to validate for
        
    Raises:
        ConfigError: If configuration is invalid for the action
    """
    # Minimal validation - specific actions may have additional requirements
    if action == "create":
        # Check if regions are defined
        if not config.get_regions():
            raise ConfigError("No regions defined in configuration")
            
        # Check if total instances is defined
        if config.get_total_instances() <= 0:
            raise ConfigError("Total instances must be greater than 0")
    
    elif action in ["destroy", "list"]:
        # These actions don't require specific configuration
        pass


async def dispatch_action_interactive(args: argparse.Namespace) -> None:
    """
    Dispatch to the appropriate action handler with interactive UI.
    
    Args:
        args: Command line arguments
    """
    # Start the display
    display_task = None
    
    try:
        # Start UI display task
        display_task = asyncio.create_task(start_display())
        
        if args.action == "create":
            from .spot import create
            result = await create.create_spot_instances(
                config_path=args.config,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            
            # Check result for errors
            if not result.success:
                logger.error(f"Create operation failed: {result.error}")
                if result.error_type:
                    print_error(f"Create operation failed: {result.error}", result.error_type)
                else:
                    print_error(f"Create operation failed: {result.error}")
                    
                if args.debug:
                    raise RuntimeError(f"Create operation failed: {result.error}")
                    
        elif args.action == "destroy":
            from .spot import destroy
            result = await destroy.destroy_instances(
                force=args.force,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            
            # Check result for errors
            if not result.success:
                logger.error(f"Destroy operation failed: {result.error}")
                if result.error_type:
                    print_error(f"Destroy operation failed: {result.error}", result.error_type)
                else:
                    print_error(f"Destroy operation failed: {result.error}")
                    
                if args.debug:
                    raise RuntimeError(f"Destroy operation failed: {result.error}")
                    
        elif args.action == "list":
            from .spot import list_
            result = await list_.list_spot_instances(
                timeout=args.timeout,
            )
            
            # Check result for errors
            if not result.success:
                logger.error(f"List operation failed: {result.error}")
                if result.error_type:
                    print_error(f"List operation failed: {result.error}", result.error_type)
                else:
                    print_error(f"List operation failed: {result.error}")
                    
                if args.debug:
                    raise RuntimeError(f"List operation failed: {result.error}")
                    
        elif args.action == "delete_disconnected_aws_nodes":
            from .spot import cleanup
            result = await cleanup.delete_disconnected_aws_nodes()
            
            # Check result for errors
            if not result.success:
                logger.error(f"Cleanup operation failed: {result.error}")
                if result.error_type:
                    print_error(f"Cleanup operation failed: {result.error}", result.error_type)
                else:
                    print_error(f"Cleanup operation failed: {result.error}")
                    
                if args.debug:
                    raise RuntimeError(f"Cleanup operation failed: {result.error}")
                    
        elif args.action == "nuke":
            from .spot import destroy
            result = await destroy.nuke_all_resources(
                force=args.force,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            
            # Check result for errors
            if not result.success:
                logger.error(f"Nuke operation failed: {result.error}")
                if result.error_type:
                    print_error(f"Nuke operation failed: {result.error}", result.error_type)
                else:
                    print_error(f"Nuke operation failed: {result.error}")
                    
                if args.debug:
                    raise RuntimeError(f"Nuke operation failed: {result.error}")
                    
        else:
            error_msg = f"Unknown action: {args.action}"
            print_error(error_msg)
            logger.error(error_msg)
            if args.debug:
                raise ValueError(error_msg)
                
    except asyncio.CancelledError:
        logger.warning("Operation was cancelled")
        print_warning("Operation was cancelled")
            
    except Exception as e:
        logger.error(f"Error in {args.action} action: {str(e)}", exc_info=True)
        print_error(f"Error in {args.action} action: {str(e)}")
        
        # Log detailed information
        trace = traceback.format_exc()
        logger.debug(f"Traceback:\n{trace}")
        
        # Re-raise in debug mode
        if args.debug:
            raise
            
    finally:
        # Stop the display (which will also end the display_task)
        stop_display()
        
        # Make sure the display task is properly awaited
        if display_task:
            try:
                # Wait for the display to finish (with timeout)
                await asyncio.wait_for(display_task, timeout=3.0)
            except asyncio.TimeoutError:
                # If it doesn't finish in time, cancel it
                display_task.cancel()
                try:
                    await display_task
                except asyncio.CancelledError:
                    pass
                    
        # Print the saved console output if there was any
        if display_state.json_result:
            print(display_state.json_result)
            
        # Always print summary information after Rich display closes
        if args.action == "create" and "result" in locals():
            if not result.success:
                # Print detailed error summary
                if "Architecture mismatch" in str(result.error):
                    print_architecture_mismatch_summary(result)
                else:
                    print_detailed_error_summary(result)
            else:
                # Print success summary with instance details
                print_success_summary(result)
        elif args.action == "list" and "result" in locals():
            # Always print instance list after display closes
            print_instance_list_summary(result)
        elif args.action == "destroy" and "result" in locals():
            # Print destroy summary
            print_destroy_summary(result)
        elif args.action == "nuke" and "result" in locals():
            # Print nuke summary
            print_nuke_summary(result)


async def dispatch_action_json(args: argparse.Namespace) -> None:
    """
    Dispatch to the appropriate action handler with JSON output.
    
    Args:
        args: Command line arguments
    """
    try:
        import json
        
        result = {
            "action": args.action,
            "success": False,
            "data": None,
            "error": None,
        }
        
        if args.action == "create":
            from .spot import create
            data = await create.create_spot_instances_json(
                config_path=args.config,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            result["success"] = True
            result["data"] = data
            
        elif args.action == "destroy":
            from .spot import destroy
            data = await destroy.destroy_instances_json(
                force=args.force,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            result["success"] = True
            result["data"] = data
            
        elif args.action == "list":
            from .spot import list_
            data = await list_.list_spot_instances_json(
                timeout=args.timeout,
            )
            result["success"] = True
            result["data"] = data
            
        elif args.action == "delete_disconnected_aws_nodes":
            from .spot import cleanup
            data = await cleanup.delete_disconnected_aws_nodes_json()
            result["success"] = True
            result["data"] = data
            
        elif args.action == "nuke":
            from .spot import destroy
            data = await destroy.nuke_all_resources_json(
                force=args.force,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            result["success"] = True
            result["data"] = data
            
        else:
            result["error"] = f"Unknown action: {args.action}"
        
        # Store result for later printing after display closes
        display_state.json_result = json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        # Log error details
        logger.error(f"Error in {args.action} action: {str(e)}", exc_info=True)
        
        # Store error result for later printing after display closes
        error_result = {
            "action": args.action,
            "success": False,
            "data": None,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        
        import json
        display_state.json_result = json.dumps(error_result, indent=2, default=str)
        
        # Re-raise in debug mode
        if args.debug:
            raise


if __name__ == "__main__":
    asyncio.run(main())