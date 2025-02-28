#!/usr/bin/env python3
# tune_postgres.py - A tool for optimizing PostgreSQL performance

import argparse
import logging
import os
import random
import string
import sys
import time
from datetime import datetime, timezone
from io import StringIO

import psycopg2
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Function to read config
def read_config(config_path):
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        if "postgresql" not in config:
            raise ValueError("Missing 'postgresql' section in config")
        required_fields = ["host", "port", "user", "password", "database"]
        missing = [f for f in required_fields if f not in config["postgresql"]]
        if missing:
            raise ValueError(
                f"Missing required PostgreSQL fields: {', '.join(missing)}"
            )
        return config
    except Exception as e:
        logger.error(f"Error reading config: {str(e)}")
        sys.exit(1)


# Function to get database connection
def get_db_connection(pg_config):
    connect_args = {
        "host": pg_config["host"],
        "port": pg_config["port"],
        "user": pg_config["user"],
        "password": pg_config["password"],
        "database": pg_config["database"],
        "sslmode": "require",
    }

    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise


# Function to apply session-level optimizations
def apply_session_optimizations(conn):
    try:
        with conn.cursor() as cur:
            # Try to set various optimizations
            optimizations = [
                ("statement_timeout", "120000"),  # 2 minutes
                ("synchronous_commit", "OFF"),
                ("work_mem", "'128MB'"),
                ("maintenance_work_mem", "'256MB'"),
                ("effective_io_concurrency", "200"),
                ("random_page_cost", "1.1"),
            ]

            success_count = 0
            for setting, value in optimizations:
                try:
                    cur.execute(f"SET {setting} = {value}")
                    logger.info(f"Successfully set {setting} = {value}")
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Could not set {setting}: {str(e)}")

            logger.info(
                f"Applied {success_count}/{len(optimizations)} session-level optimizations"
            )
    except Exception as e:
        logger.error(f"Error applying session optimizations: {str(e)}")


# Function to check current PostgreSQL settings
def check_postgres_settings(pg_config):
    try:
        conn = get_db_connection(pg_config)
        logger.info(
            f"Connected to PostgreSQL at {pg_config['host']}:{pg_config['port']}"
        )

        with conn.cursor() as cur:
            # Check PostgreSQL version
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            logger.info(f"PostgreSQL version: {version}")

            # Check if this is a Citus cluster
            is_citus = False
            try:
                cur.execute("SELECT citus_version()")
                citus_version = cur.fetchone()[0]
                logger.info(f"Citus version: {citus_version}")
                is_citus = True
            except:
                logger.info("This is not a Citus cluster")

            # Check important settings
            settings = [
                "max_connections",
                "shared_buffers",
                "effective_cache_size",
                "maintenance_work_mem",
                "checkpoint_completion_target",
                "wal_buffers",
                "default_statistics_target",
                "random_page_cost",
                "effective_io_concurrency",
                "work_mem",
                "min_wal_size",
                "max_wal_size",
                "max_worker_processes",
                "max_parallel_workers_per_gather",
                "max_parallel_workers",
                "max_parallel_maintenance_workers",
            ]

            logger.info("Current PostgreSQL settings:")
            for setting in settings:
                try:
                    cur.execute(f"SHOW {setting}")
                    value = cur.fetchone()[0]
                    logger.info(f"  {setting} = {value}")
                except:
                    logger.info(f"  {setting} = [not available]")

            # Check user privileges
            cur.execute("SELECT current_user")
            current_user = cur.fetchone()[0]
            logger.info(f"Connected as user: {current_user}")

            cur.execute("SELECT usesuper FROM pg_user WHERE usename = current_user")
            is_superuser = cur.fetchone()[0]
            logger.info(f"User is superuser: {is_superuser}")

            # Check table structure
            try:
                cur.execute("SELECT COUNT(*) FROM log_analytics.raw_logs")
                row_count = cur.fetchone()[0]
                logger.info(f"log_analytics.raw_logs contains {row_count} rows")

                # Check for indexes
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'log_analytics' AND tablename = 'raw_logs'
                """)
                indexes = cur.fetchall()
                if indexes:
                    logger.info("Indexes on log_analytics.raw_logs:")
                    for idx_name, idx_def in indexes:
                        logger.info(f"  {idx_name}: {idx_def}")
                else:
                    logger.info("No indexes found on log_analytics.raw_logs")

                # Check if table is distributed (Citus)
                if is_citus:
                    try:
                        cur.execute("""
                            SELECT logicalrelid, partmethod, partkey
                            FROM pg_dist_partition
                            WHERE logicalrelid = 'log_analytics.raw_logs'::regclass
                        """)
                        dist_info = cur.fetchone()
                        if dist_info:
                            logger.info(f"Table is distributed: {dist_info}")
                        else:
                            logger.info("Table is not distributed")
                    except:
                        logger.info("Could not check distribution info")
            except Exception as e:
                logger.warning(f"Could not check table structure: {str(e)}")

        conn.close()
    except Exception as e:
        logger.error(f"Error checking PostgreSQL settings: {str(e)}")


# Function to test COPY performance
def test_copy_performance(pg_config, batch_sizes):
    try:
        conn = get_db_connection(pg_config)
        logger.info(f"Testing COPY performance with batch sizes: {batch_sizes}")

        # Apply session optimizations
        apply_session_optimizations(conn)

        # Create a temporary table for testing
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    CREATE TEMP TABLE temp_logs (
                        raw_line TEXT,
                        upload_time TIMESTAMP WITH TIME ZONE
                    )
                """)
                conn.commit()
                logger.info("Created temporary table for testing")
            except Exception as e:
                logger.warning(f"Could not create temp table: {str(e)}")
                logger.info("Will use log_analytics.raw_logs for testing")
                use_temp_table = False
            else:
                use_temp_table = True

            table_name = "temp_logs" if use_temp_table else "log_analytics.raw_logs"

            # Generate some random data for testing
            def generate_test_data(size):
                data = StringIO()
                timestamp = datetime.now(timezone.utc).isoformat()
                for i in range(size):
                    # Generate a random log line
                    log_line = f"TEST LOG {i}: " + "".join(
                        random.choices(string.ascii_letters + string.digits, k=50)
                    )
                    escaped_line = (
                        log_line.replace("\\", "\\\\")
                        .replace("\t", "\\t")
                        .replace("\n", "\\n")
                    )
                    data.write(f"{escaped_line}\t{timestamp}\n")
                data.seek(0)
                return data

            # Test each batch size
            results = []
            for size in batch_sizes:
                logger.info(f"Testing batch size: {size}")

                # Generate test data
                test_data = generate_test_data(size)

                # Measure COPY performance
                try:
                    start_time = time.time()
                    cur.copy_expert(
                        f"COPY {table_name} (raw_line, upload_time) FROM STDIN WITH DELIMITER E'\\t'",
                        test_data,
                    )
                    conn.commit()
                    end_time = time.time()

                    duration = end_time - start_time
                    rows_per_sec = size / duration if duration > 0 else 0

                    logger.info(
                        f"Batch size {size}: {duration:.2f} seconds ({rows_per_sec:.1f} rows/sec)"
                    )
                    results.append((size, duration, rows_per_sec))
                except Exception as e:
                    logger.error(f"Error testing batch size {size}: {str(e)}")

            # Clean up temp table
            if use_temp_table:
                try:
                    cur.execute("DROP TABLE temp_logs")
                    conn.commit()
                    logger.info("Dropped temporary table")
                except Exception as e:
                    logger.warning(f"Could not drop temp table: {str(e)}")

            # Print summary
            if results:
                logger.info("\nCOPY Performance Summary:")
                logger.info("------------------------")
                logger.info("Batch Size | Duration (s) | Rows/Second")
                logger.info("------------------------")
                for size, duration, rows_per_sec in results:
                    logger.info(f"{size:10} | {duration:12.2f} | {rows_per_sec:11.1f}")

                # Find optimal batch size
                optimal_size, _, optimal_rate = max(results, key=lambda x: x[2])
                logger.info(
                    f"\nOptimal batch size: {optimal_size} ({optimal_rate:.1f} rows/sec)"
                )

                # Recommendations
                if optimal_rate < 100:
                    logger.info("\nPerformance is very slow. Consider:")
                    logger.info("1. Checking Azure CosmosDB scaling limits")
                    logger.info("2. Using unlogged tables")
                    logger.info("3. Dropping indexes during bulk loading")
                    logger.info("4. Using alternative storage solutions for logs")
                elif optimal_rate < 1000:
                    logger.info("\nPerformance is moderate. Consider:")
                    logger.info(
                        "1. Using the optimal batch size in your uploader script"
                    )
                    logger.info("2. Checking for resource contention")
                    logger.info("3. Optimizing table structure")
                else:
                    logger.info(
                        "\nPerformance is good. Use the optimal batch size in your uploader script."
                    )

        conn.close()
    except Exception as e:
        logger.error(f"Error testing COPY performance: {str(e)}")


# Function to optimize table structure
def optimize_table_structure(pg_config):
    try:
        conn = get_db_connection(pg_config)
        logger.info("Checking and optimizing table structure")

        with conn.cursor() as cur:
            # Check if table exists
            try:
                cur.execute("SELECT COUNT(*) FROM log_analytics.raw_logs")
                row_count = cur.fetchone()[0]
                logger.info(f"log_analytics.raw_logs exists with {row_count} rows")
            except:
                logger.info("log_analytics.raw_logs does not exist")
                logger.info("Creating schema and table")
                try:
                    cur.execute("CREATE SCHEMA IF NOT EXISTS log_analytics")
                    conn.commit()

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS log_analytics.raw_logs (
                            raw_line TEXT,
                            upload_time TIMESTAMP WITH TIME ZONE
                        )
                    """)
                    conn.commit()
                    logger.info("Created schema and table")
                except Exception as e:
                    logger.error(f"Error creating schema/table: {str(e)}")
                    return

            # Check if unlogged table exists
            try:
                cur.execute("SELECT COUNT(*) FROM log_analytics.raw_logs_unlogged")
                row_count = cur.fetchone()[0]
                logger.info(
                    f"log_analytics.raw_logs_unlogged exists with {row_count} rows"
                )
            except:
                logger.info("log_analytics.raw_logs_unlogged does not exist")
                logger.info("Creating unlogged table")
                try:
                    cur.execute("""
                        CREATE UNLOGGED TABLE IF NOT EXISTS log_analytics.raw_logs_unlogged (
                            raw_line TEXT,
                            upload_time TIMESTAMP WITH TIME ZONE
                        )
                    """)
                    conn.commit()
                    logger.info("Created unlogged table")
                except Exception as e:
                    logger.error(f"Error creating unlogged table: {str(e)}")

            # Check for indexes
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'log_analytics' AND tablename = 'raw_logs'
            """)
            indexes = cur.fetchall()
            if indexes:
                logger.info("Indexes on log_analytics.raw_logs:")
                for idx_name, idx_def in indexes:
                    logger.info(f"  {idx_name}: {idx_def}")

                logger.info("\nConsider dropping indexes during bulk loading:")
                for idx_name, _ in indexes:
                    logger.info(f"DROP INDEX IF EXISTS log_analytics.{idx_name};")
            else:
                logger.info("No indexes found on log_analytics.raw_logs")

            # Check for triggers
            cur.execute("""
                SELECT trigger_name, event_manipulation, action_statement
                FROM information_schema.triggers
                WHERE event_object_schema = 'log_analytics' AND event_object_table = 'raw_logs'
            """)
            triggers = cur.fetchall()
            if triggers:
                logger.info("Triggers on log_analytics.raw_logs:")
                for trigger_name, event, action in triggers:
                    logger.info(f"  {trigger_name}: {event} - {action}")

                logger.info("\nConsider disabling triggers during bulk loading:")
                for trigger_name, _, _ in triggers:
                    logger.info(
                        f"ALTER TABLE log_analytics.raw_logs DISABLE TRIGGER {trigger_name};"
                    )
            else:
                logger.info("No triggers found on log_analytics.raw_logs")

            # Recommendations
            logger.info("\nTable Structure Recommendations:")
            logger.info("1. For bulk loading, use the unlogged table:")
            logger.info("   log_analytics.raw_logs_unlogged")
            logger.info(
                "2. After loading, you can copy data to the logged table if needed:"
            )
            logger.info(
                "   INSERT INTO log_analytics.raw_logs SELECT * FROM log_analytics.raw_logs_unlogged;"
            )
            logger.info("3. Consider adding a distribution column if using Citus:")
            logger.info(
                "   ALTER TABLE log_analytics.raw_logs ADD COLUMN log_date DATE GENERATED ALWAYS AS (upload_time::date) STORED;"
            )

        conn.close()
    except Exception as e:
        logger.error(f"Error optimizing table structure: {str(e)}")


# Function to optimize Citus distribution
def optimize_citus_distribution(pg_config):
    try:
        conn = get_db_connection(pg_config)
        logger.info("Checking and optimizing Citus distribution")

        with conn.cursor() as cur:
            # Check if Citus is installed
            try:
                cur.execute("SELECT citus_version()")
                citus_version = cur.fetchone()[0]
                logger.info(f"Citus version: {citus_version}")
            except:
                logger.info("Citus is not installed or not available")
                logger.info("Skipping Citus optimization")
                return

            # Check if table exists
            try:
                cur.execute("SELECT COUNT(*) FROM log_analytics.raw_logs")
                row_count = cur.fetchone()[0]
                logger.info(f"log_analytics.raw_logs exists with {row_count} rows")
            except:
                logger.info("log_analytics.raw_logs does not exist")
                logger.info("Skipping Citus optimization")
                return

            # Check if table is distributed
            try:
                cur.execute("""
                    SELECT logicalrelid, partmethod, partkey
                    FROM pg_dist_partition
                    WHERE logicalrelid = 'log_analytics.raw_logs'::regclass
                """)
                dist_info = cur.fetchone()
                if dist_info:
                    logger.info(f"Table is already distributed: {dist_info}")
                    return
                else:
                    logger.info("Table is not distributed")
            except Exception as e:
                logger.warning(f"Could not check distribution info: {str(e)}")
                return

            # Check if table has a distribution column
            try:
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'log_analytics' AND table_name = 'raw_logs'
                """)
                columns = cur.fetchall()
                column_names = [col[0] for col in columns]

                if "log_date" in column_names:
                    logger.info("Table has log_date column for distribution")
                else:
                    logger.info("Table does not have a log_date column")
                    logger.info("Recommending to add a log_date column:")
                    logger.info(
                        "ALTER TABLE log_analytics.raw_logs ADD COLUMN log_date DATE GENERATED ALWAYS AS (upload_time::date) STORED;"
                    )
                    return

                # Recommend distribution
                logger.info("\nCitus Distribution Recommendations:")
                logger.info("1. Distribute table by log_date:")
                logger.info(
                    "   SELECT create_distributed_table('log_analytics.raw_logs', 'log_date');"
                )
                logger.info("2. For time-based partitioning, consider:")
                logger.info("""
   CREATE TABLE log_analytics.raw_logs_partitioned (
       raw_line TEXT,
       upload_time TIMESTAMP WITH TIME ZONE,
       log_date DATE GENERATED ALWAYS AS (upload_time::date) STORED
   ) PARTITION BY RANGE (log_date);
                """)
                logger.info("3. Create partitions for each month:")
                logger.info(
                    "   CREATE TABLE log_analytics.raw_logs_y2023m01 PARTITION OF log_analytics.raw_logs_partitioned"
                )
                logger.info("       FOR VALUES FROM ('2023-01-01') TO ('2023-02-01');")
                logger.info("4. Distribute each partition:")
                logger.info(
                    "   SELECT create_distributed_table('log_analytics.raw_logs_y2023m01', 'log_date');"
                )
            except Exception as e:
                logger.error(f"Error checking columns: {str(e)}")

        conn.close()
    except Exception as e:
        logger.error(f"Error optimizing Citus distribution: {str(e)}")


# Function to apply recommended optimizations
def apply_recommended_optimizations(pg_config):
    try:
        conn = get_db_connection(pg_config)
        logger.info("Applying recommended optimizations")

        with conn.cursor() as cur:
            # Apply session-level optimizations
            apply_session_optimizations(conn)

            # Create unlogged table if it doesn't exist
            try:
                cur.execute("""
                    CREATE UNLOGGED TABLE IF NOT EXISTS log_analytics.raw_logs_unlogged (
                        raw_line TEXT,
                        upload_time TIMESTAMP WITH TIME ZONE
                    )
                """)
                conn.commit()
                logger.info("Created unlogged table log_analytics.raw_logs_unlogged")
            except Exception as e:
                logger.error(f"Error creating unlogged table: {str(e)}")

            # Add log_date column if it doesn't exist
            try:
                cur.execute("""
                    ALTER TABLE log_analytics.raw_logs 
                    ADD COLUMN IF NOT EXISTS log_date DATE GENERATED ALWAYS AS (upload_time::date) STORED
                """)
                conn.commit()
                logger.info("Added log_date column to log_analytics.raw_logs")
            except Exception as e:
                logger.error(f"Error adding log_date column: {str(e)}")

        conn.close()
        logger.info("Recommended optimizations applied")
    except Exception as e:
        logger.error(f"Error applying recommended optimizations: {str(e)}")


# Function to generate SQL commands for optimizations
def generate_optimization_sql(pg_config):
    try:
        conn = get_db_connection(pg_config)
        logger.info("Generating SQL commands for optimizations")

        sql_commands = []

        # Session-level optimizations
        sql_commands.append("-- Session-level optimizations")
        sql_commands.append("SET statement_timeout = 120000;  -- 2 minutes")
        sql_commands.append("SET synchronous_commit = OFF;")
        sql_commands.append("SET work_mem = '128MB';")
        sql_commands.append("SET maintenance_work_mem = '256MB';")
        sql_commands.append("SET effective_io_concurrency = 200;")
        sql_commands.append("SET random_page_cost = 1.1;")
        sql_commands.append("")

        # Table structure optimizations
        sql_commands.append("-- Table structure optimizations")
        sql_commands.append("CREATE SCHEMA IF NOT EXISTS log_analytics;")
        sql_commands.append("")
        sql_commands.append("-- Create unlogged table for better performance")
        sql_commands.append("""
CREATE UNLOGGED TABLE IF NOT EXISTS log_analytics.raw_logs_unlogged (
    raw_line TEXT,
    upload_time TIMESTAMP WITH TIME ZONE
);""")
        sql_commands.append("")

        # Write SQL commands to file
        sql_file_path = "postgres_optimizations.sql"
        with open(sql_file_path, "w") as f:
            f.write("\n".join(sql_commands))

        logger.info(f"SQL commands written to {sql_file_path}")
        conn.close()
    except Exception as e:
        logger.error(f"Error generating SQL commands: {str(e)}")


# Main function
def main():
    parser = argparse.ArgumentParser(description="PostgreSQL Performance Tuning Tool")
    parser.add_argument("--config", help="Path to config.yaml file", required=True)
    parser.add_argument(
        "--test-copy",
        help="Test COPY performance with different batch sizes",
        action="store_true",
    )
    parser.add_argument(
        "--optimize-table", help="Optimize table structure", action="store_true"
    )
    parser.add_argument(
        "--optimize-citus", help="Optimize Citus distribution", action="store_true"
    )
    parser.add_argument(
        "--check-settings",
        help="Check current PostgreSQL settings",
        action="store_true",
    )
    parser.add_argument(
        "--apply-optimizations",
        help="Apply recommended optimizations",
        action="store_true",
    )
    parser.add_argument(
        "--generate-sql",
        help="Generate SQL commands for optimizations",
        action="store_true",
    )
    parser.add_argument("--all", help="Run all optimizations", action="store_true")
    parser.add_argument(
        "--tune-all",
        help="Run all tuning operations (alias for --all)",
        action="store_true",
    )

    args = parser.parse_args()

    # Read config
    config = read_config(args.config)
    pg_config = config["postgresql"]

    logger.info(f"PostgreSQL host: {pg_config['host']}")
    logger.info(f"PostgreSQL database: {pg_config['database']}")

    # Check if either --all or --tune-all is specified
    run_all = args.all or args.tune_all

    # Run selected optimizations
    if run_all or args.check_settings:
        check_postgres_settings(pg_config)

    if run_all or args.test_copy:
        batch_sizes = [10, 50, 100, 500, 1000, 5000, 10000]
        test_copy_performance(pg_config, batch_sizes)

    if run_all or args.optimize_table:
        optimize_table_structure(pg_config)

    if run_all or args.optimize_citus:
        optimize_citus_distribution(pg_config)

    if run_all or args.apply_optimizations:
        apply_recommended_optimizations(pg_config)

    if run_all or args.generate_sql:
        generate_optimization_sql(pg_config)

    logger.info("PostgreSQL tuning completed")


if __name__ == "__main__":
    main()
