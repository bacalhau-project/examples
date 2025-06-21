#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
# "duckdb",
# "requests",
# "natsort",
# "google-cloud-storage",
# "google-cloud-bigquery",
# "google-cloud-resource-manager",
# "google-cloud-iam",
# "google-cloud-service-usage",
# "google-auth",
# "pyyaml",
# "google-api-core",
# ]
# ///
"""
Integration tests for the unified log processor

These tests connect to actual BigQuery endpoints but perform only read operations.
They verify that the processor can successfully connect and interact with BigQuery
without making any destructive changes.
"""

import os
import sys
import pytest
import tempfile
import yaml
from pathlib import Path

# Add the parent directory to the path so we can import the processor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bigquery-uploader'))

from bigquery_uploader import load_config, SCHEMAS


class TestBigQueryIntegration:
    """Integration tests that connect to real BigQuery"""

    @pytest.fixture
    def real_config(self):
        """Load the actual project configuration"""
        config_path = os.environ.get('CONFIG_FILE')
        if not config_path:
            pytest.skip("CONFIG_FILE environment variable is required but not set")

        if not os.path.exists(config_path):
            pytest.skip("Project config file not found")

        try:
            config = load_config(config_path)
        except Exception as e:
            pytest.skip(f"Could not load config: {e}")

        # Skip if no valid project ID configured
        if not config.get('project_id') or config['project_id'] == 'your-gcp-project-id':
            pytest.skip("No valid project ID in config")

        # Set credentials if specified, with environment variable override
        credentials_path = os.environ.get('CREDENTIALS_FILE') or config.get('credentials_path')

        if credentials_path:
            if os.path.exists(credentials_path):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            else:
                pytest.skip(f"Credentials file not found: {credentials_path}")
        elif not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            pytest.skip("No BigQuery credentials available")

        return config

    def test_bigquery_client_creation(self, real_config):
        """Test that we can create a BigQuery client"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=real_config['project_id'])

            # Verify client has correct project
            assert client.project == real_config['project_id']

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            pytest.fail(f"Failed to create BigQuery client: {e}")

    def test_list_datasets(self, real_config):
        """Test that we can list datasets (read-only operation)"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=real_config['project_id'])

            # List datasets - this is a read-only operation
            datasets = list(client.list_datasets(max_results=10))

            # Should be able to iterate through datasets
            for dataset in datasets:
                assert dataset.dataset_id is not None
                assert dataset.project == real_config['project_id']

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            pytest.fail(f"Failed to list datasets: {e}")

    def test_dataset_access(self, real_config):
        """Test accessing the configured dataset"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=real_config['project_id'])

            dataset_id = f"{real_config['project_id']}.{real_config['dataset']}"

            try:
                dataset = client.get_dataset(dataset_id)

                # Verify dataset properties
                assert dataset.dataset_id == real_config['dataset']
                assert dataset.project == real_config['project_id']

                # Test listing tables in the dataset
                tables = list(client.list_tables(dataset, max_results=10))

                print(f"Found {len(tables)} tables in dataset {dataset_id}")
                for table in tables:
                    print(f"  - {table.table_id}")

            except Exception as e:
                print(f"Dataset {dataset_id} not accessible (may not exist yet): {e}")
                # This is not a failure - dataset might not exist yet

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")

    def test_table_schemas_validation(self, real_config):
        """Test that our table schemas would be valid in BigQuery"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=real_config['project_id'])

            # Test each schema by creating a temporary table reference
            # (without actually creating the table)
            dataset_id = f"{real_config['project_id']}.{real_config['dataset']}"

            for mode, schema in SCHEMAS.items():
                table_name = real_config['tables'].get(mode, f'test_table_{mode}')
                table_id = f"{dataset_id}.{table_name}"

                # Create a table reference to validate schema
                table_ref = bigquery.Table(table_id, schema=schema)

                # Verify schema properties
                assert len(table_ref.schema) > 0

                for field in table_ref.schema:
                    assert field.name is not None
                    assert field.field_type is not None
                    assert field.mode in ['REQUIRED', 'NULLABLE', 'REPEATED']

                print(f"Schema for {mode} mode is valid ({len(schema)} fields)")

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            pytest.fail(f"Schema validation failed: {e}")

    def test_query_permissions(self, real_config):
        """Test that we have query permissions (read-only)"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=real_config['project_id'])

            # Try a simple query that doesn't access any tables
            query = "SELECT 1 as test_value, 'hello' as test_string"

            query_job = client.query(query)
            results = list(query_job.result())

            assert len(results) == 1
            assert results[0].test_value == 1
            assert results[0].test_string == 'hello'

            print("Basic query permissions verified")

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            pytest.fail(f"Query permissions test failed: {e}")

    def test_existing_tables_access(self, real_config):
        """Test reading from existing tables if they exist"""
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=real_config['project_id'])

            dataset_id = f"{real_config['project_id']}.{real_config['dataset']}"

            for mode, table_name in real_config['tables'].items():
                table_id = f"{dataset_id}.{table_name}"

                try:
                    # Try to get table metadata
                    table = client.get_table(table_id)

                    print(f"Table {table_id} exists:")
                    print(f"  - Rows: {table.num_rows}")
                    print(f"  - Schema fields: {len(table.schema)}")
                    print(f"  - Created: {table.created}")
                    print(f"  - Modified: {table.modified}")

                    # Try to query a small sample (read-only)
                    if table.num_rows > 0:
                        query = f"SELECT * FROM `{table_id}` LIMIT 1"
                        query_job = client.query(query)
                        results = list(query_job.result())

                        if results:
                            print(f"  - Sample row has {len(results[0])} columns")

                except Exception as e:
                    print(f"Table {table_id} not accessible: {e}")
                    # Not a failure - table might not exist yet

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            print(f"Table access test encountered error: {e}")
            # Not failing the test as tables might not exist yet


class TestEndToEndConfiguration:
    """Test the complete configuration pipeline"""

    def test_config_to_bigquery_pipeline(self):
        """Test loading config and using it to connect to BigQuery"""
        config_path = os.environ.get('CONFIG_FILE')
        if not config_path:
            pytest.skip("CONFIG_FILE environment variable is required but not set")

        if not os.path.exists(config_path):
            pytest.skip(f"Project config file not found: {config_path}")

        try:
            # Load configuration
            config = load_config(config_path)

            # Skip if no valid setup
            if not config.get('project_id') or config['project_id'] == 'your-gcp-project-id':
                pytest.skip("No valid project ID in config")

            # Set credentials from config, with environment variable override
            credentials_path = os.environ.get('CREDENTIALS_FILE') or config.get('credentials_path')

            if credentials_path:
                if os.path.exists(credentials_path):
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                else:
                    pytest.skip(f"Credentials file not found: {credentials_path}")
            elif not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                pytest.skip("No BigQuery credentials available")

            # Test BigQuery connection using config
            from google.cloud import bigquery
            client = bigquery.Client(project=config['project_id'])

            # Verify we can use the configured dataset
            dataset_id = f"{config['project_id']}.{config['dataset']}"
            print(f"Testing dataset: {dataset_id}")

            # Test that all configured table names are valid
            for mode, table_name in config['tables'].items():
                table_id = f"{dataset_id}.{table_name}"

                # Validate table ID format
                assert '.' in table_id
                assert len(table_name) > 0
                assert table_name.replace('_', '').isalnum()

            print("Configuration to BigQuery pipeline test passed")

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            pytest.fail(f"End-to-end configuration test failed: {e}")


if __name__ == '__main__':
    # Run integration tests if executed directly
    pytest.main([__file__, '-v', '-s'])
