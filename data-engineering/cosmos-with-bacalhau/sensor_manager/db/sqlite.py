"""
SQLite database operations for the Sensor Manager.

This module handles queries and information retrieval from SQLite databases
created by the sensor simulation.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple

from sensor_manager.utils import logging as log


class SQLiteManager:
    """Manager for SQLite operations."""
    
    def __init__(self, base_dir: str = "./data"):
        """
        Initialize the SQLite manager.
        
        Args:
            base_dir: Base directory for SQLite databases
        """
        self.base_dir = Path(base_dir)
    
    def find_databases(self, pattern: str = "*.db") -> List[Path]:
        """
        Find SQLite database files in the base directory.
        
        Args:
            pattern: File glob pattern for database files
            
        Returns:
            List of database file paths
        """
        if not self.base_dir.exists():
            log.warning(f"Base directory {self.base_dir} does not exist")
            return []
        
        # Find all database files matching the pattern
        return list(self.base_dir.glob(f"**/{pattern}"))
    
    def get_database_info(self, db_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get information about a SQLite database.
        
        Args:
            db_path: Path to the database file
            
        Returns:
            Dictionary with database information
        """
        db_path = Path(db_path)
        
        if not db_path.exists():
            return {
                "path": str(db_path),
                "exists": False,
                "error": "File not found"
            }
        
        info = {
            "path": str(db_path),
            "exists": True,
            "size": db_path.stat().st_size,
            "modified": db_path.stat().st_mtime
        }
        
        try:
            # Connect to database and get schema information
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if sensor_readings table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'")
            if not cursor.fetchone():
                info["has_sensor_readings"] = False
                info["error"] = "Table 'sensor_readings' not found"
                return info
            
            info["has_sensor_readings"] = True
            
            # Get row count
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            info["row_count"] = cursor.fetchone()[0]
            
            # Get sensor_id
            cursor.execute("SELECT DISTINCT sensor_id FROM sensor_readings LIMIT 1")
            result = cursor.fetchone()
            info["sensor_id"] = result[0] if result else None
            
            # Get location
            cursor.execute("SELECT DISTINCT location FROM sensor_readings LIMIT 1")
            result = cursor.fetchone()
            info["location"] = result[0] if result else None
            
            conn.close()
        except sqlite3.Error as e:
            info["error"] = str(e)
        
        return info
    
    def query_database(self, db_path: Union[str, Path], query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a query on a SQLite database.
        
        Args:
            db_path: Path to the database file
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            List of dictionaries with query results
        """
        db_path = Path(db_path)
        
        if not db_path.exists():
            log.error(f"Database file {db_path} does not exist")
            return []
        
        try:
            # Connect to database
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Execute query
            cursor.execute(query, params)
            
            # Convert to list of dictionaries
            results = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return results
        except sqlite3.Error as e:
            log.error(f"Error executing query: {e}")
            return []
    
    def get_sensor_readings(self, db_path: Union[str, Path], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sensor readings from a database.
        
        Args:
            db_path: Path to the database file
            limit: Maximum number of readings to return
            
        Returns:
            List of dictionaries with sensor readings
        """
        query = """
            SELECT id, sensor_id, timestamp, temperature, vibration, voltage, location
            FROM sensor_readings
            ORDER BY timestamp DESC
            LIMIT ?
        """
        
        return self.query_database(db_path, query, (limit,))
    
    def get_sensor_stats(self, db_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get statistics about sensor readings in a database.
        
        Args:
            db_path: Path to the database file
            
        Returns:
            Dictionary with statistics
        """
        db_path = Path(db_path)
        
        if not db_path.exists():
            log.error(f"Database file {db_path} does not exist")
            return {}
        
        try:
            # Connect to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get row count
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            row_count = cursor.fetchone()[0]
            
            # Get average readings
            cursor.execute("SELECT AVG(temperature), AVG(vibration), AVG(voltage) FROM sensor_readings")
            avg_temp, avg_vib, avg_volt = cursor.fetchone()
            
            # Get min/max readings
            cursor.execute("SELECT MIN(temperature), MAX(temperature) FROM sensor_readings")
            min_temp, max_temp = cursor.fetchone()
            
            # Get time range
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM sensor_readings")
            min_time, max_time = cursor.fetchone()
            
            conn.close()
            
            return {
                "row_count": row_count,
                "avg_temperature": avg_temp,
                "avg_vibration": avg_vib,
                "avg_voltage": avg_volt,
                "min_temperature": min_temp,
                "max_temperature": max_temp,
                "first_reading": min_time,
                "last_reading": max_time
            }
        except sqlite3.Error as e:
            log.error(f"Error getting sensor stats: {e}")
            return {}
    
    def list_all_sensors(self) -> List[Dict[str, Any]]:
        """
        List all sensors with data in the base directory.
        
        Returns:
            List of dictionaries with sensor information
        """
        sensors = []
        
        # Find all database files
        db_files = self.find_databases()
        
        for db_path in db_files:
            # Get database info
            info = self.get_database_info(db_path)
            
            if info.get("has_sensor_readings"):
                sensors.append({
                    "path": str(db_path),
                    "sensor_id": info.get("sensor_id"),
                    "location": info.get("location"),
                    "row_count": info.get("row_count", 0),
                    "size": info.get("size", 0)
                })
        
        return sensors