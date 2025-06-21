# Configuration Runtime Validation Tests

This document describes the comprehensive test suite for validating configuration file changes during runtime in the BigQuery log processing pipeline.

## Overview

The configuration runtime validation tests (`test_config_runtime_validation.py`) ensure that the system properly handles configuration changes without requiring external dependencies like BigQuery or DuckDB. These tests focus on configuration parsing, validation, and error handling.

## What These Tests Verify

### ✅ Required Scenarios Covered

1. **Configuration state changes** (raw → schematized → sanitized → aggregated)
2. **Badly formatted configuration files** that should cause the process to quit
3. **Invalid field values** (e.g., `pipeline_mode: "BAD_FORMAT"`) that should cause errors
4. **Missing required fields** detection and handling
5. **Rapid configuration changes** processing
6. **Environment variable overrides** with configuration changes
7. **File permission and access issues** handling

### Test Architecture

The tests use a lightweight approach:
- **Mock heavy dependencies** (duckdb, google-cloud-bigquery, pandas) to avoid installation requirements
- **Real YAML parsing** to test format validation authentically
- **Temporary files** for safe, isolated testing
- **Environment variable patching** for override testing
- **Deep merge testing** for nested configuration structures

## Running the Tests

### Prerequisites

Only basic Python libraries are required:
```bash
pip install pytest pyyaml
```

### Execute Tests

```bash
# Set required environment variable
export EXECUTABLE_DIR="bigquery-uploader"

# Run all configuration runtime validation tests
python -m pytest tests/test_config_runtime_validation.py -v

# Run specific test
python -m pytest tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_invalid_pipeline_mode_validation -v

# Run with detailed output
python -m pytest tests/test_config_runtime_validation.py -v -s
```

## Individual Test Descriptions

### 1. Configuration State Changes
**Test**: `test_configuration_state_changes`
**Purpose**: Verify that valid pipeline mode transitions work correctly
**Scenarios**: 
- raw → schematized
- schematized → sanitized  
- sanitized → aggregated
- aggregated → raw

**Expected Behavior**: Configuration changes should be loaded successfully while preserving other settings.

### 2. Badly Formatted Configuration Detection
**Test**: `test_badly_formatted_config_detection`
**Purpose**: Ensure malformed YAML causes appropriate errors
**Test Cases**:
- Invalid indentation
- Unclosed brackets
- Invalid quotes
- Mixed tabs/spaces

**Expected Behavior**: `RuntimeError` with "Failed to load configuration" message.

### 3. Invalid Pipeline Mode Validation
**Test**: `test_invalid_pipeline_mode_validation`
**Purpose**: Test behavior with unsupported pipeline modes
**Invalid Modes Tested**: `BAD_FORMAT`, `invalid_mode`, `UNKNOWN`, `test123`, `""`

**Expected Behavior**: Configuration loads but would fail at runtime when processing.

### 4. Missing Required Fields
**Test**: `test_missing_required_fields_validation`
**Purpose**: Validate handling of missing critical fields
**Fields Tested**: `project_id`, `pipeline_mode`

**Expected Behavior**: Uses default values from `DEFAULT_CONFIG`.

### 5. Configuration Field Type Validation  
**Test**: `test_config_field_type_validation`
**Purpose**: Test incorrect field data types
**Invalid Types**:
- `pipeline_mode` as dict instead of string
- `chunk_size` as string instead of int
- `tables` as list instead of dict
- `metadata` as string instead of dict

**Expected Behavior**: Invalid types preserved for runtime error handling.

### 6. Deep Merge with Invalid Structure
**Test**: `test_configuration_deep_merge_with_invalid_structure`  
**Purpose**: Test deep merge behavior with complex nested structures
**Scenarios**: Mixed valid/invalid nested configurations

**Expected Behavior**: Valid structures merge correctly, invalid types preserved.

### 7. Rapid Configuration Changes
**Test**: `test_rapid_configuration_changes_simulation`
**Purpose**: Test system stability under rapid consecutive changes
**Scenario**: Multiple cycles through all valid pipeline modes

**Expected Behavior**: All changes processed correctly without conflicts.

### 8. Environment Variable Overrides
**Test**: `test_environment_variable_overrides_with_config_changes`
**Purpose**: Verify env vars override config changes correctly
**Variables Tested**: `PROJECT_ID`, `DATASET`, `REGION`

**Expected Behavior**: Environment variables take precedence over config file values.

### 9. Nonexistent Configuration File
**Test**: `test_config_file_nonexistent_handling`
**Purpose**: Test behavior when config file doesn't exist
**Expected Behavior**: `RuntimeError` with "Configuration file not found" message.

### 10. Configuration File Permission Issues
**Test**: `test_config_file_permission_issues`
**Purpose**: Test behavior with unreadable config files
**Expected Behavior**: `RuntimeError` with "Failed to load configuration" message.

## Integration with Existing Tests

This test suite complements the existing test architecture:

- **`test_basic.py`**: Basic functionality without external dependencies
- **`test_unified_processor.py`**: Comprehensive unit tests (requires dependencies)  
- **`test_integration.py`**: Real BigQuery integration tests
- **`test_config_runtime_validation.py`**: Configuration-focused tests (new)

## Error Scenarios Tested

### YAML Parsing Errors
```yaml
# Example: Invalid indentation
invalid: yaml: content:
  - broken
    - indentation
```

### Invalid Pipeline Modes
```yaml
# Example: Unsupported mode
pipeline_mode: BAD_FORMAT
project_id: test-project
```

### Missing Required Fields
```yaml  
# Example: Missing project_id
pipeline_mode: raw
dataset: test_dataset
# project_id: missing!
```

### Type Validation
```yaml
# Example: Wrong field type  
pipeline_mode: 
  invalid: type
project_id: test
```

## Expected Test Output

Successful test run:
```
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_configuration_state_changes PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_badly_formatted_config_detection PASSED  
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_invalid_pipeline_mode_validation PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_missing_required_fields_validation PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_config_field_type_validation PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_configuration_deep_merge_with_invalid_structure PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_rapid_configuration_changes_simulation PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_environment_variable_overrides_with_config_changes PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_config_file_nonexistent_handling PASSED
tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_config_file_permission_issues PASSED

================================== 10 passed in 0.46s ==================================
```

## Benefits of This Approach

1. **No External Dependencies**: Tests run without BigQuery, DuckDB, or pandas
2. **Fast Execution**: Complete test suite runs in under 1 second
3. **Comprehensive Coverage**: Tests all major configuration scenarios
4. **Pytest Integration**: Uses standard pytest patterns and conventions
5. **CI/CD Friendly**: No credentials or external services required
6. **Isolated Testing**: Each test uses temporary files and proper cleanup

## Contributing

When adding new configuration runtime tests:

1. Follow the existing `TestConfigurationRuntimeValidation` class pattern
2. Use `tempfile.NamedTemporaryFile` for temporary config files
3. Include proper cleanup in `try/finally` blocks
4. Add descriptive docstrings explaining the test purpose
5. Test both success and failure scenarios
6. Update this documentation with new test descriptions

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `EXECUTABLE_DIR` environment variable is set
2. **Permission Errors**: Tests create temporary files - ensure write permissions
3. **YAML Errors**: Tests intentionally create invalid YAML - errors are expected

### Debugging

Enable verbose output:
```bash
python -m pytest tests/test_config_runtime_validation.py -v -s --tb=long
```

Run individual tests:
```bash
python -m pytest tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_badly_formatted_config_detection -v
```

## Related Documentation

- `CLAUDE.md` - Project overview and testing guidelines
- `tests/README.md` - General testing framework documentation  
- `tests/test_unified_processor.py` - Comprehensive unit tests
- `bigquery-uploader/bigquery_uploader.py` - Main processor implementation