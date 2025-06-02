#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.0.0",
#     "pyarrow>=12.0.0",
#     "pyyaml>=6.0",
#     "databricks-sql-connector>=2.0.0"
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
import time
from pathlib import Path

import databricks.sql
import pandas as pd
import yaml

# deltalake imports removed


# New helper function for quoting Databricks SQL identifiers
def quote_databricks_identifier(name: str) -> str:
    """Quotes an identifier for Databricks SQL using backticks.
    Escapes existing backticks within the name.
    """
    return f"`{name.replace('`', '``')}`"


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

                # Get processing mode
                processing_mode = (
                    args.processing_mode
                    or os.getenv("PROCESSING_MODE")
                    or cfg.get("processing_mode", "schematized")
                )

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

                if processing_mode == "raw":
                    processed_df = process_raw_data(df, timestamp_field)
                elif processing_mode == "schematized":
                    processed_df = schematize_data(df)
                elif processing_mode == "sanitized":
                    processed_df = sanitize_data(df, gps_fuzzing_config)
                elif processing_mode == "aggregated":
                    processed_df = aggregate_data(df, aggregate_config)
                elif processing_mode == "emergency":
                    processed_df = filter_emergency_data(df, emergency_config)
                else:
                    logging.error(f"Unknown processing mode: {processing_mode}")
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

                        # Determine target table based on processing mode
                        table_suffix_map = {
                            "raw": "0_raw",
                            "schematized": "1_schematized",
                            "sanitized": "2_sanitized",
                            "aggregated": "3_aggregated",
                            "emergency": "4_emergency",
                        }

                        table_suffix = table_suffix_map.get(processing_mode)
                        if not table_suffix:
                            logging.error(
                                f"No table mapping for processing mode: {processing_mode}"
                            )
                            continue

                        # Construct the full table name with new naming convention
                        final_table_name = f"{databricks_table}_{table_suffix}"
                        table_name_qualified = f"{quote_databricks_identifier(databricks_database)}.{quote_databricks_identifier(final_table_name)}"

                        logging.info(
                            f"Routing data to table: {table_name_qualified} (processing mode: {processing_mode})"
                        )

                        # Add databricks-specific columns for all modes
                        processed_df["databricks_inserted_at"] = pd.Timestamp.now()

                        # Note: The 'id' column is not added here as it's defined in the schema
                        # without GENERATED ALWAYS AS IDENTITY, so Databricks won't auto-generate it.
                        # The uploader will need to handle ID generation if required.

                        columns = [
                            quote_databricks_identifier(col)
                            for col in processed_df.columns
                        ]
                        placeholders = ", ".join(["?"] * len(columns))
                        insert_sql_template = f"INSERT INTO {table_name_qualified} ({', '.join(columns)}) VALUES ({placeholders})"

                        data_to_insert = [
                            tuple(row) for row in processed_df.to_numpy()
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
