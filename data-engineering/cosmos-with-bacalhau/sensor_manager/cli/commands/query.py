"""
Query command implementation.

This module implements the 'query' command for the Sensor Manager CLI,
which queries SQLite databases for sensor readings.
"""

import os
import sqlite3
import subprocess
from pathlib import Path
from sensor_manager.utils import logging as log


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


def query_db(db_path, city=None, sensor=None):
    """
    Query a SQLite database for sensor readings.
    
    Args:
        db_path: Path to the SQLite database
        city: City name (optional)
        sensor: Sensor ID (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    log.separator()
    log.info(f"Database: {db_path}")
    log.info(f"City: {city or 'Unknown'}, Sensor: {sensor or 'Unknown'}")
    log.separator()
    
    # Check if file exists
    if not Path(db_path).exists():
        log.warning("⚠️ Database file not found")
        return False
    
    # Check file size
    file_size = get_file_size(db_path)
    log.info(f"File size: {file_size}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Run SQLite query to get table info
        log.info("\nTable schema:")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sensor_readings'")
        schema = cursor.fetchone()
        if schema:
            log.plain(schema[0])
        else:
            log.warning("No schema found for sensor_readings table")
        
        # Run SQLite query to get row count
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        row_count = cursor.fetchone()[0]
        log.info(f"\nTotal records: {row_count}")
        
        # Run SQLite query to get sample data
        log.info("\nSample records:")
        cursor.execute("SELECT id, sensor_id, timestamp, temperature, location FROM sensor_readings LIMIT 5")
        records = cursor.fetchall()
        
        # Print column headers
        log.plain(f"{'ID':<10} {'SENSOR_ID':<20} {'TIMESTAMP':<25} {'TEMPERATURE':<15} {'LOCATION'}")
        log.plain("-" * 80)
        
        # Print records
        for record in records:
            log.plain(f"{record[0]:<10} {record[1]:<20} {record[2]:<25} {record[3]:<15} {record[4]}")
        
        # Check for sensor_id values
        log.info("\nUnique sensor_id values:")
        cursor.execute("SELECT DISTINCT sensor_id FROM sensor_readings")
        sensors = cursor.fetchall()
        for s in sensors:
            log.plain(s[0])
        
        # Check location values
        log.info("\nUnique location values:")
        cursor.execute("SELECT DISTINCT location FROM sensor_readings")
        locations = cursor.fetchall()
        for loc in locations:
            log.plain(loc[0])
        
        conn.close()
        return True
    
    except sqlite3.Error as e:
        log.error(f"SQLite error: {e}")
        return False
    except Exception as e:
        log.error(f"Error querying database: {e}")
        return False


def query_command(args):
    """
    Implementation of the 'query' command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    log.header("Querying SQLite databases")
    
    # Process command arguments
    if hasattr(args, 'all') and args.all:
        # Query all databases found in the data directory
        log.info("Querying all SQLite databases in the data directory...")
        
        # Find all sensor_data.db files in the data directory
        data_dir = Path('./data')
        if not data_dir.exists():
            log.warning("Data directory not found. No sensors are running or data hasn't been generated yet.")
            return 1
        
        db_files = list(data_dir.glob('**/sensor_data.db'))
        
        if not db_files:
            log.warning("No database files found. Make sure the sensors have generated data.")
            return 1
        
        # Process each database file
        success = True
        for db_path in db_files:
            try:
                # Extract sensor information from the database if possible
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Get sensor ID
                cursor.execute("SELECT DISTINCT sensor_id FROM sensor_readings LIMIT 1")
                sensor_id_row = cursor.fetchone()
                sensor_id = sensor_id_row[0] if sensor_id_row else "Unknown"
                
                # Get location
                cursor.execute("SELECT DISTINCT location FROM sensor_readings LIMIT 1")
                location_row = cursor.fetchone()
                location = location_row[0] if location_row else "Unknown"
                
                conn.close()
                
                # Query the database
                if not query_db(str(db_path), location, sensor_id):
                    success = False
            
            except sqlite3.Error as e:
                log.error(f"SQLite error on {db_path}: {e}")
                success = False
                continue
        
        return 0 if success else 1
    
    elif hasattr(args, 'list') and args.list:
        # List all sensors found in the databases
        log.info("Listing all sensors with data:")
        
        # Find all sensor_data.db files
        data_dir = Path('./data')
        if not data_dir.exists():
            log.warning("Data directory not found. No sensors are running or data hasn't been generated yet.")
            return 1
        
        db_files = list(data_dir.glob('**/sensor_data.db'))
        
        if not db_files:
            log.warning("No database files found. Make sure the sensors have generated data.")
            return 1
        
        # Print header
        log.info(f"{'DATABASE PATH':<30} {'SENSOR ID':<30} {'LOCATION':<30}")
        log.separator()
        
        # Process each database file
        for db_path in db_files:
            try:
                # Extract sensor information
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Get sensor ID
                cursor.execute("SELECT DISTINCT sensor_id FROM sensor_readings LIMIT 1")
                sensor_id_row = cursor.fetchone()
                sensor_id = sensor_id_row[0] if sensor_id_row else "Unknown"
                
                # Get location
                cursor.execute("SELECT DISTINCT location FROM sensor_readings LIMIT 1")
                location_row = cursor.fetchone()
                location = location_row[0] if location_row else "Unknown"
                
                conn.close()
                
                # Print the information
                log.plain(f"{str(db_path):<30} {sensor_id:<30} {location:<30}")
            
            except sqlite3.Error as e:
                log.error(f"SQLite error on {db_path}: {e}")
                log.plain(f"{str(db_path):<30} {'Error':<30} {'Error':<30}")
        
        return 0
    
    elif hasattr(args, 'sensor_id') and args.sensor_id:
        # Try to find a database with the specified sensor ID
        sensor_id = args.sensor_id
        log.info(f"Searching for sensor with ID: {sensor_id}")
        
        # Find all sensor_data.db files
        data_dir = Path('./data')
        if not data_dir.exists():
            log.warning("Data directory not found. No sensors are running or data hasn't been generated yet.")
            return 1
        
        db_files = list(data_dir.glob('**/sensor_data.db'))
        
        if not db_files:
            log.warning("No database files found. Make sure the sensors have generated data.")
            return 1
        
        # Try to find the specified sensor ID
        found = False
        for db_path in db_files:
            try:
                # Check if this database contains the requested sensor ID
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM sensor_readings WHERE sensor_id LIKE ?", (f'%{sensor_id}%',))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # Found a match, get the location
                    cursor.execute("SELECT DISTINCT location FROM sensor_readings WHERE sensor_id LIKE ? LIMIT 1", 
                                   (f'%{sensor_id}%',))
                    location_row = cursor.fetchone()
                    location = location_row[0] if location_row else "Unknown"
                    
                    conn.close()
                    
                    log.success(f"Found sensor {sensor_id} in database: {db_path}")
                    query_db(str(db_path), location, sensor_id)
                    found = True
                    break
                
                conn.close()
            
            except sqlite3.Error as e:
                log.error(f"SQLite error on {db_path}: {e}")
                continue
        
        if not found:
            log.warning(f"No database found for sensor ID: {sensor_id}")
            log.info("Available sensors:")
            
            # Create list args and call list function
            list_args = type('ListArgs', (), {'list': True})
            query_command(list_args)
            
            return 1
        
        return 0
    
    else:
        # Show usage
        log.info("Usage: sensor_manager.py query [--all | --list | --sensor-id SENSOR_ID]")
        log.info("")
        log.info("Examples:")
        log.info("  sensor_manager.py query --all                  # Query all databases")
        log.info("  sensor_manager.py query --list                 # List all available sensors")
        log.info("  sensor_manager.py query --sensor-id AMS_SENSOR001  # Query specific sensor by ID")
        
        return 1