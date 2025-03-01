#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psycopg2-binary",
#     "pyyaml",
# ]
# ///

import argparse
import datetime
import json

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


def query_database(config: dict, query: str, json_output: bool = False):
    connection = None
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

        if json_output:
            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Convert results to list of dictionaries
            json_results = []
            for row in results:
                # Convert any non-serializable types to strings
                row_dict = {}
                for i, value in enumerate(row):
                    if isinstance(value, (int, float, str, bool, type(None))):
                        row_dict[columns[i]] = value
                    elif isinstance(value, datetime.datetime):
                        # Format datetime as ISO8601 without spaces
                        row_dict[columns[i]] = value.isoformat()
                    else:
                        row_dict[columns[i]] = str(value)
                json_results.append(row_dict)

            # Print JSON
            print(json.dumps(json_results))
        else:
            # Print results in standard format
            for row in results:
                print(row)

    except Exception as error:
        if json_output:
            print(json.dumps({"error": str(error)}))
        else:
            print(f"Error querying database: {error}")
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query PostgreSQL database")
    parser.add_argument("--config", help="Path to config.yaml file", required=True)
    parser.add_argument("--query", help="SQL query to execute", required=True)
    parser.add_argument(
        "--json", help="Output results in JSON format", action="store_true"
    )
    args = parser.parse_args()

    # Read config and execute query
    config = read_config(args.config)
    query_database(config, args.query, args.json)
