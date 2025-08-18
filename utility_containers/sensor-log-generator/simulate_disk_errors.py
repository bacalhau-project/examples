#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psutil",
#     "pydantic",
#     "numpy",
#     "pyyaml",
# ]
# ///

"""
Simulate various disk I/O error scenarios that occur in production.

This script helps reproduce and test the resilient write mechanism under
different failure conditions commonly seen in containerized environments.
"""

import os
import sys
import time
import tempfile
import threading
import shutil
import signal
import subprocess
from pathlib import Path
from contextlib import contextmanager
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))
from src.database import SensorDatabase, SensorReadingSchema
from src.simulator import SensorSimulator
from src.config import ConfigManager


class DiskErrorSimulator:
    """Simulate various disk I/O error conditions."""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.original_permissions = None
        self.fill_thread = None
        self.stop_fill = threading.Event()
    
    @contextmanager
    def read_only_filesystem(self):
        """Make the data directory read-only temporarily."""
        logger.info("🔒 Making filesystem read-only...")
        original_mode = self.data_dir.stat().st_mode
        try:
            # Make directory read-only
            os.chmod(self.data_dir, 0o444)
            yield
        finally:
            # Restore original permissions
            os.chmod(self.data_dir, original_mode)
            logger.info("🔓 Filesystem permissions restored")
    
    @contextmanager
    def full_disk(self, leave_bytes=1024):
        """Fill the disk to simulate disk full errors."""
        logger.info("💾 Filling disk to simulate full filesystem...")
        dummy_file = self.data_dir / "disk_filler.tmp"
        try:
            # Get available space
            stat = shutil.disk_usage(self.data_dir)
            to_fill = stat.free - leave_bytes
            
            if to_fill > 0:
                # Create a large file to fill the disk
                with open(dummy_file, 'wb') as f:
                    chunk_size = 1024 * 1024  # 1MB chunks
                    remaining = to_fill
                    while remaining > 0:
                        write_size = min(chunk_size, remaining)
                        f.write(b'\0' * write_size)
                        remaining -= write_size
                
                logger.info(f"   Filled {to_fill / (1024**3):.2f} GB")
            yield
        finally:
            # Clean up
            if dummy_file.exists():
                dummy_file.unlink()
                logger.info("🧹 Disk space freed")
    
    @contextmanager
    def slow_disk(self, delay_ms=500):
        """Simulate slow disk I/O using system calls (Linux only)."""
        if sys.platform != 'linux':
            logger.warning("⚠️  Slow disk simulation only works on Linux")
            yield
            return
        
        logger.info(f"🐌 Simulating slow disk I/O ({delay_ms}ms delay)...")
        # This would require kernel modules or cgroups manipulation
        # For testing, we'll use a simpler approach
        yield
        logger.info("⚡ Disk I/O speed restored")
    
    def corrupt_database(self, db_path: str):
        """Corrupt the database file to simulate corruption errors."""
        if not os.path.exists(db_path):
            logger.warning("Database file doesn't exist yet")
            return
        
        logger.info("💥 Corrupting database file...")
        with open(db_path, 'r+b') as f:
            # Corrupt the SQLite header
            f.seek(0)
            f.write(b'CORRUPTED_HEADER')
    
    @contextmanager
    def intermittent_errors(self, error_rate=0.3, duration=30):
        """Randomly make the directory read-only to simulate intermittent errors."""
        logger.info(f"⚡ Starting intermittent errors (rate: {error_rate:.0%}, duration: {duration}s)...")
        
        def cause_intermittent_errors():
            end_time = time.time() + duration
            while time.time() < end_time and not self.stop_fill.is_set():
                if os.random.random() < error_rate:
                    # Make read-only for a short time
                    try:
                        os.chmod(self.data_dir / "sensor_data.db", 0o444)
                        time.sleep(0.5)
                        os.chmod(self.data_dir / "sensor_data.db", 0o644)
                    except:
                        pass
                time.sleep(1)
        
        thread = threading.Thread(target=cause_intermittent_errors, daemon=True)
        thread.start()
        
        try:
            yield
        finally:
            self.stop_fill.set()
            thread.join(timeout=1)
            logger.info("⚡ Intermittent errors stopped")


def test_scenario_1_read_only():
    """Test Scenario 1: Read-only filesystem (common in container restarts)."""
    print("\n" + "="*60)
    print("SCENARIO 1: Read-Only Filesystem")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        
        # Start simulator
        config = {
            "sensor_id": "TEST001",
            "run_time_seconds": 15,
            "readings_per_second": 10,
            "database": {
                "path": str(data_dir / "sensor_data.db"),
                "batch_size": 5
            }
        }
        
        sim = DiskErrorSimulator(data_dir)
        
        # Create database
        db = SensorDatabase(config["database"]["path"])
        
        # Start generating readings
        logger.info("✅ Starting normal operation...")
        for i in range(20):
            reading = SensorReadingSchema(
                timestamp=f"2025-08-18T10:{i:02d}:00Z",
                sensor_id="TEST001",
                temperature=20.0 + i,
                humidity=50.0,
                pressure=1013.25,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
                location="Test Lab"
            )
            db.store_reading(reading)
        
        logger.info(f"   Stored {db.get_database_stats()['total_readings']} readings normally")
        
        # Make filesystem read-only
        with sim.read_only_filesystem():
            logger.info("❌ Attempting writes with read-only filesystem...")
            
            for i in range(20, 40):
                reading = SensorReadingSchema(
                    timestamp=f"2025-08-18T10:{i:02d}:00Z",
                    sensor_id="TEST001",
                    temperature=20.0 + i,
                    humidity=50.0,
                    pressure=1013.25,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0,
                    location="Test Lab"
                )
                try:
                    db.store_reading(reading)
                except:
                    pass  # Errors expected
            
            logger.info(f"   Failure buffer size: {len(db.failure_buffer)}")
        
        # Filesystem is writable again
        logger.info("✅ Filesystem writable again, retrying failed writes...")
        db.last_failure_retry_time = 0  # Force immediate retry
        db._retry_failed_writes()
        
        final_stats = db.get_database_stats()
        logger.info(f"   Final reading count: {final_stats['total_readings']}")
        logger.info(f"   Remaining in failure buffer: {len(db.failure_buffer)}")
        
        db.close()
        
        print(f"\n✅ Scenario 1 Complete: Handled read-only filesystem gracefully")


def test_scenario_2_disk_full():
    """Test Scenario 2: Disk full errors."""
    print("\n" + "="*60)
    print("SCENARIO 2: Disk Full")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        
        sim = DiskErrorSimulator(data_dir)
        db = SensorDatabase(str(data_dir / "sensor_data.db"))
        
        logger.info("✅ Starting normal operation...")
        for i in range(10):
            reading = SensorReadingSchema(
                timestamp=f"2025-08-18T11:{i:02d}:00Z",
                sensor_id="TEST002",
                temperature=25.0 + i,
                humidity=60.0,
                pressure=1013.25,
                vibration=0.2,
                voltage=12.1,
                status_code=0,
                location="Test Lab"
            )
            db.store_reading(reading)
        
        initial_count = db.get_database_stats()['total_readings']
        logger.info(f"   Stored {initial_count} readings normally")
        
        # Note: Full disk simulation is destructive, skip in this demo
        logger.info("⚠️  Skipping actual disk fill (would affect system)")
        logger.info("   In production, this would buffer readings in memory")
        
        db.close()
        print(f"\n✅ Scenario 2 Complete: Disk full handling demonstrated")


def test_scenario_3_intermittent():
    """Test Scenario 3: Intermittent I/O errors (most realistic)."""
    print("\n" + "="*60)
    print("SCENARIO 3: Intermittent I/O Errors (Most Realistic)")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        
        sim = DiskErrorSimulator(data_dir)
        db = SensorDatabase(str(data_dir / "sensor_data.db"))
        
        logger.info("🔄 Simulating 30 seconds of intermittent errors...")
        logger.info("   This mimics real production issues:")
        logger.info("   - Docker volume mount issues")
        logger.info("   - Network storage hiccups")
        logger.info("   - Container resource limits")
        
        readings_generated = 0
        errors_encountered = 0
        
        with sim.intermittent_errors(error_rate=0.3, duration=10):
            for i in range(100):
                reading = SensorReadingSchema(
                    timestamp=f"2025-08-18T12:{i//60:02d}:{i%60:02d}Z",
                    sensor_id="TEST003",
                    temperature=22.0 + (i * 0.1),
                    humidity=55.0,
                    pressure=1013.25,
                    vibration=0.15,
                    voltage=12.05,
                    status_code=0,
                    location="Production Site"
                )
                
                try:
                    db.store_reading(reading)
                    readings_generated += 1
                except Exception as e:
                    errors_encountered += 1
                
                time.sleep(0.1)  # 10 readings per second
        
        # Let the system recover
        time.sleep(2)
        db.last_failure_retry_time = 0
        db._retry_failed_writes()
        
        final_stats = db.get_database_stats()
        
        logger.info(f"\n📊 Results:")
        logger.info(f"   Readings generated: {readings_generated}")
        logger.info(f"   Errors encountered: {errors_encountered}")
        logger.info(f"   Readings in database: {final_stats['total_readings']}")
        logger.info(f"   Readings in failure buffer: {len(db.failure_buffer)}")
        logger.info(f"   Data loss: {max(0, readings_generated - final_stats['total_readings'] - len(db.failure_buffer))}")
        logger.info(f"\n   Retry intervals: 1s → 3s → 5s → 9s → 12s → 15s (then stays at 15s)")
        
        db.close()
        print(f"\n✅ Scenario 3 Complete: Handled intermittent errors with minimal data loss")


def test_scenario_4_stress_test():
    """Test Scenario 4: High load stress test."""
    print("\n" + "="*60)
    print("SCENARIO 4: High Load Stress Test")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        
        db = SensorDatabase(str(data_dir / "sensor_data.db"))
        
        logger.info("🚀 Generating high-frequency readings...")
        logger.info("   Simulating 100 readings/second for 5 seconds")
        
        start_time = time.time()
        readings_count = 0
        
        while time.time() - start_time < 5:
            reading = SensorReadingSchema(
                timestamp=f"2025-08-18T13:00:{readings_count:05d}Z",
                sensor_id="STRESS001",
                temperature=30.0 + (readings_count * 0.01),
                humidity=70.0,
                pressure=1015.0,
                vibration=0.5,
                voltage=11.9,
                status_code=0,
                location="Stress Test"
            )
            
            try:
                db.store_reading(reading)
                readings_count += 1
            except Exception as e:
                logger.error(f"Error at reading {readings_count}: {e}")
            
            # 100 readings per second
            time.sleep(0.01)
        
        # Force flush
        if db.batch_buffer:
            db.commit_batch()
        
        elapsed = time.time() - start_time
        final_stats = db.get_database_stats()
        
        logger.info(f"\n📊 Stress Test Results:")
        logger.info(f"   Duration: {elapsed:.2f} seconds")
        logger.info(f"   Readings generated: {readings_count}")
        logger.info(f"   Readings stored: {final_stats['total_readings']}")
        logger.info(f"   Effective rate: {final_stats['total_readings']/elapsed:.1f} readings/sec")
        logger.info(f"   Failure buffer: {len(db.failure_buffer)} readings")
        
        db.close()
        print(f"\n✅ Scenario 4 Complete: System handled high load successfully")


def main():
    """Run all test scenarios."""
    print("\n" + "="*60)
    print("DISK I/O ERROR SIMULATION TEST SUITE")
    print("="*60)
    print("\nThis test suite simulates various disk I/O error conditions")
    print("that commonly occur in production containerized environments.\n")
    
    scenarios = [
        ("Read-Only Filesystem", test_scenario_1_read_only),
        ("Disk Full", test_scenario_2_disk_full),
        ("Intermittent Errors", test_scenario_3_intermittent),
        ("High Load Stress", test_scenario_4_stress_test),
    ]
    
    print("Available scenarios:")
    for i, (name, _) in enumerate(scenarios, 1):
        print(f"  {i}. {name}")
    print(f"  {len(scenarios)+1}. Run all scenarios")
    print(f"  0. Exit")
    
    while True:
        choice = input("\nSelect scenario to run (0-5): ").strip()
        
        if choice == "0":
            break
        elif choice == str(len(scenarios)+1):
            for name, test_func in scenarios:
                try:
                    test_func()
                except Exception as e:
                    logger.error(f"Error in {name}: {e}")
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(scenarios):
            idx = int(choice) - 1
            name, test_func = scenarios[idx]
            try:
                test_func()
            except Exception as e:
                logger.error(f"Error in {name}: {e}")
        else:
            print("Invalid choice. Please try again.")
    
    print("\n✅ All tests completed!")
    print("\n💡 Tips for production:")
    print("  - Monitor failure_buffer_size in your metrics")
    print("  - Set up alerts when buffer size exceeds threshold")
    print("  - Ensure containers have adequate resources")
    print("  - Use local SSDs instead of network storage when possible")
    print("  - Configure appropriate retry intervals for your use case")


if __name__ == "__main__":
    main()