#!/usr/bin/env python3

import argparse
import time
from datetime import datetime, timezone
from io import StringIO

import psycopg2
import yaml


def read_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)["postgresql"]


def optimize_database_settings(config_path):
    pg_config = read_config(config_path)

    connect_args = {
        "host": pg_config["host"],
        "port": pg_config["port"],
        "user": pg_config["user"],
        "password": pg_config["password"],
        "database": pg_config["database"],
        "sslmode": "require",
        "connect_timeout": 30,
    }

    print(f"Connecting to {pg_config['host']}:{pg_config['port']}...")

    try:
        with psycopg2.connect(**connect_args) as conn:
            print("Connection established.")

            # First, get current settings
            with conn.cursor() as cur:
                print("\nCurrent PostgreSQL Configuration:")
                cur.execute("""
                    SELECT name, setting, context, short_desc 
                    FROM pg_settings 
                    WHERE name IN (
                        'synchronous_commit', 'work_mem', 'maintenance_work_mem', 
                        'statement_timeout', 'checkpoint_timeout', 'max_wal_size',
                        'wal_buffers', 'shared_buffers', 'effective_cache_size',
                        'random_page_cost'
                    )
                """)
                current_settings = cur.fetchall()

                for name, setting, context, desc in current_settings:
                    print(f"  {name} = {setting} ({context}) - {desc}")

            # Check if we have superuser or alter system privileges
            with conn.cursor() as cur:
                cur.execute("SELECT usesuper FROM pg_user WHERE usename = current_user")
                is_superuser = cur.fetchone()[0]

                if is_superuser:
                    print(
                        "\nUser has superuser privileges. Can apply permanent settings."
                    )
                else:
                    print(
                        "\nUser does not have superuser privileges. May be limited in applying settings."
                    )

            # Try to apply optimizations at session level
            print("\nApplying session-level optimizations for testing...")
            with conn.cursor() as cur:
                try:
                    cur.execute("SET synchronous_commit TO OFF;")
                    print("  Set synchronous_commit = OFF")
                except Exception as e:
                    print(f"  Failed to set synchronous_commit: {str(e)}")

                try:
                    cur.execute("SET work_mem TO '128MB';")
                    print("  Set work_mem = 128MB")
                except Exception as e:
                    print(f"  Failed to set work_mem: {str(e)}")

            # Run performance tests with different methods and batch sizes
            print("\nRunning performance tests...")

            # Test different batch sizes
            batch_sizes = [10, 50, 100, 500, 1000]

            print("\nTesting INSERT with COPY command:")
            for size in batch_sizes:
                try:
                    with conn.cursor() as cur:
                        # Create test data for COPY
                        copy_data = StringIO()
                        timestamp = datetime.now(timezone.utc).isoformat()
                        for i in range(size):
                            line = f"Test log line {i}"
                            escaped_line = (
                                line.replace("\\", "\\\\")
                                .replace("\t", "\\t")
                                .replace("\n", "\\n")
                            )
                            copy_data.write(f"{escaped_line}\t{timestamp}\n")

                        copy_data.seek(0)

                        # Test COPY performance
                        start_time = time.time()
                        cur.copy_expert(
                            "COPY log_analytics.raw_logs (raw_line, upload_time) FROM STDIN WITH DELIMITER E'\\t'",
                            copy_data,
                        )
                        conn.commit()
                        copy_time = time.time() - start_time

                        copy_rate = size / copy_time if copy_time > 0 else 0
                        print(
                            f"  Batch size {size}: {copy_time:.2f} seconds ({copy_rate:.1f} rows/sec)"
                        )
                except Exception as e:
                    print(f"  Error with batch size {size}: {str(e)}")

            print(
                "\nPerformance test complete. Use these results to optimize your batch size."
            )
            print(
                "The COPY command is the recommended method for bulk data loading in PostgreSQL."
            )

    except Exception as e:
        print(f"Error: {str(e)}")
        return False

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PostgreSQL Performance Optimizer")
    parser.add_argument("--config", help="Path to config.yaml file", required=True)
    args = parser.parse_args()

    optimize_database_settings(args.config)
