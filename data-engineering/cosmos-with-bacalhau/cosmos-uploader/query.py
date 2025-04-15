#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml",
# ]
# ///

"""
Query tool for CosmosDB to check sensor data uploads
"""

import argparse
import json
import os

import yaml
from azure.cosmos import CosmosClient, PartitionKey


def load_config(config_path):
    """Load configuration from a YAML file"""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def query_cosmosdb(endpoint, key, database_name, container_name, query, verbose=False):
    """Query CosmosDB and return results"""
    # Initialize the Cosmos client
    client = CosmosClient(endpoint, credential=key)

    # Get the database and container
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    if verbose:
        print(f"Connected to {endpoint}")
        print(f"Database: {database_name}")
        print(f"Container: {container_name}")
        print(f"Executing query: {query}")

    # Execute the query
    items = list(container.query_items(query=query, enable_cross_partition_query=True))

    return items


def count_items(endpoint, key, database_name, container_name):
    """Count items in the container"""
    client = CosmosClient(endpoint, credential=key)
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    count_query = "SELECT VALUE COUNT(1) FROM c"
    items = list(
        container.query_items(query=count_query, enable_cross_partition_query=True)
    )
    if items:
        return items[0]
    return 0


def main():
    parser = argparse.ArgumentParser(description="Query CosmosDB")
    parser.add_argument("--config", required=True, help="Path to the config file")
    parser.add_argument(
        "--query", default="SELECT * FROM c LIMIT 10", help="SQL query to execute"
    )
    parser.add_argument(
        "--count", action="store_true", help="Count documents instead of querying"
    )
    parser.add_argument("--city", help="Filter by city (partition key)")
    parser.add_argument("--sensor", help="Filter by sensor ID")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Extract Cosmos DB configuration
    endpoint = config.get("cosmos", {}).get("endpoint")
    key = config.get("cosmos", {}).get("key")
    database_name = config.get("cosmos", {}).get("database_name")
    container_name = config.get("cosmos", {}).get("container_name")

    # Check for environment variable overrides
    endpoint = os.environ.get("COSMOS_ENDPOINT", endpoint)
    key = os.environ.get("COSMOS_KEY", key)
    database_name = os.environ.get("COSMOS_DATABASE", database_name)
    container_name = os.environ.get("COSMOS_CONTAINER", container_name)

    if not all([endpoint, key, database_name, container_name]):
        print("Error: Missing Cosmos DB configuration values")
        return

    if args.count:
        # Count items
        count = count_items(endpoint, key, database_name, container_name)
        print(f"Total documents: {count}")
        return

    # Build query if not provided
    query = args.query
    if args.query == "SELECT * FROM c LIMIT 10" and (
        args.city or args.sensor or args.limit != 10
    ):
        # Build custom query
        query = "SELECT * FROM c WHERE 1=1"
        if args.city:
            query += f" AND c.city = '{args.city}'"
        if args.sensor:
            query += f" AND c.sensorId = '{args.sensor}'"
        query += f" LIMIT {args.limit}"

    # Execute query
    items = query_cosmosdb(
        endpoint, key, database_name, container_name, query, args.verbose
    )

    # Display results
    if args.verbose:
        print(f"Found {len(items)} items")

    for item in items:
        print(json.dumps(item, indent=2))


if __name__ == "__main__":
    main()
