#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.9.0",
#     "pyyaml",
# ]
# ///
import argparse
import os
import sys

import yaml
from azure.cosmos import CosmosClient, PartitionKey


def create_sproc(container):
    """Create or update the bulk delete stored procedure"""
    sproc_body = {
        "id": "bulkDeleteSproc",
        "body": """
function bulkDeleteSproc(partitionKeyValue) {
    var context = getContext();
    var collection = context.getCollection();
    var response = context.getResponse();
    var deleted = 0;
    var continuation = null;
    
    // First query to get count for progress tracking
    var countQuery = {
        query: "SELECT VALUE COUNT(1) FROM c WHERE c.city = @city",
        parameters: [{name: "@city", value: partitionKeyValue}]
    };
    
    collection.queryDocuments(
        collection.getSelfLink(),
        countQuery,
        {},
        function(err, countResult) {
            if (err) throw err;
            
            var totalCount = countResult[0];
            console.log("Total documents to delete: " + totalCount);
            
            // Main deletion logic with pagination
            function processNextBatch() {
                var query = {
                    query: "SELECT c._self FROM c WHERE c.city = @city",
                    parameters: [{name: "@city", value: partitionKeyValue}],
                    requestContinuation: continuation
                };
                
                var isAccepted = collection.queryDocuments(
                    collection.getSelfLink(),
                    query,
                    {},
                    function(err, docs, options) {
                        if (err) throw err;
                        
                        // Process current batch
                        function processBatch(index) {
                            if (index >= docs.length) {
                                // Get next batch if available
                                continuation = options.continuation;
                                if (continuation) {
                                    processNextBatch();
                                } else {
                                    response.setBody({ 
                                        deleted: deleted,
                                        total: totalCount
                                    });
                                }
                                return;
                            }
                            
                            var isDeleteAccepted = collection.deleteDocument(
                                docs[index]._self,
                                {},
                                function(err) {
                                    if (err) throw err;
                                    deleted++;
                                    processBatch(index + 1);
                                }
                            );
                            
                            if (!isDeleteAccepted) {
                                response.setBody({
                                    deleted: deleted,
                                    total: totalCount,
                                    status: "partial",
                                    continuation: options.continuation
                                });
                            }
                        }
                        
                        processBatch(0);
                    }
                );
                
                if (!isAccepted) {
                    response.setBody({
                        deleted: deleted,
                        total: totalCount,
                        status: "rejected",
                        continuation: continuation
                    });
                }
            }
            
            processNextBatch();
        }
    );
}
""",
    }

    try:
        print("Creating bulk delete stored procedure...")
        container.scripts.create_stored_procedure(body=sproc_body)
        print("Stored procedure created successfully.")
    except Exception as e:
        error_str = str(e)
        print(f"Caught exception: {type(e).__name__}")

        if "Resource with specified id" in error_str:
            try:
                print("Stored procedure already exists, replacing it...")
                container.scripts.replace_stored_procedure(
                    sproc=sproc_body["id"], body=sproc_body
                )
                print("Stored procedure replaced successfully.")
            except Exception as replace_error:
                print(f"Error replacing stored procedure: {str(replace_error)}")
                sys.exit(1)
        else:
            print(f"Error creating stored procedure: {error_str}")
            print(
                "Please check your connection string, database and container names, and permissions."
            )
            sys.exit(1)


def clean_container(container, dry_run=False):
    """Delete all documents in the container using the stored procedure"""
    print("Finding all partition key values...")
    query = "SELECT DISTINCT VALUE c.city FROM c"
    cities = list(container.query_items(query=query, enable_cross_partition_query=True))

    if not cities:
        print("No data found in the container.")
        return

    total_deleted = 0
    cities_count = len(cities)
    print(f"Found {cities_count} partition key values. Starting deletion...")

    for i, city in enumerate(cities):
        try:
            if dry_run:
                query = f'SELECT VALUE COUNT(1) FROM c WHERE c.city = "{city}"'
                count_results = list(
                    container.query_items(
                        query=query,
                        enable_cross_partition_query=False,
                        partition_key=city,
                    )
                )
                count = count_results[0] if count_results else 0
                print(f"Would delete {count} documents for city={city}")
                total_deleted += count
            else:
                # Execute stored procedure
                result = container.scripts.execute_stored_procedure(
                    sproc="bulkDeleteSproc",
                    partition_key=city,
                    params=[city],
                )

                # Properly handle response
                if isinstance(result, dict):
                    deleted = result.get("deleted", 0)
                else:
                    # Handle unexpected response format
                    print(f"Unexpected response format for city {city}: {result}")
                    deleted = 0

                total_deleted += deleted
                print(
                    f"Processed {i + 1}/{cities_count} (city={city}): Deleted {deleted} documents"
                )

        except Exception as e:
            print(f"Error processing partition {city}: {str(e)}")
            continue

    print(
        f"Done. Total documents {'would be' if dry_run else ''} deleted: {total_deleted}"
    )


def load_config(config_file):
    """Load configuration from a YAML file"""
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config file: {str(e)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Bulk delete data from Cosmos DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--database",
        type=str,
        help="Database name (defaults to COSMOS_DATABASE env var or value from config file)",
    )
    parser.add_argument(
        "--container",
        type=str,
        help="Container name (defaults to COSMOS_CONTAINER env var or value from config file)",
    )
    parser.add_argument(
        "--config", type=str, help="Config file path to load connection settings from"
    )
    args = parser.parse_args()

    # Set default values
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    key = os.environ.get("COSMOS_KEY")
    database_name = args.database or os.environ.get("COSMOS_DATABASE", "SensorData")
    container_name = args.container or os.environ.get(
        "COSMOS_CONTAINER", "SensorReadings"
    )

    # If config file is provided, load settings from there
    if args.config:
        try:
            print(f"Loading configuration from {args.config}")
            config = load_config(args.config)

            # Get cosmos DB settings from config file
            if "cosmos" in config:
                cosmos_config = config["cosmos"]
                endpoint = cosmos_config.get("endpoint", endpoint)
                key = cosmos_config.get("key", key)
                database_name = args.database or cosmos_config.get(
                    "database_name", database_name
                )
                container_name = args.container or cosmos_config.get(
                    "container_name", container_name
                )

                # For debugging
                print(f"Config file loaded successfully")
                print(f"Config contains: endpoint={bool(endpoint)}, key={bool(key)}")
                print(
                    f"Using database_name={database_name}, container_name={container_name}"
                )
            else:
                print(f"Warning: No 'cosmos' section found in config file")
        except Exception as config_error:
            print(f"Error processing config file: {str(config_error)}")
            sys.exit(1)

    # Check if we have the required credentials
    if not endpoint or not key:
        print(
            "Error: COSMOS_ENDPOINT and COSMOS_KEY must be provided either in environment variables or in the config file."
        )
        sys.exit(1)

    print(f"Connecting to Cosmos DB: {endpoint}")
    print(f"Database: {database_name}")
    print(f"Container: {container_name}")
    if args.dry_run:
        print("DRY RUN MODE - No data will be deleted")

    # Connect to Cosmos DB
    try:
        print(f"Creating CosmosClient with endpoint: {endpoint}")
        client = CosmosClient(endpoint, key)

        print(f"Accessing database: {database_name}")
        database = client.get_database_client(database_name)

        print(f"Accessing container: {container_name}")
        container = database.get_container_client(container_name)

        # Create the sproc first
        create_sproc(container)

        # Run the cleanup
        clean_container(container, args.dry_run)
    except Exception as e:
        print(f"Error connecting to Cosmos DB: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
