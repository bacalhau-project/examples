#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos",
#     "pyyaml",
# ]
# ///

import argparse
import datetime
import json
import time

import yaml
from azure.cosmos import CosmosClient, PartitionKey


def read_config(config_path: str) -> dict:
    """Read configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Validate required fields
    if "cosmos" not in config:
        raise ValueError("Missing 'cosmos' section in config")

    required_fields = ["endpoint", "key", "database_name", "container_name"]
    missing = [f for f in required_fields if f not in config["cosmos"]]
    if missing:
        raise ValueError(f"Missing required Cosmos DB fields: {', '.join(missing)}")

    return config["cosmos"]


def query_database(
    config: dict, query: str, json_output: bool = False, max_item_count: int = 100
):
    try:
        # Connect to the Cosmos DB account
        client = CosmosClient(
            url=config["endpoint"],
            credential=config["key"],
            connection_mode=config.get("connection", {}).get("mode", "direct"),
            connection_protocol=config.get("connection", {}).get("protocol", "Https"),
        )

        # Get database and container
        database = client.get_database_client(config["database_name"])
        container = database.get_container_client(config["container_name"])

        # Execute the query
        start_time = time.time()
        query_iterable = container.query_items(
            query=query,
            enable_cross_partition_query=True,
            max_item_count=max_item_count,
        )

        # Fetch all results
        results = list(query_iterable)
        end_time = time.time()

        # Calculate request charge (RUs)
        request_charge = query_iterable.response_headers.get("x-ms-request-charge", 0)

        if json_output:
            # Convert results to JSON
            for item in results:
                # Convert any non-serializable types to strings
                for key, value in item.items():
                    if isinstance(value, datetime.datetime):
                        item[key] = value.isoformat()

            # Add metadata
            metadata = {
                "count": len(results),
                "query_time_ms": round((end_time - start_time) * 1000, 2),
                "request_charge": float(request_charge),
            }

            # Print JSON with metadata
            print(json.dumps({"metadata": metadata, "results": results}))
        else:
            # Print results in standard format
            print(
                f"Query executed in {round((end_time - start_time) * 1000, 2)} ms, consumed {request_charge} RUs"
            )
            print(f"Found {len(results)} results:")
            for item in results:
                print(json.dumps(item, indent=2))

    except Exception as error:
        if json_output:
            print(json.dumps({"error": str(error)}))
        else:
            print(f"Error querying Cosmos DB: {error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Azure Cosmos DB")
    parser.add_argument("--config", help="Path to config.yaml file", required=True)
    parser.add_argument("--query", help="SQL query to execute", required=True)
    parser.add_argument(
        "--json", help="Output results in JSON format", action="store_true"
    )
    parser.add_argument(
        "--max-items",
        help="Maximum number of items to return per page",
        type=int,
        default=100,
    )
    args = parser.parse_args()

    # Read config and execute query
    config = read_config(args.config)
    query_database(config, args.query, args.json, args.max_items)
