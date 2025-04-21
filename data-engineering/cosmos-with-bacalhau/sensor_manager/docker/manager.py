"""
Docker container management for the Sensor Manager.

This module handles direct interaction with Docker containers via subprocess commands,
including checking container status, retrieving logs, and cleaning up containers.
"""

import os
import subprocess
from typing import Dict, List, Optional, Union

from sensor_manager.utils import logging as log


class DockerManager:
    """Manager for Docker operations using subprocess commands."""
    
    def __init__(self):
        """Initialize the Docker manager."""
        pass
    
    def is_docker_running(self) -> bool:
        """
        Check if Docker is running.
        
        Returns:
            True if Docker is running, False otherwise
        """
        try:
            # Use subprocess to check if Docker is running
            subprocess.run(
                ["docker", "info"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False
    
    def get_container_status(self, container_name: str) -> Optional[str]:
        """
        Get the status of a container.
        
        Args:
            container_name: Name of the container
            
        Returns:
            Container status or None if the container doesn't exist
        """
        try:
            # Use subprocess to get container status
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            log.error(f"Failed to get container status: {e}")
            return None
    
    def get_container_logs(self, container_name: str, tail: int = 10) -> str:
        """
        Get logs from a container.
        
        Args:
            container_name: Name of the container
            tail: Number of lines to return from the end of the logs
            
        Returns:
            Container logs
        """
        try:
            # Use subprocess to get container logs
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return result.stdout
            return f"Failed to get logs for container '{container_name}'"
        except Exception as e:
            log.error(f"Failed to get container logs: {e}")
            return f"Error retrieving logs: {e}"
    
    def cleanup_containers(self, name_filters: List[str]) -> int:
        """
        Remove containers matching the specified name filters.
        
        Args:
            name_filters: List of name patterns to match
            
        Returns:
            Number of containers removed
        """
        try:
            # Use list instead of shell=True for safer execution
            cmd = ["docker", "ps", "-a", "-q"]
            for pattern in name_filters:
                cmd.extend(["--filter", f"name={pattern}"])
            
            # Get container IDs
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                container_ids = [cid for cid in result.stdout.strip().split('\n') if cid]
                
                if not container_ids:
                    return 0
                
                log.info(f"Found {len(container_ids)} containers to remove")
                
                # Remove containers
                remove_result = subprocess.run(
                    ["docker", "rm", "-f"] + container_ids,
                    capture_output=True,
                    text=True
                )
                
                if remove_result.returncode == 0:
                    removed_count = len(container_ids)
                    log.info(f"Removed {removed_count} containers")
                    return removed_count
                else:
                    log.error(f"Error removing containers: {remove_result.stderr}")
            else:
                if result.stderr:
                    log.debug(f"Docker ps command error: {result.stderr}")
                log.info(f"No containers found matching filters: {name_filters}")
            
            return 0
        except Exception as e:
            log.error(f"Failed to cleanup containers: {e}")
            return 0
    
    def list_containers(self, name_filters: Optional[List[str]] = None) -> List[Dict]:
        """
        List containers matching the specified name filters.
        
        Args:
            name_filters: List of name patterns to match
            
        Returns:
            List of container information dictionaries
        """
        containers = []
        
        try:
            # Use subprocess to list containers
            cmd = ["docker", "ps", "-a", "--format", "{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}"]
            
            if name_filters:
                for filter_pattern in name_filters:
                    cmd.extend(["--filter", f"name={filter_pattern}"])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|')
                        if len(parts) >= 4:
                            container_id, name, status, image = parts
                            containers.append({
                                "id": container_id,
                                "name": name,
                                "status": status,
                                "image": image
                            })
        
            return containers
        except Exception as e:
            log.error(f"Failed to list containers: {e}")
            return []