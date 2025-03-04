#!/usr/bin/env python3
"""
Benchmark Azure Cosmos DB operations.
This script measures the performance of various Cosmos DB operations.
"""

import argparse
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import yaml
from azure.cosmos import CosmosClient, PartitionKey, exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("cosmos_benchmark")


class CosmosBenchmark:
    """Benchmark Azure Cosmos DB operations."""

    def __init__(self, config_path: str):
        """Initialize the benchmark with configuration."""
        # Load configuration
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Initialize Cosmos DB client
        cosmos_config = self.config.get("cosmos", {})
        self.endpoint = cosmos_config.get("endpoint")
        self.key = cosmos_config.get("key")
        self.database_name = cosmos_config.get("database_name")
        self.container_name = cosmos_config.get("container_name")
        self.partition_key = cosmos_config.get("partition_key", "/id")

        # Connection settings
        connection_config = cosmos_config.get("connection", {})
        self.connection_mode = connection_config.get("mode", "direct")
        self.connection_protocol = connection_config.get("protocol", "Https")

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

        # Benchmark results
        self.results = {}

    def initialize_client(self):
        """Initialize the Cosmos DB client, database, and container."""
        try:
            # Create the client
            self.client = CosmosClient(
                url=self.endpoint,
                credential=self.key,
                connection_mode=self.connection_mode,
                connection_protocol=self.connection_protocol,
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

    def generate_test_document(self, size_kb: int = 1) -> Dict[str, Any]:
        """Generate a test document of the specified size."""
        # Create a base document
        doc = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "test_run_id": str(uuid.uuid4()),
            "data_type": "benchmark",
        }

        # Add padding to reach the desired size
        # Each character is approximately 1 byte
        padding_size = size_kb * 1024 - len(json.dumps(doc))
        if padding_size > 0:
            doc["padding"] = "x" * padding_size

        return doc

    def generate_test_documents(
        self, count: int, size_kb: int = 1
    ) -> List[Dict[str, Any]]:
        """Generate multiple test documents."""
        return [self.generate_test_document(size_kb) for _ in range(count)]

    def benchmark_single_insert(self, doc_size_kb: int = 1) -> float:
        """Benchmark a single document insert."""
        doc = self.generate_test_document(doc_size_kb)

        start_time = time.time()
        self.container.create_item(body=doc)
        end_time = time.time()

        return end_time - start_time

    def benchmark_bulk_insert(
        self, doc_count: int, doc_size_kb: int = 1
    ) -> Tuple[float, List[float]]:
        """Benchmark bulk document insert."""
        docs = self.generate_test_documents(doc_count, doc_size_kb)

        # Prepare operations for bulk execution
        operations = []
        for doc in docs:
            operations.append({"operationType": "Create", "resourceBody": doc})

        # Measure total time
        start_time = time.time()
        results = list(self.container.execute_bulk(operations))
        end_time = time.time()
        total_time = end_time - start_time

        # Extract individual operation times from request charge (RU)
        # This is an approximation as Cosmos DB doesn't provide exact timing for each operation
        request_charges = [result.get("requestCharge", 0) for result in results]

        return total_time, request_charges

    def benchmark_query(
        self, query: str, parameters: List[Dict[str, Any]] = None
    ) -> float:
        """Benchmark a query."""
        start_time = time.time()
        list(
            self.container.query_items(
                query=query, parameters=parameters, enable_cross_partition_query=True
            )
        )
        end_time = time.time()

        return end_time - start_time

    def benchmark_parallel_inserts(
        self, doc_count: int, doc_size_kb: int = 1, max_workers: int = 10
    ) -> List[float]:
        """Benchmark parallel document inserts."""
        docs = self.generate_test_documents(doc_count, doc_size_kb)
        times = []

        def insert_doc(doc):
            start_time = time.time()
            self.container.create_item(body=doc)
            end_time = time.time()
            return end_time - start_time

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            times = list(executor.map(insert_doc, docs))

        return times

    def run_benchmarks(
        self, doc_sizes: List[int], doc_counts: List[int], max_workers: List[int]
    ):
        """Run all benchmarks."""
        # Single insert benchmarks
        single_insert_results = {}
        for size in doc_sizes:
            times = []
            for _ in range(10):  # Run each test 10 times
                times.append(self.benchmark_single_insert(size))
            single_insert_results[size] = times
        self.results["single_insert"] = single_insert_results

        # Bulk insert benchmarks
        bulk_insert_results = {}
        for count in doc_counts:
            for size in doc_sizes:
                key = f"{count}_{size}"
                times = []
                charges = []
                for _ in range(5):  # Run each test 5 times
                    time_taken, request_charges = self.benchmark_bulk_insert(
                        count, size
                    )
                    times.append(time_taken)
                    charges.extend(request_charges)
                bulk_insert_results[key] = {"times": times, "charges": charges}
        self.results["bulk_insert"] = bulk_insert_results

        # Parallel insert benchmarks
        parallel_insert_results = {}
        for workers in max_workers:
            for count in [
                min(100, c) for c in doc_counts
            ]:  # Limit to 100 docs for parallel tests
                for size in doc_sizes:
                    key = f"{workers}_{count}_{size}"
                    times = self.benchmark_parallel_inserts(count, size, workers)
                    parallel_insert_results[key] = times
        self.results["parallel_insert"] = parallel_insert_results

        # Query benchmarks
        query_results = {}
        # Simple query
        simple_query = "SELECT * FROM c WHERE c.data_type = @dataType"
        simple_params = [{"name": "@dataType", "value": "benchmark"}]
        times = []
        for _ in range(10):  # Run each test 10 times
            times.append(self.benchmark_query(simple_query, simple_params))
        query_results["simple"] = times

        # Complex query
        complex_query = """
        SELECT c.id, c.timestamp, c.test_run_id
        FROM c
        WHERE c.data_type = @dataType
        AND c.timestamp > @timestamp
        ORDER BY c.timestamp DESC
        """
        complex_params = [
            {"name": "@dataType", "value": "benchmark"},
            {
                "name": "@timestamp",
                "value": (
                    datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                ).isoformat(),
            },
        ]
        times = []
        for _ in range(10):  # Run each test 10 times
            times.append(self.benchmark_query(complex_query, complex_params))
        query_results["complex"] = times

        self.results["query"] = query_results

    def plot_results(self, output_dir: str = "."):
        """Plot benchmark results."""
        # Create output directory if it doesn't exist
        import os

        os.makedirs(output_dir, exist_ok=True)

        # Plot single insert results
        plt.figure(figsize=(10, 6))
        sizes = sorted(self.results["single_insert"].keys())
        times = [np.mean(self.results["single_insert"][size]) for size in sizes]
        plt.bar(range(len(sizes)), times)
        plt.xticks(range(len(sizes)), [f"{size} KB" for size in sizes])
        plt.xlabel("Document Size")
        plt.ylabel("Average Time (seconds)")
        plt.title("Single Document Insert Performance")
        plt.savefig(f"{output_dir}/single_insert.png")

        # Plot bulk insert results
        plt.figure(figsize=(12, 8))
        keys = sorted(self.results["bulk_insert"].keys())
        times = [np.mean(self.results["bulk_insert"][key]["times"]) for key in keys]
        plt.bar(range(len(keys)), times)
        plt.xticks(
            range(len(keys)),
            [key.replace("_", " docs, ") + " KB" for key in keys],
            rotation=45,
        )
        plt.xlabel("Bulk Insert Configuration")
        plt.ylabel("Average Time (seconds)")
        plt.title("Bulk Insert Performance")
        plt.tight_layout()
        plt.savefig(f"{output_dir}/bulk_insert.png")

        # Plot parallel insert results
        plt.figure(figsize=(12, 8))
        keys = sorted(self.results["parallel_insert"].keys())
        times = [np.mean(self.results["parallel_insert"][key]) for key in keys]
        plt.bar(range(len(keys)), times)
        plt.xticks(
            range(len(keys)),
            [
                key.replace("_", " workers, ").replace("_", " docs, ") + " KB"
                for key in keys
            ],
            rotation=45,
        )
        plt.xlabel("Parallel Insert Configuration")
        plt.ylabel("Average Time (seconds)")
        plt.title("Parallel Insert Performance")
        plt.tight_layout()
        plt.savefig(f"{output_dir}/parallel_insert.png")

        # Plot query results
        plt.figure(figsize=(10, 6))
        query_types = sorted(self.results["query"].keys())
        times = [
            np.mean(self.results["query"][query_type]) for query_type in query_types
        ]
        plt.bar(range(len(query_types)), times)
        plt.xticks(
            range(len(query_types)),
            [query_type.capitalize() for query_type in query_types],
        )
        plt.xlabel("Query Type")
        plt.ylabel("Average Time (seconds)")
        plt.title("Query Performance")
        plt.savefig(f"{output_dir}/query.png")

        # Save results as JSON
        with open(f"{output_dir}/benchmark_results.json", "w") as f:
            # Convert numpy arrays to lists for JSON serialization
            results_json = {}
            for category, category_results in self.results.items():
                results_json[category] = {}
                for key, values in category_results.items():
                    if isinstance(values, dict):
                        results_json[category][key] = {
                            k: v.tolist() if isinstance(v, np.ndarray) else v
                            for k, v in values.items()
                        }
                    else:
                        results_json[category][key] = (
                            values.tolist()
                            if isinstance(values, np.ndarray)
                            else values
                        )

            json.dump(results_json, f, indent=2)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Benchmark Azure Cosmos DB operations")
    parser.add_argument("--config", required=True, help="Path to configuration file")
    parser.add_argument(
        "--output",
        default="benchmark_results",
        help="Output directory for benchmark results",
    )

    args = parser.parse_args()

    try:
        # Initialize benchmark
        benchmark = CosmosBenchmark(args.config)

        # Run benchmarks
        benchmark.run_benchmarks(
            doc_sizes=[1, 10, 100],  # Document sizes in KB
            doc_counts=[10, 100, 1000],  # Number of documents
            max_workers=[1, 5, 10, 20],  # Number of worker threads
        )

        # Plot results
        benchmark.plot_results(args.output)

        logger.info(f"Benchmark results saved to {args.output}")

    except Exception as e:
        logger.error(f"Benchmark failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
