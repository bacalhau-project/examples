#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "psycopg2-binary",
#     "pyyaml",
# ]
# ///


import os
import sys
from typing import Any, Dict

import psycopg2
import yaml
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def read_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config


def create_tables(conn):
    with conn.cursor() as cur:
        # Create schema if it doesn't exist
        print("Checking if schema exists...")
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS log_analytics;
        """)

        # Create raw_logs table
        print("Dropping raw_logs table if exists...")
        cur.execute("DROP TABLE IF EXISTS log_analytics.raw_logs")

        print("Creating raw_logs table with basic schema...")
        cur.execute("""
            CREATE TABLE log_analytics.raw_logs (
                raw_line TEXT,
                upload_time TIMESTAMP
            )
        """)

        # Create log_results table
        print("Dropping log_results table to fix schema...")
        cur.execute("DROP TABLE IF EXISTS log_analytics.log_results")

        print("Creating log_results table with correct schema...")
        cur.execute("""
            CREATE TABLE log_analytics.log_results (
                project_id TEXT,
                region TEXT,
                nodeName TEXT,
                hostname TEXT,
                provider TEXT,
                sync_time TIMESTAMP,
                ip TEXT,
                user_id TEXT,
                timestamp TIMESTAMP,
                method TEXT,
                path TEXT,
                protocol TEXT,
                status INTEGER,
                bytes INTEGER,
                referer TEXT,
                user_agent TEXT,
                status_category TEXT
            )
        """)

        # Create log_aggregates table
        print("Dropping log_aggregates table to fix schema...")
        cur.execute("DROP TABLE IF EXISTS log_analytics.log_aggregates")

        print("Creating log_aggregates table with correct schema...")
        cur.execute("""
            CREATE TABLE log_analytics.log_aggregates (
                project_id TEXT,
                region TEXT,
                nodeName TEXT,
                provider TEXT,
                hostname TEXT,
                time_window TIMESTAMP,
                ok_count BIGINT,
                redirect_count BIGINT,
                not_found_count BIGINT,
                system_error_count BIGINT,
                total_count BIGINT,
                total_bytes BIGINT,
                avg_bytes DOUBLE PRECISION
            )
        """)

        # Create emergency_logs table
        print("Dropping emergency_logs table to fix schema...")
        cur.execute("DROP TABLE IF EXISTS log_analytics.emergency_logs")

        print("Creating emergency_logs table with correct schema...")
        cur.execute("""
            CREATE TABLE log_analytics.emergency_logs (
                project_id TEXT,
                region TEXT,
                nodeName TEXT,
                provider TEXT,
                hostname TEXT,
                timestamp TIMESTAMP,
                version TEXT,
                message TEXT,
                remote_log_id TEXT,
                alert_level TEXT,
                source_module TEXT,
                event_id TEXT,
                ip TEXT,
                sync_time TIMESTAMP
            )
        """)


def verify_columns(conn):
    print("\nVerifying columns...")
    with conn.cursor() as cur:
        cur.execute("""
            WITH required_columns AS (
                SELECT table_name, column_name, data_type, true as required
                FROM (VALUES
                    ('raw_logs'::text, 'raw_line'::text, 'text'::text),
                    ('raw_logs', 'upload_time', 'timestamp without time zone'),
                    ('log_results', 'project_id', 'text'),
                    ('log_results', 'region', 'text'),
                    ('log_results', 'nodename', 'text'),
                    ('log_results', 'hostname', 'text'),
                    ('log_results', 'provider', 'text'),
                    ('log_results', 'sync_time', 'timestamp without time zone'),
                    ('log_results', 'ip', 'text'),
                    ('log_results', 'user_id', 'text'),
                    ('log_results', 'timestamp', 'timestamp without time zone'),
                    ('log_results', 'method', 'text'),
                    ('log_results', 'path', 'text'),
                    ('log_results', 'protocol', 'text'),
                    ('log_results', 'status', 'integer'),
                    ('log_results', 'bytes', 'integer'),
                    ('log_results', 'referer', 'text'),
                    ('log_results', 'user_agent', 'text'),
                    ('log_results', 'status_category', 'text'),
                    ('log_aggregates', 'project_id', 'text'),
                    ('log_aggregates', 'region', 'text'),
                    ('log_aggregates', 'nodename', 'text'),
                    ('log_aggregates', 'provider', 'text'),
                    ('log_aggregates', 'hostname', 'text'),
                    ('log_aggregates', 'time_window', 'timestamp without time zone'),
                    ('log_aggregates', 'ok_count', 'bigint'),
                    ('log_aggregates', 'redirect_count', 'bigint'),
                    ('log_aggregates', 'not_found_count', 'bigint'),
                    ('log_aggregates', 'system_error_count', 'bigint'),
                    ('log_aggregates', 'total_count', 'bigint'),
                    ('log_aggregates', 'total_bytes', 'bigint'),
                    ('log_aggregates', 'avg_bytes', 'double precision'),
                    ('emergency_logs', 'project_id', 'text'),
                    ('emergency_logs', 'region', 'text'),
                    ('emergency_logs', 'nodename', 'text'),
                    ('emergency_logs', 'provider', 'text'),
                    ('emergency_logs', 'hostname', 'text'),
                    ('emergency_logs', 'timestamp', 'timestamp without time zone'),
                    ('emergency_logs', 'version', 'text'),
                    ('emergency_logs', 'message', 'text'),
                    ('emergency_logs', 'remote_log_id', 'text'),
                    ('emergency_logs', 'alert_level', 'text'),
                    ('emergency_logs', 'source_module', 'text'),
                    ('emergency_logs', 'event_id', 'text'),
                    ('emergency_logs', 'ip', 'text'),
                    ('emergency_logs', 'sync_time', 'timestamp without time zone')
                ) AS t(table_name, column_name, data_type)
            )
            SELECT 
                r.table_name,
                r.column_name,
                c.data_type as current_type,
                r.data_type as required_type,
                CASE 
                    WHEN c.data_type = r.data_type THEN '✓'
                    ELSE '✗'
                END as matches
            FROM required_columns r
            LEFT JOIN information_schema.columns c
                ON c.table_name = r.table_name
                AND c.column_name = r.column_name
                AND c.table_schema = 'log_analytics'
            ORDER BY r.table_name, r.column_name;
        """)

        results = cur.fetchall()
        for row in results:
            print(f"{row[0]:<15} {row[1]:<20} {row[2]:<20} {row[3]:<20} {row[4]}")


def main():
    try:
        config = read_config()
        print(
            f"Creating and configuring tables in database: {config['postgresql']['database']}"
        )

        # Replace these with your actual connection details
        conn = psycopg2.connect(
            dbname=config["postgresql"]["database"],
            user=config["postgresql"]["user"],
            password=config["postgresql"]["password"],
            host=config["postgresql"]["host"],
            port=config["postgresql"]["port"],
            sslmode="require",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        create_tables(conn)
        verify_columns(conn)

        print("\nDone. All tables exist with correct schema.")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    main()
