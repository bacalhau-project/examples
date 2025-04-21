"""
Monitor command implementation.

This module implements the 'monitor' command for the Sensor Manager CLI,
which monitors sensor status and data uploads.
"""

import os
import time
from pathlib import Path
from typing import Dict, List

from sensor_manager.db.sqlite import SQLiteManager
from sensor_manager.docker.manager import DockerManager
from sensor_manager.utils import logging as log


class MonitorDisplay:
    """Class for displaying monitoring information."""
    
    def __init__(self, plain: bool = False):
        """
        Initialize the monitor display.
        
        Args:
            plain: Whether to disable colored output
        """
        self.plain = plain
        
        # Force set logger colors based on plain mode
        if plain:
            log.logger.handlers[0].formatter.colors_enabled = False
    
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print the monitoring header."""
        log.header(f"SENSOR DATA MONITORING - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log.info("Checking data for sensor replicas...")
        print()
    
    def print_container_status(self, sensor_count: int, uploader_status: str):
        """
        Print container status information.
        
        Args:
            sensor_count: Number of sensor containers
            uploader_status: Status of uploader containers
        """
        log.header("CONTAINER STATUS:")
        log.info(f"Sensor Replicas: {sensor_count}")
        log.info(f"Uploader Status: {uploader_status}")
        print()
    
    def print_database_status(self, db_count: int, archive_count: int):
        """
        Print database status information.
        
        Args:
            db_count: Number of database files
            archive_count: Number of archive files
        """
        log.header("DATABASE STATUS:")
        log.info(f"SQLite Databases: {db_count}")
        log.info(f"Archive Files: {archive_count}")
        print()
    
    def print_sensors_table(self, sensors: List[Dict]):
        """
        Print a table of active sensors.
        
        Args:
            sensors: List of sensor information dictionaries
        """
        log.header("ACTIVE SENSORS:")
        print()
        
        if not sensors:
            log.warning("No database files found yet. Sensors may still be initializing.")
            return
        
        # Print table header
        header_format = "%-25s %-25s %-15s %-15s"
        log.info(header_format % ("SENSOR ID", "LOCATION", "DB SIZE", "READINGS"))
        print("-" * 80)
        
        # Print each sensor (limit to 10 for display purposes)
        for idx, sensor in enumerate(sensors[:10]):
            size_mb = sensor["size"] / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB"
            
            print("%-25s %-25s %-15s %-15s" % (
                sensor["sensor_id"] or "Unknown",
                sensor["location"] or "Unknown",
                size_str,
                str(sensor["row_count"])
            ))
        
        # Show count of additional sensors
        if len(sensors) > 10:
            print(f"... and {len(sensors) - 10} more database files ...")
    
    def print_archives_table(self, archive_files: List[Dict]):
        """
        Print a table of recent archive files.
        
        Args:
            archive_files: List of archive file information dictionaries
        """
        log.header("RECENT ARCHIVES:")
        print()
        
        if not archive_files:
            log.warning("No archive files found yet. May need to wait for the uploader cycle.")
            return
        
        # Print table header
        header_format = "%-60s %-25s"
        log.info(header_format % ("ARCHIVE FILE", "CREATION TIME"))
        print("-" * 85)
        
        # Print each archive file (limit to 5 most recent)
        for archive in archive_files[:5]:
            print("%-60s %-25s" % (
                archive["filename"],
                archive["created"]
            ))
    
    def print_tips(self):
        """Print monitoring tips."""
        print()
        log.info("TIP: Run with 'watch' for real-time updates: watch -n 5 python -m sensor_manager monitor")
        log.info("TIP: For more details: python -m sensor_manager query --list")


def get_container_status():
    """
    Get the status of all sensor and uploader containers.
    
    Returns:
        Tuple of (sensor_count, uploader_status)
    """
    docker_manager = DockerManager()
    
    # Get all sensor containers
    sensor_containers = docker_manager.list_containers(["sensor"])
    sensor_count = len(sensor_containers)
    
    # Get all uploader containers
    uploader_containers = docker_manager.list_containers(["uploader"])
    
    # Determine uploader status
    if any(container["status"].lower().startswith("up") for container in uploader_containers):
        uploader_status = "RUNNING"
    else:
        uploader_status = "STOPPED"
    
    return sensor_count, uploader_status


def get_archive_files(limit: int = 5):
    """
    Get the most recent archive files.
    
    Args:
        limit: Maximum number of files to return
        
    Returns:
        List of archive file information dictionaries
    """
    archive_dir = Path("./archive")
    if not archive_dir.exists():
        return []
    
    # Find all parquet files and sort by modification time
    parquet_files = list(archive_dir.glob("**/*.parquet"))
    parquet_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Get the most recent files
    recent_files = []
    for path in parquet_files[:limit]:
        mtime = path.stat().st_mtime
        created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        
        recent_files.append({
            "path": str(path),
            "filename": path.name,
            "created": created,
            "size": path.stat().st_size
        })
    
    return recent_files


def monitor_command(args):
    """
    Implementation of the 'monitor' command.
    
    Args:
        args: Command-line arguments
    """
    # Initialize the display
    display = MonitorDisplay(plain=args.plain)
    
    # Clear the screen and print header
    display.clear_screen()
    display.print_header()
    
    # Get container status
    sensor_count, uploader_status = get_container_status()
    display.print_container_status(sensor_count, uploader_status)
    
    # Get database information
    sqlite_manager = SQLiteManager("./data")
    db_files = sqlite_manager.find_databases()
    
    # Get archive information
    archive_dir = Path("./archive")
    archive_files = []
    if archive_dir.exists():
        archive_files = list(archive_dir.glob("**/*.parquet"))
    
    # Print database status
    display.print_database_status(len(db_files), len(archive_files))
    
    # Get and print sensor information
    sensors = sqlite_manager.list_all_sensors()
    display.print_sensors_table(sensors)
    
    # Get and print archive information
    archive_info = get_archive_files()
    display.print_archives_table(archive_info)
    
    # Print tips
    display.print_tips()
    
    return 0