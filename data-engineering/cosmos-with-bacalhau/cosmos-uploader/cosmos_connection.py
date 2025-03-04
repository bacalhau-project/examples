#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml",
# ]
# ///

import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

import yaml
from azure.cosmos import (
    ContainerProxy,
    CosmosClient,
    DatabaseProxy,
    PartitionKey,
    exceptions,
)
from azure.cosmos.cosmos_client import CosmosClientConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global configuration
DEBUG = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
CONNECTION_TIMEOUT = int(
    os.environ.get("CONNECTION_TIMEOUT", "120")
)  # seconds - timeout for operations


class CosmosDBConnection:
    """
    Singleton class for managing Azure Cosmos DB connections.
    """

    _instance = None
    _client = None
    _database = None
    _container = None
    _config = None

    def __new__(cls, config_path: str = None):
        if cls._instance is None:
            cls._instance = super(CosmosDBConnection, cls).__new__(cls)
            if config_path:
                cls._instance._initialize(config_path)
        return cls._instance

    def _initialize(self, config_path: str):
        """Initialize the Cosmos DB connection with configuration from a YAML file."""
        self._config = self._read_config(config_path)
        self._setup_client()
        self._setup_database()
        self._setup_container()

    def _read_config(self, config_path: str) -> dict:
        """Read configuration from YAML file."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            if "cosmosdb" not in config:
                raise ValueError("Missing 'cosmosdb' section in config")

            required_fields = ["endpoint", "key", "database", "container"]
            missing = [f for f in required_fields if f not in config["cosmosdb"]]
            if missing:
                raise ValueError(
                    f"Missing required Cosmos DB fields: {', '.join(missing)}"
                )

            return config
        except Exception as e:
            logger.error(f"Error reading configuration: {str(e)}")
            raise

    def _setup_client(self):
        """Create and configure the Cosmos DB client."""
        try:
            cosmos_config = self._config["cosmosdb"]
            connection_config = cosmos_config.get("connection", {})

            # Configure client options
            connection_mode = connection_config.get("mode", "Gateway")
            connection_timeout = connection_config.get(
                "connection_timeout", CONNECTION_TIMEOUT
            )
            max_retry_attempts = connection_config.get("max_retry_attempts", 9)
            max_retry_wait_time = connection_config.get(
                "max_retry_wait_time_in_seconds", 30
            )
            enable_endpoint_discovery = connection_config.get(
                "enable_endpoint_discovery", True
            )
            preferred_regions = connection_config.get("preferred_regions", [])

            # Create the client
            self._client = CosmosClient(
                url=cosmos_config["endpoint"],
                credential=cosmos_config["key"],
                connection_mode=connection_mode,
                connection_timeout=connection_timeout,
                retry_total=max_retry_attempts,
                retry_backoff_max=max_retry_wait_time,
                enable_endpoint_discovery=enable_endpoint_discovery,
                preferred_regions=preferred_regions or None,
            )

            logger.info(
                f"Successfully created Cosmos DB client for endpoint: {cosmos_config['endpoint']}"
            )
        except Exception as e:
            logger.error(f"Error creating Cosmos DB client: {str(e)}")
            raise

    def _setup_database(self):
        """Create database if it doesn't exist."""
        try:
            cosmos_config = self._config["cosmosdb"]
            database_name = cosmos_config["database"]

            # Check if we should use throughput at database level
            performance_config = self._config.get("performance", {})
            throughput = performance_config.get("throughput")
            autoscale = performance_config.get("autoscale", False)

            # Create database if it doesn't exist
            if throughput and autoscale:
                from azure.cosmos import ThroughputProperties

                throughput_properties = ThroughputProperties(
                    auto_scale_max_throughput=throughput
                )
                self._database = self._client.create_database_if_not_exists(
                    id=database_name, offer_throughput=throughput_properties
                )
            elif throughput:
                self._database = self._client.create_database_if_not_exists(
                    id=database_name, offer_throughput=throughput
                )
            else:
                self._database = self._client.create_database_if_not_exists(
                    id=database_name
                )

            logger.info(f"Successfully connected to database: {database_name}")
        except Exception as e:
            logger.error(f"Error setting up database: {str(e)}")
            raise

    def _setup_container(self):
        """Create container if it doesn't exist."""
        try:
            cosmos_config = self._config["cosmosdb"]
            container_name = cosmos_config["container"]
            partition_key_path = cosmos_config.get("partition_key_path", "/region")

            # Check if we should use throughput at container level
            performance_config = self._config.get("performance", {})
            throughput = performance_config.get("throughput")
            autoscale = performance_config.get("autoscale", False)

            # Create container if it doesn't exist
            if throughput and autoscale:
                from azure.cosmos import ThroughputProperties

                throughput_properties = ThroughputProperties(
                    auto_scale_max_throughput=throughput
                )
                self._container = self._database.create_container_if_not_exists(
                    id=container_name,
                    partition_key=PartitionKey(path=partition_key_path),
                    offer_throughput=throughput_properties,
                )
            elif throughput:
                self._container = self._database.create_container_if_not_exists(
                    id=container_name,
                    partition_key=PartitionKey(path=partition_key_path),
                    offer_throughput=throughput,
                )
            else:
                self._container = self._database.create_container_if_not_exists(
                    id=container_name,
                    partition_key=PartitionKey(path=partition_key_path),
                )

            logger.info(f"Successfully connected to container: {container_name}")
        except Exception as e:
            logger.error(f"Error setting up container: {str(e)}")
            raise

    def get_client(self) -> CosmosClient:
        """Get the Cosmos DB client instance."""
        if not self._client:
            raise ValueError(
                "Cosmos DB client not initialized. Call initialize() first."
            )
        return self._client

    def get_database(self) -> DatabaseProxy:
        """Get the database instance."""
        if not self._database:
            raise ValueError("Database not initialized. Call initialize() first.")
        return self._database

    def get_container(self) -> ContainerProxy:
        """Get the container instance."""
        if not self._container:
            raise ValueError("Container not initialized. Call initialize() first.")
        return self._container

    def test_connection(self) -> bool:
        """Test the connection to Cosmos DB."""
        try:
            # Try to read database properties
            self._database.read()
            # Try to read container properties
            self._container.read()
            return True
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    def get_last_request_charge(self) -> float:
        """Get the request charge (RU) from the last operation."""
        if not self._client:
            return 0.0

        try:
            client_connection = self._client.client_connection
            if hasattr(client_connection, "last_response_headers"):
                return float(
                    client_connection.last_response_headers.get(
                        "x-ms-request-charge", 0
                    )
                )
        except Exception as e:
            logger.warning(f"Error getting request charge: {str(e)}")

        return 0.0


def main(config_path: str):
    """Test the Cosmos DB connection."""
    try:
        # Initialize the connection
        cosmos_connection = CosmosDBConnection(config_path)

        # Test the connection
        if cosmos_connection.test_connection():
            logger.info("Connection test successful!")

            # Get connection details
            client = cosmos_connection.get_client()
            database = cosmos_connection.get_database()
            container = cosmos_connection.get_container()

            logger.info(f"Connected to Cosmos DB endpoint: {client.url}")
            logger.info(f"Database: {database.id}")
            logger.info(f"Container: {container.id}")

            # Create a test document
            test_doc = {
                "id": f"test-{int(time.time())}",
                "region": "test-region",
                "message": "Connection test successful",
                "timestamp": time.time(),
            }

            # Insert the test document
            response = container.create_item(body=test_doc)

            # Get the request charge
            request_charge = cosmos_connection.get_last_request_charge()

            logger.info(f"Test document created with ID: {response['id']}")
            logger.info(f"Request charge (RUs): {request_charge}")

            return True
        else:
            logger.error("Connection test failed!")
            return False
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <config_path>")
        sys.exit(1)

    success = main(sys.argv[1])
    sys.exit(0 if success else 1)
