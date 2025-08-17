#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

import sqlite3
import time
import sys
import os
from datetime import datetime
from pathlib import Path

# Colors for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
MAGENTA = "\033[0;35m"
NC = "\033[0m"  # No Color


def find_database_file(base_dir):
    """Find the sensor database file in the given directory"""
    possible_names = [
        "sensor_data.db",
        "wind_turbine_sensors.db",
        "sensor_readings.db",
        "sensors.db",
    ]

    data_dir = Path(base_dir) / "data"
    if data_dir.exists():
        for db_name in possible_names:
            db_path = data_dir / db_name
            if db_path.exists():
                return str(db_path)

    # Also check base directory
    for db_name in possible_names:
        db_path = Path(base_dir) / db_name
        if db_path.exists():
            return str(db_path)

    return None


def get_table_name(conn):
    """Get the name of the sensor data table"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    # Priority order for table names
    priority_tables = ["sensor_readings", "sensor_logs", "sensors"]

    for priority_table in priority_tables:
        for table in tables:
            if table[0] == priority_table:
                return table[0]

    # Fallback: Look for any sensor-related table
    for table in tables:
        table_name = table[0].lower()
        if "sensor" in table_name or "reading" in table_name or "log" in table_name:
            return table[0]

    return None


def print_progress_update(total_records, last_update_time, update_size=1000, sensors_per_batch=5):
    """Print progress update every N records"""
    print()
    print(f"{GREEN}{'=' * 40}{NC}")
    print(f"{MAGENTA}[PROGRESS]{NC} Sensor Data Generation Update")
    print(f"{GREEN}{'=' * 40}{NC}")
    print(f"  {CYAN}Total Records Generated:{NC} {total_records:,}")
    print(f"  {CYAN}Time for Last 1000 Records:{NC} {last_update_time:.2f} seconds")
    print(f"  {CYAN}Records per Second:{NC} {1000 / last_update_time:.2f}")
    print(f"  {CYAN}Batches Processed:{NC} {total_records // sensors_per_batch:,}")
    print(f"  {CYAN}Current Timestamp:{NC} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{GREEN}{'=' * 40}{NC}")
    print()


def monitor_database(base_dir, check_interval=1):
    """Monitor the database for record count changes"""
    last_count = 0
    last_100_milestone = 0
    last_100_time = time.time()
    table_name = None
    db_path = None
    wait_count = 0

    # Initial message
    print(f"{BLUE}[MONITOR]{NC} Waiting for sensor database to be created...")

    while True:
        try:
            # Find database file if we haven't yet
            if not db_path:
                db_path = find_database_file(base_dir)
                if not db_path:
                    wait_count += 1
                    if wait_count % 10 == 0:  # Print every 10 seconds
                        print(
                            f"{YELLOW}[MONITOR]{NC} Still waiting for database in {base_dir}/data/..."
                        )
                    time.sleep(check_interval)
                    continue
                else:
                    print(f"{GREEN}[MONITOR]{NC} Found database: {db_path}")

            # Connect to the database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get table name if we haven't yet
            if not table_name:
                table_name = get_table_name(conn)
                if not table_name:
                    conn.close()
                    time.sleep(check_interval)
                    continue
                print(f"{GREEN}[MONITOR]{NC} Monitoring table: {table_name}")

            # Get the total count of sensor logs
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_count = cursor.fetchone()[0]

            # Check if we've hit a new 1000-record milestone
            current_1000_milestone = (total_count // 1000) * 1000
            if current_1000_milestone > last_100_milestone and current_1000_milestone > 0:
                current_time = time.time()
                time_diff = current_time - last_100_time
                print_progress_update(total_count, time_diff, 1000)
                last_100_milestone = current_1000_milestone
                last_100_time = current_time

            conn.close()
            time.sleep(check_interval)

        except sqlite3.OperationalError as e:
            # Database might be locked or table doesn't exist yet
            if "no such table" in str(e):
                table_name = None  # Reset and try finding again
            time.sleep(check_interval)
        except KeyboardInterrupt:
            print(f"\n{BLUE}[MONITOR]{NC} Monitoring stopped by user")
            break
        except Exception as e:
            print(f"{RED}[ERROR]{NC} {e}")
            time.sleep(check_interval)


def main():
    # Get base directory from command line or use default
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        # Determine if we're in anomaly mode based on environment or arguments
        anomaly_mode = "--with-anomalies" in sys.argv or os.environ.get("ANOMALY_MODE") == "true"

        # Set paths based on mode
        if anomaly_mode:
            base_dir = "./sample-sensor-anomaly"
        else:
            base_dir = "./sample-sensor"

    print(f"{GREEN}{'=' * 40}{NC}")
    print(f"{GREEN}  Sensor Progress Monitor{NC}")
    print(f"{GREEN}{'=' * 40}{NC}")
    print(f"{CYAN}[CONFIG]{NC} Monitoring directory: {base_dir}")
    print(f"{CYAN}[CONFIG]{NC} Update frequency: Every 1000 records")
    print(f"{GREEN}{'=' * 40}{NC}")
    print()

    # Start monitoring
    monitor_database(base_dir)


if __name__ == "__main__":
    main()
