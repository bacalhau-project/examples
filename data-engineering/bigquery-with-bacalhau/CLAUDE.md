# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a distributed log processing pipeline that demonstrates processing logs across multiple nodes using Bacalhau and uploading results to Google BigQuery. The system processes Apache-style access logs through four progressive stages: raw upload, structured parsing, privacy-preserving sanitization, and smart aggregation. The system includes automatic timestamp tracking to prevent duplicate log processing between runs.

## Common Development Commands

### Setup and Configuration
```bash
# Interactive setup for BigQuery project and tables
./utility_scripts/setup.py -i

# Confirm tables exist and create if needed
./utility_scripts/confirm_tables.sh

# Distribute credentials to Bacalhau nodes
./utility_scripts/distribute_credentials.sh

# Test BigQuery connection
./utility_scripts/test_bigquery.py
```

### Building and Testing
```bash
# Build Docker image for log processors
./bigquery-exporter/build.sh

# Test log processor locally (versions 0-3)
./bigquery-exporter/local_debug.sh <version_number> [input_file]

# Test unified processor locally with debugging
./debug_local.sh --generate --mode sanitized --project your-gcp-project-id

# Test fail-fast behavior
python3 test_failfast.py

# Test timestamp tracking functionality
./tests/test_timestamp_tracking.py

# Demo timestamp tracking in action
./tests/demo_timestamp_tracking.py

# Run specific processor with base64 encoding
bacalhau job run bigquery_export_job.yaml --template-vars=python_file_b64=$(cat bigquery-exporter/log_process_0.py | base64)
```

### BigQuery Queries
```bash
# Query results (replace $PROJECT_ID with actual project)
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.log_analytics.raw_logs\` LIMIT 5"
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.log_analytics.log_results\` LIMIT 5"
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.log_analytics.log_aggregates\` ORDER BY time_window DESC LIMIT 5"
```

### Local Debugging
```bash
# Debug unified processor with custom config
CONFIG_FILE=./debug-config.yaml uv run --no-project bigquery_uploader.py

# Generate test logs and debug
./debug_local.sh --generate --mode sanitized

# Validate fail-fast behavior works
python3 test_failfast.py
```

### Testing
```bash
# Run configuration runtime validation tests (NO dependencies required)
./tests/run_config_tests.sh

# Or run manually:
EXECUTABLE_DIR=bigquery-uploader pytest tests/test_config_runtime_validation.py -v

# Run configuration runtime validation tests (NO dependencies required)
# These test configuration changes, state transitions, bad YAML, invalid modes, etc.
EXECUTABLE_DIR=bigquery-uploader pytest tests/test_config_runtime_validation.py -v

# IMPORTANT: Other tests require full dependencies and may fail without them
# Install dependencies first: pip install duckdb pandas google-cloud-bigquery

# Run all tests (requires dependencies: duckdb, pandas, google-cloud-bigquery)
# Note: Many tests may fail if dependencies are not installed
EXECUTABLE_DIR=bigquery-uploader CONFIG_FILE=tests/test_config.yaml pytest tests/ -v

# Run specific test categories (requires dependencies)
EXECUTABLE_DIR=bigquery-uploader pytest tests/test_basic.py -v            # Basic smoke tests - may fail without deps
EXECUTABLE_DIR=bigquery-uploader pytest tests/test_unified_processor.py -v # Unit tests - may fail without deps  
EXECUTABLE_DIR=bigquery-uploader pytest tests/test_integration.py -v       # Integration tests - requires BigQuery creds
```

## Architecture Overview

### Log Processing Pipeline
The system implements four progressive log processors in `bigquery-exporter/`:

1. **log_process_0.py**: Raw log upload - minimal processing, direct upload
2. **log_process_1.py**: Structured parsing - extracts fields from Apache logs
3. **log_process_2.py**: Privacy-preserving - anonymizes IP addresses
4. **log_process_3.py**: Smart aggregation - hourly summaries + emergency event extraction

Each processor follows the same pattern:
- Read logs from `/bacalhau_data` using DuckDB
- Process in chunks (default 10,000 rows) for memory efficiency
- Upload to BigQuery with retry logic and exponential backoff
- Continue processing even if individual chunks fail

### Key Design Patterns

**Retry Logic**: All BigQuery operations use `@with_retries` decorator with exponential backoff (max 20 retries, up to 60s delay).

**Chunked Processing**: Prevents memory exhaustion by processing logs in configurable chunks.

**Environment Configuration**: All settings via environment variables (GOOGLE_APPLICATION_CREDENTIALS, PROJECT_ID, etc.).

**Incremental Processing**: Uses timestamp tracking file (`last_batch_timestamp.json`) to maintain state between runs and only process new log entries.

**Privacy by Design**: IP sanitization preserves network information while protecting individual privacy.

**Fail-Fast File Validation**: System immediately crashes with clear error message if log files are not found, preventing repeated error messages and wasted processing time.

**Timestamp Tracking**: Automatically tracks the last processed log timestamp to prevent duplicate uploads. Only processes logs newer than the last successful batch, enabling efficient incremental processing.

### Bacalhau Job Structure

Jobs are defined in YAML files with key parameters:
- `Count`: Number of parallel instances (e.g., 20 for distributed processing)
- `TemplateVars`: Pass Python scripts as base64-encoded variables
- `InputSources`: Mount `/bacalhau_data` for log access
- `NetworkConfig`: Full network access for BigQuery API calls

### Extension Points

To add new processing logic:
1. Create `log_process_4.py` following the existing pattern
2. Define BigQuery schema for new table if needed
3. Update job YAML to reference new processor
4. Test locally with `local_debug.sh` before deploying

To modify aggregations:
- Edit time windows in `log_process_3.py`
- Add new statistical calculations
- Define additional BigQuery tables as needed

## Testing Guidelines

### Test Architecture
- **Use pytest exclusively** - Do not create custom test runners or bash scripts for tests
- **Follow existing patterns** - Study `tests/test_unified_processor.py` and `tests/test_basic.py` for structure
- **Use proper test classes** - Group related tests in classes like `TestConfigurationHandling`
- **Mock external dependencies** - Tests should not require BigQuery credentials or network access unless explicitly testing integration
- **Use temporary files** - Create and clean up test files using `tempfile.NamedTemporaryFile`

### Test Categories
1. **Smoke Tests** (`test_basic.py`) - Quick validation without external dependencies
2. **Unit Tests** (`test_unified_processor.py`) - Comprehensive component testing with mocks
3. **Integration Tests** (`test_integration.py`) - Real BigQuery connections (requires credentials)

### Configuration Testing Patterns
- **Test valid configurations** - Verify all pipeline modes work correctly
- **Test invalid configurations** - Ensure proper error handling for bad YAML, missing fields, invalid values
- **Test state transitions** - Verify configuration changes between pipeline modes
- **Test environment overrides** - Validate environment variables override config files
- **Test deep merging** - Ensure nested configuration structures merge correctly

### Running Tests
```bash
# Standard pytest execution
cd tests && python -m pytest -v

# Set required environment variables
export EXECUTABLE_DIR="bigquery-uploader"
export CONFIG_FILE="demo-network/files/config.yaml"

# Run with proper Python path
export PYTHONPATH="../bigquery-uploader:$PYTHONPATH"
python -m pytest tests/test_unified_processor.py::TestConfigurationRuntimeValidation -v
```

### Test Development Rules
- **No subprocess testing** - Test functions directly, not by spawning processes
- **No custom runners** - Use pytest's built-in test discovery and execution
- **Proper cleanup** - Always use try/finally or context managers to clean up resources
- **Clear assertions** - Use descriptive error messages in assertions
- **Test both success and failure cases** - Verify error conditions are handled properly

## Important Notes

- Always test processors locally before deploying to Bacalhau
- Use `./debug_local.sh` for comprehensive local testing with log generation
- Check BigQuery permissions with `check_permissions.sh` if uploads fail
- The system now fails fast when log files are missing - no more repeated "file not found" errors
- Monitor logs for chunk processing failures - the system continues but logs errors
- Use categorical data types in Pandas for memory efficiency with high-cardinality fields
- IP sanitization is critical for privacy compliance - do not remove without careful consideration
- Run `python3 test_failfast.py` to validate the fail-fast behavior works correctly
- The system automatically tracks processed timestamps in `last_batch_timestamp.json` - delete this file to reprocess all logs
- Timestamp tracking works for `schematized`, `sanitized`, and `aggregated` modes (not `raw` mode)
- Use `./tests/test_timestamp_tracking.py` and `./tests/demo_timestamp_tracking.py` to verify timestamp functionality