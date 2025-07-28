#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.2.3",
#     "pyarrow>=17.0.0",
#     "pyyaml>=6.0.2",
#     "numpy>=2.0.0",
#     "databricks-sql-connector>=3.0.0",
#     "pydantic>=2.0.0"
# ]
# ///
"""
Continuously export new sensor log entries from a SQLite database and append them to a Databricks table.
Parameters and paths are read from a YAML config file, with optional environment variable overrides.
Only command-line flag is --config pointing to the YAML file.
"""

import argparse
import io
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path

import databricks.sql
import pandas as pd
import yaml

# deltalake imports removed
# Pipeline configuration is now read directly from the database

# Suppress verbose HTTP logging from Databricks connector
logging.getLogger("databricks").setLevel(logging.WARNING)
logging.getLogger("databricks.sql").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


# New helper function for quoting Databricks SQL identifiers
def quote_databricks_identifier(name: str) -> str:
    """Quotes an identifier for Databricks SQL using backticks.
    Escapes existing backticks within the name.
    """
    return f"`{name.replace('`', '``')}`"


def convert_timestamps_to_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all timestamp columns in DataFrame to ISO format strings.

    This is necessary because Databricks SQL connector cannot handle pandas Timestamp objects.
    """
    df_copy = df.copy()
    for col in df_copy.columns:
        # Check if column is datetime type
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            # Convert to ISO format string
            df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        else:
            # Check if column contains timestamp objects (e.g., when a single Timestamp is assigned)
            try:
                # Check if the first non-null value is a Timestamp
                first_val = (
                    df_copy[col].dropna().iloc[0]
                    if not df_copy[col].dropna().empty
                    else None
                )
                if first_val is not None and isinstance(first_val, pd.Timestamp):
                    # Convert all values in the column
                    df_copy[col] = df_copy[col].apply(
                        lambda x: x.strftime("%Y-%m-%d %H:%M:%S.%f")
                        if pd.notna(x)
                        else None
                    )
            except (IndexError, AttributeError):
                # Column doesn't contain timestamps, skip
                pass
    return df_copy


class ConfigWatcher:
    """Watches a configuration file for changes and updates settings dynamically."""

    def __init__(self, config_path: str, check_interval: float = 2.0):
        """
        Initialize the config watcher.

        Args:
            config_path: Path to the configuration file
            check_interval: How often to check for changes (in seconds)
        """
        self.config_path = Path(config_path) if config_path else None
        self.check_interval = check_interval
        self.last_mtime = None
        self.current_config = {}
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        # Load initial config if path exists
        if self.config_path and self.config_path.exists():
            self._load_config()
            self.last_mtime = self.config_path.stat().st_mtime

    def _load_config(self):
        """Load the configuration file."""
        try:
            with open(self.config_path, "r") as f:
                new_config = yaml.safe_load(f)

            # Processing mode validation removed - now handled by PipelineManager

            with self.lock:
                old_processing_mode = self.current_config.get("processing_mode")
                new_processing_mode = new_config.get("processing_mode")

                if (
                    old_processing_mode != new_processing_mode
                    and old_processing_mode is not None
                ):
                    logging.info(
                        f"Processing mode changed from '{old_processing_mode}' to '{new_processing_mode}'"
                    )

                self.current_config = new_config

        except Exception as e:
            logging.error(f"Error loading config file: {e}")

    def _watch_loop(self):
        """Main loop that checks for config file changes."""
        while self.running:
            try:
                if self.config_path and self.config_path.exists():
                    current_mtime = self.config_path.stat().st_mtime
                    if current_mtime != self.last_mtime:
                        logging.info(f"Config file changed, reloading...")
                        self._load_config()
                        self.last_mtime = current_mtime
            except Exception as e:
                logging.error(f"Error checking config file: {e}")

            time.sleep(self.check_interval)

    def start(self):
        """Start watching the config file."""
        if not self.config_path:
            return

        self.running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        logging.info(f"Started watching config file: {self.config_path}")

    def stop(self):
        """Stop watching the config file."""
        self.running = False
        if self.thread:
            self.thread.join()
        logging.info("Stopped watching config file")

    def get(self, key: str, default=None):
        """Get a configuration value with thread safety."""
        with self.lock:
            return self.current_config.get(key, default)

    def get_all(self):
        """Get all configuration values with thread safety."""
        with self.lock:
            return self.current_config.copy()


def parse_args():
    p = argparse.ArgumentParser(
        description="SQLite → Databricks uploader"
    )  # Updated description
    p.add_argument("--config", help="YAML config file (optional)")
    p.add_argument("--sqlite", help="Path to SQLite DB")
    # --storage-uri removed
    p.add_argument("--state-dir", help="Directory for last-upload state file")
    p.add_argument(
        "--interval", type=int, help="Seconds between cycles (ignored with --once)"
    )
    p.add_argument("--once", action="store_true", help="Upload once and exit (no loop)")
    p.add_argument("--table", help="Override SQLite table name")
    p.add_argument("--timestamp-col", help="Override timestamp column")
    # Pipeline management arguments
    p.add_argument(
        "--show-pipeline",
        action="store_true",
        help="Show current pipeline type and exit",
    )
    p.add_argument(
        "--set-pipeline",
        choices=["raw", "schematized", "filtered", "emergency"],
        help="Set pipeline type and exit (requires --by)",
    )
    p.add_argument(
        "--by", help="Who is making the pipeline change (used with --set-pipeline)"
    )
    p.add_argument(
        "--max-batch-size",
        type=int,
        help="Maximum number of records to upload per batch cycle (default: 500)",
    )
    p.add_argument(
        "--fuzz-factor",
        type=float,
        help="Fuzz factor for sleep interval as a percentage (0-1, default: 0.1 = 10%%)",
    )
    # Updated argument for processing mode
    p.add_argument(
        "--processing-mode",
        choices=["raw", "schematized", "sanitized", "aggregated", "emergency"],
        default="schematized",
        help="Processing mode for data upload",
    )
    # Processing configurations
    p.add_argument(
        "--gps-fuzzing-config", default="{}", help="JSON config string for GPS fuzzing"
    )
    p.add_argument(
        "--aggregate-config", default="{}", help="JSON config string for aggregation"
    )
    p.add_argument(
        "--emergency-config",
        default="{}",
        help="JSON config string for emergency filtering",
    )

    # Databricks connection parameters
    p.add_argument(
        "--databricks-host", type=str, help="Databricks workspace host name."
    )
    p.add_argument(
        "--databricks-http-path",
        type=str,
        help="HTTP path for the Databricks SQL warehouse or cluster.",
    )
    p.add_argument(
        "--databricks-token",
        type=str,
        help="Databricks personal access token (PAT). Best practice: use DATABRICKS_TOKEN env var.",
    )
    p.add_argument(
        "--databricks-database", type=str, help="Target database name in Databricks."
    )
    p.add_argument(
        "--databricks-table",
        type=str,
        help="Target table name in Databricks (e.g., 'schema.table' or just 'table' if database is set).",
    )

    p.add_argument(
        "--run-query",
        type=str,
        default=None,
        help="Run a query against the target Databricks table and exit. "  # Updated help
        "Use 'INFO' for table details or a SQL-like 'SELECT * ... [LIMIT N]' query.",
    )
    return p.parse_args()


# Updated processing functions to match new architecture
def process_raw_data(df: pd.DataFrame, timestamp_field: str = None) -> pd.DataFrame:
    """Convert DataFrame to raw format (timestamp, reading_string)."""
    logging.info("Converting to raw format")
    # Combine all columns into a single reading_string
    raw_df = pd.DataFrame()

    # Use provided timestamp field or try to detect it
    if timestamp_field and timestamp_field in df.columns:
        raw_df["timestamp"] = pd.to_datetime(df[timestamp_field])
    else:
        # Try to find a timestamp column
        timestamp_cols = df.select_dtypes(include=["datetime64"]).columns
        if len(timestamp_cols) > 0:
            raw_df["timestamp"] = df[timestamp_cols[0]]
        else:
            # Look for columns with 'timestamp' or 'date' in the name
            for col in df.columns:
                if "timestamp" in col.lower() or "date" in col.lower():
                    raw_df["timestamp"] = pd.to_datetime(df[col])
                    break
            else:
                # Use the first column as fallback
                raw_df["timestamp"] = pd.to_datetime(df[df.columns[0]])

    raw_df["reading_string"] = df.apply(
        lambda row: json.dumps(row.to_dict(), default=str), axis=1
    )
    return raw_df


def schematize_data(df: pd.DataFrame) -> pd.DataFrame:
    """Pass through data as-is for schematized table (already structured)."""
    logging.info("Using schematized format (structured data)")
    # Rename 'id' column to 'reading_id' if exists
    if "id" in df.columns:
        df = df.rename(columns={"id": "reading_id"})
    return df


def sanitize_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Sanitizes the input DataFrame, particularly fuzzing GPS coordinates."""
    logging.info("Sanitizing data with config: %s", config)
    df = df.copy()

    # Fuzzy GPS coordinates if configured
    decimal_places = config.get("decimal_places", 2)
    if "latitude" in df.columns and "longitude" in df.columns:
        df["latitude"] = df["latitude"].round(decimal_places)
        df["longitude"] = df["longitude"].round(decimal_places)
        logging.info(f"Fuzzed GPS coordinates to {decimal_places} decimal places")

    # Rename 'id' column if exists
    if "id" in df.columns:
        df = df.rename(columns={"id": "reading_id"})

    return df


def filter_emergency_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Filters for emergency/anomaly data only."""
    logging.info("Filtering for emergency data with config: %s", config)
    anomaly_column = config.get("anomaly_column", "anomaly_flag")
    anomaly_value = config.get("anomaly_value", 1)

    if anomaly_column in df.columns:
        emergency_df = df[df[anomaly_column] == anomaly_value].copy()
        logging.info(
            f"Filtered {len(emergency_df)} emergency records from {len(df)} total"
        )

        # Rename 'id' column if exists
        if "id" in emergency_df.columns:
            emergency_df = emergency_df.rename(columns={"id": "reading_id"})

        return emergency_df
    else:
        logging.warning(f"Anomaly column '{anomaly_column}' not found in data")
        return pd.DataFrame()  # Return empty DataFrame if column not found


def aggregate_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aggregates the input DataFrame with time windows."""
    logging.info("Aggregating data with config: %s", config)

    window_minutes = config.get("window_minutes", 60)
    group_by = config.get("group_by", ["sensor_id", "location"])

    # Ensure timestamp column exists and is datetime
    timestamp_col = (
        df.select_dtypes(include=["datetime64"]).columns[0]
        if len(df.select_dtypes(include=["datetime64"]).columns) > 0
        else "timestamp"
    )
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # Create time windows
    df["start_window"] = df[timestamp_col].dt.floor(f"{window_minutes}min")
    df["end_window"] = df["start_window"] + pd.Timedelta(minutes=window_minutes)

    # Identify numeric columns for aggregation
    numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()
    # Exclude non-aggregatable columns
    exclude_cols = [
        "id",
        "reading_id",
        "status_code",
        "anomaly_flag",
        "synced",
    ] + group_by
    numeric_cols = [col for col in numeric_cols if col not in exclude_cols]

    # Build aggregation dictionary
    agg_dict = {}
    for col in numeric_cols:
        agg_dict[f"{col}_min"] = (col, "min")
        agg_dict[f"{col}_max"] = (col, "max")
        agg_dict[f"{col}_avg"] = (col, "mean")

    agg_dict["reading_count"] = (timestamp_col, "count")

    # Group and aggregate
    groupby_cols = ["start_window", "end_window"] + [
        col for col in group_by if col in df.columns
    ]
    aggregated = df.groupby(groupby_cols).agg(**agg_dict).reset_index()

    logging.info(f"Aggregated {len(df)} records into {len(aggregated)} time windows")
    return aggregated


def read_data(sqlite_path, query, table_name):
    conn = sqlite3.connect(sqlite_path)
    try:
        if query:
            df = pd.read_sql_query(query, conn)
        else:
            if not table_name:
                raise ValueError("Must specify --table or --query")
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return df
    finally:
        conn.close()


def upload_batch_via_file(
    df: pd.DataFrame, table_name_qualified: str, cursor_db, pipeline_type: str
) -> bool:
    """Upload DataFrame to Databricks table using direct INSERT statements.

    Uses multi-row INSERT VALUES syntax for efficient bulk loading without
    requiring temporary tables.

    Args:
        df: DataFrame to upload
        table_name_qualified: Fully qualified table name (database.table)
        cursor_db: Databricks SQL cursor
        pipeline_type: Pipeline type for logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Insert data directly into target table in batches
        # Using VALUES clause for better performance than individual inserts
        batch_size = 500  # Databricks can handle larger batches
        total_records = len(df)

        # Build column list
        columns = [quote_databricks_identifier(col) for col in df.columns]
        column_list = ", ".join(columns)

        logging.info(
            f"Uploading {total_records} records to {table_name_qualified} in batches of {batch_size}..."
        )

        for start_idx in range(0, total_records, batch_size):
            end_idx = min(start_idx + batch_size, total_records)
            batch_df = df.iloc[start_idx:end_idx]

            # Build VALUES clause
            values_rows = []
            for _, row in batch_df.iterrows():
                values = []
                for val in row:
                    if pd.isna(val):
                        values.append("NULL")
                    elif isinstance(val, str):
                        # Escape single quotes in strings
                        escaped_val = val.replace("'", "''")
                        values.append(f"'{escaped_val}'")
                    elif isinstance(val, (pd.Timestamp, pd.DatetimeTZDtype)):
                        values.append(f"'{val}'")
                    else:
                        values.append(str(val))
                values_rows.append(f"({', '.join(values)})")

            # Direct INSERT with VALUES clause
            insert_sql = f"""
            INSERT INTO {table_name_qualified} ({column_list})
            VALUES {", ".join(values_rows)}
            """

            cursor_db.execute(insert_sql)
            logging.info(
                f"Inserted batch {start_idx // batch_size + 1}/{(total_records + batch_size - 1) // batch_size} ({len(batch_df)} records)"
            )

        logging.info(
            f"Successfully uploaded {total_records} records to {table_name_qualified}"
        )
        return True

    except Exception as e:
        logging.error(f"Error during batch upload: {e}", exc_info=True)
        return False


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    # Initialize config watcher
    config_watcher = ConfigWatcher(args.config, check_interval=2.0)

    # Get initial config - ConfigWatcher handles the file loading
    cfg = config_watcher.get_all()

    # Validate required configuration fields
    required_config_fields = {
        "processing_mode": "Processing mode (RAW, SCHEMATIZED, SANITIZED, AGGREGATED, EMERGENCY)",
        "sqlite": "SQLite database path",
        "databricks_host": "Databricks host",
        "databricks_http_path": "Databricks HTTP path",
        "databricks_database": "Databricks database name",
        "databricks_table": "Databricks table base name",
        "state_dir": "State directory path",
        "interval": "Upload interval in seconds",
        "max_batch_size": "Maximum batch size for uploads",
    }

    # Check for missing required fields
    missing_fields = []
    for field, description in required_config_fields.items():
        if field not in cfg or cfg[field] is None:
            missing_fields.append(f"{field} ({description})")

    if missing_fields:
        logging.error("Missing required configuration fields:")
        for field in missing_fields:
            logging.error(f"  - {field}")
        logging.error(
            "\nPlease ensure all required fields are present in your configuration file."
        )
        sys.exit(1)

    # Processing mode validation removed - now handled by PipelineManager

    # Start watching for config changes
    config_watcher.start()

    # 2) assemble Databricks connection params (CLI > ENV > YAML)
    databricks_host = (
        args.databricks_host
        or os.getenv("DATABRICKS_HOST")
        or cfg.get("databricks_host")
    )
    databricks_http_path = (
        args.databricks_http_path
        or os.getenv("DATABRICKS_HTTP_PATH")
        or cfg.get("databricks_http_path")
    )
    databricks_token = (
        args.databricks_token
        or os.getenv("DATABRICKS_TOKEN")
        or cfg.get("databricks_token")
    )
    databricks_database = (
        args.databricks_database
        or os.getenv("DATABRICKS_DATABASE")
        or cfg.get("databricks_database")
    )
    databricks_table = (
        args.databricks_table
        or os.getenv("DATABRICKS_TABLE")
        or cfg.get("databricks_table")
    )

    # Validate Databricks connection parameters if not in a mode that might bypass DB connection (e.g. help)
    # For now, --run-query will also need these.
    if not all(
        [
            databricks_host,
            databricks_http_path,
            databricks_token,
            databricks_database,
            databricks_table,
        ]
    ):
        missing_params = []
        if not databricks_host:
            missing_params.append(
                "databricks_host (CLI: --databricks-host, ENV: DATABRICKS_HOST)"
            )
        if not databricks_http_path:
            missing_params.append(
                "databricks_http_path (CLI: --databricks-http-path, ENV: DATABRICKS_HTTP_PATH)"
            )
        if not databricks_token:
            missing_params.append(
                "databricks_token (CLI: --databricks-token, ENV: DATABRICKS_TOKEN)"
            )
        if not databricks_database:
            missing_params.append(
                "databricks_database (CLI: --databricks-database, ENV: DATABRICKS_DATABASE)"
            )
        if not databricks_table:
            missing_params.append(
                "databricks_table (CLI: --databricks-table, ENV: DATABRICKS_TABLE)"
            )
        logging.error(
            f"Missing required Databricks connection parameters: {', '.join(missing_params)}"
        )
        sys.exit(1)

    # Handle --run-query mode
    if args.run_query:
        logging.info(f"Entering query mode for query: '{args.run_query}'")
        conn_db_query = None
        cursor_db_query = None
        try:
            conn_db_query = databricks.sql.connect(
                server_hostname=databricks_host,
                http_path=databricks_http_path,
                access_token=databricks_token,
            )
            cursor_db_query = conn_db_query.cursor()
            logging.info(
                f"Successfully connected to Databricks for query mode: {databricks_host}"
            )

            # Helper function for printing query results
            def print_query_results(cursor):
                results = cursor.fetchall()
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    df_results = pd.DataFrame(results, columns=columns)
                    print(df_results.to_string())
                elif cursor.rowcount != -1:
                    print(f"Query executed. Rows affected: {cursor.rowcount}")
                else:
                    print(
                        "Query executed. No results to display or rowcount not applicable."
                    )

            if args.run_query.strip().upper() == "INFO":
                logging.info(
                    f"Fetching information for Databricks database '{databricks_database}' and table '{databricks_table}'"
                )

                # Set current database
                cursor_db_query.execute(
                    f"USE {quote_databricks_identifier(databricks_database)}"
                )
                logging.info(f"Using database: {databricks_database}")

                print(f"\n--- Tables in Database '{databricks_database}' ---")
                cursor_db_query.execute(
                    f"SHOW TABLES IN {quote_databricks_identifier(databricks_database)}"
                )
                print_query_results(cursor_db_query)

                # Show info for all scenario tables with new naming convention
                table_suffixes = [
                    "0_raw",
                    "1_schematized",
                    "2_sanitized",
                    "3_aggregated",
                    "4_emergency",
                ]
                for suffix in table_suffixes:
                    full_table_name = f"{databricks_table}_{suffix}"
                    qualified_table_name = f"{quote_databricks_identifier(databricks_database)}.{quote_databricks_identifier(full_table_name)}"

                    try:
                        print(f"\n--- Table Info: '{qualified_table_name}' ---")
                        cursor_db_query.execute(
                            f"SELECT COUNT(*) AS row_count FROM {qualified_table_name}"
                        )
                        print_query_results(cursor_db_query)
                    except Exception as e:
                        print(
                            f"Table '{qualified_table_name}' does not exist or is not accessible: {e}"
                        )

            else:  # General SQL query
                logging.info(f"Executing user-provided query: {args.run_query}")
                # Set current database first, in case the query doesn't fully qualify table names
                try:
                    cursor_db_query.execute(
                        f"USE {quote_databricks_identifier(databricks_database)}"
                    )
                    logging.info(f"Ensured database context: {databricks_database}")
                except Exception as db_use_exc:
                    logging.warning(
                        f"Could not set database context to '{databricks_database}' (may not be an issue if query is fully qualified): {db_use_exc}"
                    )

                cursor_db_query.execute(args.run_query)
                print(f"\n--- Results for Query: {args.run_query} ---")
                print_query_results(cursor_db_query)

        except Exception as e:
            logging.error(f"Error during Databricks query mode: {e}", exc_info=True)
            sys.exit(1)

        finally:
            if cursor_db_query:
                cursor_db_query.close()
            if conn_db_query:
                conn_db_query.close()
            logging.info("Databricks query connection closed.")

        sys.exit(0)  # Exit after query mode

    # -------- Normal operation mode (uploader) --------
    # These parameters are only essential if not in query mode (which exits early)
    sqlite_path = Path(args.sqlite or os.getenv("SQLITE_PATH") or cfg.get("sqlite", ""))
    state_dir = Path(
        args.state_dir or os.getenv("STATE_DIR") or cfg.get("state_dir", "/state")
    )
    interval = int(
        (
            args.interval
            if args.interval is not None
            else os.getenv("UPLOAD_INTERVAL") or cfg.get("interval", 300)
        )
    )
    once = args.once
    # sqlite_table_name refers to the source table in SQLite
    sqlite_table_name = (
        args.table or os.getenv("SQLITE_TABLE_NAME") or cfg.get("sqlite_table_name")
    )  # Renamed for clarity
    timestamp_col = (
        args.timestamp_col or os.getenv("TIMESTAMP_COL") or cfg.get("timestamp_col")
    )

    # Validate required parameters for normal mode
    if not sqlite_path or not sqlite_path.is_file():  # This check is fine
        logging.error(
            "SQLite file not found: %s (required for uploader mode)", sqlite_path
        )
        sys.exit(1)
    # Databricks params already validated if this point is reached.

    # Handle pipeline management CLI arguments
    if args.show_pipeline or args.set_pipeline:
        # Initialize PipelineManager for CLI operations
        pipeline_manager = PipelineManager(str(sqlite_path))

        if args.show_pipeline:
            # Show current pipeline and exit
            try:
                current = pipeline_manager.get_current_pipeline()
                print(f"Current pipeline type: {current.pipeline_type.value}")
                print(f"Last updated: {current.updated_at}")
                print(f"Updated by: {current.updated_by or 'N/A'}")
            except Exception as e:
                logging.error(f"Failed to get pipeline type: {e}")
                sys.exit(1)
            sys.exit(0)

        if args.set_pipeline:
            # Set pipeline type and exit
            if not args.by:
                logging.error("--by is required when using --set-pipeline")
                sys.exit(1)
            try:
                from pipeline_manager import PipelineType

                pipeline_type = PipelineType(args.set_pipeline)
                updated = pipeline_manager.set_pipeline(
                    pipeline_type=pipeline_type, updated_by=args.by
                )
                print(f"Pipeline type updated to: {updated.pipeline_type.value}")
                print(f"Updated at: {updated.updated_at}")
                print(f"Updated by: {updated.updated_by}")
            except Exception as e:
                logging.error(f"Failed to set pipeline type: {e}")
                sys.exit(1)
            sys.exit(0)

    # Prepare state file directory
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "last_upload.json"
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                last_ts = pd.to_datetime(json.load(f).get("last_upload"), utc=True)
        except Exception:
            last_ts = pd.Timestamp("1970-01-01T00:00:00Z")
    else:
        last_ts = pd.Timestamp("1970-01-01T00:00:00Z")

    # Table and timestamp column introspection/override for SQLite source
    if sqlite_table_name is None:
        # Only run table detection if not provided
        conn_sqlite_meta = sqlite3.connect(str(sqlite_path))
        cursor_sqlite_meta = conn_sqlite_meta.cursor()
        cursor_sqlite_meta.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = [row[0] for row in cursor_sqlite_meta.fetchall()]
        conn_sqlite_meta.close()
        if not tables:
            logging.error("No tables found in SQLite database.")
            sys.exit(1)
        if len(tables) > 1:
            logging.error(
                "Multiple tables found in SQLite database: %s. Please specify one using --table.",
                tables,
            )
            sys.exit(1)
        sqlite_table_name = tables[0]
        logging.info("Detected SQLite table: %s", sqlite_table_name)
    else:
        logging.info("Using user-supplied SQLite table: %s", sqlite_table_name)

    # Initialize PipelineManager after SQLite connection is established
    pipeline_manager = PipelineManager(str(sqlite_path))
    logging.info(f"Initialized PipelineManager with database: {sqlite_path}")

    # Migrate from old config format if needed
    if "processing_mode" in cfg:
        # Map old processing_mode to new pipeline type
        old_mode = cfg["processing_mode"].lower()
        pipeline_mapping = {
            "raw": "raw",
            "schematized": "schematized",
            "sanitized": "schematized",  # Map sanitized to schematized
            "aggregated": "emergency",  # Map aggregated to emergency
            "emergency": "emergency",
        }
        new_pipeline = pipeline_mapping.get(old_mode, "raw")
        pipeline_manager.set_pipeline(new_pipeline, updated_by="migration")
        logging.info(
            f"Migrated processing_mode '{old_mode}' to pipeline type '{new_pipeline}'"
        )
    elif any(key.startswith("enable_") for key in cfg):
        # Detect old enable_* flag format
        if cfg.get("enable_aggregation", False):
            pipeline_manager.set_pipeline("emergency", updated_by="migration")
            logging.info(
                "Migrated enable_aggregation=true to pipeline type 'emergency'"
            )
        elif cfg.get("enable_sanitization", False):
            pipeline_manager.set_pipeline("schematized", updated_by="migration")
            logging.info(
                "Migrated enable_sanitization=true to pipeline type 'schematized'"
            )
        elif cfg.get("enable_schematization", False):
            pipeline_manager.set_pipeline("schematized", updated_by="migration")
            logging.info(
                "Migrated enable_schematization=true to pipeline type 'schematized'"
            )
        else:
            # Default to raw if no processing flags are enabled
            pipeline_manager.set_pipeline("raw", updated_by="migration")
            logging.info("Migrated to default pipeline type 'raw'")

    if timestamp_col is None:
        # Only run timestamp detection if not provided
        conn_sqlite_meta = sqlite3.connect(str(sqlite_path))
        cursor_sqlite_meta = conn_sqlite_meta.cursor()
        cursor_sqlite_meta.execute(f"PRAGMA table_info('{sqlite_table_name}');")
        cols = cursor_sqlite_meta.fetchall()
        conn_sqlite_meta.close()
        ts_cols = [
            c[1]
            for c in cols
            if c[1].lower() == "timestamp" or "date" in (c[2] or "").lower()
        ]
        if not ts_cols:
            logging.error(
                "No suitable timestamp column found in SQLite table '%s'",
                sqlite_table_name,
            )
            sys.exit(1)
        timestamp_field = ts_cols[0]  # Use the first detected suitable column
        logging.info(
            "Detected timestamp field in SQLite table '%s': %s",
            sqlite_table_name,
            timestamp_field,
        )
    else:
        timestamp_field = timestamp_col
        logging.info(
            "Using user-supplied timestamp column for SQLite table '%s': %s",
            sqlite_table_name,
            timestamp_field,
        )

    logging.info(
        "Starting continuous upload every %d seconds, initial timestamp=%s",
        interval,
        last_ts,
    )
    base_name = sqlite_path.stem  # Remains useful for context
    while True:
        try:
            # Start execution tracking (uses current pipeline type)
            execution_id = pipeline_manager.start_execution()
            # First, count total available records
            conn_sqlite_count = sqlite3.connect(str(sqlite_path))
            cursor_count = conn_sqlite_count.cursor()

            # Count total records available for upload
            count_sql = f"SELECT COUNT(*) as count, MIN(id) as min_id, MAX(id) as max_id FROM {sqlite_table_name} WHERE {timestamp_field} > ?"
            cursor_count.execute(count_sql, [last_ts.isoformat()])
            count_result = cursor_count.fetchone()
            available_count = count_result[0] if count_result else 0
            min_id = (
                count_result[1]
                if count_result and count_result[1] is not None
                else "N/A"
            )
            max_id = (
                count_result[2]
                if count_result and count_result[2] is not None
                else "N/A"
            )
            conn_sqlite_count.close()

            if available_count > 0:
                logging.info(f"\n{'=' * 60}")
                logging.info(f"PRE-UPLOAD STATUS:")
                logging.info(f"  Available records in SQLite: {available_count}")
                logging.info(f"  ID range: {min_id} to {max_id}")
                logging.info(f"  Will fetch up to {max_batch_size} records")
                logging.info(f"{'=' * 60}")

            # Read new data since last timestamp using introspected schema, limited by batch size
            sql = f"SELECT * FROM {sqlite_table_name} WHERE {timestamp_field} > ? ORDER BY {timestamp_field} LIMIT ?"
            conn_sqlite_data = sqlite3.connect(str(sqlite_path))
            df = pd.read_sql_query(sql, conn_sqlite_data, params=[last_ts.isoformat()])
            conn_sqlite_data.close()
            if df.empty:
                logging.info("No new records since %s", last_ts)
            else:
                # Data processing steps

                # Get pipeline type from PipelineManager
                pipeline_type = pipeline_manager.get_current_pipeline()
                logging.info(f"Using pipeline type: {pipeline_type}")

                # Load configuration for specific processing modes
                gps_fuzzing_config_str = args.gps_fuzzing_config
                if gps_fuzzing_config_str == "{}":
                    gps_fuzzing_config_str = os.getenv("GPS_FUZZING_CONFIG") or cfg.get(
                        "gps_fuzzing"
                    )

                gps_fuzzing_config = {}
                if isinstance(gps_fuzzing_config_str, dict):
                    gps_fuzzing_config = gps_fuzzing_config_str
                elif (
                    isinstance(gps_fuzzing_config_str, str)
                    and gps_fuzzing_config_str.strip()
                ):
                    try:
                        gps_fuzzing_config = json.loads(gps_fuzzing_config_str)
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse gps_fuzzing_config: {e}")

                emergency_config_str = args.emergency_config
                if emergency_config_str == "{}":
                    emergency_config_str = os.getenv("EMERGENCY_CONFIG") or cfg.get(
                        "emergency_config"
                    )

                emergency_config = {}
                if isinstance(emergency_config_str, dict):
                    emergency_config = emergency_config_str
                elif (
                    isinstance(emergency_config_str, str)
                    and emergency_config_str.strip()
                ):
                    try:
                        emergency_config = json.loads(emergency_config_str)
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse emergency_config: {e}")

                aggregate_config_str = args.aggregate_config
                if aggregate_config_str == "{}":
                    aggregate_config_str = os.getenv("AGGREGATE_CONFIG") or cfg.get(
                        "aggregate_config"
                    )

                aggregate_config = {}
                if isinstance(aggregate_config_str, dict):
                    aggregate_config = aggregate_config_str
                elif (
                    isinstance(aggregate_config_str, str)
                    and aggregate_config_str.strip()
                ):
                    try:
                        aggregate_config = json.loads(aggregate_config_str)
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse aggregate_config: {e}")

                # Process data based on mode
                processed_df = df.copy()

                if pipeline_type == "raw":
                    processed_df = process_raw_data(df, timestamp_field)
                elif pipeline_type == "schematized":
                    processed_df = schematize_data(df)
                elif pipeline_type == "filtered":
                    # For now, filtered pipeline uses sanitize_data logic
                    processed_df = sanitize_data(df, gps_fuzzing_config)
                elif pipeline_type == "emergency":
                    processed_df = filter_emergency_data(df, emergency_config)
                else:
                    logging.error(f"Unknown pipeline type: {pipeline_type}")
                    continue

                upload_successful = False
                if not processed_df.empty:
                    conn_db = None
                    cursor_db = None
                    try:
                        conn_db = databricks.sql.connect(
                            server_hostname=databricks_host,
                            http_path=databricks_http_path,
                            access_token=databricks_token,
                        )
                        cursor_db = conn_db.cursor()
                        logging.info(
                            f"Successfully connected to Databricks: {databricks_host}"
                        )

                        # Set current database
                        cursor_db.execute(
                            f"USE {quote_databricks_identifier(databricks_database)}"
                        )
                        logging.info(f"Using database: {databricks_database}")

                        # Determine target table based on pipeline type
                        table_suffix_map = {
                            "raw": "0_raw",
                            "schematized": "1_schematized",
                            "filtered": "2_filtered",
                            "emergency": "4_emergency",
                        }

                        table_suffix = table_suffix_map.get(pipeline_type)
                        if not table_suffix:
                            logging.error(
                                f"No table mapping for pipeline type: {pipeline_type}"
                            )
                            continue

                        # Construct the full table name with new naming convention
                        final_table_name = f"{databricks_table}_{table_suffix}"
                        table_name_qualified = f"{quote_databricks_identifier(databricks_database)}.{quote_databricks_identifier(final_table_name)}"

                        logging.info(
                            f"Routing data to table: {table_name_qualified} (pipeline type: {pipeline_type})"
                        )

                        # Add databricks-specific columns for all modes
                        processed_df["databricks_inserted_at"] = pd.Timestamp.now()

                        # Note: The 'id' column is not added here as it's defined in the schema
                        # without GENERATED ALWAYS AS IDENTITY, so Databricks won't auto-generate it.
                        # The uploader will need to handle ID generation if required.

                        # Store the max timestamp before converting to strings
                        # We need this as a pandas Timestamp for state file updates
                        max_timestamp_before_conversion = pd.to_datetime(
                            processed_df[timestamp_field].max()
                        )

                        # Convert timestamps to strings before insertion
                        processed_df = convert_timestamps_to_strings(processed_df)

                        # Use file-based upload instead of direct SQL insert
                        upload_successful = upload_batch_via_file(
                            processed_df,
                            table_name_qualified,
                            cursor_db,
                            pipeline_type,
                        )

                    except Exception as e:
                        logging.error(
                            f"Error during Databricks upload: {e}", exc_info=True
                        )
                        upload_successful = False  # Ensure it's false on error

                    finally:
                        if cursor_db:
                            cursor_db.close()
                        if conn_db:
                            conn_db.close()
                        logging.info("Databricks connection closed.")
                else:
                    logging.info("No new records to upload to Databricks.")
                    upload_successful = True  # No data to upload, so treat as success for timestamp update

                # Update state timestamp only if upload was successful or no data needed uploading
                if upload_successful:
                    last_ts = (
                        df[timestamp_field].max() if not df.empty else last_ts
                    )  # Keep old last_ts if df is empty
                    with open(state_file, "w") as f:
                        json.dump({"last_upload": last_ts.isoformat()}, f)
                    logging.info(f"State timestamp updated to: {last_ts.isoformat()}")

                    # Complete execution tracking
                    pipeline_manager.complete_execution(
                        execution_id, records_processed=len(df)
                    )

                    # Post-upload status check
                    conn_sqlite_post = sqlite3.connect(str(sqlite_path))
                    cursor_post = conn_sqlite_post.cursor()
                    cursor_post.execute(count_sql, [last_ts.isoformat()])
                    post_result = cursor_post.fetchone()
                    remaining_count = post_result[0] if post_result else 0
                    remaining_min_id = (
                        post_result[1]
                        if post_result and post_result[1] is not None
                        else "N/A"
                    )
                    remaining_max_id = (
                        post_result[2]
                        if post_result and post_result[2] is not None
                        else "N/A"
                    )
                    conn_sqlite_post.close()

                    logging.info(f"\n{'=' * 60}")
                    logging.info(f"POST-UPLOAD STATUS:")
                    logging.info(f"  Records uploaded: {len(df)}")
                    if "id" in df.columns:
                        logging.info(
                            f"  Uploaded ID range: {df['id'].min()} to {df['id'].max()}"
                        )
                    logging.info(f"  Remaining records in SQLite: {remaining_count}")
                    if remaining_count > 0:
                        logging.info(
                            f"  Remaining ID range: {remaining_min_id} to {remaining_max_id}"
                        )
                    logging.info(f"{'=' * 60}\n")
                else:
                    logging.warning(
                        "Upload to Databricks failed or was incomplete. State timestamp will not be updated."
                    )

        except KeyboardInterrupt:
            logging.info("Interrupted by user, exiting.")
            # Mark execution as failed due to interruption
            if "execution_id" in locals():
                pipeline_manager.complete_execution(
                    execution_id, records_processed=0, error_message="User interrupted"
                )
            break
        except Exception as e:
            logging.error("Error in upload cycle: %s", e, exc_info=True)
            # Mark execution as failed due to error
            if "execution_id" in locals():
                pipeline_manager.complete_execution(
                    execution_id, records_processed=0, error_message=str(e)
                )
        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
