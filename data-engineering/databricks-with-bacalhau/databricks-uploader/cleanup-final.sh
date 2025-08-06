#!/bin/bash
# Final cleanup: Consolidate configs and create a clean structure

set -e

echo "🧹 Final cleanup: Creating clean structure..."

# Archive redundant configs
mkdir -p archive/old-configs
echo "📁 Consolidating configuration files..."
mv -f aggregation_scheduler_config.yaml archive/old-configs/ 2>/dev/null || true
mv -f data_validation_config.yaml archive/old-configs/ 2>/dev/null || true
mv -f json_log_processor_config.yaml archive/old-configs/ 2>/dev/null || true
mv -f sensor_validation_spec.yaml archive/old-configs/ 2>/dev/null || true
mv -f unity_catalog_config.yaml archive/old-configs/ 2>/dev/null || true

# Keep only essential configs
echo "📁 Keeping essential configs:"
echo "  - s3-uploader-config.yaml (main pipeline config)"
echo "  - logging_config.yaml (logging settings)"
echo "  - retry_config.yaml (retry policies)"

# Create a clean README for what's left
cat > README.md << 'EOF'
# Databricks Uploader - Core Components

This directory contains the essential components for uploading data from SQLite to Databricks.

## Core Pipeline Files

### Main Components
- `pipeline_manager.py` - Manages pipeline state and configuration
- `pipeline_orchestrator.py` - Orchestrates the data pipeline flow
- `sqlite_to_json_transformer.py` - Transforms SQLite data to JSON format
- `upload_state_manager.py` - Tracks upload progress and state

### Supporting Utilities
- `config_db.py` - Database configuration management
- `retry_handler.py` & `retry_manager.py` - Retry logic for failed operations
- `log_monitor.py` & `pipeline_logging.py` - Logging and monitoring
- `spec_version_manager.py` - Manages data specification versions

### Configuration Files
- `s3-uploader-config.yaml` - Main configuration for the S3 uploader
- `logging_config.yaml` - Logging configuration
- `retry_config.yaml` - Retry policies configuration

### Additional Components
- `autoloader_main.py` - Main entry point for Auto Loader
- `api_backend.py` - API backend for pipeline management
- `json_log_processor.py` - Processes JSON log files
- `sensor_data_models.py` - Data models for sensor data

## Archived Files

All test files, demos, examples, and redundant implementations have been moved to the `archive/` directory for reference.

## Usage

See the main project README for usage instructions.
EOF

echo "✅ Final cleanup complete!"
echo ""
echo "📊 Final structure:"
echo "  Essential Python scripts: $(ls -1 *.py 2>/dev/null | wc -l)"
echo "  Essential configs: $(ls -1 *.yaml 2>/dev/null | wc -l)"
echo "  Database files: $(ls -1 *.db 2>/dev/null | wc -l)"
echo ""
echo "📁 Directory structure:"
ls -la | grep -E "^d" | grep -v "^\." | awk '{print "  - " $9}'
echo ""
echo "✨ The databricks-uploader directory is now clean and organized!"