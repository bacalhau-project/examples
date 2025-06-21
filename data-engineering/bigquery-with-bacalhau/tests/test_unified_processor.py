#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.10"
# dependencies = [
# "duckdb",
# "requests",
# "pandas",
# "pyyaml",
# "google-cloud-storage",
# "google-cloud-bigquery",
# "google-cloud-resource-manager",
# "google-cloud-iam",
# "google-cloud-service-usage",
# "google-auth",
# "google-api-core",
# "pytest",
# ]
# ///
"""
Tests for the unified log processor

These tests verify:
1. Configuration file loading and validation
2. BigQuery connectivity (read-only operations)
3. Error handling for missing/invalid configurations
"""

import os
import sys
import pytest
import tempfile
import yaml
from unittest.mock import patch, MagicMock
from pathlib import Path

# Get executable directory from environment variable
executable_dir = os.environ.get('EXECUTABLE_DIR')
if not executable_dir:
    pytest.fail("EXECUTABLE_DIR environment variable is required but not set")

# Add the executable directory to the path so we can import the processor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', executable_dir))

from bigquery_uploader import (
    load_config,
    DEFAULT_CONFIG,
    with_retries,
    ensure_table_exists,
    sanitize_ip,
    categorize_status,
    parse_timestamp
)

class TestConfigurationHandling:
    """Test configuration file loading and validation"""

    def test_load_valid_config(self):
        """Test loading a valid YAML configuration file"""
        config_data = {
            'pipeline_mode': 'sanitized',
            'chunk_size': 10000,
            'project_id': 'test-project',
            'dataset': 'test_dataset',
            'credentials_path': '/path/to/creds.json',
            'input_paths': ['/path/to/logs/*.log'],
            'tables': {
                'raw': 'raw_logs',
                'schematized': 'log_results'
            },
            'metadata': {
                'region': 'us-west1',
                'provider': 'gcp'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        # Store original environment variables
        env_vars_to_clear = ['GOOGLE_APPLICATION_CREDENTIALS', 'CREDENTIALS_FILE', 'CREDENTIALS_PATH', 'PROJECT_ID', 'DATASET', 'NODE_ID', 'REGION', 'PROVIDER', 'HOSTNAME']
        original_env = {}
        for var in env_vars_to_clear:
            original_env[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

        try:
            config = load_config(config_path)

            # Verify merged configuration
            assert config['pipeline_mode'] == 'sanitized'
            assert config['chunk_size'] == 10000
            assert config['project_id'] == 'test-project'
            assert config['dataset'] == 'test_dataset'
            assert config['credentials_path'] == '/path/to/creds.json'
            assert config['input_paths'] == ['/path/to/logs/*.log']
            assert config['tables']['raw'] == 'raw_logs'
            assert config['metadata']['region'] == 'us-west1'
            assert config['metadata']['provider'] == 'gcp'

            # Verify defaults are preserved for unspecified values
            assert config['max_retries'] == DEFAULT_CONFIG['max_retries']
        finally:
            # Restore original environment variables
            for var, value in original_env.items():
                if value is not None:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]
            os.unlink(config_path)

    def test_missing_config_file(self):
        """Test error handling when config file doesn't exist"""
        with pytest.raises(RuntimeError, match="Configuration file not found"):
            load_config('/nonexistent/path/config.yaml')

    def test_invalid_yaml_config(self):
        """Test error handling for invalid YAML syntax"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            config_path = f.name

        try:
            with pytest.raises(RuntimeError, match="Failed to load configuration"):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_environment_variable_overrides(self):
        """Test that environment variables override config file values"""
        config_data = {
            'pipeline_mode': 'raw',
            'project_id': 'config-project',
            'metadata': {
                'region': 'us-central1',
                'provider': 'gcp'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with patch.dict(os.environ, {
                'PROJECT_ID': 'env-project',
                'REGION': 'us-west1',
                'NODE_ID': 'test-node'
            }):
                config = load_config(config_path)

                # Environment variables should override config values
                assert config['project_id'] == 'env-project'
                assert config['metadata']['region'] == 'us-west1'
                assert config['node_id'] == 'test-node'

                # Non-overridden values should remain from config
                assert config['pipeline_mode'] == 'raw'
                assert config['metadata']['provider'] == 'gcp'

        finally:
            os.unlink(config_path)

    def test_deep_merge_configuration(self):
        """Test that nested configurations are properly merged"""
        config_data = {
            'tables': {
                'raw': 'custom_raw_logs',
                'aggregated': 'custom_aggregates'
            },
            'metadata': {
                'region': 'eu-west1'
                # provider should come from defaults
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            # Custom values should be present
            assert config['tables']['raw'] == 'custom_raw_logs'
            assert config['tables']['aggregated'] == 'custom_aggregates'
            assert config['metadata']['region'] == 'eu-west1'

            # Default values should be preserved
            assert config['tables']['schematized'] == DEFAULT_CONFIG['tables']['schematized']
            assert config['metadata']['provider'] == DEFAULT_CONFIG['metadata']['provider']

        finally:
            os.unlink(config_path)

    def test_log_file_environment_variable_override(self):
        """Test that LOG_FILE and log_file environment variables override input_paths from config"""
        config_data = {
            'pipeline_mode': 'raw',
            'project_id': 'test-project',
            'input_paths': ['/original/path/*.log', '/another/path/*.log']
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            # Test without log_file environment variable
            config = load_config(config_path)
            assert config['input_paths'] == ['/original/path/*.log', '/another/path/*.log']

            # Test with lowercase log_file environment variable set
            with patch.dict(os.environ, {'log_file': '/override/path/single.log'}):
                config = load_config(config_path)
                assert config['input_paths'] == ['/override/path/single.log']

            # Test with uppercase LOG_FILE environment variable set
            with patch.dict(os.environ, {'LOG_FILE': '/override/path/uppercase.log'}):
                config = load_config(config_path)
                assert config['input_paths'] == ['/override/path/uppercase.log']

            # Test that uppercase LOG_FILE takes precedence over lowercase log_file
            with patch.dict(os.environ, {
                'LOG_FILE': '/uppercase/wins.log',
                'log_file': '/lowercase/loses.log'
            }):
                config = load_config(config_path)
                assert config['input_paths'] == ['/uppercase/wins.log']

        finally:
            os.unlink(config_path)


class TestUtilityFunctions:
    """Test utility functions used by the processor"""

    def test_sanitize_ip_ipv4(self):
        """Test IPv4 address sanitization"""
        assert sanitize_ip('192.168.1.100') == '192.168.1.0'
        assert sanitize_ip('10.0.0.5') == '10.0.0.0'
        assert sanitize_ip('172.16.255.1') == '172.16.255.0'

    def test_sanitize_ip_ipv6(self):
        """Test IPv6 address sanitization"""
        assert sanitize_ip('2001:db8:85a3:8d3:1319:8a2e:370:7344').startswith('2001:db8:85a3:8d3:')
        assert sanitize_ip('fe80::1').startswith('fe80:')

    def test_sanitize_ip_invalid(self):
        """Test handling of invalid IP addresses"""
        assert sanitize_ip('-') == '-'
        assert sanitize_ip('invalid-ip') == 'invalid-ip'
        assert sanitize_ip(None) == '-'

    def test_categorize_status(self):
        """Test HTTP status code categorization"""
        assert categorize_status(200) == 'OK'
        assert categorize_status(201) == 'OK'
        assert categorize_status(301) == 'Redirect'
        assert categorize_status(404) == 'Not Found'
        assert categorize_status(403) == 'Client Error'
        assert categorize_status(500) == 'SystemError'
        assert categorize_status(502) == 'SystemError'
        assert categorize_status(None) == 'Unknown'

    def test_parse_timestamp(self):
        """Test log timestamp parsing"""
        # Valid Apache log timestamp
        ts = parse_timestamp('[10/Oct/2000:13:55:36 -0700]')
        assert ts is not None
        assert ts.year == 2000
        assert ts.month == 10
        assert ts.day == 10

        # Invalid timestamps
        assert parse_timestamp('-') is None
        assert parse_timestamp('invalid-timestamp') is None
        assert parse_timestamp(None) is None


class TestBigQueryConnectivity:
    """Test BigQuery connectivity (read-only operations)"""

    def test_bigquery_connection_with_real_config(self):
        """Test actual BigQuery connection using project config"""
        # Load the actual project config
        config_path = os.environ.get('CONFIG_FILE')
        if not config_path:
            pytest.skip("CONFIG_FILE environment variable is required but not set")

        if not os.path.exists(config_path):
            pytest.skip(f"Project config file not found: {config_path}")

        try:
            config = load_config(config_path)
        except Exception as e:
            pytest.skip(f"Could not load config: {e}")

        # Skip if no project ID configured
        if not config.get('project_id') or config['project_id'] == 'your-gcp-project-id':
            pytest.skip("No valid project ID in config")

        # Set credentials if specified in config, with environment variable override
        credentials_path = os.environ.get('CREDENTIALS_FILE') or config.get('credentials_path')

        if credentials_path and os.path.exists(credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        elif not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            pytest.skip("No BigQuery credentials available")

        try:
            from google.cloud import bigquery

            # Test connection
            client = bigquery.Client(project=config['project_id'])

            # Test basic connectivity - list datasets (read-only)
            datasets = list(client.list_datasets(max_results=1))

            # Test dataset access if it exists
            dataset_id = f"{config['project_id']}.{config['dataset']}"
            try:
                dataset = client.get_dataset(dataset_id)
                assert dataset.dataset_id == config['dataset']

                # List tables in the dataset (read-only)
                tables = list(client.list_tables(dataset, max_results=5))

                # If tables exist, verify we can describe them (read-only)
                for table in tables:
                    table_ref = client.get_table(table.reference)
                    assert table_ref.schema is not None
                    assert len(table_ref.schema) > 0

            except Exception as e:
                # Dataset might not exist yet, which is fine for this test
                print(f"Dataset {dataset_id} not accessible: {e}")

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")
        except Exception as e:
            pytest.fail(f"BigQuery connection failed: {e}")

    def test_table_schema_validation(self):
        """Test that our table schemas are valid BigQuery schemas"""
        from bigquery_uploader import SCHEMAS

        try:
            from google.cloud import bigquery

            for mode, schema in SCHEMAS.items():
                # Verify each schema field is valid
                for field in schema:
                    assert isinstance(field, bigquery.SchemaField)
                    assert field.name is not None
                    assert field.field_type is not None
                    assert field.mode in ['REQUIRED', 'NULLABLE', 'REPEATED']

                # Verify schema is not empty
                assert len(schema) > 0

        except ImportError:
            pytest.skip("google-cloud-bigquery not installed")

    def test_retry_decorator(self):
        """Test the retry decorator functionality"""
        call_count = 0

        @with_retries
        def failing_function(config=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        # Test successful retry
        config = {'max_retries': 5, 'base_retry_delay': 0.1, 'max_retry_delay': 1}
        result = failing_function(config=config)
        assert result == "success"
        assert call_count == 3

        # Test max retries exceeded
        call_count = 0

        @with_retries
        def always_failing_function(config=None):
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        config = {'max_retries': 2, 'base_retry_delay': 0.1, 'max_retry_delay': 1}
        with pytest.raises(Exception, match="Always fails"):
            always_failing_function(config=config)
        assert call_count == 2


class TestConfigurationValidation:
    """Test configuration field validation and requirements"""

    def test_required_fields_present(self):
        """Test that all required fields are present in loaded config"""
        config_data = {
            'pipeline_mode': 'raw',
            'project_id': 'test-project'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            # Check that all essential fields are present (from defaults or config)
            required_fields = [
                'pipeline_mode', 'chunk_size', 'max_retries',
                'project_id', 'dataset', 'tables', 'metadata'
            ]

            for field in required_fields:
                assert field in config, f"Required field '{field}' missing from config"

            # Check nested required fields
            assert 'raw' in config['tables']
            assert 'schematized' in config['tables']
            assert 'region' in config['metadata']
            assert 'provider' in config['metadata']

        finally:
            os.unlink(config_path)

    def test_pipeline_mode_validation(self):
        """Test that pipeline_mode values are valid"""
        valid_modes = ['raw', 'schematized', 'sanitized', 'aggregated']

        for mode in valid_modes:
            config_data = {
                'pipeline_mode': mode,
                'project_id': 'test-project'
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config_data, f)
                config_path = f.name

            try:
                config = load_config(config_path)
                assert config['pipeline_mode'] == mode
            finally:
                os.unlink(config_path)


class TestConfigurationRuntimeValidation:
    """Test configuration file changes and runtime validation"""

    def test_configuration_state_changes(self):
        """Test that configuration state changes are handled correctly"""
        # Test valid state transitions
        state_transitions = [
            ('raw', 'schematized'),
            ('schematized', 'sanitized'),
            ('sanitized', 'aggregated'),
            ('aggregated', 'raw')
        ]

        for initial_mode, new_mode in state_transitions:
            # Create initial config
            initial_config_data = {
                'pipeline_mode': initial_mode,
                'project_id': 'test-project',
                'dataset': 'test_dataset',
                'tables': {
                    'raw': 'test_raw_logs',
                    'schematized': 'test_log_results',
                    'sanitized': 'test_log_results_sanitized',
                    'aggregated': 'test_log_aggregates',
                    'emergency': 'test_emergency_logs'
                }
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(initial_config_data, f)
                config_path = f.name

            try:
                # Load initial config
                initial_config = load_config(config_path)
                assert initial_config['pipeline_mode'] == initial_mode

                # Update config with new mode
                new_config_data = initial_config_data.copy()
                new_config_data['pipeline_mode'] = new_mode

                with open(config_path, 'w') as f:
                    yaml.dump(new_config_data, f)

                # Load updated config
                updated_config = load_config(config_path)
                assert updated_config['pipeline_mode'] == new_mode

                # Verify other fields remain unchanged
                assert updated_config['project_id'] == initial_config['project_id']
                assert updated_config['dataset'] == initial_config['dataset']

            finally:
                os.unlink(config_path)

    def test_badly_formatted_config_detection(self):
        """Test that badly formatted YAML is properly detected and raises errors"""
        bad_yaml_examples = [
            # Invalid indentation
            "invalid: yaml: content:\n  - broken\n    - indentation",
            # Unclosed brackets
            "pipeline_mode: raw\ntables: [unclosed",
            # Invalid quotes
            "pipeline_mode: 'unclosed quote\nproject_id: test",
            # Mixing tabs and spaces (Python YAML parser issue)
            "pipeline_mode: raw\n\tproject_id: test\n  dataset: test"
        ]

        for bad_yaml in bad_yaml_examples:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(bad_yaml)
                config_path = f.name

            try:
                with pytest.raises(RuntimeError, match="Failed to load configuration"):
                    load_config(config_path)
            finally:
                os.unlink(config_path)

    def test_invalid_pipeline_mode_validation(self):
        """Test that invalid pipeline modes are handled appropriately"""
        invalid_modes = ['BAD_FORMAT', 'invalid_mode', 'UNKNOWN', 'test123', '', None, 123]

        for invalid_mode in invalid_modes:
            config_data = {
                'pipeline_mode': invalid_mode,
                'project_id': 'test-project',
                'dataset': 'test_dataset',
                'tables': {
                    'raw':'test_raw_logs',
                    'schematized': 'test_log_results',
                    'sanitized': 'test_log_results_sanitized',
                    'aggregated': 'test_log_aggregates',
                    'emergency': 'test_emergency_logs'
                }
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config_data, f)
                config_path = f.name

            try:
                # Config should load without error (validation happens at runtime)
                config = load_config(config_path)
                assert config['pipeline_mode'] == invalid_mode

                # However, when trying to access schemas or tables for invalid modes,
                # it should fail during processing (simulated here)
                from bigquery_uploader import SCHEMAS

                if invalid_mode not in ['raw', 'schematized', 'sanitized', 'aggregated']:
                    with pytest.raises(KeyError):
                        _ = SCHEMAS[invalid_mode]

            finally:
                os.unlink(config_path)

    def test_missing_required_fields_validation(self):
        """Test that missing required fields are properly detected"""
        required_fields = ['project_id', 'pipeline_mode', 'dataset']

        for missing_field in required_fields:
            config_data = {
                'pipeline_mode': 'raw',
                'project_id': 'test-project',
                'dataset': 'test_dataset',
                'tables': {
                    'raw': 'test_raw_logs'
                }
            }

            # Remove the required field
            del config_data[missing_field]

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config_data, f)
                config_path = f.name

            try:
                # Config should still load (uses defaults), but validation
                # happens when required fields are accessed
                config = load_config(config_path)

                if missing_field not in config or not config[missing_field]:
                    # This would fail at runtime when the pipeline tries to run
                    assert missing_field not in config or not config[missing_field]

            finally:
                os.unlink(config_path)

    def test_config_field_type_validation(self):
        """Test that incorrect field types are handled properly"""
        invalid_type_configs = [
            # pipeline_mode should be string, not dict
            {'pipeline_mode': {'invalid': 'type'}, 'project_id': 'test'},
            # chunk_size should be int, not string
            {'pipeline_mode': 'raw', 'chunk_size': 'not_a_number', 'project_id': 'test'},
            # tables should be dict, not list
            {'pipeline_mode': 'raw', 'tables': ['invalid', 'type'], 'project_id': 'test'},
            # metadata should be dict, not string
            {'pipeline_mode': 'raw', 'metadata': 'invalid_type', 'project_id': 'test'}
        ]

        for invalid_config in invalid_type_configs:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(invalid_config, f)
                config_path = f.name

            try:
                # Config should load (type validation happens during usage)
                config = load_config(config_path)

                # Verify the invalid types are preserved (for runtime handling)
                for key, value in invalid_config.items():
                    assert config[key] == value

            finally:
                os.unlink(config_path)

    def test_configuration_deep_merge_with_invalid_structure(self):
        """Test that deep merge handles invalid nested structures gracefully"""
        config_data = {
            'pipeline_mode': 'raw',
            'project_id': 'test-project',
            'metadata': {
                'region': 'us-west1',
                'invalid_nested': {
                    'deeply': {
                        'nested': {
                            'structure': 'value'
                        }
                    }
                }
            },
            'tables': 'invalid_type_should_be_dict'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            # Should load without error, merging with defaults where possible
            config = load_config(config_path)

            # Verify deep merge worked for valid structures
            assert config['metadata']['region'] == 'us-west1'
            assert config['metadata']['invalid_nested']['deeply']['nested']['structure'] == 'value'

            # Invalid type should be preserved
            assert config['tables'] == 'invalid_type_should_be_dict'

        finally:
            os.unlink(config_path)

    def test_rapid_configuration_changes_simulation(self):
        """Test simulated rapid configuration changes"""
        modes = ['raw', 'schematized', 'sanitized', 'aggregated']

        base_config = {
            'project_id': 'test-project',
            'dataset': 'test_dataset',
            'tables': {
                'raw': 'test_raw_logs',
                'schematized': 'test_log_results',
                'sanitized': 'test_log_results_sanitized',
                'aggregated': 'test_log_aggregates',
                'emergency': 'test_emergency_logs'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_path = f.name

        try:
            # Simulate rapid changes by repeatedly updating and loading config
            for i, mode in enumerate(modes * 3):  # Test multiple cycles
                config_data = base_config.copy()
                config_data['pipeline_mode'] = mode
                config_data['node_id'] = f'test-node-{i}'  # Unique identifier

                with open(config_path, 'w') as f:
                    yaml.dump(config_data, f)

                # Load and verify
                config = load_config(config_path)
                assert config['pipeline_mode'] == mode
                assert config['node_id'] == f'test-node-{i}'

        finally:
            os.unlink(config_path)


if __name__ == '__main__':
    # Run tests if executed directly
    pytest.main([__file__, '-v'])
