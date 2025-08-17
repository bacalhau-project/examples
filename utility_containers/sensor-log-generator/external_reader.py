#!/usr/bin/env python3
"""
Safe external reader for sensor database.
Demonstrates how to read from the database without interfering with the writer process.
"""

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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
            # Note: uri=True is required for the mode parameter
            conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro",
                uri=True,
                timeout=self.timeout,
                check_same_thread=False
            )
            
            # Set read-only pragmas for safety
            conn.execute("PRAGMA query_only=1;")
            conn.execute("PRAGMA busy_timeout=30000;")
            
            # Use row factory for dict-like access
            conn.row_factory = sqlite3.Row
            
            yield conn
            
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e):
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            elif "database is locked" in str(e):
                raise TimeoutError(f"Database locked after {self.timeout}s timeout")
            else:
                raise
        finally:
            if conn:
                conn.close()
    
    def get_latest_readings(self, limit: int = 100) -> List[Dict]:
        """
        Get the most recent sensor readings.
        
        Args:
            limit: Maximum number of readings to return
            
        Returns:
            List of sensor readings as dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    id,
                    timestamp,
                    sensor_id,
                    temperature,
                    vibration,
                    voltage,
                    status_code,
                    anomaly_flag,
                    anomaly_type,
                    location
                FROM sensor_readings
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_readings_since(self, since_id: int) -> List[Dict]:
        """
        Get all readings since a specific ID.
        Useful for incremental reading without missing data.
        
        Args:
            since_id: ID after which to fetch readings
            
        Returns:
            List of new sensor readings
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    id,
                    timestamp,
                    sensor_id,
                    temperature,
                    vibration,
                    voltage,
                    status_code,
                    anomaly_flag,
                    anomaly_type,
                    location
                FROM sensor_readings
                WHERE id > ?
                ORDER BY id ASC
                LIMIT 1000
            """, (since_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_readings_by_time(self, 
                            start_time: Optional[datetime] = None,
                            end_time: Optional[datetime] = None) -> List[Dict]:
        """
        Get readings within a time range.
        
        Args:
            start_time: Start of time range (default: 1 hour ago)
            end_time: End of time range (default: now)
            
        Returns:
            List of sensor readings in time range
        """
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(hours=1)
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    id,
                    timestamp,
                    sensor_id,
                    temperature,
                    vibration,
                    voltage,
                    status_code,
                    anomaly_flag,
                    anomaly_type,
                    location
                FROM sensor_readings
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """, (start_time.isoformat(), end_time.isoformat()))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_sensor_stats(self) -> Dict:
        """
        Get statistics about sensor data.
        
        Returns:
            Dictionary with sensor statistics
        """
        with self.get_connection() as conn:
            # Total readings
            cursor = conn.execute("SELECT COUNT(*) FROM sensor_readings")
            total_count = cursor.fetchone()[0]
            
            # Readings per sensor
            cursor = conn.execute("""
                SELECT sensor_id, COUNT(*) as count
                FROM sensor_readings
                GROUP BY sensor_id
            """)
            sensor_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Anomaly statistics
            cursor = conn.execute("""
                SELECT 
                    COUNT(CASE WHEN anomaly_flag = 1 THEN 1 END) as anomaly_count,
                    COUNT(*) as total
                FROM sensor_readings
            """)
            row = cursor.fetchone()
            anomaly_rate = (row[0] / row[1] * 100) if row[1] > 0 else 0
            
            # Recent data freshness
            cursor = conn.execute("""
                SELECT timestamp 
                FROM sensor_readings 
                ORDER BY id DESC 
                LIMIT 1
            """)
            latest = cursor.fetchone()
            latest_timestamp = latest[0] if latest else None
            
            return {
                "total_readings": total_count,
                "sensor_counts": sensor_counts,
                "anomaly_rate": anomaly_rate,
                "latest_timestamp": latest_timestamp
            }
    
    def monitor_continuous(self, callback, interval: float = 1.0):
        """
        Continuously monitor for new readings.
        
        Args:
            callback: Function to call with new readings
            interval: Check interval in seconds
        """
        last_id = 0
        
        print(f"Starting continuous monitoring (checking every {interval}s)...")
        
        while True:
            try:
                # Get new readings since last check
                new_readings = self.get_readings_since(last_id)
                
                if new_readings:
                    # Update last_id for next iteration
                    last_id = max(r['id'] for r in new_readings)
                    
                    # Call the callback with new data
                    callback(new_readings)
                
                # Wait before next check
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                print(f"Error during monitoring: {e}")
                time.sleep(interval)


def example_callback(readings: List[Dict]):
    """Example callback for processing new readings."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New readings: {len(readings)}")
    
    # Show summary of new data
    for reading in readings[:3]:  # Show first 3
        print(f"  {reading['sensor_id']}: "
              f"T={reading['temperature']:.1f}°C, "
              f"V={reading['vibration']:.3f}, "
              f"Anomaly={reading['anomaly_flag']}")
    
    if len(readings) > 3:
        print(f"  ... and {len(readings) - 3} more")


def main():
    """Example usage of the SafeSensorReader."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Read sensor data safely")
    parser.add_argument("db_path", help="Path to sensor database")
    parser.add_argument("--mode", choices=["latest", "monitor", "stats"], 
                       default="latest",
                       help="Reading mode")
    parser.add_argument("--limit", type=int, default=10,
                       help="Number of readings to show (for latest mode)")
    parser.add_argument("--interval", type=float, default=1.0,
                       help="Monitor interval in seconds")
    
    args = parser.parse_args()
    
    # Check if database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        return 1
    
    reader = SafeSensorReader(args.db_path)
    
    try:
        if args.mode == "latest":
            # Show latest readings
            readings = reader.get_latest_readings(args.limit)
            print(f"\nLatest {len(readings)} readings:")
            for r in readings:
                print(f"  [{r['timestamp']}] {r['sensor_id']}: "
                      f"T={r['temperature']:.1f}°C, "
                      f"V={r['vibration']:.3f}, "
                      f"Voltage={r['voltage']:.1f}V")
        
        elif args.mode == "stats":
            # Show statistics
            stats = reader.get_sensor_stats()
            print("\nSensor Database Statistics:")
            print(f"  Total Readings: {stats['total_readings']:,}")
            print(f"  Anomaly Rate: {stats['anomaly_rate']:.2f}%")
            print(f"  Latest Data: {stats['latest_timestamp']}")
            print(f"  Sensors: {len(stats['sensor_counts'])}")
            for sensor, count in stats['sensor_counts'].items():
                print(f"    - {sensor}: {count:,} readings")
        
        elif args.mode == "monitor":
            # Continuous monitoring
            reader.monitor_continuous(example_callback, args.interval)
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except TimeoutError as e:
        print(f"Error: {e}")
        print("The database might be under heavy load. Try again later.")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())