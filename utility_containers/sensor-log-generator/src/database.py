import logging
import os
import sqlite3
import time
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional

import numpy as np
import requests


def retry_on_error(max_retries=3, retry_delay=1.0):
    """Decorator to retry a function on error.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Decorated function that will retry on error
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Log the error and retry
                        logging.warning(
                            f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {retry_delay} seconds..."
                        )
                        time.sleep(retry_delay)
                    else:
                        # Log the final failure
                        logging.error(
                            f"Database operation failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None

        return wrapper

    return decorator


class SensorDatabase:
    def __init__(self, db_path: str):
        """Initialize the sensor database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger("SensorDatabase")

        # Check if old database exists and needs to be removed
        if os.path.exists(self.db_path) and self.db_path != ":memory:":
            try:
                # Try to connect to the database and check for the synced column
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(sensor_readings)")
                columns = [column[1] for column in cursor.fetchall()]
                if "synced" not in columns:
                    self.logger.warning(
                        "Old database schema detected. Removing old database file."
                    )
                    conn.close()
                    os.remove(self.db_path)
                else:
                    conn.close()
            except Exception as e:
                self.logger.error(f"Error checking database schema: {e}")
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)

        # Create database directory if it doesn't exist
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create sensor_readings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    sensor_id TEXT,
                    temperature REAL,
                    vibration REAL,
                    voltage REAL,
                    status_code INTEGER,
                    anomaly_flag INTEGER,
                    anomaly_type TEXT,
                    firmware_version TEXT,
                    model TEXT,
                    manufacturer TEXT,
                    location TEXT,
                    synced INTEGER DEFAULT 0
                )
                """
            )

            # Create indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_readings(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sensor_id ON sensor_readings(sensor_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_synced ON sensor_readings(synced)"
            )

            conn.commit()
            conn.close()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise

    def store_reading(
        self,
        sensor_id: str,
        temperature: float,
        vibration: float,
        voltage: float,
        status_code: int,
        anomaly_flag: bool,
        anomaly_type: Optional[str],
        firmware_version: str,
        model: str,
        manufacturer: str,
        location: str,
    ):
        """Store a sensor reading in the database.

        Args:
            sensor_id: ID of the sensor
            temperature: Temperature reading
            vibration: Vibration reading
            voltage: Voltage reading
            status_code: Status code
            anomaly_flag: Whether this reading is an anomaly
            anomaly_type: Type of anomaly if any
            firmware_version: Firmware version of the sensor
            model: Model of the sensor
            manufacturer: Manufacturer of the sensor
            location: Location of the sensor
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO sensor_readings (
                    timestamp, sensor_id, temperature, vibration, voltage,
                    status_code, anomaly_flag, anomaly_type, firmware_version,
                    model, manufacturer, location, synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    sensor_id,
                    temperature,
                    vibration,
                    voltage,
                    status_code,
                    int(anomaly_flag),
                    anomaly_type,
                    firmware_version,
                    model,
                    manufacturer,
                    location,
                    0,  # synced = False
                ),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error storing reading: {e}")
            raise

    def get_unsynced_readings(self, limit: int = 1000) -> List[Dict]:
        """Get readings that haven't been synced yet.

        Args:
            limit: Maximum number of readings to return

        Returns:
            List of dictionaries containing the readings
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM sensor_readings
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            )

            columns = [description[0] for description in cursor.description]
            readings = []
            for row in cursor.fetchall():
                reading = dict(zip(columns, row))
                reading["anomaly_flag"] = bool(reading["anomaly_flag"])
                readings.append(reading)

            conn.close()
            return readings
        except Exception as e:
            self.logger.error(f"Error getting unsynced readings: {e}")
            return []

    def mark_readings_as_synced(self, reading_ids: List[int]):
        """Mark readings as synced.

        Args:
            reading_ids: List of reading IDs to mark as synced
        """
        if not reading_ids:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            placeholders = ",".join("?" * len(reading_ids))
            cursor.execute(
                f"""
                UPDATE sensor_readings
                SET synced = 1
                WHERE id IN ({placeholders})
                """,
                reading_ids,
            )

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error marking readings as synced: {e}")
            raise

    def get_reading_stats(self) -> Dict:
        """Get statistics about the readings in the database.

        Returns:
            Dictionary containing statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get total readings
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            total_readings = cursor.fetchone()[0]

            # Get unsynced readings
            cursor.execute("SELECT COUNT(*) FROM sensor_readings WHERE synced = 0")
            unsynced_readings = cursor.fetchone()[0]

            # Get anomaly statistics
            cursor.execute(
                """
                SELECT anomaly_type, COUNT(*)
                FROM sensor_readings
                WHERE anomaly_flag = 1
                GROUP BY anomaly_type
                """
            )
            anomaly_stats = dict(cursor.fetchall())

            # Get sensor statistics
            cursor.execute(
                """
                SELECT sensor_id, COUNT(*)
                FROM sensor_readings
                GROUP BY sensor_id
                """
            )
            sensor_stats = dict(cursor.fetchall())

            conn.close()

            return {
                "total_readings": total_readings,
                "unsynced_readings": unsynced_readings,
                "anomaly_stats": anomaly_stats,
                "sensor_stats": sensor_stats,
            }
        except Exception as e:
            self.logger.error(f"Error getting reading stats: {e}")
            return {
                "total_readings": 0,
                "unsynced_readings": 0,
                "anomaly_stats": {},
                "sensor_stats": {},
            }

    def connect(self):
        """Establish connection to the SQLite database."""
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Created database directory: {db_dir}")

            self.conn = sqlite3.connect(self.db_path)

            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")

            # Set busy timeout to avoid "database is locked" errors
            self.conn.execute(f"PRAGMA busy_timeout = 5000")

            # Performance optimizations
            self.conn.execute(
                "PRAGMA journal_mode = WAL"
            )  # Write-Ahead Logging for better concurrency
            self.conn.execute(
                "PRAGMA synchronous = NORMAL"
            )  # Reduce synchronous writes for better performance

            self.cursor = self.conn.cursor()
            logging.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise
        except Exception as e:
            logging.error(f"Error setting up database: {e}")
            raise

    @retry_on_error()
    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        try:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                temperature REAL,
                vibration REAL,
                voltage REAL,
                status_code INTEGER,
                anomaly_flag BOOLEAN,
                anomaly_type TEXT,
                firmware_version TEXT,
                model TEXT,
                manufacturer TEXT,
                location TEXT,
                synced BOOLEAN DEFAULT 0
            )
            """)

            # Create index on timestamp for faster queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON sensor_readings (timestamp)
            """)

            # Create index on sensor_id for faster queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_id 
            ON sensor_readings (sensor_id)
            """)

            # Create index on firmware_version for faster queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_firmware 
            ON sensor_readings (firmware_version)
            """)

            # Create index on synced column for faster sync queries
            self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_synced 
            ON sensor_readings (synced)
            """)

            self.conn.commit()
            logging.info("Database tables created successfully")
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")
            self.conn.rollback()
            raise

    @retry_on_error()
    def insert_reading(
        self,
        sensor_id,
        temperature,
        vibration,
        voltage,
        status_code,
        anomaly_flag=False,
        anomaly_type=None,
        firmware_version=None,
        model=None,
        manufacturer=None,
        location=None,
    ):
        """Insert a new sensor reading into the database.

        Args:
            sensor_id: Identifier for the sensor
            temperature: Temperature reading in Celsius
            vibration: Vibration reading in mm/s²
            voltage: Voltage reading in Volts
            status_code: Status code (0=normal, 1=anomaly)
            anomaly_flag: Boolean flag indicating if this is an anomaly
            anomaly_type: Type of anomaly (if anomaly_flag is true)
            firmware_version: Version of sensor firmware
            model: Sensor model
            manufacturer: Sensor manufacturer
            location: Sensor location

        Returns:
            ID of the inserted row or None if using batch mode

        Raises:
            sqlite3.Error: If the database operation fails after retries
        """
        timestamp = datetime.now().isoformat()

        # Add to batch buffer
        self.batch_buffer.append(
            (
                timestamp,
                sensor_id,
                temperature,
                vibration,
                voltage,
                status_code,
                anomaly_flag,
                anomaly_type,
                firmware_version,
                model,
                manufacturer,
                location,
                0,  # Not synced by default
            )
        )

        # Check if we should commit the batch
        current_time = time.time()
        batch_age = current_time - self.last_batch_time

        if len(self.batch_buffer) >= self.batch_size or batch_age >= self.batch_timeout:
            return self.commit_batch()

        return None

    @retry_on_error()
    def commit_batch(self):
        """Commit the current batch of readings to the database.

        Returns:
            Number of readings committed

        Raises:
            sqlite3.Error: If the database operation fails after retries
        """
        if not self.batch_buffer:
            return 0

        start_time = time.time()
        try:
            # Use executemany for better performance with batches
            self.cursor.executemany(
                """
                INSERT INTO sensor_readings 
                (timestamp, sensor_id, temperature, vibration, voltage, 
                status_code, anomaly_flag, anomaly_type, firmware_version,
                model, manufacturer, location, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self.batch_buffer,
            )

            self.conn.commit()
            batch_size = len(self.batch_buffer)
            self.batch_insert_count += 1
            self.insert_count += batch_size

            # Update performance metrics
            batch_time = time.time() - start_time
            self.total_batch_time += batch_time
            self.total_insert_time += batch_time

            # Log batch insert performance
            if self.batch_insert_count % 10 == 0:
                avg_time_per_reading = (
                    (self.total_batch_time / self.insert_count) * 1000
                    if self.insert_count > 0
                    else 0
                )
                logging.info(
                    f"Batch insert performance: {batch_size} readings in {batch_time:.3f}s ({avg_time_per_reading:.2f}ms/reading)"
                )

            # Reset batch buffer and timer
            self.batch_buffer = []
            self.last_batch_time = time.time()

            return batch_size
        except sqlite3.Error as e:
            logging.error(f"Error committing batch: {e}")
            self.conn.rollback()
            raise

    @retry_on_error()
    def get_readings(self, limit=100, sensor_id=None):
        """Retrieve sensor readings from the database.

        Args:
            limit: Maximum number of readings to retrieve
            sensor_id: Optional sensor ID to filter by

        Returns:
            List of readings

        Raises:
            sqlite3.Error: If the database operation fails after retries
        """
        try:
            # Commit any pending batch before querying
            if self.batch_buffer:
                self.commit_batch()

            query = "SELECT * FROM sensor_readings"
            params = []

            if sensor_id:
                query += " WHERE sensor_id = ?"
                params.append(sensor_id)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error retrieving readings: {e}")
            raise

    def close(self):
        """Close the database connection."""
        if self.batch_buffer:
            try:
                self.commit_batch()
            except Exception as e:
                logging.error(f"Error committing final batch during close: {e}")

        if self.conn:
            try:
                self.conn.close()
                logging.info("Database connection closed")
            except sqlite3.Error as e:
                logging.error(f"Error closing database connection: {e}")

    @retry_on_error()
    def sync_to_central_db(self, central_db_url, batch_size=100):
        """Sync recent readings to a central database.

        Args:
            central_db_url: URL of the central database API
            batch_size: Number of readings to sync in each batch

        Returns:
            Number of readings synced

        Raises:
            sqlite3.Error: If the database operation fails after retries
            requests.RequestException: If the HTTP request fails
        """
        try:
            # Commit any pending batch before syncing
            if self.batch_buffer:
                self.commit_batch()

            # Get recent unsynced readings
            self.cursor.execute(
                """
            SELECT * FROM sensor_readings 
            WHERE synced = 0
            ORDER BY timestamp ASC
            LIMIT ?
            """,
                (batch_size,),
            )

            readings = self.cursor.fetchall()

            if not readings:
                logging.info("No new readings to sync")
                return 0

            # Push to central database
            try:
                response = requests.post(
                    f"{central_db_url}/api/readings/batch",
                    json={"readings": readings},
                    headers={"Content-Type": "application/json"},
                    timeout=30,  # Add timeout to prevent hanging
                )

                if response.status_code == 200:
                    # Mark as synced
                    reading_ids = [
                        r[0] for r in readings
                    ]  # Assuming id is first column
                    placeholders = ",".join(["?"] * len(reading_ids))

                    self.cursor.execute(
                        f"""
                    UPDATE sensor_readings
                    SET synced = 1
                    WHERE id IN ({placeholders})
                    """,
                        reading_ids,
                    )

                    self.conn.commit()
                    logging.info(f"Synced {len(readings)} readings to central database")
                    return len(readings)
                else:
                    logging.error(
                        f"Failed to sync readings: {response.status_code} - {response.text}"
                    )
                    return 0
            except requests.RequestException as e:
                logging.error(f"HTTP request failed during sync: {e}")
                return 0

        except sqlite3.Error as e:
            logging.error(f"Database error during sync: {e}")
            self.conn.rollback()
            raise
        except Exception as e:
            logging.error(f"Error syncing to central database: {e}")
            return 0

    @retry_on_error()
    def get_sync_stats(self):
        """Get statistics about synced and unsynced readings.

        Returns:
            Dictionary with sync statistics

        Raises:
            sqlite3.Error: If the database operation fails after retries
        """
        try:
            # Commit any pending batch before querying
            if self.batch_buffer:
                self.commit_batch()

            self.cursor.execute(
                """
            SELECT 
                COUNT(*) as total_readings,
                SUM(CASE WHEN synced = 1 THEN 1 ELSE 0 END) as synced_readings,
                SUM(CASE WHEN synced = 0 THEN 1 ELSE 0 END) as unsynced_readings
            FROM sensor_readings
            """
            )

            result = self.cursor.fetchone()
            if result:
                total, synced, unsynced = result
                return {
                    "total_readings": total,
                    "synced_readings": synced or 0,  # Handle NULL values
                    "unsynced_readings": unsynced or 0,  # Handle NULL values
                    "sync_percentage": (synced / total * 100) if total > 0 else 0,
                }
            return {
                "total_readings": 0,
                "synced_readings": 0,
                "unsynced_readings": 0,
                "sync_percentage": 0,
            }

        except sqlite3.Error as e:
            logging.error(f"Error getting sync stats: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error getting sync stats: {e}")
            return {"error": str(e)}

    @retry_on_error()
    def get_performance_stats(self):
        """Get database performance statistics.

        Returns:
            Dictionary with performance statistics
        """
        try:
            avg_time_per_reading = (
                (self.total_insert_time / self.insert_count) * 1000
                if self.insert_count > 0
                else 0
            )
            avg_batch_size = (
                self.insert_count / self.batch_insert_count
                if self.batch_insert_count > 0
                else 0
            )

            # Get database size
            db_size = 0
            if self.db_path != ":memory:":
                try:
                    db_size = os.path.getsize(self.db_path)
                except OSError:
                    pass

            return {
                "total_readings": self.insert_count,
                "total_batches": self.batch_insert_count,
                "avg_batch_size": avg_batch_size,
                "avg_insert_time_ms": avg_time_per_reading,
                "total_insert_time_s": self.total_insert_time,
                "database_size_bytes": db_size,
                "database_size_mb": db_size / (1024 * 1024) if db_size > 0 else 0,
                "pending_batch_size": len(self.batch_buffer),
            }
        except Exception as e:
            logging.error(f"Error getting performance stats: {e}")
            return {"error": str(e)}

    def is_healthy(self):
        """Check if the database connection is healthy.

        Returns:
            Boolean indicating if the database is healthy
        """
        try:
            # Simple query to check if database is responsive
            self.cursor.execute("SELECT 1")
            result = self.cursor.fetchone()
            return result is not None and result[0] == 1
        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            return False
