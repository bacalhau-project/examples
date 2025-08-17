#!/usr/bin/env python3
"""
Simple example of reading from sensor database while it's being written to.
This demonstrates the minimal code needed for safe external reading.
"""

import sqlite3
import time
from pathlib import Path


def read_sensor_data_safely(db_path: str, last_id: int = 0) -> tuple:
    """
    Safely read new sensor data from an active database.
    
    Args:
        db_path: Path to the sensor database
        last_id: ID of the last reading we processed (for incremental reads)
    
    Returns:
        Tuple of (new_readings, max_id)
    """
    # IMPORTANT: Open in read-only mode to avoid lock conflicts
    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro",  # Read-only mode
        uri=True,
        timeout=30.0  # Wait up to 30 seconds if database is busy
    )
    
    try:
        # Set to query-only for extra safety
        conn.execute("PRAGMA query_only=1;")
        
        # Get new readings since last_id
        cursor = conn.execute("""
            SELECT id, timestamp, sensor_id, temperature, vibration, voltage
            FROM sensor_readings
            WHERE id > ?
            ORDER BY id ASC
            LIMIT 100
        """, (last_id,))
        
        readings = cursor.fetchall()
        
        # Get the highest ID for next iteration
        if readings:
            max_id = max(r[0] for r in readings)
        else:
            max_id = last_id
        
        return readings, max_id
        
    finally:
        conn.close()


def main():
    """Example of continuous reading from active sensor database."""
    
    # Path to your sensor database
    db_path = "data/sensor_data.db"  # Adjust this path as needed
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        print("Make sure the sensor is running first!")
        return
    
    print("Starting to monitor sensor database...")
    print("Press Ctrl+C to stop\n")
    
    last_id = 0
    
    try:
        while True:
            # Read new data
            readings, last_id = read_sensor_data_safely(db_path, last_id)
            
            if readings:
                print(f"Got {len(readings)} new readings:")
                for reading in readings[:3]:  # Show first 3
                    id_, timestamp, sensor_id, temp, vib, volt = reading
                    print(f"  [{timestamp}] {sensor_id}: T={temp:.1f}°C")
                
                if len(readings) > 3:
                    print(f"  ... and {len(readings) - 3} more\n")
            
            # Wait before next check
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nStopped monitoring")
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("Database is locked - the writer might be doing a large transaction")
            print("This is normal and will resolve when the transaction completes")
        else:
            print(f"Database error: {e}")


if __name__ == "__main__":
    main()