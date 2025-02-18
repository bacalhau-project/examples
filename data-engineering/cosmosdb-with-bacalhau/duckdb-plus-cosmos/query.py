#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psycopg2-binary",
#     "pyyaml",
# ]
# ///

import argparse

import psycopg2
import yaml


def read_config(config_path: str) -> dict:
    """Read configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Validate required fields
    if "postgresql" not in config:
        raise ValueError("Missing 'postgresql' section in config")

    required_fields = ["host", "port", "user", "password", "database"]
    missing = [f for f in required_fields if f not in config["postgresql"]]
    if missing:
        raise ValueError(f"Missing required PostgreSQL fields: {', '.join(missing)}")

    return config["postgresql"]


def query_database(config: dict, query: str):
    try:
        # Connect to the PostgreSQL database
        connection = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            sslmode="require",
        )

        cursor = connection.cursor()

        # Execute the query
        cursor.execute(query)

        # Fetch all results
        results = cursor.fetchall()

        # Print results
        for row in results:
            print(row)

    except Exception as error:
        print(f"Error querying database: {error}")
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query PostgreSQL database")
    parser.add_argument("--config", help="Path to config.yaml file", required=True)
    parser.add_argument("--query", help="SQL query to execute", required=True)
    args = parser.parse_args()

    # Read config and execute query
    config = read_config(args.config)
    query_database(config, args.query)
