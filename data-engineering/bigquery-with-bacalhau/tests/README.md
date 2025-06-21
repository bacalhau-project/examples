# Tests for Unified Log Processor

This directory contains comprehensive tests for the unified log processor, including unit tests, integration tests, and smoke tests.

## Test Types

### 1. Smoke Tests (`test_smoke.py`)
Quick validation that basic functionality works without external dependencies.

**What it tests:**
- Module imports work correctly
- Basic configuration loading
- Utility functions (IP sanitization, status categorization)
- BigQuery schema definitions are valid
- Default configuration is properly structured

**Run with:**
```bash
python test_smoke.py
```

### 2. Unit Tests (`test_unified_processor.py`)
Comprehensive unit tests for all processor components.

**What it tests:**
- Configuration file loading and validation
- Environment variable overrides
- Deep merging of configuration
- Error handling for missing/invalid configs
- Utility functions with edge cases
- Retry decorator functionality
- BigQuery connectivity (if credentials available)

**Run with:**
```bash
pytest test_unified_processor.py -v
```

### 3. Integration Tests (`test_integration.py`)
Real-world tests that connect to actual BigQuery endpoints (read-only operations).

**What it tests:**
- Actual BigQuery client creation
- Dataset listing and access
- Table schema validation
- Query permissions
- Reading from existing tables (if they exist)
- End-to-end configuration pipeline

**Run with:**
```bash
pytest test_integration.py -v -s
```

## Prerequisites

### For Unit and Smoke Tests
```bash
pip install -r requirements.txt
```

### For Integration Tests
1. Valid BigQuery project and credentials
2. Update `../bigquery-exporter/config.yaml` with your project settings
3. **Important**: The config file specifies `credentials_path: /var/log/app/log_uploader_credentials.json` - you need to either:
   - Place your service account JSON file at that exact path, OR
   - Update the `credentials_path` in config.yaml to point to your actual credentials file, OR  
   - Set `CREDENTIALS_FILE` environment variable to override the config path, OR
   - Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable to override the config path

**Why Integration Tests Skip:**
Integration tests will be skipped if:
- No valid project_id in config (still set to template value)
- Credentials file not found at the specified path
- No `CREDENTIALS_FILE` or `GOOGLE_APPLICATION_CREDENTIALS` environment variable set

## Running All Tests

### Quick Test (Smoke Tests Only)
```bash
./run_tests.sh
```

### Full Test Suite
```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest -v

# Run with coverage
pytest --cov=../bigquery-exporter --cov-report=html
```

### Specific Test Categories
```bash
# Only configuration tests
pytest test_unified_processor.py::TestConfigurationHandling -v

# Only utility function tests
pytest test_unified_processor.py::TestUtilityFunctions -v

# Only BigQuery connectivity tests (requires credentials)
pytest test_unified_processor.py::TestBigQueryConnectivity -v

# Only integration tests (requires credentials)
pytest test_integration.py -v -s
```

## Test Configuration

### Test Config File (`test_config.yaml`)
Sample configuration for testing purposes. Modify as needed for your tests.

### Environment Variables for Testing
```bash
export CREDENTIALS_FILE="/path/to/service-account.json"  # Override credentials path
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"  # Alternative to CREDENTIALS_FILE
export PROJECT_ID="your-test-project"
export DATASET="test_dataset"
```

## What the Tests Verify

### Configuration Handling ✅
- YAML configuration loading
- Environment variable overrides  
- Deep merging of nested configurations
- Error handling for missing/invalid files
- Required field validation

### Utility Functions ✅
- IP address sanitization (IPv4 and IPv6)
- HTTP status code categorization
- Apache log timestamp parsing
- Error handling for invalid inputs

### BigQuery Integration ✅
- Client creation and authentication
- Dataset and table access (read-only)
- Schema validation
- Query permissions
- Table metadata reading

### Error Handling ✅
- Missing configuration files
- Invalid YAML syntax
- BigQuery connection failures
- Retry logic and exponential backoff

## Test Data

Tests use temporary files and mock data to avoid dependencies on external resources. Integration tests connect to real BigQuery but perform only read operations.

## Continuous Integration

These tests are designed to run in CI/CD environments:

```bash
# For CI without BigQuery access
pytest test_smoke.py test_unified_processor.py::TestConfigurationHandling test_unified_processor.py::TestUtilityFunctions -v

# For CI with BigQuery credentials
pytest -v
```

## Troubleshooting

### Import Errors
Make sure the processor module is importable:
```bash
export PYTHONPATH="$(pwd)/../bigquery-exporter:$PYTHONPATH"
```

### BigQuery Connection Issues
1. Verify credentials file exists and is valid
2. Check that project ID in config is correct
3. Ensure service account has necessary permissions:
   - BigQuery Data Viewer (for reading)
   - BigQuery Job User (for running queries)

### Missing Dependencies
```bash
pip install PyYAML pytest pandas duckdb google-cloud-bigquery
```

## Test Coverage

The tests aim for comprehensive coverage of:
- All configuration scenarios
- All utility functions
- Error conditions
- BigQuery operations (read-only)
- Integration scenarios

Run with coverage reporting:
```bash
pytest --cov=../bigquery-exporter --cov-report=term-missing
```