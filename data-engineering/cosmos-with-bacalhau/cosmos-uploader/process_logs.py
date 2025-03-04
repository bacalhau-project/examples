#!/usr/bin/env python3
"""
Process logs and upload to Azure Cosmos DB.
This script handles both standard processing and data cleaning modes.
"""

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml
from azure.cosmos import CosmosClient, PartitionKey, exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("cosmos_processor")


class CosmosDBClient:
    """Client for interacting with Azure Cosmos DB."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the Cosmos DB client with configuration."""
        cosmos_config = config.get("cosmos", {})
        self.endpoint = cosmos_config.get("endpoint")
        self.key = cosmos_config.get("key")
        self.database_name = cosmos_config.get("database_name")
        self.container_name = cosmos_config.get("container_name")
        self.partition_key = cosmos_config.get("partition_key", "/id")

        # Connection settings
        connection_config = cosmos_config.get("connection", {})
        self.connection_mode = connection_config.get("mode", "direct")
        self.connection_protocol = connection_config.get("protocol", "Https")
        self.retry_total = connection_config.get("retry_total", 10)
        self.retry_backoff_max = connection_config.get("retry_backoff_max", 30)
        self.max_retry_attempts = connection_config.get("max_retry_attempts", 10)
        self.max_retry_wait_time = connection_config.get("max_retry_wait_time", 30)

        # Performance settings
        perf_config = cosmos_config.get("performance", {})
        self.preferred_regions = perf_config.get("preferred_regions", [])
        self.enable_endpoint_discovery = perf_config.get(
            "enable_endpoint_discovery", True
        )
        self.bulk_execution = perf_config.get("bulk_execution", True)

        # Initialize client
        self.client = None
        self.database = None
        self.container = None
        self.initialize_client()

    def initialize_client(self):
        """Initialize the Cosmos DB client, database, and container."""
        try:
            # Create the client
            self.client = CosmosClient(
                url=self.endpoint,
                credential=self.key,
                connection_mode=self.connection_mode,
                connection_protocol=self.connection_protocol,
                retry_total=self.retry_total,
                retry_backoff_max=self.retry_backoff_max,
                max_retry_attempts=self.max_retry_attempts,
                max_retry_wait_time=self.max_retry_wait_time,
                preferred_regions=self.preferred_regions,
                enable_endpoint_discovery=self.enable_endpoint_discovery,
            )

            # Get or create database
            self.database = self.client.get_database_client(self.database_name)
            try:
                self.database.read()
            except exceptions.CosmosResourceNotFoundError:
                logger.info(f"Creating database: {self.database_name}")
                self.database = self.client.create_database(self.database_name)

            # Get or create container
            self.container = self.database.get_container_client(self.container_name)
            try:
                self.container.read()
            except exceptions.CosmosResourceNotFoundError:
                logger.info(f"Creating container: {self.container_name}")
                self.container = self.database.create_container(
                    id=self.container_name,
                    partition_key=PartitionKey(path=self.partition_key),
                )

            logger.info("Successfully connected to Cosmos DB")
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB client: {str(e)}")
            raise

    def upsert_items(self, items: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Upsert multiple items to Cosmos DB.

        Args:
            items: List of items to upsert

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not items:
            return 0, 0

        success_count = 0
        failure_count = 0

        if self.bulk_execution:
            # Use bulk execution for better performance
            operations = []
            for item in items:
                operations.append({"operationType": "Upsert", "resourceBody": item})

            try:
                results = list(self.container.execute_bulk(operations))
                for result in results:
                    if result["statusCode"] >= 200 and result["statusCode"] < 300:
                        success_count += 1
                    else:
                        failure_count += 1
                        logger.warning(f"Failed to upsert item: {result}")
            except Exception as e:
                logger.error(f"Bulk operation failed: {str(e)}")
                failure_count += len(items)
        else:
            # Use individual upserts
            for item in items:
                try:
                    self.container.upsert_item(body=item)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to upsert item: {str(e)}")
                    failure_count += 1

        return success_count, failure_count


def parse_log_line(line: str, clean_mode: bool = False) -> Optional[Dict[str, Any]]:
    """
    Parse a log line into a structured document.

    Args:
        line: The log line to parse
        clean_mode: Whether to perform additional data cleaning

    Returns:
        Parsed document or None if parsing failed
    """
    try:
        # Skip empty lines
        if not line or line.isspace():
            return None

        # Try to parse as JSON
        data = json.loads(line)

        # Generate a unique ID if not present
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow().isoformat()

        # Add processing metadata
        data["processed_at"] = datetime.utcnow().isoformat()
        data["processor_version"] = "1.0.0"

        # Add region information for partitioning
        if "region" not in data:
            # Try to extract region from system data if available
            if "system" in data and "environment" in data["system"]:
                data["region"] = data["system"]["environment"]
            else:
                # Default to a random region for demo purposes
                regions = ["us-east", "us-west", "eu-west", "ap-southeast"]
                data["region"] = regions[hash(data["id"]) % len(regions)]

        # Additional cleaning in clean mode
        if clean_mode:
            # Remove sensitive fields
            sensitive_fields = ["password", "secret", "token", "api_key", "credit_card"]
            for field in sensitive_fields:
                if field in data:
                    data[field] = "[REDACTED]"

            # Normalize field names (convert to lowercase)
            data = {k.lower(): v for k, v in data.items()}

            # Ensure all string values are properly encoded
            for key, value in data.items():
                if isinstance(value, str):
                    # Replace invalid characters
                    data[key] = value.replace("\x00", "")

            # Add data quality flag
            data["data_cleaned"] = True

        return data
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse log line as JSON: {line[:100]}...")
        return None
    except Exception as e:
        logger.error(f"Error parsing log line: {str(e)}")
        return None


def process_chunk(
    lines: List[str], cosmos_client: CosmosDBClient, batch_size: int, clean_mode: bool
) -> Tuple[int, int, int]:
    """
    Process a chunk of log lines and upload to Cosmos DB.

    Args:
        lines: List of log lines to process
        cosmos_client: Cosmos DB client
        batch_size: Number of documents to upload in a single batch
        clean_mode: Whether to perform additional data cleaning

    Returns:
        Tuple of (processed_count, success_count, failure_count)
    """
    documents = []
    processed_count = 0
    total_success = 0
    total_failure = 0

    for line in lines:
        document = parse_log_line(line, clean_mode)
        if document:
            documents.append(document)
            processed_count += 1

        # Upload in batches
        if len(documents) >= batch_size:
            success, failure = cosmos_client.upsert_items(documents)
            total_success += success
            total_failure += failure
            documents = []

    # Upload any remaining documents
    if documents:
        success, failure = cosmos_client.upsert_items(documents)
        total_success += success
        total_failure += failure

    return processed_count, total_success, total_failure


def process_file(
    input_file: str,
    cosmos_client: CosmosDBClient,
    chunk_size: int,
    batch_size: int,
    max_workers: int,
    clean_mode: bool,
) -> Tuple[int, int, int]:
    """
    Process a log file in chunks using multiple workers.

    Args:
        input_file: Path to the input file
        cosmos_client: Cosmos DB client
        chunk_size: Number of lines to process in a chunk
        batch_size: Number of documents to upload in a single batch
        max_workers: Maximum number of worker threads
        clean_mode: Whether to perform additional data cleaning

    Returns:
        Tuple of (processed_count, success_count, failure_count)
    """
    total_processed = 0
    total_success = 0
    total_failure = 0

    try:
        # Get file size for progress reporting
        file_size = os.path.getsize(input_file)
        logger.info(
            f"Processing file: {input_file} ({file_size / (1024 * 1024):.2f} MB)"
        )

        with open(input_file, "r") as f:
            start_time = time.time()

            # Process file in chunks
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = []

                while True:
                    lines = list(islice(f, chunk_size))
                    if not lines:
                        break

                    logger.info(
                        f"Submitting chunk of {len(lines)} lines for processing"
                    )
                    future = executor.submit(
                        process_chunk, lines, cosmos_client, batch_size, clean_mode
                    )
                    futures.append(future)

                # Process results as they complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        processed, success, failure = future.result()
                        total_processed += processed
                        total_success += success
                        total_failure += failure

                        # Log progress
                        elapsed = time.time() - start_time
                        rate = total_processed / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"Progress: {total_processed} processed, "
                            f"{total_success} succeeded, {total_failure} failed, "
                            f"{rate:.2f} records/sec"
                        )
                    except Exception as e:
                        logger.error(f"Error processing chunk: {str(e)}")
                        total_failure += chunk_size  # Estimate failure count

        # Log final statistics
        elapsed = time.time() - start_time
        rate = total_processed / elapsed if elapsed > 0 else 0
        logger.info(
            f"Completed processing {input_file} in {elapsed:.2f} seconds. "
            f"Processed: {total_processed}, Succeeded: {total_success}, "
            f"Failed: {total_failure}, Rate: {rate:.2f} records/sec"
        )

        return total_processed, total_success, total_failure

    except Exception as e:
        logger.error(f"Error processing file {input_file}: {str(e)}")
        return total_processed, total_success, total_failure


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Process logs and upload to Cosmos DB")
    parser.add_argument("--config", required=True, help="Path to configuration file")
    parser.add_argument("--input", required=True, help="Path to input log file")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100000,
        help="Number of lines to process in a chunk",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to upload in a single batch",
    )
    parser.add_argument(
        "--max-workers", type=int, default=4, help="Maximum number of worker threads"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Enable data cleaning mode"
    )

    args = parser.parse_args()

    try:
        # Load configuration
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)

        # Initialize Cosmos DB client
        cosmos_client = CosmosDBClient(config)

        # Process the file
        processed, success, failure = process_file(
            input_file=args.input,
            cosmos_client=cosmos_client,
            chunk_size=args.chunk_size,
            batch_size=args.batch_size,
            max_workers=args.max_workers,
            clean_mode=args.clean,
        )

        # Exit with error if any failures
        if failure > 0:
            logger.warning(
                f"Completed with {failure} failures out of {processed} records"
            )
            sys.exit(1)
        else:
            logger.info(f"Successfully processed {processed} records")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Add missing import for islice
    from itertools import islice

    main()
