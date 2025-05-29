#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.0.0",
#     "pyarrow>=12.0.0",
#     "pyyaml>=6.0",
#     "databricks-sql-connector>=2.0.0"
# ]
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
import time
from pathlib import Path

import databricks.sql
import pandas as pd
import yaml
from databricks.sql.utils import ParamEscaper

# deltalake imports removed


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
    # New arguments for data processing
    p.add_argument(
        "--enable-sanitize", action="store_true", help="Enable data sanitization"
    )
    p.add_argument(
        "--sanitize-config", default="{}", help="JSON config string for sanitization"
    )
    p.add_argument("--enable-filter", action="store_true", help="Enable data filtering")
    p.add_argument(
        "--filter-config", default="{}", help="JSON config string for filtering"
    )
    p.add_argument(
        "--enable-aggregate", action="store_true", help="Enable data aggregation"
    )
    p.add_argument(
        "--aggregate-config", default="{}", help="JSON config string for aggregation"
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
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    # 1) load YAML if supplied
    cfg = {}
    if args.config:
        cfg = yaml.safe_load(Path(args.config).read_text())

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
                # Increase timeout to 1 hour for large operations
                # Default is 900 seconds (15 minutes) which can be too short for large datasets
                _retry_timeout_seconds=3600,
                # Also increase the socket timeout
                _socket_timeout_seconds=1800,
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
                    f"USE {ParamEscaper.escape_path(databricks_database)}"
                )
                logging.info(f"Using database: {databricks_database}")

                print(f"\n--- Tables in Database '{databricks_database}' ---")
                cursor_db_query.execute(
                    f"SHOW TABLES IN {ParamEscaper.escape_path(databricks_database)}"
                )
                print_query_results(cursor_db_query)

                qualified_table_name = f"{ParamEscaper.escape_path(databricks_database)}.{ParamEscaper.escape_path(databricks_table)}"
                print(f"\n--- Description for Table '{qualified_table_name}' ---")
                cursor_db_query.execute(
                    f"DESCRIBE TABLE EXTENDED {qualified_table_name}"
                )
                print_query_results(cursor_db_query)

                print(f"\n--- Row Count for Table '{qualified_table_name}' ---")
                cursor_db_query.execute(
                    f"SELECT COUNT(*) AS row_count FROM {qualified_table_name}"
                )
                print_query_results(cursor_db_query)

            else:  # General SQL query
                logging.info(f"Executing user-provided query: {args.run_query}")
                # Set current database first, in case the query doesn't fully qualify table names
                try:
                    cursor_db_query.execute(
                        f"USE {ParamEscaper.escape_path(databricks_database)}"
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
            # Read new data since last timestamp using introspected schema
            sql = f"SELECT * FROM {sqlite_table_name} WHERE {timestamp_field} > ? ORDER BY {timestamp_field}"
            conn_sqlite_data = sqlite3.connect(str(sqlite_path))
            df = pd.read_sql_query(sql, conn_sqlite_data, params=[last_ts.isoformat()])
            conn_sqlite_data.close()
            if df.empty:
                logging.info("No new records since %s", last_ts)
            else:
                # Data processing steps

                # Sanitize config loading
                enable_sanitize = args.enable_sanitize or os.getenv(
                    "ENABLE_SANITIZE", cfg.get("enable_sanitize", False)
                )
                sanitize_config_source_value = (
                    args.sanitize_config
                )  # CLI has priority (always string)
                if (
                    sanitize_config_source_value == "{}"
                ):  # Default from argparse might be "{}", check env if so
                    sanitize_config_source_value = os.getenv(
                        "SANITIZE_CONFIG"
                    ) or cfg.get("sanitize_config")
                else:  # CLI value was something other than default "{}"
                    pass  # Keep CLI value

                if sanitize_config_source_value is None:  # Not in CLI or ENV, try YAML
                    sanitize_config_source_value = cfg.get("sanitize_config")

                sanitize_config_dict = {}  # Default
                if isinstance(sanitize_config_source_value, (dict, list)):
                    sanitize_config_dict = sanitize_config_source_value
                    logging.info("Loaded sanitize_config directly as structured YAML.")
                elif (
                    isinstance(sanitize_config_source_value, str)
                    and sanitize_config_source_value.strip()
                ):
                    try:
                        sanitize_config_dict = json.loads(sanitize_config_source_value)
                        logging.info(
                            "Loaded sanitize_config by parsing string (JSON expected)."
                        )
                    except json.JSONDecodeError as e:
                        logging.warning(
                            f"Failed to parse sanitize_config string '{sanitize_config_source_value}' as JSON: {e}. Using default {{}}."
                        )
                elif sanitize_config_source_value is not None:
                    logging.warning(
                        f"Unexpected type for sanitize_config: {type(sanitize_config_source_value)}. Using default {{}}."
                    )
                else:  # None
                    logging.info("sanitize_config not provided. Using default {{}}.")

                if enable_sanitize:
                    logging.info("Sanitizing data...")
                    df = sanitize_data(df, sanitize_config_dict)

                # Filter config loading
                enable_filter = args.enable_filter or os.getenv(
                    "ENABLE_FILTER", cfg.get("enable_filter", False)
                )
                filter_config_source_value = args.filter_config  # CLI
                if filter_config_source_value == "{}":  # Default from argparse
                    filter_config_source_value = os.getenv("FILTER_CONFIG") or cfg.get(
                        "filter_config"
                    )
                else:  # CLI value was not default
                    pass

                if filter_config_source_value is None:  # Not in CLI or ENV
                    filter_config_source_value = cfg.get("filter_config")

                filter_config_dict = {}  # Default
                if isinstance(filter_config_source_value, (dict, list)):
                    filter_config_dict = filter_config_source_value
                    logging.info("Loaded filter_config directly as structured YAML.")
                elif (
                    isinstance(filter_config_source_value, str)
                    and filter_config_source_value.strip()
                ):
                    try:
                        filter_config_dict = json.loads(filter_config_source_value)
                        logging.info(
                            "Loaded filter_config by parsing string (JSON expected)."
                        )
                    except json.JSONDecodeError as e:
                        logging.warning(
                            f"Failed to parse filter_config string '{filter_config_source_value}' as JSON: {e}. Using default {{}}."
                        )
                elif filter_config_source_value is not None:
                    logging.warning(
                        f"Unexpected type for filter_config: {type(filter_config_source_value)}. Using default {{}}."
                    )
                else:  # None
                    logging.info("filter_config not provided. Using default {{}}.")

                if enable_filter:
                    logging.info("Filtering data...")
                    df = filter_data(df, filter_config_dict)

                # Aggregate config loading
                enable_aggregate = args.enable_aggregate or os.getenv(
                    "ENABLE_AGGREGATE", cfg.get("enable_aggregate", False)
                )
                aggregate_config_source_value = args.aggregate_config  # CLI
                if aggregate_config_source_value == "{}":  # Default from argparse
                    aggregate_config_source_value = os.getenv(
                        "AGGREGATE_CONFIG"
                    ) or cfg.get("aggregate_config")
                else:  # CLI value was not default
                    pass

                if aggregate_config_source_value is None:  # Not in CLI or ENV
                    aggregate_config_source_value = cfg.get("aggregate_config")

                aggregate_config_dict = {}  # Default
                if isinstance(aggregate_config_source_value, (dict, list)):
                    aggregate_config_dict = aggregate_config_source_value
                    logging.info("Loaded aggregate_config directly as structured YAML.")
                elif (
                    isinstance(aggregate_config_source_value, str)
                    and aggregate_config_source_value.strip()
                ):
                    try:
                        aggregate_config_dict = json.loads(
                            aggregate_config_source_value
                        )
                        logging.info(
                            "Loaded aggregate_config by parsing string (JSON expected)."
                        )
                    except json.JSONDecodeError as e:
                        logging.warning(
                            f"Failed to parse aggregate_config string '{aggregate_config_source_value}' as JSON: {e}. Using default {{}}."
                        )
                elif aggregate_config_source_value is not None:
                    logging.warning(
                        f"Unexpected type for aggregate_config: {type(aggregate_config_source_value)}. Using default {{}}."
                    )
                else:  # None
                    logging.info("aggregate_config not provided. Using default {{}}.")

                if enable_aggregate:
                    logging.info("Aggregating data...")
                    df = aggregate_data(df, aggregate_config_dict)

                upload_successful = False
                if not df.empty:
                    conn_db = None
                    cursor_db = None
                    try:
                        conn_db = databricks.sql.connect(
                            server_hostname=databricks_host,
                            http_path=databricks_http_path,
                            access_token=databricks_token,
                            # Increase timeout to 1 hour for large operations
                            # Default is 900 seconds (15 minutes) which can be too short for large datasets
                            _retry_timeout_seconds=3600,
                            # Also increase the socket timeout
                            _socket_timeout_seconds=1800,
                        )
                        cursor_db = conn_db.cursor()
                        logging.info(
                            f"Successfully connected to Databricks: {databricks_host}"
                        )

                        # Set current database
                        cursor_db.execute(
                            f"USE {ParamEscaper.escape_path(databricks_database)}"
                        )
                        logging.info(f"Using database: {databricks_database}")

                        # Prepare for batch insert
                        table_name_qualified = f"{ParamEscaper.escape_path(databricks_database)}.{ParamEscaper.escape_path(databricks_table)}"

                        columns = [
                            ParamEscaper.escape_identifier(col) for col in df.columns
                        ]
                        placeholders = ", ".join(["%s"] * len(columns))
                        insert_sql_template = f"INSERT INTO {table_name_qualified} ({', '.join(columns)}) VALUES ({placeholders})"

                        data_to_insert = [
                            tuple(row) for row in df.to_numpy()
                        ]  # Convert DataFrame rows to tuples

                        batch_size = 500  # Configurable or fixed batch size
                        num_batches = (
                            len(data_to_insert) + batch_size - 1
                        ) // batch_size

                        logging.info(
                            f"Preparing to insert {len(data_to_insert)} records in {num_batches} batches of size {batch_size} into {table_name_qualified}..."
                        )

                        for i in range(num_batches):
                            batch_data = data_to_insert[
                                i * batch_size : (i + 1) * batch_size
                            ]
                            cursor_db.executemany(insert_sql_template, batch_data)
                            logging.info(
                                f"Inserted batch {i + 1}/{num_batches} ({len(batch_data)} records)."
                            )

                        # conn_db.commit() # Databricks SQL Connector typically autocommits DML like INSERT
                        logging.info(
                            f"Successfully inserted {len(data_to_insert)} new records into Databricks table {table_name_qualified}"
                        )
                        upload_successful = True

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
                else:
                    logging.warning(
                        "Upload to Databricks failed or was incomplete. State timestamp will not be updated."
                    )

        except KeyboardInterrupt:
            logging.info("Interrupted by user, exiting.")
            break
        except Exception as e:
            logging.error("Error in upload cycle: %s", e, exc_info=True)
        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
