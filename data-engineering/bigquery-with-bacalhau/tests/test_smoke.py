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
Smoke tests for the unified log processor

Quick tests to verify basic functionality without external dependencies.
"""

import os
import sys
import tempfile
import yaml

# Add the parent directory to the path so we can import the processor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bigquery-uploader'))

def test_import_processor():
    """Test that we can import the processor module"""
    try:
        import bigquery_uploader as log_processor_unified
        assert hasattr(log_processor_unified, 'load_config')
        assert hasattr(log_processor_unified, 'DEFAULT_CONFIG')
        assert hasattr(log_processor_unified, 'sanitize_ip')
        print("✓ Processor module imports successfully")
    except ImportError as e:
        raise AssertionError(f"Failed to import processor: {e}")

def test_basic_config_loading():
    """Test basic configuration loading"""
    from bigquery_uploader import load_config

    # Create a minimal config
    config_data = {
        'pipeline_mode': 'raw',
        'project_id': 'test-project'
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config['pipeline_mode'] == 'raw'
        assert config['project_id'] == 'test-project'
        print("✓ Basic configuration loading works")
    finally:
        os.unlink(config_path)

def test_utility_functions():
    """Test utility functions"""
    from bigquery_uploader import sanitize_ip, categorize_status, parse_timestamp

    # Test IP sanitization
    assert sanitize_ip('192.168.1.100') == '192.168.1.0'
    assert sanitize_ip('-') == '-'

    # Test status categorization
    assert categorize_status(200) == 'OK'
    assert categorize_status(404) == 'Not Found'
    assert categorize_status(500) == 'SystemError'

    # Test timestamp parsing
    ts = parse_timestamp('[10/Oct/2000:13:55:36 -0700]')
    assert ts is not None
    assert ts.year == 2000

    print("✓ Utility functions work correctly")

def test_schemas_are_valid():
    """Test that BigQuery schemas are properly defined"""
    from bigquery_uploader import SCHEMAS

    assert 'raw' in SCHEMAS
    assert 'schematized' in SCHEMAS
    assert 'aggregated' in SCHEMAS
    assert 'emergency' in SCHEMAS

    for mode, schema in SCHEMAS.items():
        assert len(schema) > 0, f"Schema for {mode} is empty"
        for field in schema:
            assert hasattr(field, 'name'), f"Field in {mode} schema missing name"
            assert hasattr(field, 'field_type'), f"Field in {mode} schema missing field_type"

    print("✓ BigQuery schemas are properly defined")

def test_default_config_is_valid():
    """Test that default configuration is valid"""
    from bigquery_uploader import DEFAULT_CONFIG

    required_fields = [
        'pipeline_mode', 'chunk_size', 'max_retries',
        'project_id', 'dataset', 'tables', 'metadata'
    ]

    for field in required_fields:
        assert field in DEFAULT_CONFIG, f"Required field '{field}' missing from DEFAULT_CONFIG"

    # Test nested structures
    assert 'raw' in DEFAULT_CONFIG['tables']
    assert 'region' in DEFAULT_CONFIG['metadata']

    print("✓ Default configuration is valid")

if __name__ == '__main__':
    """Run all smoke tests"""
    print("Running smoke tests for Unified Log Processor")
    print("=" * 50)

    tests = [
        test_import_processor,
        test_basic_config_loading,
        test_utility_functions,
        test_schemas_are_valid,
        test_default_config_is_valid
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1

    print()
    if failed == 0:
        print("🎉 All smoke tests passed!")
    else:
        print(f"❌ {failed} out of {len(tests)} tests failed")
        sys.exit(1)
