#!/usr/bin/env python3
"""
Comprehensive example for reading from the sensor database while it's being written to.
Demonstrates both simple and advanced reading patterns for different use cases.
"""

import sqlite3
import time
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import sys


class SafeSensorReader:
    """
    Thread-safe reader for sensor database that doesn't interfere with writers.
    
    Key features:
    - Read-only connection to prevent accidental writes
    - Proper timeout handling for busy database
    - Connection pooling for efficiency
    - Error recovery and retry logic
    """
    
    def __init__(self, db_path: str, timeout: float = 30.0):
        """
        Initialize the reader.
        
        Args:
            db_path: Path to the SQLite database
            timeout: Maximum time to wait for database lock (seconds)
        """
        self.db_path = db_path
        self.timeout = timeout
        self._conn = None
    
    @contextmanager
    def get_connection(self):
        """
        Get a read-only connection to the database.
        
        Yields:
            sqlite3.Connection: Read-only database connection
        """
        conn = None
        try:
            # Open in read-only mode to prevent any writes
            conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro",
                uri=True,
                timeout=self.timeout
            )
            
            # Set to query-only mode for extra safety
            conn.execute("PRAGMA query_only=1;")
            
            # Use WAL mode for better concurrency (reader settings)
            conn.execute("PRAGMA journal_mode=WAL;")
            
            yield conn
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                print(f"Database is busy, retry after delay: {e}")
            elif "no such table" in str(e):
                print(f"Table doesn't exist yet: {e}")
            else:
                print(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def read_latest(self, limit: int = 10) -> List[Dict]:
        """
        Read the latest sensor readings.
        
        Args:
            limit: Maximum number of readings to return
            
        Returns:
            List of sensor readings as dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sensor_id, temperature, humidity, 
                       pressure, air_quality, vibration, voltage, 
                       light_level, latitude, longitude, battery_level,
                       signal_strength, error_code
                FROM sensor_readings
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def read_incremental(self, last_id: int = 0, limit: int = 100) -> Tuple[List[Dict], int]:
        """
        Read new sensor data since the last known ID.
        
        Args:
            last_id: ID of the last reading we processed
            limit: Maximum number of readings to return
            
        Returns:
            Tuple of (new_readings, max_id)
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sensor_id, temperature, humidity, 
                       pressure, air_quality, vibration, voltage, 
                       light_level, latitude, longitude, battery_level,
                       signal_strength, error_code
                FROM sensor_readings
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
            """, (last_id, limit))
            
            columns = [desc[0] for desc in cursor.description]
            readings = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Get the highest ID for next iteration
            if readings:
                max_id = max(r['id'] for r in readings)
            else:
                max_id = last_id
                
            return readings, max_id
    
    def read_time_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Read sensor data within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of sensor readings in the time range
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM sensor_readings
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """, (start_time.isoformat(), end_time.isoformat()))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_statistics(self, sensor_id: Optional[str] = None) -> Dict:
        """
        Get statistical summary of sensor readings.
        
        Args:
            sensor_id: Optional sensor ID to filter by
            
        Returns:
            Dictionary with statistics
        """
        with self.get_connection() as conn:
            if sensor_id:
                where_clause = "WHERE sensor_id = ?"
                params = (sensor_id,)
            else:
                where_clause = ""
                params = ()
            
            cursor = conn.execute(f"""
                SELECT 
                    COUNT(*) as total_readings,
                    MIN(timestamp) as first_reading,
                    MAX(timestamp) as last_reading,
                    AVG(temperature) as avg_temperature,
                    MIN(temperature) as min_temperature,
                    MAX(temperature) as max_temperature,
                    AVG(humidity) as avg_humidity,
                    AVG(pressure) as avg_pressure,
                    AVG(battery_level) as avg_battery,
                    COUNT(DISTINCT sensor_id) as unique_sensors
                FROM sensor_readings
                {where_clause}
            """, params)
            
            row = cursor.fetchone()
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row)) if row else {}


def simple_reader_example(db_path: str):
    """
    Simple example of reading from sensor database.
    """
    print("\n=== Simple Reader Example ===")
    
    # IMPORTANT: Open in read-only mode to avoid lock conflicts
    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro",  # Read-only mode
        uri=True,
        timeout=30.0  # Wait up to 30 seconds if database is busy
    )
    
    try:
        # Set to query-only for extra safety
        conn.execute("PRAGMA query_only=1;")
        
        # Get latest 5 readings
        cursor = conn.execute("""
            SELECT id, timestamp, sensor_id, temperature, humidity
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT 5
        """)
        
        readings = cursor.fetchall()
        
        print(f"Found {len(readings)} readings:")
        for reading in readings:
            print(f"  ID={reading[0]}, Time={reading[1]}, Sensor={reading[2]}, "
                  f"Temp={reading[3]:.1f}°C, Humidity={reading[4]:.1f}%")
    
    finally:
        conn.close()


def continuous_reader_example(db_path: str, duration: int = 30):
    """
    Example of continuously reading new data as it arrives.
    """
    print(f"\n=== Continuous Reader Example (running for {duration} seconds) ===")
    
    reader = SafeSensorReader(db_path)
    last_id = 0
    start_time = time.time()
    
    while time.time() - start_time < duration:
        try:
            # Read new data since last check
            new_readings, last_id = reader.read_incremental(last_id, limit=10)
            
            if new_readings:
                print(f"\nFound {len(new_readings)} new readings:")
                for reading in new_readings:
                    print(f"  [{reading['timestamp']}] Sensor {reading['sensor_id']}: "
                          f"Temp={reading['temperature']:.1f}°C, "
                          f"Humidity={reading['humidity']:.1f}%")
            else:
                print(".", end="", flush=True)
            
            # Check every 2 seconds
            time.sleep(2)
            
        except sqlite3.OperationalError as e:
            print(f"\nDatabase temporarily unavailable: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopped by user")
            break
    
    print(f"\nProcessed up to ID {last_id}")


def statistics_example(db_path: str):
    """
    Example of getting statistical summaries from the database.
    """
    print("\n=== Statistics Example ===")
    
    reader = SafeSensorReader(db_path)
    
    try:
        stats = reader.get_statistics()
        
        if stats and stats.get('total_readings'):
            print(f"Total readings: {stats['total_readings']:,}")
            print(f"Unique sensors: {stats['unique_sensors']}")
            print(f"Time range: {stats['first_reading']} to {stats['last_reading']}")
            print(f"Temperature: {stats['min_temperature']:.1f}°C to {stats['max_temperature']:.1f}°C "
                  f"(avg: {stats['avg_temperature']:.1f}°C)")
            print(f"Average humidity: {stats['avg_humidity']:.1f}%")
            print(f"Average pressure: {stats['avg_pressure']:.1f} hPa")
            print(f"Average battery: {stats['avg_battery']:.1f}%")
        else:
            print("No data available yet")
            
    except sqlite3.OperationalError as e:
        print(f"Could not read statistics: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Read from sensor database safely while it's being written to"
    )
    parser.add_argument(
        "db_path",
        nargs="?",
        default="data/sensor_data.db",
        help="Path to the sensor database (default: data/sensor_data.db)"
    )
    parser.add_argument(
        "--mode",
        choices=["simple", "continuous", "stats", "all"],
        default="all",
        help="Reading mode to demonstrate (default: all)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration for continuous mode in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        print("Make sure the sensor simulator is running first.")
        sys.exit(1)
    
    print(f"Reading from database: {args.db_path}")
    
    try:
        if args.mode in ["simple", "all"]:
            simple_reader_example(args.db_path)
        
        if args.mode in ["stats", "all"]:
            statistics_example(args.db_path)
        
        if args.mode in ["continuous", "all"]:
            continuous_reader_example(args.db_path, args.duration)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()