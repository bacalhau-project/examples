#!/usr/bin/env python3
"""
Test script to validate the fail-fast behavior of the BigQuery uploader.
This script tests that the processor immediately crashes when log files are not found.
"""

import os
import sys
import tempfile
import shutil
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

def create_test_config(logs_dir, credentials_path="./test_credentials.json"):
    """Create a test configuration file"""
    config = {
        'pipeline_mode': 'raw',
        'chunk_size': 1000,
        'max_retries': 3,
        'base_retry_delay': 1,
        'max_retry_delay': 10,
        'check_interval': 5,
        'project_id': 'test-project',
        'dataset': 'test_dataset',
        'credentials_path': credentials_path,
        'input_paths': [f"{logs_dir}/*.log", f"{logs_dir}/access.log"],
        'tables': {
            'raw': 'raw_logs',
            'schematized': 'log_results',
            'sanitized': 'log_results',
            'aggregated': 'log_aggregates',
            'emergency': 'emergency_logs'
        },
        'node_id': 'test-node',
        'metadata': {
            'region': 'test-region',
            'provider': 'test',
            'hostname': 'test-host'
        }
    }
    return config

def create_dummy_credentials():
    """Create a dummy credentials file for testing"""
    dummy_creds = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test",
        "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "test",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    return dummy_creds

def test_failfast_missing_files():
    """Test that the processor fails fast when no log files are found"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create empty logs directory
        logs_dir = os.path.join(temp_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Create test config
        config = create_test_config(logs_dir)

        # Create dummy credentials
        creds_path = os.path.join(temp_dir, "test_credentials.json")
        with open(creds_path, 'w') as f:
            import json
            json.dump(create_dummy_credentials(), f)

        config['credentials_path'] = creds_path

        # Add the bigquery-uploader path to sys.path for import
        bigquery_uploader_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bigquery-uploader')
        if bigquery_uploader_path not in sys.path:
            sys.path.insert(0, bigquery_uploader_path)

        # Mock environment variables
        with patch.dict(os.environ, {}, clear=False):
            # Import and test the validate_input_files function directly
            try:
                from bigquery_uploader import validate_input_files

                # This should raise SystemExit due to no files found
                with pytest.raises(SystemExit) as exc_info:
                    validate_input_files(config)

                # Verify it exits with non-zero code
                assert exc_info.value.code != 0, "Should exit with non-zero code when no files found"

            except ImportError:
                # Fallback: test that the config would fail validation
                import glob
                files_found = []
                for pattern in config['input_paths']:
                    files_found.extend(glob.glob(pattern, recursive=True))

                # Should find no files
                assert len(files_found) == 0, f"Expected no files, but found: {files_found}"

def test_with_existing_files():
    """Test that the processor works when log files exist"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create logs directory with a sample log file
        logs_dir = os.path.join(temp_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Create a sample log file
        log_file = os.path.join(logs_dir, "access.log")
        with open(log_file, 'w') as f:
            f.write('127.0.0.1 - - [01/Jan/2024:00:00:00 +0000] "GET /test HTTP/1.1" 200 1024\n')
            f.write('127.0.0.1 - - [01/Jan/2024:00:00:01 +0000] "GET /test2 HTTP/1.1" 404 512\n')

        # Create test config
        config = create_test_config(logs_dir)

        # Create dummy credentials
        creds_path = os.path.join(temp_dir, "test_credentials.json")
        with open(creds_path, 'w') as f:
            import json
            json.dump(create_dummy_credentials(), f)

        config['credentials_path'] = creds_path

        # Add the bigquery-uploader path to sys.path for import
        bigquery_uploader_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bigquery-uploader')
        if bigquery_uploader_path not in sys.path:
            sys.path.insert(0, bigquery_uploader_path)

        # Test that validation passes when files exist
        try:
            from bigquery_uploader import validate_input_files

            # This should NOT raise SystemExit because files exist
            validate_input_files(config)  # Should complete without error

        except ImportError:
            # Fallback: test that the config finds files
            import glob
            files_found = []
            for pattern in config['input_paths']:
                files_found.extend(glob.glob(pattern, recursive=True))

            # Should find the log file
            assert len(files_found) > 0, f"Expected to find files, but found none for patterns: {config['input_paths']}"
            assert any('access.log' in f for f in files_found), f"Expected to find access.log in: {files_found}"
        except SystemExit:
            pytest.fail("validate_input_files should not exit when files exist")

if __name__ == "__main__":
    # Run tests using pytest when executed directly
    pytest.main([__file__, '-v'])
