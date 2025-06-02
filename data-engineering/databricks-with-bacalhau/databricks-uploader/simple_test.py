#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sql-connector>=2.0.0",
#     "pyyaml>=6.0",
#     "pandas>=2.0.0"
# ]
# ///
"""
Test script for verifying Databricks table setup for the SQLite to Databricks uploader.
Ensures all required tables exist for different processing scenarios.
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import databricks.sql
import yaml


def quote_databricks_identifier(name: str) -> str:
    """Quotes an identifier for Databricks SQL using backticks."""
    return f"`{name.replace('`', '``')}`"


def get_sqlite_schema(sqlite_path: str, table_name: str) -> list:
    """Get the schema of a SQLite table."""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    try:
        # Get table info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        if not columns:
            raise ValueError(f"Table '{table_name}' not found in SQLite database")

        # Returns tuples of (cid, name, type, notnull, dflt_value, pk)
        return columns
    finally:
        conn.close()


def sqlite_to_databricks_type(sqlite_type: str) -> str:
    """Convert SQLite data types to Databricks SQL types."""
    type_mapping = {
        "INTEGER": "BIGINT",
        "REAL": "DOUBLE",
        "TEXT": "STRING",
        "BLOB": "BINARY",
        "NUMERIC": "DECIMAL",
        "DATETIME": "TIMESTAMP",
        "DATE": "DATE",
        "TIME": "STRING",
        "BOOLEAN": "BOOLEAN",
    }

    # SQLite types can have modifiers like VARCHAR(255)
    base_type = sqlite_type.upper().split("(")[0]
    return type_mapping.get(base_type, "STRING")


def create_databricks_tables(config, cursor):
    """Create all required Databricks tables for different processing scenarios."""
    database = config["databricks_database"]
    base_table = config["databricks_table"]
    sqlite_path = config.get("sqlite")
    sqlite_table = config.get("sqlite_table_name", "sensor_readings")

    # Ensure database exists
    print(f"\nEnsuring database '{database}' exists...")
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS {quote_databricks_identifier(database)}"
    )
    cursor.execute(f"USE {quote_databricks_identifier(database)}")
    print(f"✓ Using database: {database}")

    # Get SQLite schema
    print(f"\nReading schema from SQLite database: {sqlite_path}")
    sqlite_columns = get_sqlite_schema(sqlite_path, sqlite_table)
    print(f"✓ Found {len(sqlite_columns)} columns in SQLite table '{sqlite_table}'")

    # Build schematized schema from SQLite
    schematized_columns = []
    numeric_fields = []  # Track numeric fields for aggregation

    for col in sqlite_columns:
        col_name = col[1]
        col_type = col[2]
        databricks_type = sqlite_to_databricks_type(col_type)

        # Rename 'id' to 'reading_id' to avoid conflicts
        if col_name == "id":
            col_name = "reading_id"

        schematized_columns.append(f"{col_name} {databricks_type}")

        # Track numeric fields for aggregation
        if databricks_type in ["BIGINT", "DOUBLE", "DECIMAL", "INT"]:
            # Only aggregate meaningful numeric fields
            if col_name not in [
                "reading_id",
                "id",
                "status_code",
                "anomaly_flag",
                "synced",
            ]:
                numeric_fields.append(col_name)

    # Add Databricks-specific columns (without defaults to avoid the error)
    schematized_columns.append("id BIGINT")
    schematized_columns.append("databricks_inserted_at TIMESTAMP")

    schematized_schema = ",\n        ".join(schematized_columns)

    # Define schemas for each table type
    raw_schema = """
        id BIGINT,
        timestamp TIMESTAMP,
        reading_string STRING,
        databricks_inserted_at TIMESTAMP
    """

    # Sanitized is same as schematized (fuzzing will be done during processing)
    sanitized_schema = schematized_schema

    # Emergency is same as sanitized (filtering will be done during processing)
    emergency_schema = sanitized_schema

    # Build aggregated schema
    aggregated_columns = [
        "id BIGINT",
        "start_window TIMESTAMP",
        "end_window TIMESTAMP",
        "sensor_id STRING",  # Keep sensor_id for grouping
        "location STRING",  # Keep location for grouping
    ]

    # Add min/max/avg for each numeric field
    for field in numeric_fields:
        aggregated_columns.append(f"{field}_min DOUBLE")
        aggregated_columns.append(f"{field}_max DOUBLE")
        aggregated_columns.append(f"{field}_avg DOUBLE")

    aggregated_columns.append("reading_count BIGINT")
    aggregated_columns.append("databricks_inserted_at TIMESTAMP")

    aggregated_schema = ",\n        ".join(aggregated_columns)

    # Table configurations - updated naming convention
    tables = [
        {
            "name": f"{base_table}_0_raw",
            "schema": raw_schema,
            "description": "Raw sensor data (one string per reading)",
        },
        {
            "name": f"{base_table}_1_schematized",
            "schema": schematized_schema,
            "description": "Schematized sensor data matching SQLite structure",
        },
        {
            "name": f"{base_table}_2_sanitized",
            "schema": sanitized_schema,
            "description": "Sanitized sensor data with fuzzy GPS",
        },
        {
            "name": f"{base_table}_3_aggregated",
            "schema": aggregated_schema,
            "description": "Aggregated sensor data with time windows",
        },
        {
            "name": f"{base_table}_4_emergency",
            "schema": emergency_schema,
            "description": "Emergency data (anomalies only)",
        },
    ]

    print(f"\nCreating tables for base table name: {base_table}")
    print("=" * 60)

    created_tables = []
    for table_config in tables:
        table_name = table_config["name"]
        qualified_name = f"{quote_databricks_identifier(database)}.{quote_databricks_identifier(table_name)}"

        try:
            # Drop table if requested
            if config.get("drop_existing", False):
                print(f"\nDropping table if exists: {qualified_name}")
                cursor.execute(f"DROP TABLE IF EXISTS {qualified_name}")

            # Create table
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {qualified_name} (
                    {table_config["schema"]}
                ) USING DELTA
            """

            print(f"\nCreating table: {qualified_name}")
            print(f"Description: {table_config['description']}")
            cursor.execute(create_sql)

            # Verify table exists
            cursor.execute(f"DESCRIBE TABLE {qualified_name}")
            columns = cursor.fetchall()

            print(f"✓ Table created successfully with {len(columns)} columns")
            created_tables.append(qualified_name)

        except Exception as e:
            print(f"✗ Error creating table {qualified_name}: {e}")
            raise

    # Print aggregated fields info
    print(f"\n✓ Identified {len(numeric_fields)} numeric fields for aggregation:")
    for field in numeric_fields:
        print(f"  - {field} → {field}_min, {field}_max, {field}_avg")

    return created_tables


def verify_table_routing(config, cursor):
    """Verify that all tables exist and test the routing logic."""
    database = config["databricks_database"]
    base_table = config["databricks_table"]

    print("\n\nVerifying Table Routing Logic")
    print("=" * 60)

    # Test scenarios - updated for new table structure
    scenarios = [
        {
            "name": "Raw Data (unprocessed strings)",
            "processing_config": {"processing_mode": "raw"},
            "expected_table": f"{base_table}_0_raw",
        },
        {
            "name": "Schematized Data (parsed and structured)",
            "processing_config": {"processing_mode": "schematized"},
            "expected_table": f"{base_table}_1_schematized",
        },
        {
            "name": "Sanitized Data (fuzzy GPS)",
            "processing_config": {"processing_mode": "sanitized"},
            "expected_table": f"{base_table}_2_sanitized",
        },
        {
            "name": "Aggregated Data (time windows)",
            "processing_config": {"processing_mode": "aggregated"},
            "expected_table": f"{base_table}_3_aggregated",
        },
        {
            "name": "Emergency Data (anomalies only)",
            "processing_config": {"processing_mode": "emergency"},
            "expected_table": f"{base_table}_4_emergency",
        },
    ]

    all_passed = True

    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"Processing config: {scenario['processing_config']}")

        # Verify table exists
        qualified_table = f"{quote_databricks_identifier(database)}.{quote_databricks_identifier(scenario['expected_table'])}"
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {qualified_table}")
            count = cursor.fetchone()[0]
            print(
                f"✓ PASS: Table '{scenario['expected_table']}' exists (contains {count} rows)"
            )
        except Exception as e:
            print(f"✗ FAIL: Table '{scenario['expected_table']}' not accessible: {e}")
            all_passed = False

    return all_passed


def test_query_tables(config, cursor):
    """Run test queries against each table type."""
    database = config["databricks_database"]
    base_table = config["databricks_table"]

    print("\n\nTesting Table Queries")
    print("=" * 60)

    tables = [
        f"{base_table}_0_raw",
        f"{base_table}_1_schematized",
        f"{base_table}_2_sanitized",
        f"{base_table}_3_aggregated",
        f"{base_table}_4_emergency",
    ]

    for table in tables:
        qualified_table = f"{quote_databricks_identifier(database)}.{quote_databricks_identifier(table)}"
        print(f"\nQuerying {table}:")

        try:
            # Get row count
            cursor.execute(f"SELECT COUNT(*) as count FROM {qualified_table}")
            count = cursor.fetchone()[0]
            print(f"  Row count: {count}")

            # Get table schema
            cursor.execute(f"DESCRIBE TABLE {qualified_table}")
            columns = cursor.fetchall()
            print(f"  Columns: {', '.join([col.col_name for col in columns])}")

            # Show sample data if any exists
            if count > 0:
                cursor.execute(f"SELECT * FROM {qualified_table} LIMIT 5")
                samples = cursor.fetchall()
                print(f"  Sample records: {len(samples)}")

        except Exception as e:
            print(f"  Error querying table: {e}")


def generate_example_config(config_path):
    """Generate an example configuration file for reference."""
    example_config = {
        "databricks_host": "your-workspace.cloud.databricks.com",
        "databricks_http_path": "/sql/1.0/warehouses/your_warehouse_id",
        "databricks_token": "dapi...",  # Should use env var
        "databricks_database": "sensor_data",
        "databricks_table": "sensor_readings",
        "sqlite": "/path/to/sensor_data.db",
        "sqlite_table_name": "sensor_readings",
        "timestamp_col": "timestamp",
        "state_dir": "./state",
        "interval": 300,
        # Processing mode - one of: raw, schematized, sanitized, aggregated, emergency
        "processing_mode": "schematized",
        # GPS fuzzing configuration for sanitized mode
        "gps_fuzzing": {
            "decimal_places": 2,  # Reduce GPS precision to 2 decimal places
        },
        # Aggregation configuration
        "aggregate_config": {
            "window_minutes": 60,  # 1 hour windows
            "group_by": ["sensor_id", "location"],
        },
        # Emergency filter configuration
        "emergency_config": {
            "anomaly_column": "anomaly_flag",  # Column that indicates anomalies
            "anomaly_value": 1,  # Value that indicates an anomaly
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)

    print(f"\nGenerated example configuration at: {config_path}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test and verify Databricks table setup for SQLite to Databricks uploader"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the YAML configuration file (e.g., databricks-uploader-config.yaml)",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create all required Databricks tables for different scenarios",
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing tables before creating (use with caution)",
    )
    parser.add_argument(
        "--verify-routing", action="store_true", help="Verify table routing logic"
    )
    parser.add_argument(
        "--test-queries",
        action="store_true",
        help="Run test queries against all tables",
    )
    parser.add_argument(
        "--generate-config",
        type=str,
        help="Generate an example configuration file at the specified path",
    )
    return parser.parse_args()


def main():
    """Main function to run Databricks table verification and setup."""
    args = parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("Databricks Table Setup and Verification Tool")
    print("=" * 60)

    # Generate example config if requested
    if args.generate_config:
        generate_example_config(args.generate_config)
        return

    # Load configuration
    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"ERROR: Configuration file not found at {config_path}")
        sys.exit(1)

    print(f"Loading configuration from: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Add command line options to config
    config["drop_existing"] = args.drop_existing

    # Validate required configuration
    required_fields = [
        "databricks_host",
        "databricks_http_path",
        "databricks_token",
        "databricks_database",
        "databricks_table",
        "sqlite",
        "sqlite_table_name",
    ]

    missing_fields = [field for field in required_fields if not config.get(field)]
    if missing_fields:
        print(
            f"ERROR: Missing required configuration fields: {', '.join(missing_fields)}"
        )
        sys.exit(1)

    # Validate SQLite file exists
    sqlite_path = Path(config["sqlite"])
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    # Connect to Databricks
    connection = None
    try:
        print(f"\nConnecting to Databricks at {config['databricks_host']}...")
        connection = databricks.sql.connect(
            server_hostname=config["databricks_host"],
            http_path=config["databricks_http_path"],
            access_token=config["databricks_token"],
        )
        cursor = connection.cursor()
        print("✓ Successfully connected to Databricks")

        # Run requested operations
        if args.create_tables:
            created_tables = create_databricks_tables(config, cursor)
            print(f"\n✓ Created {len(created_tables)} tables successfully")

        if args.verify_routing:
            all_passed = verify_table_routing(config, cursor)
            if all_passed:
                print("\n✓ All table routing tests passed")
            else:
                print("\n✗ Some table routing tests failed")

        if args.test_queries:
            test_query_tables(config, cursor)

        # If no specific action requested, show current status
        if not any([args.create_tables, args.verify_routing, args.test_queries]):
            print("\nCurrent Table Status:")
            test_query_tables(config, cursor)

        print("\n" + "=" * 60)
        print("Summary:")
        print(f"Database: {config['databricks_database']}")
        print(f"Base table name: {config['databricks_table']}")
        print("\nTable types:")
        print(f"  1. {config['databricks_table']}_0_raw - Raw string data")
        print(
            f"  2. {config['databricks_table']}_1_schematized - Parsed and structured data"
        )
        print(f"  3. {config['databricks_table']}_2_sanitized - Data with fuzzy GPS")
        print(
            f"  4. {config['databricks_table']}_3_aggregated - Time-windowed aggregations"
        )
        print(f"  5. {config['databricks_table']}_4_emergency - Anomalies only")

    except Exception as e:
        print(f"\nERROR: {e}")
        logging.error("Failed to complete operation", exc_info=True)
        sys.exit(1)

    finally:
        if connection:
            cursor.close()
            connection.close()
            print("\nConnection closed.")


if __name__ == "__main__":
    main()
