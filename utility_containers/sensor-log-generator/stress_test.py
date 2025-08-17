#!/usr/bin/env python3
"""
Stress test for sensor database to validate concurrent read/write access.
Tests database resilience under aggressive load conditions.
"""

import multiprocessing
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Test configuration
TEST_CONFIG = {
    "num_writers": 5,  # Number of concurrent writer processes
    "num_readers": 10,  # Number of concurrent reader processes
    "writes_per_second": 50,  # Target writes per second per writer
    "test_duration": 30,  # Test duration in seconds
    "reader_interval": 0.1,  # How often readers check for new data
    "db_path": "test_sensor_data.db",  # Test database path
}


class TestStats:
    """Thread-safe statistics collector."""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.stats = {
            "writes_attempted": 0,
            "writes_succeeded": 0,
            "writes_failed": 0,
            "reads_attempted": 0,
            "reads_succeeded": 0,
            "reads_failed": 0,
            "read_errors": [],
            "write_errors": [],
            "corruption_detected": False,
            "max_read_latency": 0,
            "max_write_latency": 0,
        }
    
    def increment(self, key: str, value: int = 1):
        with self.lock:
            self.stats[key] += value
    
    def update_max(self, key: str, value: float):
        with self.lock:
            self.stats[key] = max(self.stats[key], value)
    
    def add_error(self, error_type: str, error: str):
        with self.lock:
            self.stats[f"{error_type}_errors"].append(error)
    
    def get_stats(self) -> Dict:
        with self.lock:
            return self.stats.copy()


def setup_database(db_path: str):
    """Create database with production schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            sensor_id TEXT NOT NULL,
            temperature REAL,
            vibration REAL,
            voltage REAL,
            status_code INTEGER,
            anomaly_flag INTEGER DEFAULT 0,
            anomaly_type TEXT,
            firmware_version TEXT,
            model TEXT,
            manufacturer TEXT,
            location TEXT,
            original_timezone TEXT,
            synced INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def writer_process(process_id: int, db_path: str, duration: int, writes_per_second: int, stats_queue):
    """Simulate sensor writes with batching."""
    stats = TestStats()
    conn = None
    
    try:
        # Setup connection with production pragmas
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        
        batch_size = 20
        batch_timeout = 5.0
        batch = []
        last_batch_time = time.time()
        
        start_time = time.time()
        write_count = 0
        
        while time.time() - start_time < duration:
            try:
                # Generate sensor reading
                reading = (
                    datetime.now(timezone.utc).isoformat(),
                    f"SENSOR_{process_id:03d}",
                    20.0 + (write_count % 10),  # Temperature
                    0.1 + (write_count % 5) * 0.01,  # Vibration
                    3.3,  # Voltage
                    200,  # Status code
                    0,  # Anomaly flag
                    None,  # Anomaly type
                    "1.0.0",
                    "TestSensor",
                    "TestCorp",
                    f"Location_{process_id}",
                    "+00:00",
                    0  # Not synced
                )
                
                batch.append(reading)
                stats.increment("writes_attempted")
                
                # Check if we should commit batch
                current_time = time.time()
                batch_age = current_time - last_batch_time
                
                if len(batch) >= batch_size or batch_age >= batch_timeout:
                    # Commit batch
                    write_start = time.time()
                    cursor = conn.executemany("""
                        INSERT INTO sensor_readings 
                        (timestamp, sensor_id, temperature, vibration, voltage,
                         status_code, anomaly_flag, anomaly_type, firmware_version,
                         model, manufacturer, location, original_timezone, synced)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    conn.commit()
                    write_latency = time.time() - write_start
                    
                    stats.increment("writes_succeeded", len(batch))
                    stats.update_max("max_write_latency", write_latency)
                    
                    batch = []
                    last_batch_time = current_time
                
                write_count += 1
                
                # Control write rate
                time.sleep(1.0 / writes_per_second)
                
            except sqlite3.Error as e:
                stats.increment("writes_failed")
                stats.add_error("write", str(e))
                if "malformed" in str(e).lower() or "corrupt" in str(e).lower():
                    stats.stats["corruption_detected"] = True
            except Exception as e:
                stats.add_error("write", f"Unexpected: {str(e)}")
        
        # Final batch commit
        if batch:
            try:
                conn.executemany("""
                    INSERT INTO sensor_readings 
                    (timestamp, sensor_id, temperature, vibration, voltage,
                     status_code, anomaly_flag, anomaly_type, firmware_version,
                     model, manufacturer, location, original_timezone, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                stats.increment("writes_succeeded", len(batch))
            except Exception as e:
                stats.increment("writes_failed", len(batch))
                stats.add_error("write", str(e))
    
    finally:
        if conn:
            conn.close()
        stats_queue.put(("writer", process_id, stats.get_stats()))


def reader_process(process_id: int, db_path: str, duration: int, read_interval: float, stats_queue):
    """Simulate external reader accessing the database."""
    stats = TestStats()
    conn = None
    last_row_id = 0
    
    try:
        # Setup read-only connection
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30.0)
        conn.execute("PRAGMA query_only=1;")
        conn.execute("PRAGMA busy_timeout=30000;")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                read_start = time.time()
                stats.increment("reads_attempted")
                
                # Read new data since last check
                cursor = conn.execute("""
                    SELECT id, timestamp, sensor_id, temperature, vibration, voltage
                    FROM sensor_readings
                    WHERE id > ?
                    ORDER BY id DESC
                    LIMIT 100
                """, (last_row_id,))
                
                rows = cursor.fetchall()
                read_latency = time.time() - read_start
                
                # Count as successful even if no new rows (query succeeded)
                stats.increment("reads_succeeded")
                stats.update_max("max_read_latency", read_latency)
                
                if rows:
                    last_row_id = max(row[0] for row in rows)
                    
                    # Validate data integrity
                    for row in rows:
                        if row[1] is None or row[2] is None:
                            stats.add_error("read", "NULL in required field")
                            stats.stats["corruption_detected"] = True
                
                time.sleep(read_interval)
                
            except sqlite3.Error as e:
                stats.increment("reads_failed")
                stats.add_error("read", str(e))
                if "malformed" in str(e).lower() or "corrupt" in str(e).lower():
                    stats.stats["corruption_detected"] = True
            except Exception as e:
                stats.add_error("read", f"Unexpected: {str(e)}")
    
    finally:
        if conn:
            conn.close()
        stats_queue.put(("reader", process_id, stats.get_stats()))


def run_stress_test(config: Dict) -> Dict:
    """Run the stress test with multiple concurrent readers and writers."""
    print("\n" + "="*60)
    print("DATABASE STRESS TEST")
    print("="*60)
    print(f"Configuration:")
    print(f"  Writers: {config['num_writers']}")
    print(f"  Readers: {config['num_readers']}")
    print(f"  Writes/sec/writer: {config['writes_per_second']}")
    print(f"  Duration: {config['test_duration']}s")
    print(f"  Database: {config['db_path']}")
    print("-"*60)
    
    # Clean up any existing test database
    if os.path.exists(config['db_path']):
        os.remove(config['db_path'])
    
    # Setup database
    setup_database(config['db_path'])
    
    # Create multiprocessing queue for stats collection
    stats_queue = multiprocessing.Queue()
    
    # Start writer processes
    writers = []
    for i in range(config['num_writers']):
        p = multiprocessing.Process(
            target=writer_process,
            args=(i, config['db_path'], config['test_duration'], 
                  config['writes_per_second'], stats_queue)
        )
        p.start()
        writers.append(p)
    
    # Start reader processes
    readers = []
    for i in range(config['num_readers']):
        p = multiprocessing.Process(
            target=reader_process,
            args=(i, config['db_path'], config['test_duration'],
                  config['reader_interval'], stats_queue)
        )
        p.start()
        readers.append(p)
    
    # Monitor progress
    print("\nTest running", end="")
    for i in range(config['test_duration']):
        print(".", end="", flush=True)
        time.sleep(1)
    print(" Done!")
    
    # Wait for all processes to complete
    for p in writers + readers:
        p.join(timeout=5)
        if p.is_alive():
            p.terminate()
    
    # Collect statistics
    aggregated_stats = {
        "writes_attempted": 0,
        "writes_succeeded": 0,
        "writes_failed": 0,
        "reads_attempted": 0,
        "reads_succeeded": 0,
        "reads_failed": 0,
        "read_errors": [],
        "write_errors": [],
        "corruption_detected": False,
        "max_read_latency": 0,
        "max_write_latency": 0,
    }
    
    while not stats_queue.empty():
        process_type, process_id, stats = stats_queue.get()
        for key in ["writes_attempted", "writes_succeeded", "writes_failed",
                   "reads_attempted", "reads_succeeded", "reads_failed"]:
            aggregated_stats[key] += stats.get(key, 0)
        
        aggregated_stats["read_errors"].extend(stats.get("read_errors", []))
        aggregated_stats["write_errors"].extend(stats.get("write_errors", []))
        aggregated_stats["corruption_detected"] |= stats.get("corruption_detected", False)
        aggregated_stats["max_read_latency"] = max(
            aggregated_stats["max_read_latency"],
            stats.get("max_read_latency", 0)
        )
        aggregated_stats["max_write_latency"] = max(
            aggregated_stats["max_write_latency"],
            stats.get("max_write_latency", 0)
        )
    
    # Final database check
    try:
        conn = sqlite3.connect(config['db_path'])
        cursor = conn.execute("SELECT COUNT(*) FROM sensor_readings")
        total_records = cursor.fetchone()[0]
        
        # Check for integrity
        cursor = conn.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        
        conn.close()
        
        aggregated_stats["total_records"] = total_records
        aggregated_stats["integrity_check"] = integrity_result
        
    except Exception as e:
        aggregated_stats["final_check_error"] = str(e)
    
    return aggregated_stats


def print_results(stats: Dict):
    """Print test results in a formatted way."""
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    # Write statistics
    write_success_rate = (
        (stats["writes_succeeded"] / stats["writes_attempted"] * 100)
        if stats["writes_attempted"] > 0 else 0
    )
    print(f"\nWrite Operations:")
    print(f"  Attempted: {stats['writes_attempted']:,}")
    print(f"  Succeeded: {stats['writes_succeeded']:,}")
    print(f"  Failed: {stats['writes_failed']:,}")
    print(f"  Success Rate: {write_success_rate:.2f}%")
    print(f"  Max Latency: {stats['max_write_latency']*1000:.2f}ms")
    
    # Read statistics
    read_success_rate = (
        (stats["reads_succeeded"] / stats["reads_attempted"] * 100)
        if stats["reads_attempted"] > 0 else 0
    )
    print(f"\nRead Operations:")
    print(f"  Attempted: {stats['reads_attempted']:,}")
    print(f"  Succeeded: {stats['reads_succeeded']:,}")
    print(f"  Failed: {stats['reads_failed']:,}")
    print(f"  Success Rate: {read_success_rate:.2f}%")
    print(f"  Max Latency: {stats['max_read_latency']*1000:.2f}ms")
    
    # Database state
    print(f"\nDatabase State:")
    print(f"  Total Records: {stats.get('total_records', 'Unknown'):,}")
    print(f"  Integrity Check: {stats.get('integrity_check', 'Unknown')}")
    print(f"  Corruption Detected: {stats['corruption_detected']}")
    
    # Errors
    if stats["write_errors"] or stats["read_errors"]:
        print(f"\nErrors Encountered:")
        
        if stats["write_errors"]:
            unique_write_errors = list(set(stats["write_errors"]))[:5]
            print(f"  Write Errors ({len(stats['write_errors'])} total):")
            for error in unique_write_errors:
                print(f"    - {error}")
        
        if stats["read_errors"]:
            unique_read_errors = list(set(stats["read_errors"]))[:5]
            print(f"  Read Errors ({len(stats['read_errors'])} total):")
            for error in unique_read_errors:
                print(f"    - {error}")
    
    # Test verdict
    print("\n" + "="*60)
    if (write_success_rate >= 99.0 and 
        read_success_rate >= 99.0 and 
        not stats["corruption_detected"] and
        stats.get("integrity_check") == "ok"):
        print("✅ TEST PASSED - Database configuration is resilient")
    else:
        print("❌ TEST FAILED - Issues detected with database configuration")
        if write_success_rate < 99.0:
            print(f"   - Write success rate too low: {write_success_rate:.2f}%")
        if read_success_rate < 99.0:
            print(f"   - Read success rate too low: {read_success_rate:.2f}%")
        if stats["corruption_detected"]:
            print("   - Database corruption detected")
        if stats.get("integrity_check") != "ok":
            print(f"   - Integrity check failed: {stats.get('integrity_check')}")
    print("="*60)


if __name__ == "__main__":
    # Allow overriding config from command line
    if len(sys.argv) > 1:
        import json
        try:
            custom_config = json.loads(sys.argv[1])
            TEST_CONFIG.update(custom_config)
        except:
            print("Usage: python stress_test.py ['{\"num_writers\": 10, ...}']")
    
    # Run the stress test
    results = run_stress_test(TEST_CONFIG)
    
    # Print results
    print_results(results)
    
    # Clean up test database
    if os.path.exists(TEST_CONFIG['db_path']):
        os.remove(TEST_CONFIG['db_path'])
    
    # Exit with appropriate code
    sys.exit(0 if results.get("integrity_check") == "ok" else 1)