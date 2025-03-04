#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "pyyaml",
# ]
# ///

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

from azure.cosmos import exceptions
from cosmos_connection import CosmosDBConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global configuration
DEBUG = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1000"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))


class CosmosDBOperations:
    """
    Class for Azure Cosmos DB operations.
    """

    def __init__(self, connection: CosmosDBConnection):
        self.connection = connection
        self.container = connection.get_container()
        self.client = connection.get_client()
        self.database = connection.get_database()
        self.total_ru_consumed = 0.0
        self.operation_counts = {
            "create": 0,
            "upsert": 0,
            "read": 0,
            "query": 0,
            "delete": 0,
            "batch": 0,
            "error": 0,
        }
        self.start_time = time.time()

    def create_item(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single document in Cosmos DB."""
        try:
            response = self.container.create_item(body=document)
            self._track_operation("create", 1)
            self._track_ru_consumption()
            return response
        except exceptions.CosmosHttpResponseError as e:
            self._track_operation("error", 1)
            logger.error(f"Error creating document: {str(e)}")
            raise

    def upsert_item(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a single document in Cosmos DB."""
        try:
            response = self.container.upsert_item(body=document)
            self._track_operation("upsert", 1)
            self._track_ru_consumption()
            return response
        except exceptions.CosmosHttpResponseError as e:
            self._track_operation("error", 1)
            logger.error(f"Error upserting document: {str(e)}")
            raise

    def read_item(self, item_id: str, partition_key: str) -> Dict[str, Any]:
        """Read a single document from Cosmos DB."""
        try:
            response = self.container.read_item(
                item=item_id, partition_key=partition_key
            )
            self._track_operation("read", 1)
            self._track_ru_consumption()
            return response
        except exceptions.CosmosHttpResponseError as e:
            self._track_operation("error", 1)
            logger.error(f"Error reading document: {str(e)}")
            raise

    def delete_item(self, item_id: str, partition_key: str) -> Dict[str, Any]:
        """Delete a single document from Cosmos DB."""
        try:
            response = self.container.delete_item(
                item=item_id, partition_key=partition_key
            )
            self._track_operation("delete", 1)
            self._track_ru_consumption()
            return response
        except exceptions.CosmosHttpResponseError as e:
            self._track_operation("error", 1)
            logger.error(f"Error deleting document: {str(e)}")
            raise

    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None,
        max_item_count: int = 100,
    ) -> Generator[Dict[str, Any], None, None]:
        """Query documents from Cosmos DB."""
        try:
            query_options = {"max_item_count": max_item_count}
            if partition_key:
                query_options["partition_key"] = partition_key

            items = self.container.query_items(
                query=query, parameters=parameters, **query_options
            )

            # Convert to list to execute the query and track RU consumption
            count = 0
            for item in items:
                count += 1
                yield item

            self._track_operation("query", count)
            self._track_ru_consumption()
        except exceptions.CosmosHttpResponseError as e:
            self._track_operation("error", 1)
            logger.error(f"Error querying documents: {str(e)}")
            raise

    def bulk_create(
        self, documents: List[Dict[str, Any]], batch_size: int = BATCH_SIZE
    ) -> Tuple[int, float]:
        """Create multiple documents in batches."""
        return self._bulk_operation(documents, self.create_item, batch_size)

    def bulk_upsert(
        self, documents: List[Dict[str, Any]], batch_size: int = BATCH_SIZE
    ) -> Tuple[int, float]:
        """Upsert multiple documents in batches."""
        return self._bulk_operation(documents, self.upsert_item, batch_size)

    def _bulk_operation(
        self, documents: List[Dict[str, Any]], operation_func, batch_size: int
    ) -> Tuple[int, float]:
        """Execute a bulk operation using the specified function."""
        if not documents:
            return 0, 0.0

        total_documents = len(documents)
        start_time = time.time()
        success_count = 0
        error_count = 0

        # Process in batches
        for i in range(0, total_documents, batch_size):
            batch = documents[i : i + batch_size]
            batch_start_time = time.time()

            try:
                # Process batch in parallel
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = [executor.submit(operation_func, doc) for doc in batch]

                    for future in as_completed(futures):
                        try:
                            future.result()
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error in bulk operation: {str(e)}")

                batch_end_time = time.time()
                batch_size_actual = len(batch)
                batch_duration = batch_end_time - batch_start_time
                batch_rate = (
                    batch_size_actual / batch_duration if batch_duration > 0 else 0
                )

                logger.info(
                    f"Processed batch {i // batch_size + 1}/{(total_documents + batch_size - 1) // batch_size}: "
                    f"{batch_size_actual} documents in {batch_duration:.2f}s ({batch_rate:.2f} docs/s)"
                )

                self._track_operation("batch", 1)
            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}")
                error_count += len(batch)

        end_time = time.time()
        duration = end_time - start_time
        rate = success_count / duration if duration > 0 else 0

        logger.info(
            f"Bulk operation completed: {success_count} succeeded, {error_count} failed, "
            f"total time: {duration:.2f}s, rate: {rate:.2f} docs/s"
        )

        return success_count, self.total_ru_consumed

    def parallel_bulk_create(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = BATCH_SIZE,
        max_workers: int = MAX_WORKERS,
    ) -> Tuple[int, float]:
        """Create multiple documents in parallel batches."""
        return self._parallel_bulk_operation(
            documents, "create", batch_size, max_workers
        )

    def parallel_bulk_upsert(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = BATCH_SIZE,
        max_workers: int = MAX_WORKERS,
    ) -> Tuple[int, float]:
        """Upsert multiple documents in parallel batches."""
        return self._parallel_bulk_operation(
            documents, "upsert", batch_size, max_workers
        )

    def _parallel_bulk_operation(
        self,
        documents: List[Dict[str, Any]],
        operation_type: str,
        batch_size: int,
        max_workers: int,
    ) -> Tuple[int, float]:
        """Execute a parallel bulk operation."""
        if not documents:
            return 0, 0.0

        total_documents = len(documents)
        start_time = time.time()
        success_count = 0
        error_count = 0

        # Split documents into batches
        batches = [
            documents[i : i + batch_size] for i in range(0, total_documents, batch_size)
        ]

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            if operation_type == "create":
                futures = [
                    executor.submit(self._process_batch_create, batch, i)
                    for i, batch in enumerate(batches)
                ]
            else:  # upsert
                futures = [
                    executor.submit(self._process_batch_upsert, batch, i)
                    for i, batch in enumerate(batches)
                ]

            for future in as_completed(futures):
                try:
                    batch_success, batch_error = future.result()
                    success_count += batch_success
                    error_count += batch_error
                except Exception as e:
                    logger.error(f"Error in parallel bulk operation: {str(e)}")
                    # Assume all documents in the batch failed
                    error_count += batch_size

        end_time = time.time()
        duration = end_time - start_time
        rate = success_count / duration if duration > 0 else 0

        logger.info(
            f"Parallel bulk operation completed: {success_count} succeeded, {error_count} failed, "
            f"total time: {duration:.2f}s, rate: {rate:.2f} docs/s"
        )

        return success_count, self.total_ru_consumed

    def _process_batch_create(
        self, batch: List[Dict[str, Any]], batch_index: int
    ) -> Tuple[int, int]:
        """Process a batch of documents for creation."""
        return self._process_batch(batch, self.container.create_item, batch_index)

    def _process_batch_upsert(
        self, batch: List[Dict[str, Any]], batch_index: int
    ) -> Tuple[int, int]:
        """Process a batch of documents for upsertion."""
        return self._process_batch(batch, self.container.upsert_item, batch_index)

    def _process_batch(
        self, batch: List[Dict[str, Any]], operation_func, batch_index: int
    ) -> Tuple[int, int]:
        """Process a batch of documents using the specified function."""
        batch_start_time = time.time()
        success_count = 0
        error_count = 0

        for doc in batch:
            try:
                operation_func(body=doc)
                success_count += 1
                self._track_ru_consumption()
            except exceptions.CosmosHttpResponseError as e:
                error_count += 1
                logger.error(f"Error in batch {batch_index}: {str(e)}")

        batch_end_time = time.time()
        batch_duration = batch_end_time - batch_start_time
        batch_rate = len(batch) / batch_duration if batch_duration > 0 else 0

        logger.info(
            f"Batch {batch_index}: {success_count} succeeded, {error_count} failed, "
            f"time: {batch_duration:.2f}s, rate: {batch_rate:.2f} docs/s"
        )

        return success_count, error_count

    def _track_ru_consumption(self):
        """Track Request Units consumed by the last operation."""
        ru_consumed = self.connection.get_last_request_charge()
        self.total_ru_consumed += ru_consumed
        return ru_consumed

    def _track_operation(self, operation_type: str, count: int = 1):
        """Track operation counts."""
        if operation_type in self.operation_counts:
            self.operation_counts[operation_type] += count

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for operations."""
        end_time = time.time()
        duration = end_time - self.start_time

        total_operations = sum(self.operation_counts.values())
        operations_per_second = total_operations / duration if duration > 0 else 0
        ru_per_second = self.total_ru_consumed / duration if duration > 0 else 0

        return {
            "duration_seconds": duration,
            "total_operations": total_operations,
            "operations_per_second": operations_per_second,
            "total_ru_consumed": self.total_ru_consumed,
            "ru_per_second": ru_per_second,
            "operation_counts": self.operation_counts,
        }

    def reset_metrics(self):
        """Reset performance metrics."""
        self.total_ru_consumed = 0.0
        self.operation_counts = {
            "create": 0,
            "upsert": 0,
            "read": 0,
            "query": 0,
            "delete": 0,
            "batch": 0,
            "error": 0,
        }
        self.start_time = time.time()


def main(config_path: str):
    """Test basic Cosmos DB operations."""
    try:
        # Initialize the connection
        cosmos_connection = CosmosDBConnection(config_path)

        # Create operations instance
        operations = CosmosDBOperations(cosmos_connection)

        # Create test documents
        test_docs = []
        for i in range(10):
            test_docs.append(
                {
                    "id": f"test-{int(time.time())}-{i}",
                    "region": "test-region",
                    "message": f"Test document {i}",
                    "timestamp": time.time(),
                    "data": {"value": i, "text": f"Sample text {i}"},
                }
            )

        # Test single document operations
        logger.info("Testing single document operations...")

        # Create
        created_doc = operations.create_item(test_docs[0])
        logger.info(f"Created document with ID: {created_doc['id']}")
        logger.info(f"RU consumed: {operations.connection.get_last_request_charge()}")

        # Read
        read_doc = operations.read_item(created_doc["id"], created_doc["region"])
        logger.info(f"Read document with ID: {read_doc['id']}")
        logger.info(f"RU consumed: {operations.connection.get_last_request_charge()}")

        # Update
        read_doc["message"] = "Updated message"
        updated_doc = operations.upsert_item(read_doc)
        logger.info(f"Updated document with ID: {updated_doc['id']}")
        logger.info(f"RU consumed: {operations.connection.get_last_request_charge()}")

        # Query
        logger.info("Testing query operations...")
        query = "SELECT * FROM c WHERE c.region = @region"
        parameters = [{"name": "@region", "value": "test-region"}]

        items = list(operations.query_items(query, parameters))
        logger.info(f"Query returned {len(items)} documents")
        logger.info(f"RU consumed: {operations.connection.get_last_request_charge()}")

        # Bulk operations
        logger.info("Testing bulk operations...")
        success_count, ru_consumed = operations.bulk_create(test_docs[1:6])
        logger.info(f"Bulk created {success_count} documents")
        logger.info(f"Total RU consumed: {ru_consumed}")

        # Parallel bulk operations
        logger.info("Testing parallel bulk operations...")
        success_count, ru_consumed = operations.parallel_bulk_upsert(test_docs[6:])
        logger.info(f"Parallel bulk upserted {success_count} documents")
        logger.info(f"Total RU consumed: {ru_consumed}")

        # Get performance metrics
        metrics = operations.get_performance_metrics()
        logger.info(f"Performance metrics: {json.dumps(metrics, indent=2)}")

        return True
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <config_path>")
        sys.exit(1)

    success = main(sys.argv[1])
    sys.exit(0 if success else 1)
