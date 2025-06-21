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
# ]
# ///
"""
Basic tests for the unified log processor that don't require external dependencies
"""

import os
import pytest
import sys

# Get executable directory from environment variable
executable_dir = os.environ.get('EXECUTABLE_DIR')
if not executable_dir:
    pytest.fail("EXECUTABLE_DIR environment variable is required but not set")

# Add the executable directory to the path so we can import the processor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', executable_dir))

def test_processor_import():
    """Test that we can import the processor module and its key components"""
    import bigquery_uploader as log_processor_unified

    # Check that key functions exist
    assert hasattr(log_processor_unified, 'DEFAULT_CONFIG')
    assert hasattr(log_processor_unified, 'sanitize_ip')
    assert hasattr(log_processor_unified, 'categorize_status')
    assert hasattr(log_processor_unified, 'parse_timestamp')
    assert hasattr(log_processor_unified, 'SCHEMAS')

    print("✓ Successfully imported log_processor_unified module")

def test_default_config_structure():
    """Test that DEFAULT_CONFIG has the expected structure"""
    from bigquery_uploader import DEFAULT_CONFIG

    required_fields = [
        'pipeline_mode', 'chunk_size', 'max_retries',
        'project_id', 'dataset', 'tables', 'metadata'
    ]

    for field in required_fields:
        assert field in DEFAULT_CONFIG, f"Missing required field: {field}"

    # Check nested structures
    assert isinstance(DEFAULT_CONFIG['tables'], dict)
    assert isinstance(DEFAULT_CONFIG['metadata'], dict)
    assert 'raw' in DEFAULT_CONFIG['tables']
    assert 'region' in DEFAULT_CONFIG['metadata']

    print("✓ DEFAULT_CONFIG has correct structure")

def test_ip_sanitization():
    """Test IP address sanitization functionality"""
    from bigquery_uploader import sanitize_ip

    # Test IPv4 sanitization
    assert sanitize_ip('192.168.1.100') == '192.168.1.0'
    assert sanitize_ip('10.0.0.5') == '10.0.0.0'
    assert sanitize_ip('172.16.255.1') == '172.16.255.0'

    # Test edge cases
    assert sanitize_ip('-') == '-'
    assert sanitize_ip('invalid-ip') == 'invalid-ip'

    print("✓ IP sanitization works correctly")

def test_status_categorization():
    """Test HTTP status code categorization"""
    from bigquery_uploader import categorize_status

    # Test various status codes
    assert categorize_status(200) == 'OK'
    assert categorize_status(201) == 'OK'
    assert categorize_status(301) == 'Redirect'
    assert categorize_status(302) == 'Redirect'
    assert categorize_status(404) == 'Not Found'
    assert categorize_status(403) == 'Client Error'
    assert categorize_status(500) == 'SystemError'
    assert categorize_status(502) == 'SystemError'

    # Test edge cases
    import pandas as pd
    assert categorize_status(pd.NA) == 'Unknown'
    assert categorize_status(None) == 'Unknown'

    print("✓ Status categorization works correctly")

def test_timestamp_parsing():
    """Test Apache log timestamp parsing"""
    from bigquery_uploader import parse_timestamp

    # Test valid timestamp
    ts = parse_timestamp('[10/Oct/2000:13:55:36 -0700]')
    assert ts is not None
    assert ts.year == 2000
    assert ts.month == 10
    assert ts.day == 10
    assert ts.hour == 13
    assert ts.minute == 55
    assert ts.second == 36

    # Test invalid timestamps
    assert parse_timestamp('-') is None
    assert parse_timestamp('invalid-timestamp') is None
    assert parse_timestamp(None) is None

    print("✓ Timestamp parsing works correctly")

def test_bigquery_schemas():
    """Test that BigQuery schemas are properly defined"""
    from bigquery_uploader import SCHEMAS

    expected_modes = ['raw', 'schematized', 'aggregated', 'emergency']

    for mode in expected_modes:
        assert mode in SCHEMAS, f"Missing schema for mode: {mode}"
        schema = SCHEMAS[mode]
        assert len(schema) > 0, f"Empty schema for mode: {mode}"

        # Check that each field has required attributes
        for field in schema:
            assert hasattr(field, 'name'), f"Field missing name in {mode} schema"
            assert hasattr(field, 'field_type'), f"Field missing field_type in {mode} schema"
            assert hasattr(field, 'mode'), f"Field missing mode in {mode} schema"

    print("✓ BigQuery schemas are properly defined")

def test_config_file_exists():
    """Test that the main config file exists and is readable"""
    config_path = os.environ.get('CONFIG_FILE')
    if not config_path:
        pytest.fail("CONFIG_FILE environment variable is required but not set")

    assert os.path.exists(config_path), f"Config file not found: {config_path}"

    # Try to read the file
    with open(config_path, 'r') as f:
        content = f.read()
        assert len(content) > 0, "Config file is empty"
        assert 'pipeline_mode' in content, "Config file missing pipeline_mode"
        assert 'project_id' in content, "Config file missing project_id"

    print("✓ Main config file exists and is readable")

def main():
    """Run all basic tests"""
    print("Running Basic Tests for Unified Log Processor")
    print("=" * 50)

    tests = [
        test_processor_import,
        test_default_config_structure,
        test_ip_sanitization,
        test_status_categorization,
        test_timestamp_parsing,
        test_bigquery_schemas,
        test_config_file_exists
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All basic tests passed!")
        return 0
    else:
        print(f"❌ {failed} tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
