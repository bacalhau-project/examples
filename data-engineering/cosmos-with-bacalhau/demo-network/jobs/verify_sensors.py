#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
#     "tabulate"
# ]
# ///

import json
import os
import yaml
import sqlite3
import time
from datetime import datetime
from tabulate import tabulate

def wait_for_db(db_path, max_wait=30):
    """Wait for the database file to exist, up to max_wait seconds."""
    start_time = time.time()
    while not os.path.exists(db_path):
        if time.time() - start_time > max_wait:
            return False
        time.sleep(1)
    return True

def format_coordinates(latitude, longitude):
    """Format coordinates, handling None values."""
    if latitude is None or longitude is None:
        return "N/A"
    return f"({latitude:.4f}, {longitude:.4f})"

def main():
    # Get the database path from the config file
    config_file = "/root/config.yaml"
    
    # Check if config file exists
    if not os.path.exists(config_file):
        print(json.dumps({
            "error": f"Config file not found at {config_file}",
            "status": "error"
        }))
        exit(1)
    
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(json.dumps({
            "error": f"Error reading config file: {str(e)}",
            "status": "error"
        }))
        exit(1)
    
    # Verify config structure
    if not config or not config.get("database") or not config["database"].get("path"):
        print(json.dumps({
            "error": "Invalid config structure",
            "status": "error"
        }))
        exit(1)
    
    db_path = config["database"]["path"]
    
    # Wait for database file to exist
    if not wait_for_db(db_path):
        print(json.dumps({
            "error": f"Database file not found after waiting",
            "db_path": db_path,
            "status": "error"
        }))
        exit(1)
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        row_count = cursor.fetchone()[0]
        
        # Get the most recent entry
        cursor.execute("""
            SELECT 
                timestamp,
                sensor_id,
                temperature,
                humidity,
                pressure,
                vibration,
                voltage,
                status_code,
                anomaly_flag,
                anomaly_type,
                firmware_version,
                model,
                manufacturer,
                location,
                latitude,
                longitude
            FROM sensor_readings 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            (timestamp, sensor_id, temperature, humidity, pressure, vibration,
             voltage, status_code, anomaly_flag, anomaly_type, firmware_version,
             model, manufacturer, location, latitude, longitude) = row
            
            # Convert timestamp to readable format
            dt = datetime.fromtimestamp(float(timestamp))
            
            # Create a status message based on status_code and anomaly
            status = "OK" if status_code == 0 else f"Error: {status_code}"
            if anomaly_flag:
                status = f"Anomaly: {anomaly_type}"
            
            latest_entry = {
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "sensor_id": sensor_id,
                "readings": {
                    "temperature": f"{temperature:.1f}°C" if temperature is not None else "N/A",
                    "humidity": f"{humidity:.1f}%" if humidity is not None else "N/A",
                    "pressure": f"{pressure:.1f}hPa" if pressure is not None else "N/A",
                    "vibration": f"{vibration:.3f}Hz" if vibration is not None else "N/A",
                    "voltage": f"{voltage:.1f}V" if voltage is not None else "N/A"
                },
                "status": status,
                "firmware": firmware_version,
                "model": model,
                "manufacturer": manufacturer,
                "location": location,
                "coordinates": format_coordinates(latitude, longitude)
            }
            
            print(json.dumps({
                "db_path": db_path,
                "status": "success",
                "row_count": row_count,
                "latest_entry": latest_entry
            }))
        else:
            print(json.dumps({
                "db_path": db_path,
                "status": "empty",
                "row_count": 0
            }))
        
    except sqlite3.Error as e:
        print(json.dumps({
            "error": f"Database error: {str(e)}",
            "db_path": db_path,
            "status": "error"
        }))
        exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main() 