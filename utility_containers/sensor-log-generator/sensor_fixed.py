#!/usr/bin/env python3
"""
Fixed sensor.py - Robust SQLite data persistence with WAL mode and graceful SIGTERM handling
"""

import sqlite3
import time
import random
import os
import signal
import sys
import logging
import atexit
from datetime import datetime
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_FILE = "/app/data/sensor_data.db"

class DatabaseManager:
    """Thread-safe database manager with proper WAL checkpoint handling"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.lock = Lock()
        self.pending_writes = 0
        self.last_checkpoint_time = time.time()
        self.checkpoint_interval = 60  # Force checkpoint every 60 seconds
        
    def connect(self):
        """Create database connection with WAL mode and optimized settings"""
        logger.info(f"Connecting to database at {self.db_path}")
        
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        
        # Configure SQLite for optimal performance with data safety
        pragmas = [
            "PRAGMA journal_mode=WAL;",           # Enable WAL mode for concurrency
            "PRAGMA synchronous=NORMAL;",         # Balance between safety and speed
            "PRAGMA cache_size=-64000;",          # 64MB cache
            "PRAGMA temp_store=MEMORY;",          # Use memory for temp tables
            "PRAGMA mmap_size=268435456;",        # 256MB memory-mapped I/O
            "PRAGMA wal_autocheckpoint=1000;",    # Auto-checkpoint every 1000 pages
            "PRAGMA busy_timeout=5000;",          # 5 second timeout for locks
        ]
        
        for pragma in pragmas:
            result = self.conn.execute(pragma).fetchone()
            logger.debug(f"{pragma.split()[1]} = {result}")
        
        return self.conn
    
    def setup_database(self):
        """Create the database table if it doesn't exist"""
        logger.info("Setting up database table...")
        with self.lock:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        temperature REAL,
                        humidity REAL,
                        sensor_id TEXT,
                        status TEXT DEFAULT 'normal'
                    )
                """)
                # Create index for better query performance
                self.conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON sensor_readings(timestamp)
                """)
        logger.info("Database setup complete")
    
    def insert_reading(self, temperature, humidity, sensor_id="SENSOR001"):
        """Insert a sensor reading with automatic checkpointing"""
        with self.lock:
            try:
                with self.conn:
                    self.conn.execute(
                        """INSERT INTO sensor_readings 
                           (temperature, humidity, sensor_id, timestamp) 
                           VALUES (?, ?, ?, ?)""",
                        (temperature, humidity, sensor_id, datetime.now().isoformat())
                    )
                self.pending_writes += 1
                
                # Periodic checkpoint to ensure durability
                current_time = time.time()
                if current_time - self.last_checkpoint_time > self.checkpoint_interval:
                    self.checkpoint()
                    self.last_checkpoint_time = current_time
                    
            except sqlite3.Error as e:
                logger.error(f"Database error during insert: {e}")
                raise
    
    def checkpoint(self, mode="PASSIVE"):
        """
        Force a WAL checkpoint to ensure data is written to main database file.
        
        Modes:
        - PASSIVE: Checkpoint as much as possible without blocking (default)
        - FULL: Wait for exclusive lock and checkpoint all frames
        - RESTART: Like FULL, but also restart the WAL for next transaction
        - TRUNCATE: Like RESTART, but also truncate the WAL file
        """
        with self.lock:
            try:
                logger.info(f"Executing WAL checkpoint (mode={mode}, pending={self.pending_writes})...")
                
                # Execute checkpoint and get statistics
                result = self.conn.execute(f"PRAGMA wal_checkpoint({mode});").fetchone()
                
                # Result format: (busy, checkpointed_frames, total_frames)
                if result:
                    busy, checkpointed, total = result
                    logger.info(
                        f"Checkpoint complete: checkpointed {checkpointed}/{total} frames"
                        f" (busy={busy}, mode={mode})"
                    )
                    
                    # If PASSIVE checkpoint couldn't checkpoint everything, try FULL
                    if mode == "PASSIVE" and checkpointed < total:
                        logger.info("PASSIVE checkpoint incomplete, attempting FULL checkpoint...")
                        self.checkpoint("FULL")
                
                self.pending_writes = 0
                return result
                
            except sqlite3.Error as e:
                logger.error(f"Error during checkpoint: {e}")
                return None
    
    def close(self):
        """Close database connection with final checkpoint"""
        if self.conn:
            with self.lock:
                try:
                    logger.info("Closing database connection...")
                    
                    # Force a TRUNCATE checkpoint for maximum durability
                    # This ensures ALL data is written and WAL is cleaned up
                    logger.info("Executing final TRUNCATE checkpoint...")
                    result = self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
                    if result:
                        _, checkpointed, total = result
                        logger.info(f"Final checkpoint: {checkpointed}/{total} frames written")
                    
                    # Ensure all data is synced to disk
                    self.conn.execute("PRAGMA synchronous=FULL;")
                    self.conn.commit()
                    
                    # Get final statistics
                    count = self.conn.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0]
                    logger.info(f"Database contains {count} total readings")
                    
                    self.conn.close()
                    logger.info("Database connection closed successfully")
                    
                except sqlite3.Error as e:
                    logger.error(f"Error during database close: {e}")
                finally:
                    self.conn = None

class SensorSimulator:
    """Main sensor simulator with graceful shutdown handling"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.running = False
        self.shutdown_requested = False
        self.sensor_id = os.environ.get("SENSOR_ID", "SENSOR_001")
        self.stats = {
            'readings_generated': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()
        
    def _register_signal_handlers(self):
        """Register handlers for graceful shutdown signals"""
        
        def signal_handler(signum, frame):
            """Handle shutdown signals gracefully"""
            signal_name = signal.Signals(signum).name
            logger.info(f"\n{signal_name} received. Initiating graceful shutdown...")
            self.shutdown_requested = True
            
            # If we're not in the main loop, force shutdown after timeout
            if not self.running:
                logger.info("Forcing immediate shutdown...")
                self._cleanup()
                sys.exit(0)
        
        # Register handlers for both SIGTERM (docker stop) and SIGINT (Ctrl+C)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Also register cleanup with atexit as a fallback
        atexit.register(self._cleanup)
        
        logger.info("Signal handlers registered for SIGTERM and SIGINT")
    
    def _cleanup(self):
        """Cleanup operations to ensure data persistence"""
        logger.info("Starting cleanup operations...")
        
        # Stop the main loop
        self.running = False
        
        # Force a final checkpoint and close database
        if self.db_manager:
            self.db_manager.close()
        
        # Log statistics
        if self.stats['start_time']:
            self.stats['end_time'] = time.time()
            duration = self.stats['end_time'] - self.stats['start_time']
            logger.info(f"Session statistics:")
            logger.info(f"  Duration: {duration:.2f} seconds")
            logger.info(f"  Readings generated: {self.stats['readings_generated']}")
            logger.info(f"  Errors: {self.stats['errors']}")
            logger.info(f"  Rate: {self.stats['readings_generated']/duration:.2f} readings/sec")
        
        logger.info("Cleanup complete. Exiting.")
    
    def generate_reading(self):
        """Generate a random sensor reading"""
        return {
            'temperature': round(random.uniform(18.0, 25.0), 2),
            'humidity': round(random.uniform(40.0, 65.0), 2)
        }
    
    def run(self, duration=None, rate=10):
        """
        Run the sensor simulator
        
        Args:
            duration: Run duration in seconds (None for infinite)
            rate: Readings per second
        """
        self.running = True
        self.stats['start_time'] = time.time()
        
        logger.info(f"Starting sensor simulator (ID: {self.sensor_id})")
        logger.info(f"Generating {rate} readings/second")
        if duration:
            logger.info(f"Will run for {duration} seconds")
        
        sleep_interval = 1.0 / rate
        start_time = time.time()
        
        try:
            while self.running and not self.shutdown_requested:
                # Check duration limit
                if duration and (time.time() - start_time) >= duration:
                    logger.info("Duration limit reached")
                    break
                
                # Generate and store reading
                try:
                    reading = self.generate_reading()
                    self.db_manager.insert_reading(
                        temperature=reading['temperature'],
                        humidity=reading['humidity'],
                        sensor_id=self.sensor_id
                    )
                    self.stats['readings_generated'] += 1
                    
                    # Log progress every 100 readings
                    if self.stats['readings_generated'] % 100 == 0:
                        logger.info(f"Generated {self.stats['readings_generated']} readings...")
                        
                except Exception as e:
                    logger.error(f"Error generating/storing reading: {e}")
                    self.stats['errors'] += 1
                
                # Sleep for the appropriate interval
                time.sleep(sleep_interval)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.running = False
            logger.info("Main loop ended")

def main():
    """Main entry point"""
    logger.info(f"Sensor simulator starting (PID: {os.getpid()})")
    
    # Create database manager
    db_manager = DatabaseManager(DB_FILE)
    
    try:
        # Initialize database
        db_manager.connect()
        db_manager.setup_database()
        
        # Create and run simulator
        simulator = SensorSimulator(db_manager)
        
        # Run indefinitely (until signal received)
        simulator.run(duration=None, rate=10)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure cleanup happens
        if db_manager:
            db_manager.close()

if __name__ == "__main__":
    main()