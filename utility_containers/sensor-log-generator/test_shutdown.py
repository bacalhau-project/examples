#!/usr/bin/env python3
"""Test script to verify graceful shutdown behavior."""

import signal
import sys
import time
import subprocess

def test_shutdown():
    """Run the sensor and send SIGINT after 3 seconds."""
    
    print("Starting sensor simulator...")
    
    # Start the process
    proc = subprocess.Popen([
        sys.executable, "main.py",
        "--config", "config/config.yaml",
        "--identity", "config/identity.json"
    ])
    
    print(f"Process started with PID {proc.pid}")
    
    # Let it run for 3 seconds
    print("Letting it run for 3 seconds...")
    time.sleep(3)
    
    # Send SIGINT
    print("Sending SIGINT...")
    proc.send_signal(signal.SIGINT)
    
    # Wait for it to shut down (max 5 seconds)
    print("Waiting for shutdown...")
    try:
        return_code = proc.wait(timeout=5)
        print(f"Process exited cleanly with code {return_code}")
    except subprocess.TimeoutExpired:
        print("Process didn't exit in 5 seconds, forcing termination...")
        proc.kill()
        proc.wait()
        print("Process forcefully terminated")
        return False
    
    # Check database
    import sqlite3
    try:
        conn = sqlite3.connect('data/sensor_data.db')
        cursor = conn.execute('SELECT COUNT(*) FROM sensor_readings')
        count = cursor.fetchone()[0]
        print(f"Database contains {count} readings")
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")
    
    return True

if __name__ == "__main__":
    # Remove old database
    import os
    if os.path.exists('data/sensor_data.db'):
        os.remove('data/sensor_data.db')
    
    success = test_shutdown()
    sys.exit(0 if success else 1)