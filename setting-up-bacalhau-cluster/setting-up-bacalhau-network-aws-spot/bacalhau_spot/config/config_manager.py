"""
Configuration manager for Bacalhau spot instance deployment.

This module provides functionality for loading, validating, and accessing
configuration settings for spot instance deployment.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import yaml

# Configure logger
logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class ConfigManager:
    """Manager for configuration settings."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file
            
        Raises:
            ConfigError: If the configuration file cannot be loaded or is invalid
        """
        self.config_path = config_path
        self.config_data: Dict[str, Any] = {}
        self.load_config()
        
    def load_config(self) -> None:
        """
        Load configuration from file.
        
        Raises:
            ConfigError: If the configuration file cannot be loaded or is invalid
        """
        try:
            if not os.path.exists(self.config_path):
                # Try alternative path with _example suffix
                example_path = f"{self.config_path}_example"
                if os.path.exists(example_path):
                    logger.warning(
                        f"Configuration file {self.config_path} not found. "
                        f"Using example configuration from {example_path}."
                    )
                    self.config_path = example_path
                else:
                    raise ConfigError(
                        f"Configuration file {self.config_path} not found and "
                        f"no example configuration available."
                    )
                    
            with open(self.config_path, "r") as f:
                self.config_data = yaml.safe_load(f)
                
            if not self.config_data:
                raise ConfigError(f"Configuration file {self.config_path} is empty.")
                
            # Validate configuration
            self._validate_config()
            
            logger.info(f"Loaded configuration from {self.config_path}")
            
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing configuration file {self.config_path}: {str(e)}")
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"Error loading configuration: {str(e)}")
            
    def _validate_config(self) -> None:
        """
        Validate the configuration.
        
        Raises:
            ConfigError: If the configuration is invalid
        """
        required_sections = ["aws", "regions", "bacalhau"]
        for section in required_sections:
            if section not in self.config_data:
                raise ConfigError(f"Required configuration section '{section}' is missing")
        
        if not self.get_regions():
            raise ConfigError("No regions configured")
            
        # Check if at least one region has a machine_type
        regions_section = self.config_data.get("regions", {})
        if not any(
            isinstance(region_config, dict) and "machine_type" in region_config
            for region_config in regions_section.values()
        ):
            raise ConfigError("No machine types configured for any region")
            
    def get_regions(self) -> List[str]:
        """
        Get the list of configured AWS regions.
        
        Returns:
            List of region names
        """
        regions_section = self.config_data.get("regions", {})
        return list(regions_section.keys())
        
    def get_region_config(self, region: str) -> Dict[str, Any]:
        """
        Get configuration for a specific region.
        
        Args:
            region: Region name
            
        Returns:
            Region-specific configuration
            
        Raises:
            ConfigError: If the region is not configured
        """
        regions_section = self.config_data.get("regions", {})
        if region not in regions_section:
            raise ConfigError(f"Region {region} is not configured")
            
        return cast(Dict[str, Any], regions_section.get(region, {}))
        
    def get_machine_type(self, region: str) -> str:
        """
        Get the machine type for a region.
        
        Args:
            region: Region name
            
        Returns:
            Machine type
            
        Raises:
            ConfigError: If no machine type is configured for the region
        """
        region_config = self.get_region_config(region)
        machine_type = region_config.get("machine_type")
        if not machine_type:
            raise ConfigError(f"No machine type configured for region {region}")
            
        return cast(str, machine_type)
        
    def get_image_for_region(self, region: str) -> str:
        """
        Get the AMI ID for a region.
        
        Args:
            region: Region name
            
        Returns:
            AMI ID
            
        Raises:
            ConfigError: If no AMI ID is configured for the region
        """
        region_config = self.get_region_config(region)
        ami_id = region_config.get("ami_id")
        
        # For backward compatibility
        if not ami_id and region_config.get("image") and region_config.get("image") != "auto":
            ami_id = region_config.get("image")
            
        if not ami_id:
            raise ConfigError(f"No AMI ID configured for region {region}")
            
        return cast(str, ami_id)
        
    def get_architecture_for_region(self, region: str) -> str:
        """
        Get the CPU architecture for a region.
        
        Args:
            region: Region name
            
        Returns:
            Architecture string ("x86_64" or "arm64")
            
        Note:
            Returns "x86_64" as default if not specified
        """
        region_config = self.get_region_config(region)
        architecture = region_config.get("architecture", "x86_64")
        return cast(str, architecture)
        
    def check_architecture_compatibility(self, region: str) -> bool:
        """
        Check if the machine type and AMI architecture are compatible in a region.
        
        Args:
            region: Region name
            
        Returns:
            True if compatible, False otherwise
            
        Note:
            ARM instance families include: a1, t4g, c6g, m6g, r6g
            x86 instance families include most others (t2, t3, m5, c5, etc.)
        """
        region_config = self.get_region_config(region)
        architecture = self.get_architecture_for_region(region)
        machine_type = self.get_machine_type(region)
        
        # Determine if the instance type is ARM-based
        is_arm_instance = any(family in machine_type for family in ["a1", "t4g", "c6g", "m6g", "r6g"])
        expected_arch = "arm64" if is_arm_instance else "x86_64"
        
        # Check if architectures match
        return architecture == expected_arch
        
    def get_node_count(self, region: str = "", default: int = 1) -> int:
        """
        Get the number of nodes to create in a region.
        
        Args:
            region: Region name (optional)
            default: Default node count if not specified
            
        Returns:
            Node count
        """
        if region:
            region_config = self.get_region_config(region)
            node_count = region_config.get("node_count", default)
            if isinstance(node_count, str) and node_count.lower() == "auto":
                # Calculate automatic node count
                total_regions = len(self.get_regions())
                total_instances = self.get_total_instances()
                return max(1, total_instances // total_regions)
            return int(node_count)
        else:
            # Return the global node count setting
            aws_section = self.config_data.get("aws", {})
            return int(aws_section.get("node_count", default))
            
    def get_total_instances(self) -> int:
        """
        Get the total number of instances to create across all regions.
        
        Returns:
            Total instance count
        """
        aws_section = self.config_data.get("aws", {})
        return int(aws_section.get("total_instances", 1))
        
    def get_username(self) -> str:
        """
        Get the SSH username for instances.
        
        Returns:
            SSH username
        """
        aws_section = self.config_data.get("aws", {})
        return cast(str, aws_section.get("username", "ubuntu"))
        
    def get_private_ssh_key_path(self) -> Optional[str]:
        """
        Get the path to the private SSH key.
        
        Returns:
            Path to private SSH key or None if not configured
        """
        aws_section = self.config_data.get("aws", {})
        ssh_key = aws_section.get("ssh_key")
        if not ssh_key:
            return None
            
        # Expand user home directory if needed
        if ssh_key.startswith("~"):
            ssh_key = os.path.expanduser(ssh_key)
            
        return cast(str, ssh_key)
        
    def get_tag_settings(self) -> Dict[str, str]:
        """
        Get tag settings for resources.
        
        Returns:
            Dictionary with tag settings
        """
        aws_section = self.config_data.get("aws", {})
        tags = aws_section.get("tags", {})
        
        return {
            "filter_tag_name": cast(str, tags.get("filter_tag_name", "ManagedBy")),
            "filter_tag_value": cast(str, tags.get("filter_tag_value", "SpotInstanceScript")),
            "creator_value": cast(str, tags.get("creator_value", "BacalhauSpotScript")),
            "resource_prefix": cast(str, tags.get("resource_prefix", "SpotInstance")),
            "vpc_name": cast(str, tags.get("vpc_name", "SpotInstanceVPC")),
        }
        
    def get_scripts_dir(self) -> str:
        """
        Get the directory containing instance scripts.
        
        Returns:
            Path to scripts directory
        """
        aws_section = self.config_data.get("aws", {})
        return cast(str, aws_section.get("scripts_dir", "instance/scripts"))
        
    def get_timeout_settings(self) -> Dict[str, int]:
        """
        Get timeout settings for various operations.
        
        Returns:
            Dictionary with timeout settings in seconds
        """
        aws_section = self.config_data.get("aws", {})
        timeouts = aws_section.get("timeouts", {})
        
        return {
            "api": int(timeouts.get("api", 30)),
            "spot_fulfillment": int(timeouts.get("spot_fulfillment", 600)),
            "ip_assignment": int(timeouts.get("ip_assignment", 300)),
            "provisioning": int(timeouts.get("provisioning", 600)),
        }
        
    def get_bacalhau_settings(self) -> Dict[str, Any]:
        """
        Get Bacalhau-specific settings.
        
        Returns:
            Dictionary with Bacalhau settings
        """
        return cast(Dict[str, Any], self.config_data.get("bacalhau", {}))


# Global config manager instance for convenience
_config_manager: Optional[ConfigManager] = None

def get_config(config_path: str = "config.yaml") -> ConfigManager:
    """
    Get the global config manager instance.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Config manager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    elif _config_manager.config_path != config_path:
        # If config path changed, reload config
        _config_manager = ConfigManager(config_path)
        
    return _config_manager