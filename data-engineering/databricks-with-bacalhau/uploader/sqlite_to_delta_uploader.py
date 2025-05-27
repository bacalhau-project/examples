#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.0.0",
#     "pyarrow>=12.0.0",
#     "deltalake>=0.11.0",
#     "pyyaml>=6.0"
# ]
"""
Continuously export new sensor log entries from a SQLite database and append them to a Delta Lake table (S3 / ADLS / local).
Parameters and paths are read from a YAML config file, with optional environment variable overrides.
Only command-line flag is --config pointing to the YAML file.
"""
import argparse
import logging
import sys
import sqlite3
import io
import os
import json
import time
from pathlib import Path

import yaml
import re
import pandas as pd
from deltalake import DeltaTable, write_deltalake


def parse_args():
    p = argparse.ArgumentParser(description="SQLite → Delta uploader")
    p.add_argument("--config", help="YAML config file (optional)")
    p.add_argument("--sqlite", help="Path to SQLite DB")
    p.add_argument("--storage-uri", help="Delta table URI (s3://… / abfs://… / file:///…)")
    p.add_argument("--state-dir", help="Directory for last-upload state file")
    p.add_argument("--interval", type=int, help="Seconds between cycles (ignored with --once)")
    p.add_argument("--once", action="store_true",
                   help="Upload once and exit (no loop)")
    p.add_argument("--table", help="Override SQLite table name")
    p.add_argument("--timestamp-col", help="Override timestamp column")
    # New arguments for data processing
    p.add_argument("--enable-sanitize", action="store_true", help="Enable data sanitization")
    p.add_argument("--sanitize-config", default="{}", help="JSON config string for sanitization")
    p.add_argument("--enable-filter", action="store_true", help="Enable data filtering")
    p.add_argument("--filter-config", default="{}", help="JSON config string for filtering")
    p.add_argument("--enable-aggregate", action="store_true", help="Enable data aggregation")
    p.add_argument("--aggregate-config", default="{}", help="JSON config string for aggregation")
    p.add_argument("--run-query", type=str, default=None,
                   help="Run a query against the Delta table and exit. "
                        "Use 'INFO' for table details or a SQL-like 'SELECT * ... [LIMIT N]' query.")
    return p.parse_args()


# Placeholder processing functions
def sanitize_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Sanitizes the input DataFrame."""
    logging.info("Sanitizing data with config: %s", config)
    # Placeholder: actual sanitization logic will be added here
    return df


def filter_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Filters the input DataFrame."""
    logging.info("Filtering data with config: %s", config)
    # Placeholder: actual filtering logic will be added here
    return df


def aggregate_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aggregates the input DataFrame."""
    logging.info("Aggregating data with config: %s", config)
    # Placeholder: actual aggregation logic will be added here
    return df


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


## removed S3 upload in favor of direct Delta Lake write


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # 1) load YAML if supplied
    cfg = {}
    if args.config:
        cfg = yaml.safe_load(Path(args.config).read_text())
    # 2) assemble params   CLI > ENV > YAML > default
    # storage_uri is needed for query mode and normal mode
    storage_uri  = (
        args.storage_uri or os.getenv("STORAGE_URI") or cfg.get("storage_uri")
    )
    # Deprecation shim for old key names
    if not storage_uri:
        storage_uri = os.getenv("TABLE_PATH") or cfg.get("table_path")

    if not storage_uri and args.run_query:
        logging.error("--storage-uri (or ENV/YAML equivalent) is required for --run-query mode.")
        sys.exit(1)
    
    # Handle --run-query mode
    if args.run_query:
        logging.info(f"Entering query mode for query: '{args.run_query}'")
        storage_opts = {}
        if os.getenv('AWS_REGION'):
            storage_opts['AWS_REGION'] = os.getenv('AWS_REGION')
        # Add other necessary storage options if used, e.g., for Azure:
        # if os.getenv('AZURE_STORAGE_ACCOUNT_NAME'):
        #     storage_opts['AZURE_STORAGE_ACCOUNT_NAME'] = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        # if os.getenv('AZURE_STORAGE_ACCESS_KEY'):
        #     storage_opts['AZURE_STORAGE_ACCESS_KEY'] = os.getenv('AZURE_STORAGE_ACCESS_KEY')

        try:
            delta_table = DeltaTable(storage_uri, storage_options=storage_opts)
            
            if args.run_query.strip().upper() == "INFO":
                logging.info(f"Fetching information for Delta table at: {storage_uri}")
                print("\n--- Table Schema ---")
                print(delta_table.schema().to_pyarrow().to_string())
                print(f"\n--- Table Version: {delta_table.version()} ---")
                print("\n--- Table History (last 5) ---")
                history = delta_table.history(limit=5)
                for item in history:
                    print(item)
                
                df_info = delta_table.to_pandas()
                print(f"\n--- Total Rows: {len(df_info)} ---")

            else: # SQL-like query
                logging.info(f"Attempting to display data for query: {args.run_query}.")
                logging.info("Note: Full SQL execution is not supported. Displaying table subset based on simple LIMIT clauses.")
                df_query = delta_table.to_pandas()
                
                limit_match = re.search(r'LIMIT\s+(\d+)', args.run_query, re.IGNORECASE)
                if limit_match:
                    limit_value = int(limit_match.group(1))
                    print(f"\n--- Query Results (LIMIT {limit_value}) ---")
                    print(df_query.head(limit_value).to_string())
                else:
                    print("\n--- Query Results (Top 20 rows) ---")
                    print(df_query.head(20).to_string())
                    print("\nDisplaying top 20 rows. For more specific queries or advanced filtering, load data into a dedicated analytics tool.")
        
        except Exception as e:
            logging.error(f"Error during query mode: {e}", exc_info=True)
            sys.exit(1)
        
        sys.exit(0) # Exit after query mode

    # -------- Normal operation mode (uploader) --------
    # These parameters are only essential if not in query mode
    sqlite_path  = Path(
        args.sqlite or os.getenv("SQLITE_PATH") or cfg.get("sqlite", "")
    )
    state_dir    = Path(
        args.state_dir or os.getenv("STATE_DIR") or cfg.get("state_dir", "/state")
    )
    interval     = int(
        (args.interval if args.interval is not None else
         os.getenv("UPLOAD_INTERVAL") or cfg.get("interval", 300))
    )
    once         = args.once
    table_name   = args.table or os.getenv("TABLE_NAME") or cfg.get("table") # Updated this line from previous turn
    timestamp_col= args.timestamp_col or os.getenv("TIMESTAMP_COL") or cfg.get("timestamp_col") # Updated this line

    # Validate required parameters for normal mode
    if not sqlite_path or not sqlite_path.is_file():
        logging.error("SQLite file not found: %s (required for uploader mode)", sqlite_path)
        sys.exit(1)
    if not storage_uri: # Should have been caught earlier if also in query mode, but double check for normal
        logging.error("Delta table URI (--storage-uri) not specified (required for uploader mode)")
        sys.exit(1)

    # Prepare state file directory
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / 'last_upload.json'
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                last_ts = pd.to_datetime(json.load(f).get('last_upload'), utc=True)
        except Exception:
            last_ts = pd.Timestamp('1970-01-01T00:00:00Z')
    else:
        last_ts = pd.Timestamp('1970-01-01T00:00:00Z')

    # Table and timestamp column introspection/override
    if table_name is None:
        # Only run table detection if not provided
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not tables:
            logging.error("No tables found in SQLite database.")
            sys.exit(1)
        if len(tables) > 1:
            logging.error("Multiple tables found in SQLite database: %s", tables)
            sys.exit(1)
        table_name = tables[0]
        logging.info("Detected table: %s", table_name)
    else:
        logging.info("Using user-supplied table: %s", table_name)

    if timestamp_col is None:
        # Only run timestamp detection if not provided
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}');")
        cols = cursor.fetchall()
        conn.close()
        ts_cols = [c[1] for c in cols if c[1].lower() == 'timestamp' or 'date' in (c[2] or '').lower()]
        if not ts_cols:
            logging.error("No suitable timestamp column found in table '%s'", table_name)
            sys.exit(1)
        timestamp_field = ts_cols[0]
        logging.info("Detected timestamp field: %s", timestamp_field)
    else:
        timestamp_field = timestamp_col
        logging.info("Using user-supplied timestamp column: %s", timestamp_field)

    logging.info("Starting continuous upload every %d seconds, initial timestamp=%s", interval, last_ts)
    base_name = sqlite_path.stem
    while True:
        try:
            # Read new data since last timestamp using introspected schema
            sql = f"SELECT * FROM {table_name} WHERE {timestamp_field} > ? ORDER BY {timestamp_field}"
            conn = sqlite3.connect(str(sqlite_path))
            df = pd.read_sql_query(sql, conn, params=[last_ts.isoformat()])
            conn.close()
            if df.empty:
                logging.info("No new records since %s", last_ts)
            else:
                # Data processing steps

                # Sanitize config loading
                enable_sanitize = args.enable_sanitize or os.getenv("ENABLE_SANITIZE", cfg.get("enable_sanitize", False))
                sanitize_config_source_value = args.sanitize_config # CLI has priority (always string)
                if sanitize_config_source_value == "{}": # Default from argparse might be "{}", check env if so
                    sanitize_config_source_value = os.getenv("SANITIZE_CONFIG") or cfg.get("sanitize_config")
                else: # CLI value was something other than default "{}"
                    pass # Keep CLI value

                if sanitize_config_source_value is None: # Not in CLI or ENV, try YAML
                     sanitize_config_source_value = cfg.get("sanitize_config")

                sanitize_config_dict = {} # Default
                if isinstance(sanitize_config_source_value, (dict, list)):
                    sanitize_config_dict = sanitize_config_source_value
                    logging.info("Loaded sanitize_config directly as structured YAML.")
                elif isinstance(sanitize_config_source_value, str) and sanitize_config_source_value.strip():
                    try:
                        sanitize_config_dict = json.loads(sanitize_config_source_value)
                        logging.info("Loaded sanitize_config by parsing string (JSON expected).")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse sanitize_config string '{sanitize_config_source_value}' as JSON: {e}. Using default {{}}.")
                elif sanitize_config_source_value is not None:
                    logging.warning(f"Unexpected type for sanitize_config: {type(sanitize_config_source_value)}. Using default {{}}.")
                else: # None
                    logging.info("sanitize_config not provided. Using default {{}}.")

                if enable_sanitize:
                    logging.info("Sanitizing data...")
                    df = sanitize_data(df, sanitize_config_dict)

                # Filter config loading
                enable_filter = args.enable_filter or os.getenv("ENABLE_FILTER", cfg.get("enable_filter", False))
                filter_config_source_value = args.filter_config # CLI
                if filter_config_source_value == "{}": # Default from argparse
                    filter_config_source_value = os.getenv("FILTER_CONFIG") or cfg.get("filter_config")
                else: # CLI value was not default
                    pass

                if filter_config_source_value is None: # Not in CLI or ENV
                    filter_config_source_value = cfg.get("filter_config")

                filter_config_dict = {} # Default
                if isinstance(filter_config_source_value, (dict, list)):
                    filter_config_dict = filter_config_source_value
                    logging.info("Loaded filter_config directly as structured YAML.")
                elif isinstance(filter_config_source_value, str) and filter_config_source_value.strip():
                    try:
                        filter_config_dict = json.loads(filter_config_source_value)
                        logging.info("Loaded filter_config by parsing string (JSON expected).")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse filter_config string '{filter_config_source_value}' as JSON: {e}. Using default {{}}.")
                elif filter_config_source_value is not None:
                    logging.warning(f"Unexpected type for filter_config: {type(filter_config_source_value)}. Using default {{}}.")
                else: # None
                    logging.info("filter_config not provided. Using default {{}}.")

                if enable_filter:
                    logging.info("Filtering data...")
                    df = filter_data(df, filter_config_dict)

                # Aggregate config loading
                enable_aggregate = args.enable_aggregate or os.getenv("ENABLE_AGGREGATE", cfg.get("enable_aggregate", False))
                aggregate_config_source_value = args.aggregate_config # CLI
                if aggregate_config_source_value == "{}": # Default from argparse
                    aggregate_config_source_value = os.getenv("AGGREGATE_CONFIG") or cfg.get("aggregate_config")
                else: # CLI value was not default
                    pass
                
                if aggregate_config_source_value is None: # Not in CLI or ENV
                    aggregate_config_source_value = cfg.get("aggregate_config")

                aggregate_config_dict = {} # Default
                if isinstance(aggregate_config_source_value, (dict, list)):
                    aggregate_config_dict = aggregate_config_source_value
                    logging.info("Loaded aggregate_config directly as structured YAML.")
                elif isinstance(aggregate_config_source_value, str) and aggregate_config_source_value.strip():
                    try:
                        aggregate_config_dict = json.loads(aggregate_config_source_value)
                        logging.info("Loaded aggregate_config by parsing string (JSON expected).")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse aggregate_config string '{aggregate_config_source_value}' as JSON: {e}. Using default {{}}.")
                elif aggregate_config_source_value is not None:
                    logging.warning(f"Unexpected type for aggregate_config: {type(aggregate_config_source_value)}. Using default {{}}.")
                else: # None
                    logging.info("aggregate_config not provided. Using default {{}}.")
                
                if enable_aggregate:
                    logging.info("Aggregating data...")
                    df = aggregate_data(df, aggregate_config_dict)
                
                # Append to Delta table
                logging.info("Appending %d new records to Delta table %s", len(df), storage_uri)
                # Pass AWS_REGION via storage_options if set
                storage_opts = {}
                if os.getenv('AWS_REGION'):
                    storage_opts['AWS_REGION'] = os.getenv('AWS_REGION')
                write_deltalake(
                    table_or_uri=storage_uri,
                    data=df,
                    mode='append',
                    storage_options=storage_opts
                )
                # Update state timestamp
                last_ts = df[timestamp_field].max()
                with open(state_file, 'w') as f:
                    json.dump({'last_upload': last_ts.isoformat()}, f)
        except KeyboardInterrupt:
            logging.info("Interrupted by user, exiting.")
            break
        except Exception as e:
            logging.error("Error in upload cycle: %s", e, exc_info=True)
        if once:
            break
        time.sleep(interval)

if __name__ == '__main__':
    main()
