import logging
import os
import platform
import signal
import sqlite3
import subprocess
import threading
import time
import atexit
import shutil
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
    
    # New fields from enhanced identity
    serial_number: Optional[str] = None
    manufacture_date: Optional[str] = None
    deployment_type: Optional[str] = None
    installation_date: Optional[str] = None
    height_meters: Optional[float] = None
    orientation_degrees: Optional[float] = None
    instance_id: Optional[str] = None
    sensor_type: Optional[str] = None

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
                    # Check circuit breaker if this is a SensorDatabase method
                    if hasattr(args[0], '_check_circuit_breaker'):
                        if not args[0]._check_circuit_breaker():
                            raise sqlite3.OperationalError("Circuit breaker is open, database operations suspended")
                    
                    if debug_mode and attempt > 0:
                        logging.getLogger("SensorDatabase").debug(
                            f"Retry attempt {attempt + 1}/{max_retries + 1} for {func.__name__}"
                        )
                    
                    result = func(*args, **kwargs)
                    
                    # Record success for circuit breaker
                    if hasattr(args[0], '_record_circuit_success'):
                        args[0]._record_circuit_success()
                    
                    return result
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                    last_exception = e
                    
                    # Record failure for circuit breaker
                    if hasattr(args[0], '_record_circuit_failure'):
                        args[0]._record_circuit_failure()
                    
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

            # Ensure we raise the last exception if we exit the loop
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
        self._shutdown_handlers_registered = False
        self._checkpoint_lock = threading.Lock()
        self._last_checkpoint_time = time.time()
        self._checkpoint_interval = 5  # Checkpoint/commit every 5 seconds for external visibility

        # Standard SQLite pragmas for container environments
        # Using DELETE mode for cross-boundary compatibility (container/host access)
        # But with optimized settings to prevent disk I/O errors
        self.pragmas = [
            "PRAGMA journal_mode=DELETE;",  # DELETE mode for cross-boundary safety
            "PRAGMA busy_timeout=30000;",
            "PRAGMA synchronous=NORMAL;",  # NORMAL instead of FULL to reduce I/O pressure
            "PRAGMA temp_store=MEMORY;",
            "PRAGMA mmap_size=268435456;",
            "PRAGMA cache_size=-64000;",
            "PRAGMA page_size=4096;",  # Optimize page size
            "PRAGMA locking_mode=NORMAL;",  # Ensure proper locking
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

    def checkpoint(self, mode="PASSIVE"):
        """
        In DELETE mode, ensure data is committed to disk.
        
        Args:
            mode: Kept for compatibility but not used in DELETE mode
            
        Returns:
            None (checkpoints not applicable in DELETE mode)
        """
        with self._checkpoint_lock:
            try:
                conn = self._get_thread_connection()
                
                # In DELETE mode, just ensure everything is committed
                conn.commit()
                
                if self.debug_mode:
                    self.logger.debug("Data committed in DELETE journal mode")
                
                self._last_checkpoint_time = time.time()
                return None
                
            except sqlite3.Error as e:
                self.logger.error(f"Error during commit: {e}")
                return None

    def periodic_checkpoint(self):
        """Perform periodic commit to ensure data is on disk."""
        current_time = time.time()
        if current_time - self._last_checkpoint_time > self._checkpoint_interval:
            self.checkpoint("PASSIVE")

    def close_thread_connection(self):
        """Close the connection for the current thread with final checkpoint."""
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                if self.debug_mode:
                    self.logger.debug(
                        f"Closing connection for thread {threading.get_ident()}"
                    )

                # Force a final commit before closing (DELETE mode doesn't use checkpoints)
                try:
                    self.logger.info("Executing final commit before connection close...")
                    self._local.conn.commit()
                except Exception as e:
                    self.logger.warning(f"Final commit failed: {e}")

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
        # Inherit parent logger's level
        self.logger.setLevel(logging.getLogger().level)

        # Enable debug mode detection
        self.debug_mode = os.environ.get('DEBUG_MODE') == 'true' or self.logger.isEnabledFor(logging.DEBUG)
        if self.debug_mode:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug(f"🔍 Database initialized in DEBUG mode at {self.db_path}")
        
        # Register signal handlers for graceful shutdown
        self._register_shutdown_handlers()
        
        # Start background commit thread for external visibility
        self._start_background_commit_thread()

        if self.debug_mode:
            self._log_debug_environment_info()

        # Handle deletion of existing database if not preserving
        if self.db_path != ":memory:" and os.path.exists(self.db_path):
            if not preserve_existing_db:
                # Don't check integrity if we're deleting anyway - just delete it
                self.logger.info(
                    f"Existing database found at '{self.db_path}' and "
                    f"'preserve_existing_db' is False. Deleting old database file."
                )
                
                try:
                    # Also remove journal files if they exist
                    self._cleanup_database_files(self.db_path)
                except OSError as e:
                    self.logger.error(
                        f"Failed to delete existing database '{self.db_path}': {e}"
                    )
                    # Try to continue anyway - maybe the file is locked but we can still create a new connection
                    self.logger.warning("Will attempt to continue despite deletion failure")
            else:
                # Check integrity even when preserving
                if not self._check_database_integrity(self.db_path):
                    self.logger.error(
                        f"Existing database at '{self.db_path}' is corrupted!"
                    )
                    self.logger.info("Attempting automatic recovery...")
                    
                    # Try to recover the database
                    if not self._attempt_database_recovery(self.db_path):
                        self.logger.error("Recovery failed. Creating backup and starting fresh.")
                        backup_path = f"{self.db_path}.corrupted.{int(time.time())}"
                        try:
                            shutil.move(self.db_path, backup_path)
                            self.logger.info(f"Corrupted database backed up to: {backup_path}")
                            self._cleanup_database_files(self.db_path, skip_main=True)
                        except Exception as e:
                            self.logger.error(f"Failed to backup corrupted database: {e}")
                            self._cleanup_database_files(self.db_path)
                else:
                    self.logger.info(
                        f"Existing database at '{self.db_path}' passed integrity check."
                    )

        abs_db_path = os.path.abspath(
            self.db_path
        )  # Use a consistent variable for absolute path
        logging.info(f"Database path: {abs_db_path}")
        self.batch_buffer = []
        self.batch_size = 20  # Batch after 20 writes for timely visibility
        self.batch_timeout = 5.0  # Commit every 5 seconds for external readers
        self.last_batch_time = time.time()
        self.batch_insert_count = 0
        self.insert_count = 0
        self.total_insert_time = 0.0
        self.total_batch_time = 0.0
        
        # In-memory failure buffer for resilient writes during disk I/O errors
        self.failure_buffer = []
        self.failure_buffer_max_size = 10000  # Keep up to 10k failed readings in memory
        # Custom retry intervals: 1s, 3s, 5s, 9s, 12s, 15s, then stay at 15s
        self.failure_buffer_retry_intervals = [1.0, 3.0, 5.0, 9.0, 12.0, 15.0]
        self.failure_buffer_max_retry_interval = 15.0  # Max 15 seconds between retries
        self.last_failure_retry_time = time.time()
        self.failure_retry_count = 0
        self.failure_buffer_lock = threading.Lock()
        
        # Circuit breaker pattern for database reliability
        self.circuit_breaker_enabled = True
        self.circuit_breaker_failure_threshold = 5  # Open circuit after 5 consecutive failures
        self.circuit_breaker_success_threshold = 2  # Close circuit after 2 consecutive successes
        self.circuit_breaker_timeout = 30.0  # Try to recover after 30 seconds
        self.circuit_breaker_state = "closed"  # closed, open, half_open
        self.circuit_breaker_failures = 0
        self.circuit_breaker_successes = 0
        self.circuit_breaker_last_failure_time = 0
        self.circuit_breaker_lock = threading.Lock()
        
        # Resource limits
        self.max_batch_size = 1000  # Maximum batch size to prevent memory issues
        self.max_database_size_mb = 1000  # Maximum database size in MB (configurable)
        self.max_memory_usage_mb = 100  # Maximum memory usage for buffers
        self.resource_check_interval = 60  # Check resources every 60 seconds
        self.last_resource_check = 0

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
    
    def _check_resources(self):
        """Check resource usage and enforce limits."""
        current_time = time.time()
        if current_time - self.last_resource_check < self.resource_check_interval:
            return True  # Skip check if too recent
        
        self.last_resource_check = current_time
        
        try:
            # Check database size
            if self.db_path != ":memory:" and os.path.exists(self.db_path):
                db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
                if db_size_mb > self.max_database_size_mb:
                    self.logger.error(f"Database size ({db_size_mb:.2f}MB) exceeds limit ({self.max_database_size_mb}MB)")
                    return False
                elif db_size_mb > self.max_database_size_mb * 0.9:
                    self.logger.warning(f"Database size ({db_size_mb:.2f}MB) approaching limit ({self.max_database_size_mb}MB)")
            
            # Check memory usage (approximate)
            import sys
            batch_memory_mb = sys.getsizeof(self.batch_buffer) / (1024 * 1024)
            if batch_memory_mb > self.max_memory_usage_mb:
                self.logger.error(f"Batch buffer memory ({batch_memory_mb:.2f}MB) exceeds limit ({self.max_memory_usage_mb}MB)")
                return False
                
            # Enforce max batch size
            if len(self.batch_buffer) > self.max_batch_size:
                self.logger.warning(f"Batch buffer size ({len(self.batch_buffer)}) exceeds max ({self.max_batch_size}), forcing commit")
                self.commit_batch()
                
        except Exception as e:
            self.logger.warning(f"Resource check failed: {e}")
            # Don't block operations if resource check fails
            
        return True
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker allows operation."""
        if not self.circuit_breaker_enabled:
            return True
            
        with self.circuit_breaker_lock:
            if self.circuit_breaker_state == "closed":
                return True
            elif self.circuit_breaker_state == "open":
                # Check if enough time has passed to try recovery
                if time.time() - self.circuit_breaker_last_failure_time > self.circuit_breaker_timeout:
                    self.circuit_breaker_state = "half_open"
                    self.logger.info("Circuit breaker entering half-open state, attempting recovery")
                    return True
                else:
                    return False
            elif self.circuit_breaker_state == "half_open":
                return True
        return False
    
    def _record_circuit_success(self):
        """Record a successful operation for circuit breaker."""
        if not self.circuit_breaker_enabled:
            return
            
        with self.circuit_breaker_lock:
            self.circuit_breaker_failures = 0
            if self.circuit_breaker_state == "half_open":
                self.circuit_breaker_successes += 1
                if self.circuit_breaker_successes >= self.circuit_breaker_success_threshold:
                    self.circuit_breaker_state = "closed"
                    self.circuit_breaker_successes = 0
                    self.logger.info("Circuit breaker closed, service recovered")
    
    def _record_circuit_failure(self):
        """Record a failed operation for circuit breaker."""
        if not self.circuit_breaker_enabled:
            return
            
        with self.circuit_breaker_lock:
            self.circuit_breaker_failures += 1
            self.circuit_breaker_successes = 0
            self.circuit_breaker_last_failure_time = time.time()
            
            if self.circuit_breaker_state == "half_open":
                self.circuit_breaker_state = "open"
                self.logger.warning("Circuit breaker opened again, recovery failed")
            elif self.circuit_breaker_failures >= self.circuit_breaker_failure_threshold:
                if self.circuit_breaker_state != "open":
                    self.circuit_breaker_state = "open"
                    self.logger.error(f"Circuit breaker opened after {self.circuit_breaker_failures} failures")
    
    def _register_shutdown_handlers(self):
        """Register handlers for graceful shutdown with data commit."""
        
        def shutdown_handler():
            """Handler to ensure final commit on shutdown."""
            try:
                self.logger.info("Shutdown detected, executing final data commit...")
                self.stop_background_commit_thread()
                self.conn_manager.checkpoint("TRUNCATE")  # This will do a commit in DELETE mode
                self.close()
            except Exception as e:
                self.logger.error(f"Error during shutdown commit: {e}")
        
        # Register with atexit
        atexit.register(shutdown_handler)
        
        # Also handle SIGTERM for docker stop
        # Signal handler removed - main.py handles signals
        # The database will be properly closed when simulator.stop() is called
        pass
    
    def _check_database_integrity(self, db_path: str) -> bool:
        """Check if an existing database file is valid and not corrupted.
        
        Args:
            db_path: Path to the database file to check
            
        Returns:
            True if database is valid, False if corrupted or inaccessible
        """
        if not os.path.exists(db_path):
            return True  # No file means no corruption
        
        try:
            # Try to connect and run integrity check
            test_conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = test_conn.cursor()
            
            # Quick integrity check
            cursor.execute("PRAGMA quick_check")
            result = cursor.fetchone()
            
            if result and result[0] != "ok":
                self.logger.debug(f"Integrity check failed: {result[0]}")
                cursor.close()
                test_conn.close()
                return False
            
            # Try to read the schema to ensure basic functionality
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            # If we have tables, try to query one
            if tables:
                try:
                    cursor.execute("SELECT COUNT(*) FROM sensor_readings")
                    count = cursor.fetchone()[0]
                    self.logger.debug(f"Database contains {count} readings")
                except sqlite3.Error as e:
                    self.logger.debug(f"Failed to query sensor_readings: {e}")
                    cursor.close()
                    test_conn.close()
                    return False
            
            cursor.close()
            test_conn.close()
            return True
            
        except sqlite3.DatabaseError as e:
            error_msg = str(e).lower()
            if "malformed" in error_msg or "corrupt" in error_msg:
                self.logger.debug(f"Database corruption detected: {e}")
                return False
            elif "locked" in error_msg:
                # Database is locked but not corrupted
                self.logger.debug("Database is locked by another process")
                return True
            else:
                self.logger.debug(f"Database error during integrity check: {e}")
                return False
        except Exception as e:
            self.logger.debug(f"Unexpected error during integrity check: {e}")
            return False
    
    def _attempt_database_recovery(self, db_path: str) -> bool:
        """Attempt to recover a corrupted database.
        
        Args:
            db_path: Path to the corrupted database
            
        Returns:
            True if recovery successful, False otherwise
        """
        self.logger.info("Attempting database recovery...")
        
        try:
            # First, try to dump what we can from the corrupted database
            recovery_conn = sqlite3.connect(db_path, timeout=5.0)
            recovery_conn.isolation_level = None  # Autocommit mode
            cursor = recovery_conn.cursor()
            
            # Try to recover data
            recovered_data = []
            try:
                cursor.execute("SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10000")
                recovered_data = cursor.fetchall()
                self.logger.info(f"Recovered {len(recovered_data)} readings from corrupted database")
            except Exception as e:
                self.logger.warning(f"Could not recover data: {e}")
            
            cursor.close()
            recovery_conn.close()
            
            # Create a new temporary database
            temp_db = f"{db_path}.recovery"
            if os.path.exists(temp_db):
                os.remove(temp_db)
            
            # Initialize new database with recovered data
            if recovered_data:
                new_conn = sqlite3.connect(temp_db)
                new_cursor = new_conn.cursor()
                
                # Create schema (will be done by _init_db later, but we need it now)
                # This is a simplified version - the real schema will be created properly
                new_cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        sensor_id TEXT NOT NULL,
                        temperature REAL,
                        humidity REAL,
                        pressure REAL,
                        vibration REAL,
                        voltage REAL,
                        status_code INTEGER,
                        anomaly_flag INTEGER,
                        anomaly_type TEXT,
                        firmware_version TEXT,
                        model TEXT,
                        manufacturer TEXT,
                        location TEXT,
                        latitude REAL,
                        longitude REAL,
                        original_timezone TEXT,
                        synced INTEGER
                    )
                """)
                
                # Insert recovered data (adjust based on actual schema)
                # This is a best-effort recovery
                self.logger.info("Reinserting recovered data...")
                for row in recovered_data:
                    try:
                        # Assuming row has the right number of columns
                        placeholders = ','.join(['?' for _ in row[1:]])  # Skip ID
                        new_cursor.execute(
                            f"INSERT INTO sensor_readings VALUES (NULL, {placeholders})",
                            row[1:]
                        )
                    except Exception as e:
                        self.logger.debug(f"Could not reinsert row: {e}")
                
                new_conn.commit()
                new_cursor.close()
                new_conn.close()
                
                # Replace corrupted database with recovered one
                shutil.move(temp_db, db_path)
                self.logger.info("Database recovery successful")
                return True
            else:
                self.logger.warning("No data could be recovered")
                return False
                
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            return False
    
    def _cleanup_database_files(self, db_path: str, skip_main: bool = False):
        """Clean up database and related files (journal, wal, shm).
        
        Args:
            db_path: Path to the database file
            skip_main: If True, skip deleting the main database file
        """
        files_to_remove = []
        
        if not skip_main and os.path.exists(db_path):
            files_to_remove.append(db_path)
        
        # Journal file (for DELETE mode)
        journal_file = f"{db_path}-journal"
        if os.path.exists(journal_file):
            files_to_remove.append(journal_file)
        
        # WAL mode files (even though we use DELETE mode, they might exist from previous runs)
        wal_file = f"{db_path}-wal"
        if os.path.exists(wal_file):
            files_to_remove.append(wal_file)
        
        shm_file = f"{db_path}-shm"
        if os.path.exists(shm_file):
            files_to_remove.append(shm_file)
        
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                self.logger.debug(f"Removed: {file_path}")
            except OSError as e:
                self.logger.warning(f"Could not remove {file_path}: {e}")
    
    def _start_background_commit_thread(self):
        """Start a background thread that commits data periodically for external readers."""
        self._commit_thread_running = True
        self._commit_lock = threading.Lock()
        
        def periodic_commit():
            """Background thread to ensure data visibility for external readers."""
            while self._commit_thread_running:
                time.sleep(5.0)  # Check every 5 seconds
                try:
                    with self._commit_lock:
                        # Check if there's uncommitted data
                        current_time = time.time()
                        batch_age = current_time - self.last_batch_time
                        
                        if self.batch_buffer and batch_age >= self.batch_timeout:
                            self.logger.debug(f"Background thread committing {len(self.batch_buffer)} readings")
                            self.commit_batch()
                    
                    # Try to flush failure buffer periodically
                    self._retry_failed_writes()
                    
                except Exception as e:
                    self.logger.error(f"Error in background commit thread: {e}")
        
        self._commit_thread = threading.Thread(target=periodic_commit, daemon=True)
        self._commit_thread.start()
        self.logger.debug("Background commit thread started")
    
    def stop_background_commit_thread(self):
        """Stop the background commit thread."""
        if hasattr(self, '_commit_thread_running'):
            self._commit_thread_running = False
            if hasattr(self, '_commit_thread'):
                self._commit_thread.join(timeout=1.0)

    def _init_db(self):
        """Initialize the database schema based on SensorReadingSchema."""
        # One more integrity check after connection manager is created
        if self.db_path != ":memory:" and os.path.exists(self.db_path):
            try:
                # Quick test query to ensure database is accessible
                test_result = self.conn_manager.execute_query("SELECT 1")
                if test_result is None or test_result[0][0] != 1:
                    raise sqlite3.DatabaseError("Database connection test failed")
            except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
                error_msg = str(e).lower()
                if "malformed" in error_msg or "corrupt" in error_msg:
                    self.logger.error(f"Database corruption detected during initialization: {e}")
                    # Try one recovery attempt
                    self.logger.info("Attempting recovery during initialization...")
                    self._cleanup_database_files(self.db_path)
                    # Reinitialize connection manager with fresh database
                    self.conn_manager = DatabaseConnectionManager(self.db_path, self.debug_mode)
                else:
                    raise
        
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
            
            # Perform periodic checkpoint to ensure data durability
            self.conn_manager.periodic_checkpoint()

            if self.debug_mode:
                self.logger.debug(
                    f"Successfully stored reading for sensor {reading_data.sensor_id}"
                )

        except sqlite3.OperationalError as e:
            error_msg = str(e)
            
            # Handle disk I/O errors with in-memory buffering
            if "disk I/O error" in error_msg:
                # Check if we're past the 15-second retry threshold
                if self.failure_retry_count >= len(self.failure_buffer_retry_intervals):
                    # We've reached the 15-second interval, now log as error
                    self.logger.error(f"DISK I/O ERROR persists after {self.failure_retry_count} retries - Buffering reading in memory")
                    if self.failure_retry_count == len(self.failure_buffer_retry_intervals):
                        # First time hitting the threshold, log possible causes
                        self.logger.error("Possible causes:")
                        self.logger.error("  - Docker volume mount issues")
                        self.logger.error("  - Host filesystem full or read-only")
                        self.logger.error("  - Container resource limits reached")
                        self.logger.error("  - Filesystem corruption")
                else:
                    # Still in early retry phase, use debug logging only
                    if len(self.failure_buffer) == 0:
                        # First failure, log as debug
                        self.logger.debug(f"Disk I/O error detected, buffering reading (retry in {self.failure_buffer_retry_intervals[0]}s)")
                    else:
                        # Subsequent failures during retry window
                        self.logger.debug(f"Disk I/O error, buffering reading (retry #{self.failure_retry_count + 1})")
                
                if self.debug_mode:
                    # Enhanced error diagnostics
                    self.logger.debug("=== SQLite Error Diagnostics ===")
                    self._log_error_diagnostics(error_msg)
                
                # Store the failed reading in the failure buffer
                self._add_to_failure_buffer(reading_data)
                
                # Don't raise, let the simulator continue
                return
            else:
                # Other operational errors - log immediately
                self.logger.error(f"SQLite Operational Error storing reading: {error_msg}")
            
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

        # Check resources before adding to batch
        if not self._check_resources():
            raise sqlite3.OperationalError("Resource limits exceeded")
        
        # Use lock for thread-safe batch operations
        with self._commit_lock:
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
                if self.debug_mode:
                    reason = "size" if len(self.batch_buffer) >= self.batch_size else "timeout"
                    self.logger.debug(f"Triggering batch commit (reason: {reason}, size: {len(self.batch_buffer)}, age: {batch_age:.1f}s)")
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
        # Use lock for thread-safe batch operations
        with self._commit_lock:
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
                
                # Explicitly commit for external readers in DELETE mode
                self.conn_manager.checkpoint("PASSIVE")

                batch_size = len(self.batch_buffer)
                self.batch_insert_count += 1
                self.insert_count += batch_size

                # Update performance metrics
                batch_time = time.time() - start_time
                self.total_batch_time += batch_time
                self.total_insert_time += batch_time

                # Log batch insert performance
                if self.debug_mode:
                    self.logger.debug(
                        f"✅ Batch committed: {batch_size} readings in {batch_time*1000:.2f}ms "
                        f"({batch_size/batch_time if batch_time > 0 else 0:.1f} records/sec)"
                    )
                elif self.batch_insert_count % 10 == 0:
                    avg_time_per_reading = (
                        (self.total_batch_time / self.insert_count) * 1000
                        if self.insert_count > 0
                        else 0
                    )
                    logger.info(
                        f"Batch insert performance: {batch_size} readings in {batch_time:.3f}s "
                        f"(avg: {avg_time_per_reading:.2f}ms/reading)"
                    )

                # Clear the buffer and reset timer
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
        """Close the database connection for the current thread with final checkpoint."""
        try:
            self.logger.info("Closing database connection...")
            
            # Commit any pending batch
            if self.batch_buffer:
                self.logger.info(f"Committing {len(self.batch_buffer)} pending writes...")
                self.commit_batch()
            
            # Try to flush failure buffer one last time
            if self.failure_buffer:
                self.logger.info(f"Attempting final flush of {len(self.failure_buffer)} failed writes...")
                # Force immediate retry without waiting for interval
                self.last_failure_retry_time = 0
                self.failure_retry_count = 0  # Reset backoff for final attempt
                self._retry_failed_writes()
                
                if self.failure_buffer:
                    self.logger.warning(f"WARNING: {len(self.failure_buffer)} readings could not be written to disk and will be lost!")
                    # Optionally save to a recovery file
                    try:
                        import json
                        recovery_file = self.db_path.replace('.db', '_recovery.json')
                        with open(recovery_file, 'w') as f:
                            readings_data = [r.model_dump() for r in self.failure_buffer]
                            json.dump(readings_data, f, indent=2, default=str)
                        self.logger.info(f"Saved {len(self.failure_buffer)} unwritten readings to {recovery_file}")
                    except Exception as e:
                        self.logger.error(f"Failed to save recovery file: {e}")
            
            # Force final commit for maximum durability (DELETE mode)
            self.logger.info("Executing final data commit...")
            self.conn_manager.checkpoint("TRUNCATE")  # This will commit in DELETE mode
            self.logger.info("Final commit complete")
            
            # Get final statistics before closing
            try:
                with self.conn_manager.get_connection() as conn:
                    # Set synchronous to FULL for final operations
                    conn.execute("PRAGMA synchronous=FULL;")
                    count = conn.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0]
                    self.logger.info(f"Database contains {count} total readings at shutdown")
            except Exception as e:
                self.logger.warning(f"Could not get final count: {e}")

            # Close the connection manager's thread connection
            self.conn_manager.close_thread_connection()
            self.logger.info("Database connection closed successfully")
            
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
                "failure_buffer_size": len(self.failure_buffer),
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

    def _add_to_failure_buffer(self, reading_data: SensorReadingSchema):
        """Add a failed reading to the in-memory failure buffer.
        
        Args:
            reading_data: The reading that failed to write to disk
        """
        with self.failure_buffer_lock:
            if len(self.failure_buffer) >= self.failure_buffer_max_size:
                # Remove oldest readings if buffer is full (FIFO)
                removed_count = min(100, len(self.failure_buffer) // 10)  # Remove 10% or 100 items
                self.failure_buffer = self.failure_buffer[removed_count:]
                self.logger.warning(f"Failure buffer full, dropped {removed_count} oldest readings")
            
            self.failure_buffer.append(reading_data)
            
            # Always use debug logging for buffer updates - the error will be logged separately
            self.logger.debug(f"Added reading to failure buffer (current size: {len(self.failure_buffer)})")
    
    def _retry_failed_writes(self):
        """Periodically retry writing failed readings from the failure buffer with custom backoff."""
        current_time = time.time()
        
        # Get current retry interval from the custom sequence
        if self.failure_retry_count < len(self.failure_buffer_retry_intervals):
            current_retry_interval = self.failure_buffer_retry_intervals[self.failure_retry_count]
        else:
            # After exhausting the list, stay at the maximum interval
            current_retry_interval = self.failure_buffer_max_retry_interval
        
        # Only retry periodically to avoid overwhelming the system
        if current_time - self.last_failure_retry_time < current_retry_interval:
            return
        
        if not self.failure_buffer:
            # Reset retry count when buffer is empty
            if self.failure_retry_count > 0:
                self.failure_retry_count = 0
                self.logger.debug("Failure buffer empty, reset retry count")
            return
        
        with self.failure_buffer_lock:
            if not self.failure_buffer:
                return
            
            # Only log retry attempts at INFO level after hitting the 15-second threshold
            if self.failure_retry_count >= len(self.failure_buffer_retry_intervals):
                # At or past the 15-second interval
                self.logger.info(f"Attempting to retry {len(self.failure_buffer)} failed writes (retry #{self.failure_retry_count + 1}, interval: {current_retry_interval:.0f}s)")
            else:
                # Still in early retry phase - use debug
                self.logger.debug(f"Attempting to retry {len(self.failure_buffer)} failed writes (retry #{self.failure_retry_count + 1}, interval: {current_retry_interval:.0f}s)")
            
            successful_writes = []
            failed_writes = []
            
            # Try to write each failed reading
            for reading in self.failure_buffer[:100]:  # Process up to 100 at a time
                try:
                    # Convert back to dict for database insertion
                    data_for_db = reading.model_dump(exclude_none=False)
                    
                    # Ensure boolean values are converted to integers
                    if "anomaly_flag" in data_for_db and isinstance(data_for_db["anomaly_flag"], bool):
                        data_for_db["anomaly_flag"] = int(data_for_db["anomaly_flag"])
                    if "synced" in data_for_db and isinstance(data_for_db["synced"], bool):
                        data_for_db["synced"] = int(data_for_db["synced"])
                    
                    # Prepare query
                    columns = list(SensorReadingSchema.model_fields.keys())
                    placeholders = ", ".join(["?"] * len(columns))
                    column_names = ", ".join(columns)
                    
                    query = f"""
                        INSERT INTO sensor_readings ({column_names})
                        VALUES ({placeholders})
                    """
                    
                    params = tuple(data_for_db[col] for col in columns)
                    
                    # Try to write with a short timeout
                    self.conn_manager.execute_write(query, params)
                    successful_writes.append(reading)
                    
                except sqlite3.OperationalError as e:
                    if "disk I/O error" in str(e):
                        # Still experiencing disk I/O issues, stop retrying for now
                        self.failure_retry_count += 1
                        next_interval = self.failure_buffer_retry_intervals[min(self.failure_retry_count, len(self.failure_buffer_retry_intervals) - 1)]
                        
                        # Only log as error after we've reached the 15-second interval
                        if self.failure_retry_count >= len(self.failure_buffer_retry_intervals):
                            self.logger.error(f"Disk I/O error persists after {self.failure_retry_count} attempts, next retry in {next_interval:.0f}s")
                        else:
                            self.logger.debug(f"Disk I/O error on retry #{self.failure_retry_count}, next retry in {next_interval:.0f}s")
                        break
                    else:
                        failed_writes.append(reading)
                except Exception as e:
                    self.logger.debug(f"Failed to retry write: {e}")
                    failed_writes.append(reading)
            
            # Remove successful writes from buffer
            if successful_writes:
                self.failure_buffer = [r for r in self.failure_buffer if r not in successful_writes]
                
                # Only log recovery at INFO level after we've hit the 15-second threshold
                if self.failure_retry_count >= len(self.failure_buffer_retry_intervals):
                    self.logger.info(f"Successfully wrote {len(successful_writes)} readings from failure buffer")
                    if len(self.failure_buffer) > 0:
                        self.logger.info(f"Remaining in failure buffer: {len(self.failure_buffer)}")
                else:
                    self.logger.debug(f"Successfully wrote {len(successful_writes)} readings from failure buffer")
                    if len(self.failure_buffer) > 0:
                        self.logger.debug(f"Remaining in failure buffer: {len(self.failure_buffer)}")
                
                # Reset retry count on successful writes
                self.failure_retry_count = 0
            
            self.last_failure_retry_time = current_time

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
