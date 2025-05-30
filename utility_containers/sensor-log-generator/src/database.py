import logging
import os
import platform
import sqlite3
import subprocess
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Generator, List, Optional

import psutil
from pydantic import BaseModel, Field


# Define a Pydantic model for the sensor reading schema
class SensorReadingSchema(BaseModel):
    timestamp: str  # ISO 8601 format
    sensor_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    vibration: Optional[float] = None
    voltage: Optional[float] = None
    status_code: Optional[int] = None
    anomaly_flag: Optional[bool] = False
    anomaly_type: Optional[str] = None
    firmware_version: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    original_timezone: Optional[str] = (
        None  # UTC offset string like "+00:00" or "-04:00"
    )
    synced: Optional[bool] = False

    # Example for future: Add custom validation if needed
    # @validator('temperature')
    # def temperature_must_be_realistic(cls, v):
    #     if v is not None and (v < -100 or v > 200): # Example range
    #         raise ValueError('temperature must be realistic')
    #     return v


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
            # Check if we're in debug mode
            debug_mode = logging.getLogger("SensorDatabase").isEnabledFor(logging.DEBUG)

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    if debug_mode and attempt > 0:
                        logging.getLogger("SensorDatabase").debug(
                            f"Retry attempt {attempt + 1}/{max_retries + 1} for {func.__name__}"
                        )
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Log the error and retry
                        logging.warning(
                            f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {retry_delay} seconds..."
                        )
                        if debug_mode:
                            logging.getLogger("SensorDatabase").debug(
                                f"Error type: {type(e).__name__}, Error details: {str(e)}"
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


class DatabaseConnectionManager:
    """Centralized database connection manager for thread-safe operations."""

    def __init__(self, db_path: str, debug_mode: bool = False):
        """Initialize the connection manager.

        Args:
            db_path: Path to the SQLite database file
            debug_mode: Whether to enable debug logging
        """
        self.db_path = db_path
        self.debug_mode = debug_mode
        self.logger = logging.getLogger("DatabaseConnectionManager")
        self._local = threading.local()

        # Standard SQLite pragmas for container environments
        self.pragmas = [
            "PRAGMA journal_mode=WAL;",
            "PRAGMA busy_timeout=30000;",
            "PRAGMA synchronous=NORMAL;",
            "PRAGMA temp_store=MEMORY;",
            "PRAGMA mmap_size=268435456;",
            "PRAGMA cache_size=-64000;",
        ]

    def _get_thread_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection.

        Returns:
            SQLite connection for the current thread
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            if self.debug_mode:
                self.logger.debug(
                    f"Creating new connection for thread {threading.get_ident()}"
                )

            try:
                self._local.conn = sqlite3.connect(self.db_path, timeout=30.0)

                # Apply all pragmas
                for pragma in self.pragmas:
                    self._local.conn.execute(pragma)

                if self.debug_mode:
                    cursor = self._local.conn.cursor()
                    cursor.execute("PRAGMA journal_mode;")
                    mode = cursor.fetchone()[0]
                    self.logger.debug(f"Connection journal mode set to: {mode}")
                    cursor.close()

            except Exception as e:
                if self.debug_mode:
                    self.logger.debug(f"Error creating connection: {e}")
                    self.logger.debug(f"Database path: {self.db_path}")
                    self.logger.debug(f"Thread ID: {threading.get_ident()}")
                raise

        return self._local.conn

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections.

        Yields:
            SQLite connection object

        Note:
            This uses thread-local connections that persist across calls
            within the same thread for better performance.
        """
        conn = self._get_thread_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database cursors with automatic commit.

        Yields:
            SQLite cursor object

        Note:
            Automatically commits the transaction if no exception occurs.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_query(self, query: str, params: tuple = ()) -> List[Any]:
        """Execute a SELECT query and return results.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of query results
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Number of affected rows
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query multiple times with different parameters.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples

        Returns:
            Total number of affected rows
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount

    def close_thread_connection(self):
        """Close the connection for the current thread."""
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                if self.debug_mode:
                    self.logger.debug(
                        f"Closing connection for thread {threading.get_ident()}"
                    )

                self._local.conn.close()
                self._local.conn = None
            except Exception as e:
                self.logger.error(f"Error closing connection: {e}")


class SensorDatabase:
    def __init__(self, db_path: str, preserve_existing_db: bool = False):
        """Initialize the sensor database.

        Args:
            db_path: Path to the SQLite database file
            preserve_existing_db: If True, an existing database file will not be deleted.
                                  If False (default), an existing database file will be
                                  deleted and recreated.
        """
        self.db_path = db_path
        self.logger = logging.getLogger(
            "SensorDatabase"
        )  # Get logger early for potential deletion message

        # Enable debug mode detection
        self.debug_mode = self.logger.isEnabledFor(logging.DEBUG)

        if self.debug_mode:
            self._log_debug_environment_info()

        # Handle deletion of existing database if not preserving
        if self.db_path != ":memory:" and os.path.exists(self.db_path):
            if not preserve_existing_db:
                self.logger.info(
                    f"Existing database found at '{self.db_path}' and "
                    f"'preserve_existing_db' is False. Deleting old database file."
                )
                try:
                    os.remove(self.db_path)
                except OSError as e:
                    self.logger.error(
                        f"Failed to delete existing database '{self.db_path}': {e}"
                    )
                    raise  # Re-raise the error as this is critical
            else:
                self.logger.info(
                    f"Existing database found at '{self.db_path}' and "
                    f"'preserve_existing_db' is True. Preserving."
                )

        abs_db_path = os.path.abspath(
            self.db_path
        )  # Use a consistent variable for absolute path
        logging.info(f"Database path: {abs_db_path}")
        self.batch_buffer = []
        self.batch_size = 100
        self.batch_timeout = 5.0  # seconds
        self.last_batch_time = time.time()
        self.batch_insert_count = 0
        self.insert_count = 0
        self.total_insert_time = 0.0
        self.total_batch_time = 0.0

        # Create database directory if it doesn't exist
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(abs_db_path)
            if (
                not os.path.exists(db_dir) and db_dir
            ):  # Ensure db_dir is not empty string
                self.logger.info(f"Creating database directory: {db_dir}")
                os.makedirs(db_dir, exist_ok=True)
            elif not db_dir:
                self.logger.debug(
                    f"Database path '{self.db_path}' is in the current directory. No directory creation needed beyond what OS provides."
                )

        # Initialize the centralized connection manager
        self.conn_manager = DatabaseConnectionManager(self.db_path, self.debug_mode)

        # Initialize database schema
        self._init_db()

        if self.debug_mode:
            self._log_database_debug_info()

    def _init_db(self):
        """Initialize the database schema based on SensorReadingSchema."""
        try:
            with self.conn_manager.get_cursor() as cursor:
                # Dynamically create the table based on the Pydantic model
                # Base columns
                columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
                # Map Pydantic types to SQLite types
                type_mapping = {
                    "str": "TEXT",
                    "float": "REAL",
                    "int": "INTEGER",
                    "bool": "INTEGER",  # SQLite uses 0 and 1 for booleans
                    # datetime is stored as TEXT (ISO format)
                }

                for field_name, field in SensorReadingSchema.model_fields.items():
                    # Determine the Python type annotation
                    python_type = None
                    if hasattr(field.annotation, "__args__"):  # Handles Optional[type]
                        # Get the first type argument from Optional[type]
                        # Filter out NoneType for Optional fields
                        field_types = [
                            arg
                            for arg in field.annotation.__args__
                            if arg is not type(None)
                        ]
                        if field_types:
                            python_type = field_types[0]
                    else:
                        python_type = field.annotation

                    sqlite_type = "TEXT"  # Default to TEXT if type is complex or not directly mappable
                    if python_type is str:
                        sqlite_type = type_mapping["str"]
                    elif python_type is float:
                        sqlite_type = type_mapping["float"]
                    elif python_type is int:
                        sqlite_type = type_mapping["int"]
                    elif python_type is bool:
                        sqlite_type = type_mapping["bool"]
                    # Add other type mappings as needed, e.g. datetime.datetime -> TEXT

                    # Handle NOT NULL for non-optional fields by checking if None is a valid type
                    is_optional = (
                        type(None) in getattr(field.annotation, "__args__", [])
                        or field.default is not None
                        or field.default_factory is not None
                    )

                    # 'timestamp' and 'sensor_id' are critical, ensure they are NOT NULL
                    # All other fields from SensorReadingSchema are made optional at Pydantic level,
                    # so they will be nullable in DB unless explicitly made required here.
                    # For now, Pydantic model's optionality will translate to nullable columns.
                    # We will rely on Pydantic for 'timestamp' and 'sensor_id' presence before this stage.
                    # However, the original schema had them as NOT NULL, so let's keep that for the table.
                    if field_name in ["timestamp", "sensor_id"]:
                        columns.append(f"{field_name} {sqlite_type} NOT NULL")
                    else:
                        columns.append(f"{field_name} {sqlite_type}")

                create_table_sql = (
                    f"CREATE TABLE IF NOT EXISTS sensor_readings ({', '.join(columns)})"
                )
                if self.debug_mode:
                    self.logger.debug(
                        f"Executing SQL for table creation: {create_table_sql}"
                    )
                cursor.execute(create_table_sql)

                # Create only essential indexes
                # Check if 'timestamp' field exists in the model before creating index
                if "timestamp" in SensorReadingSchema.model_fields:
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_readings(timestamp)"
                    )
                else:
                    self.logger.warning(
                        "Field 'timestamp' not found in SensorReadingSchema, skipping index creation."
                    )

                if self.debug_mode:
                    # Log the pragma settings
                    pragmas = [
                        "journal_mode",
                        "busy_timeout",
                        "synchronous",
                        "temp_store",
                        "mmap_size",
                        "cache_size",
                    ]
                    for pragma in pragmas:
                        cursor.execute(f"PRAGMA {pragma};")
                        value = cursor.fetchone()[0]
                        self.logger.debug(f"PRAGMA {pragma} = {value}")

            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise

    def store_reading(
        self,
        reading_data: SensorReadingSchema,  # Accept Pydantic model instance
    ):
        """Store a sensor reading in the database after Pydantic validation.

        Args:
            reading_data: An instance of SensorReadingSchema containing the reading.
        """
        if self.debug_mode:
            self.logger.debug(
                f"Attempting to store reading for sensor {reading_data.sensor_id}"
            )
            self.logger.debug(f"Thread ID: {threading.get_ident()}")
            self.logger.debug(f"Process ID: {os.getpid()}")

        try:
            # Pydantic model validation has already occurred by the time this method is called
            # with a SensorReadingSchema instance.

            # Convert model to a dictionary suitable for database insertion
            # We need to ensure all fields defined in the schema are present for the SQL query,
            # using their default values from the Pydantic model if not explicitly set.
            data_for_db = reading_data.model_dump(
                exclude_none=False
            )  # include None for fields not set

            # Ensure boolean values are converted to integers for SQLite
            if "anomaly_flag" in data_for_db and isinstance(
                data_for_db["anomaly_flag"], bool
            ):
                data_for_db["anomaly_flag"] = int(data_for_db["anomaly_flag"])
            if "synced" in data_for_db and isinstance(data_for_db["synced"], bool):
                data_for_db["synced"] = int(data_for_db["synced"])

            # Dynamically generate column names and placeholders
            # The order of fields from model_fields is preserved in model_dump in Python 3.7+
            columns = list(SensorReadingSchema.model_fields.keys())
            placeholders = ", ".join(["?"] * len(columns))
            column_names = ", ".join(columns)

            query = f"""
                INSERT INTO sensor_readings ({column_names})
                VALUES ({placeholders})
            """

            # Get values in the correct order
            params = tuple(data_for_db[col] for col in columns)

            if self.debug_mode:
                self.logger.debug("Storing reading through connection manager")
                self.logger.debug(f"Query: {query}")
                self.logger.debug(f"Params: {params}")

            self.conn_manager.execute_write(query, params)

            if self.debug_mode:
                self.logger.debug(
                    f"Successfully stored reading for sensor {reading_data.sensor_id}"
                )

        except sqlite3.OperationalError as e:
            error_msg = str(e)
            self.logger.error(f"SQLite Operational Error storing reading: {error_msg}")

            if self.debug_mode:
                # Enhanced error diagnostics
                self.logger.debug("=== SQLite Error Diagnostics ===")
                self._log_error_diagnostics(error_msg)

            raise
        except Exception as e:
            self.logger.error(f"Error storing reading: {e}")

            if self.debug_mode:
                self.logger.debug(f"Exception type: {type(e).__name__}")
                self.logger.debug(f"Exception details: {str(e)}")

            raise

    def get_unsynced_readings(self, limit: int = 1000) -> List[Dict]:
        """Get readings that haven't been synced yet.

        Args:
            limit: Maximum number of readings to return

        Returns:
            List of dictionaries containing the readings
        """
        try:
            query = """
                SELECT * FROM sensor_readings
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            """

            rows = self.conn_manager.execute_query(query, (limit,))

            # Get column names
            with self.conn_manager.get_cursor() as cursor:
                cursor.execute("SELECT * FROM sensor_readings LIMIT 0")
                columns = [description[0] for description in cursor.description]

            readings = []
            for row in rows:
                reading = dict(zip(columns, row))
                reading["anomaly_flag"] = bool(reading["anomaly_flag"])
                readings.append(reading)

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
            placeholders = ",".join("?" * len(reading_ids))
            query = f"""
                UPDATE sensor_readings
                SET synced = 1
                WHERE id IN ({placeholders})
            """

            self.conn_manager.execute_write(query, reading_ids)

        except Exception as e:
            self.logger.error(f"Error marking readings as synced: {e}")
            raise

    def get_reading_stats(self) -> Dict:
        """Get statistics about the readings in the database.

        Returns:
            Dictionary containing statistics
        """
        try:
            # Get total readings
            total_readings = self.conn_manager.execute_query(
                "SELECT COUNT(*) FROM sensor_readings"
            )[0][0]

            # Get unsynced readings
            unsynced_readings = self.conn_manager.execute_query(
                "SELECT COUNT(*) FROM sensor_readings WHERE synced = 0"
            )[0][0]

            # Get anomaly statistics
            anomaly_rows = self.conn_manager.execute_query(
                """
                SELECT anomaly_type, COUNT(*)
                FROM sensor_readings
                WHERE anomaly_flag = 1
                GROUP BY anomaly_type
                """
            )
            anomaly_stats = dict(anomaly_rows)

            # Get sensor statistics
            sensor_rows = self.conn_manager.execute_query(
                """
                SELECT sensor_id, COUNT(*)
                FROM sensor_readings
                GROUP BY sensor_id
                """
            )
            sensor_stats = dict(sensor_rows)

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
        timezone_str="+00:00",  # Default to UTC offset string
    ):
        """Insert a new sensor reading into the database (batch mode).

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
            timezone_str: UTC offset string (e.g., '+00:00', '-04:00') for the original reading time. Defaults to "+00:00".

        Returns:
            ID of the inserted row or None if using batch mode

        Raises:
            sqlite3.Error: If the database operation fails after retries
        """
        firmware_version = firmware_version or "1.0.0"
        model = model or "Standard Sensor"
        manufacturer = manufacturer or "Acme Corp"
        location = location or "Unknown"

        # Use UTC for ISO format timestamps
        timestamp = datetime.now(timezone.utc).isoformat()

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
                timezone_str,  # Add original timezone
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
            query = """
                INSERT INTO sensor_readings 
                (timestamp, sensor_id, temperature, vibration, voltage, 
                status_code, anomaly_flag, anomaly_type, firmware_version,
                model, manufacturer, location, original_timezone, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            self.conn_manager.execute_many(query, self.batch_buffer)

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

            return self.conn_manager.execute_query(query, tuple(params))
        except sqlite3.Error as e:
            logging.error(f"Error retrieving readings: {e}")
            raise

    def close(self):
        """Close the database connection for the current thread."""
        try:
            # Commit any pending batch
            if self.batch_buffer:
                self.commit_batch()

            # Close the connection manager's thread connection
            self.conn_manager.close_thread_connection()
        except Exception as e:
            self.logger.error(f"Error closing database connection: {e}")

    @retry_on_error()
    def get_database_stats(self) -> Dict:
        """Get comprehensive database statistics.

        Returns:
            Dictionary containing database statistics including:
            - Total readings count
            - Database size
            - Last write timestamp
            - Index sizes
            - Table statistics
            - Performance metrics
            - File paths and sizes
        """
        try:
            stats = {
                "total_readings": 0,
                "database_size_bytes": 0,
                "last_write_timestamp": None,
                "index_sizes": {},
                "table_stats": {},
                "performance_metrics": {},
                "sync_stats": {},
                "anomaly_stats": {},
                "files": {
                    "database": {
                        "path": self.db_path,
                        "size_bytes": 0,
                        "exists": False,
                    },
                    "log": {
                        "path": self.db_path.replace(".db", ".log"),
                        "size_bytes": 0,
                        "exists": False,
                    },
                },
            }

            # Get file information
            if self.db_path != ":memory:":
                try:
                    # Database file
                    if os.path.exists(self.db_path):
                        stats["files"]["database"]["size_bytes"] = os.path.getsize(
                            self.db_path
                        )
                        stats["files"]["database"]["exists"] = True
                        stats["database_size_bytes"] = stats["files"]["database"][
                            "size_bytes"
                        ]

                    # Log file
                    log_path = self.db_path.replace(".db", ".log")
                    if os.path.exists(log_path):
                        stats["files"]["log"]["size_bytes"] = os.path.getsize(log_path)
                        stats["files"]["log"]["exists"] = True
                except OSError as e:
                    self.logger.error(f"Error getting file sizes: {e}")

            # Get total readings count
            stats["total_readings"] = self.conn_manager.execute_query(
                "SELECT COUNT(*) FROM sensor_readings"
            )[0][0]

            # Get last write timestamp
            last_write_result = self.conn_manager.execute_query(
                "SELECT MAX(timestamp) FROM sensor_readings"
            )
            if last_write_result and last_write_result[0][0]:
                last_write = last_write_result[0][0]
                # Assume timestamp is stored as ISO string
                try:
                    stats["last_write_timestamp"] = last_write
                except Exception:
                    logging.warning(
                        f"Could not parse last_write timestamp: {last_write}"
                    )
                    stats["last_write_timestamp"] = str(last_write)

            # Get table statistics
            table_stats_result = self.conn_manager.execute_query("""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT sensor_id) as unique_sensors,
                    COUNT(DISTINCT location) as unique_locations,
                    COUNT(DISTINCT manufacturer) as unique_manufacturers,
                    COUNT(DISTINCT model) as unique_models
                FROM sensor_readings
            """)

            if table_stats_result:
                row = table_stats_result[0]
                stats["table_stats"] = {
                    "total_rows": row[0],
                    "unique_sensors": row[1],
                    "unique_locations": row[2],
                    "unique_manufacturers": row[3],
                    "unique_models": row[4],
                }

            # Get performance metrics
            stats["performance_metrics"] = {
                "total_inserts": self.insert_count,
                "total_batches": self.batch_insert_count,
                "avg_batch_size": self.insert_count / self.batch_insert_count
                if self.batch_insert_count > 0
                else 0,
                "avg_insert_time_ms": (
                    self.total_insert_time / self.insert_count * 1000
                )
                if self.insert_count > 0
                else 0,
                "total_insert_time_s": self.total_insert_time,
                "pending_batch_size": len(self.batch_buffer),
            }

            # Get sync statistics
            sync_stats_result = self.conn_manager.execute_query("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN synced = 1 THEN 1 ELSE 0 END) as synced,
                    SUM(CASE WHEN synced = 0 THEN 1 ELSE 0 END) as unsynced
                FROM sensor_readings
            """)

            if sync_stats_result:
                row = sync_stats_result[0]
                stats["sync_stats"] = {
                    "total": row[0],
                    "synced": row[1] or 0,
                    "unsynced": row[2] or 0,
                    "sync_percentage": (row[1] / row[0] * 100) if row[0] > 0 else 0,
                }

            # Get anomaly statistics
            anomaly_stats_result = self.conn_manager.execute_query("""
                SELECT 
                    anomaly_type,
                    COUNT(*) as count
                FROM sensor_readings
                WHERE anomaly_flag = 1
                GROUP BY anomaly_type
            """)

            if anomaly_stats_result:
                total_anomalies = sum(row[1] for row in anomaly_stats_result)
                stats["anomaly_stats"] = {
                    "total_anomalies": total_anomalies,
                    "unique_anomaly_types": len(anomaly_stats_result),
                    "anomaly_types": {row[0]: row[1] for row in anomaly_stats_result},
                }

            return stats

        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {
                "error": str(e),
                "total_readings": 0,
                "database_size_bytes": 0,
                "last_write_timestamp": None,
                "index_sizes": {},
                "table_stats": {},
                "performance_metrics": {},
                "sync_stats": {},
                "anomaly_stats": {},
                "files": {
                    "database": {
                        "path": self.db_path,
                        "size_bytes": 0,
                        "exists": False,
                    },
                    "log": {
                        "path": self.db_path.replace(".db", ".log"),
                        "size_bytes": 0,
                        "exists": False,
                    },
                },
            }

    def is_healthy(self):
        """Check if the database connection is healthy.

        Returns:
            Boolean indicating if the database is healthy
        """
        try:
            # Simple query to check if database is responsive
            result = self.conn_manager.execute_query("SELECT 1")
            return result is not None and result[0][0] == 1
        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            return False

    # Keep existing utility methods unchanged
    def _log_debug_environment_info(self):
        """Log comprehensive environment information when in debug mode."""
        self.logger.debug("=== Database Debug Information ===")

        # System information
        self.logger.debug(f"Platform: {platform.platform()}")
        self.logger.debug(f"Python version: {platform.python_version()}")
        self.logger.debug(f"SQLite version: {sqlite3.sqlite_version}")
        self.logger.debug(f"SQLite library version: {sqlite3.sqlite_version}")

        # Process information
        self.logger.debug(f"Process ID: {os.getpid()}")
        self.logger.debug(f"Thread ID: {threading.get_ident()}")

        # Container detection
        is_container = self._detect_container_environment()
        self.logger.debug(f"Running in container: {is_container}")

        # SQLite temp directory
        sqlite_tmpdir = os.environ.get(
            "SQLITE_TMPDIR", "Not set (using system default)"
        )
        self.logger.debug(f"SQLITE_TMPDIR: {sqlite_tmpdir}")

        # If in container, suggest setting SQLITE_TMPDIR if not set
        if is_container and not os.environ.get("SQLITE_TMPDIR"):
            self.logger.debug(
                "WARNING: Running in container without SQLITE_TMPDIR set. "
                "Consider setting SQLITE_TMPDIR to a writable directory."
            )

        # Database path information
        abs_db_path = os.path.abspath(self.db_path)
        self.logger.debug(f"Database absolute path: {abs_db_path}")

        # Directory information
        db_dir = os.path.dirname(abs_db_path) or "."
        if os.path.exists(db_dir):
            self.logger.debug(f"Database directory: {db_dir}")

            # Check directory permissions
            try:
                dir_stat = os.stat(db_dir)
                dir_perms = oct(dir_stat.st_mode)[-3:]
                self.logger.debug(f"Directory permissions: {dir_perms}")
                self.logger.debug(f"Directory owner UID: {dir_stat.st_uid}")
                self.logger.debug(f"Directory owner GID: {dir_stat.st_gid}")
            except Exception as e:
                self.logger.debug(f"Error getting directory stats: {e}")

            # Check if directory is writable
            is_writable = os.access(db_dir, os.W_OK)
            self.logger.debug(f"Directory writable: {is_writable}")

            # Disk space information
            try:
                disk_usage = psutil.disk_usage(db_dir)
                self.logger.debug(f"Disk total: {disk_usage.total / (1024**3):.2f} GB")
                self.logger.debug(f"Disk used: {disk_usage.used / (1024**3):.2f} GB")
                self.logger.debug(f"Disk free: {disk_usage.free / (1024**3):.2f} GB")
                self.logger.debug(f"Disk percent used: {disk_usage.percent}%")
            except Exception as e:
                self.logger.debug(f"Error getting disk usage: {e}")

            # Inode information (Linux/Unix only)
            if platform.system() in ["Linux", "Darwin"]:
                try:
                    result = subprocess.run(
                        ["df", "-i", db_dir], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        self.logger.debug(f"Inode info:\n{result.stdout}")
                except Exception as e:
                    self.logger.debug(f"Error getting inode info: {e}")

    def _detect_container_environment(self) -> bool:
        """Detect if running in a container environment."""
        # Check for Docker
        if os.path.exists("/.dockerenv"):
            self.logger.debug("Detected Docker environment (/.dockerenv exists)")
            return True

        # Check cgroup for docker/kubernetes
        try:
            with open("/proc/self/cgroup", "r") as f:
                cgroup_content = f.read()
                if "docker" in cgroup_content or "kubepods" in cgroup_content:
                    self.logger.debug("Detected container via /proc/self/cgroup")
                    return True
        except Exception as e:
            self.logger.debug(f"Error detecting container environment: {e}")
            pass

        # Check for common container environment variables
        container_vars = ["KUBERNETES_SERVICE_HOST", "DOCKER_CONTAINER", "container"]
        for var in container_vars:
            if os.environ.get(var):
                self.logger.debug(f"Detected container via environment variable: {var}")
                return True

        return False

    def _log_database_debug_info(self):
        """Log database-specific debug information."""
        if not self.debug_mode:
            return

        try:
            # Check if database file exists
            if os.path.exists(self.db_path):
                file_stat = os.stat(self.db_path)
                self.logger.debug(f"Database file size: {file_stat.st_size} bytes")
                file_perms = oct(file_stat.st_mode)[-3:]
                self.logger.debug(f"Database file permissions: {file_perms}")

                # Check for WAL files
                wal_path = f"{self.db_path}-wal"
                shm_path = f"{self.db_path}-shm"

                if os.path.exists(wal_path):
                    wal_size = os.path.getsize(wal_path)
                    self.logger.debug(f"WAL file exists, size: {wal_size} bytes")
                else:
                    self.logger.debug("WAL file does not exist")

                if os.path.exists(shm_path):
                    shm_size = os.path.getsize(shm_path)
                    self.logger.debug(f"SHM file exists, size: {shm_size} bytes")
                else:
                    self.logger.debug("SHM file does not exist")

        except Exception as e:
            self.logger.debug(f"Error logging database debug info: {e}")

    def _log_error_diagnostics(self, error_msg: str):
        """Log detailed error diagnostics."""
        if "disk I/O error" in error_msg:
            self.logger.debug("Disk I/O error detected - running diagnostics")

            # Re-check disk space
            try:
                db_dir = os.path.dirname(self.db_path) or "."
                disk_usage = psutil.disk_usage(db_dir)
                self.logger.debug(
                    f"Current disk free: {disk_usage.free / (1024**3):.2f} GB ({100 - disk_usage.percent:.1f}%)"
                )

                # Check if we can write a test file
                test_file = os.path.join(db_dir, f".test_write_{os.getpid()}")
                try:
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    self.logger.debug("Test file write successful")
                except Exception as e:
                    self.logger.debug(f"Test file write failed: {e}")

            except Exception as e:
                self.logger.debug(f"Error in disk diagnostics: {e}")

            # Check SQLite temporary directory
            try:
                temp_dir = os.environ.get("SQLITE_TMPDIR", "/tmp")
                self.logger.debug(f"SQLite temp directory: {temp_dir}")
                if os.path.exists(temp_dir):
                    temp_usage = psutil.disk_usage(temp_dir)
                    self.logger.debug(
                        f"Temp dir ({temp_dir}) free: {temp_usage.free / (1024**3):.2f} GB"
                    )

                    # Check if temp dir is writable
                    temp_writable = os.access(temp_dir, os.W_OK)
                    self.logger.debug(f"Temp dir writable: {temp_writable}")

                    # Try to create a test file in temp dir
                    if temp_writable:
                        test_temp_file = os.path.join(
                            temp_dir, f".sqlite_test_{os.getpid()}"
                        )
                        try:
                            with open(test_temp_file, "w") as f:
                                f.write("test")
                            os.remove(test_temp_file)
                            self.logger.debug("SQLite temp dir write test successful")
                        except Exception as e:
                            self.logger.debug(f"SQLite temp dir write test failed: {e}")
                else:
                    self.logger.debug(f"Temp dir {temp_dir} does not exist")
            except Exception as e:
                self.logger.debug(f"Error checking temp dir: {e}")

            # Check for file system errors
            if platform.system() == "Linux":
                try:
                    # Check dmesg for recent I/O errors
                    result = subprocess.run(
                        ["dmesg", "-T", "--level=err,warn", "-t"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        lines = result.stdout.strip().split("\n")[-10:]  # Last 10 lines
                        if lines and lines[0]:
                            self.logger.debug("Recent kernel messages:")
                            for line in lines:
                                if "I/O" in line or "error" in line.lower():
                                    self.logger.debug(f"  {line}")
                except Exception as e:
                    self.logger.debug(f"Could not check dmesg: {e}")

    def __del__(self):
        """Clean up database connections when the object is destroyed."""
        try:
            self.close()
        except Exception:
            # Suppress exceptions in destructor
            pass
