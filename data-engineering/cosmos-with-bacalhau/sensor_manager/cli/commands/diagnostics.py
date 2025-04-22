"""
Diagnostics command implementation.

This module implements the 'diagnostics' command for the Sensor Manager CLI,
which runs system diagnostics to check the health of the sensors and uploaders.
"""

import os
import subprocess
import sqlite3
import time
from pathlib import Path

from sensor_manager.utils import logging as log
from sensor_manager.docker.compose import DockerComposeRunner


def check_docker_running():
    """
    Check if Docker is running.
    
    Returns:
        bool: True if Docker is running, False otherwise
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
    except subprocess.CalledProcessError:
        return False


def get_container_stats(container_type):
    """
    Get statistics for containers of a specific type.
    
    Args:
        container_type (str): Type of container to check ('sensor' or 'uploader')
        
    Returns:
        list: List of container IDs
        int: Count of containers
    """
    try:
        # Get container IDs
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_type}", "-q"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        container_ids = result.stdout.strip().split('\n')
        container_count = 0
        
        # Filter out empty strings and count
        container_ids = [cid for cid in container_ids if cid]
        container_count = len(container_ids)
        
        return container_ids, container_count
    except subprocess.CalledProcessError:
        return [], 0


def check_containers():
    """
    Check running containers and print their status.
    
    Returns:
        tuple: (sensor_count, uploader_count)
    """
    log.info("Checking running containers...")
    
    # Check sensor containers
    log.info("🧪 SENSOR CONTAINERS:")
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=sensor", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log.plain(result.stdout)
    except subprocess.CalledProcessError:
        log.warning("Failed to get sensor container information")
    
    sensor_ids, sensor_count = get_container_stats('sensor')
    log.info(f"Total sensor containers: {sensor_count}")
    
    # Check uploader containers
    log.info("🧪 UPLOADER CONTAINERS:")
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=uploader", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log.plain(result.stdout)
    except subprocess.CalledProcessError:
        log.warning("Failed to get uploader container information")
    
    uploader_ids, uploader_count = get_container_stats('uploader')
    log.info(f"Total uploader containers: {uploader_count}")
    
    return sensor_count, uploader_count


def check_cosmos_uploader_images():
    """
    Check available Cosmos Uploader images.
    """
    log.info("🧪 COSMOS UPLOADER IMAGES:")
    try:
        result = subprocess.run(
            ["docker", "images", "cosmos-uploader*", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log.plain(result.stdout)
    except subprocess.CalledProcessError:
        log.warning("Failed to get Cosmos Uploader image information")


def check_uploader_logs():
    """
    Check logs from uploader containers.
    """
    log.info("🧪 CHECKING LOGS FROM UPLOADER CONTAINERS:")
    log.info("Showing last 10 lines from the uploader container...")
    
    uploader_ids, _ = get_container_stats('uploader')
    
    if uploader_ids:
        uploader_container = uploader_ids[0]
        try:
            # Get container name
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.Name}}", uploader_container],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            container_name = result.stdout.strip().replace('/', '')
            log.info(f"=== {container_name} ===")
            
            # Get container logs
            result = subprocess.run(
                ["docker", "logs", uploader_container, "--tail", "20"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Filter logs for sensor-related entries
            for line in result.stdout.split('\n'):
                if 'sensor' in line.lower():
                    log.plain(line)
        except subprocess.CalledProcessError:
            log.warning("Failed to get uploader container logs")
    else:
        log.warning("No uploader container found running")


def check_sensor_logs():
    """
    Check logs from sensor containers.
    """
    log.info("🧪 CHECKING LOGS FROM SENSOR CONTAINERS:")
    log.info("Showing last 10 lines from a few sensor replicas...")
    
    sensor_ids, _ = get_container_stats('sensor')
    
    if sensor_ids:
        # Take up to 3 sensors
        sample_sensors = sensor_ids[:3]
        
        for container in sample_sensors:
            try:
                # Get container name
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{.Name}}", container],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                container_name = result.stdout.strip().replace('/', '')
                log.info(f"=== {container_name} ===")
                
                # Get container logs
                result = subprocess.run(
                    ["docker", "logs", container, "--tail", "10"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                log.plain(result.stdout)
            except subprocess.CalledProcessError:
                log.warning(f"Failed to get logs for sensor container {container}")
    else:
        log.warning("No sensor containers found running")


def check_sqlite_databases():
    """
    Check SQLite databases for sensor readings.
    """
    log.info("🧪 CHECKING SQLITE DATABASES:")
    log.info("Looking for databases in data directory...")
    
    data_dir = Path('./data')
    if not data_dir.exists():
        log.warning("Data directory not found. No sensors are running or data hasn't been generated yet.")
        return 0
    
    db_files = list(data_dir.glob('**/sensor_data.db'))
    
    if not db_files:
        log.warning("No database files found. Make sure the sensors have generated data.")
        return 0
    
    for db_path in db_files:
        log.info(f"Database: {db_path}")
        
        if db_path.exists():
            # Get file size
            file_size = get_file_size(db_path)
            log.info(f"  - Size: {file_size}")
            
            try:
                # Connect to database and check records
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Check if the sensor_readings table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'")
                if not cursor.fetchone():
                    log.warning("  - Records: Table 'sensor_readings' not found")
                    conn.close()
                    continue
                
                # Count records
                cursor.execute("SELECT COUNT(*) FROM sensor_readings")
                count = cursor.fetchone()[0]
                
                if count == 0:
                    log.warning("  - Records: 0 (empty)")
                else:
                    log.success(f"  - Records: {count}")
                
                conn.close()
            except sqlite3.Error as e:
                log.warning(f"  - Records: Error accessing database: {e}")
        else:
            log.error("  - Not found or empty")
    
    return len(db_files)


def get_file_size(file_path):
    """
    Get the size of a file in human-readable format.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: Human-readable file size
    """
    try:
        size_bytes = Path(file_path).stat().st_size
        
        # Convert to human-readable format
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024 or unit == "GB":
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
    except Exception as e:
        return "Unknown"


def diagnostics_command(args):
    """
    Implementation of the 'diagnostics' command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    log.header("Running diagnostics")
    
    # Check if Docker is running
    if not check_docker_running():
        log.error("❌ Docker is not running. Please start Docker first.")
        return 1
    
    # Check for running containers
    sensor_count, uploader_count = check_containers()
    
    # Check images
    check_cosmos_uploader_images()
    
    # Check uploader logs
    check_uploader_logs()
    
    # Check sensor logs
    check_sensor_logs()
    
    # Check SQLite databases
    db_count = check_sqlite_databases()
    
    # Print diagnostic summary
    log.header("📊 DIAGNOSTIC SUMMARY:")
    log.info(f"- Sensor containers: {sensor_count}")
    log.info(f"- Uploader containers: {uploader_count}")
    log.info(f"- SQLite databases: {db_count}")
    
    log.info("")
    log.info("Next steps:")
    log.info("1. Check if the correct sensor IDs appear in the logs")
    log.info("2. Run 'sensor_manager.py query --all' to check database contents")
    log.info("3. Verify if all sensor IDs are appearing in Cosmos DB")
    
    return 0