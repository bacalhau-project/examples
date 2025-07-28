# Pipeline Configuration Migration Guide

This guide explains how to migrate from config-file-based pipeline selection to the new database-driven approach using PipelineManager.

## Overview

The new system stores pipeline configuration in the SQLite database alongside your sensor data, providing:

- **Atomic Operations**: Pipeline type changes are atomic and safe
- **Concurrency Safety**: Multiple processes can safely read/write configuration
- **Audit Trail**: Complete history of pipeline executions and changes
- **Dynamic Updates**: Change pipeline type without restarting the uploader

## Migration Steps

### 1. Update Your SQLite Database

The PipelineManager will automatically create the necessary tables when first initialized:

```sql
-- New tables added to your existing database
pipeline_config       -- Stores current pipeline configuration
pipeline_executions   -- Tracks execution history
```

### 2. Update Configuration Files

Remove the `processing_mode` field from your YAML configuration files. The pipeline type is now managed in the database.

**Before:**
```yaml
processing_mode: "schematized"
enable_sanitize: true
sanitize_config:
  remove_nulls: ["temperature", "humidity"]
```

**After:**
```yaml
# processing_mode removed - now in database
# Keep processing-specific configs
sanitize_config:
  remove_nulls: ["temperature", "humidity"]
```

### 3. First-Time Migration

When you first run the updated uploader with an existing config file, it will automatically migrate your settings:

```bash
# The uploader detects the old format and migrates automatically
uv run -s sqlite_to_databricks_uploader.py --config config.yaml

# You'll see:
# "Migrated pipeline configuration from config file to database"
```

### 4. Managing Pipeline Type

Use the pipeline manager CLI to view and change pipeline types:

```bash
# View current pipeline
uv run -s pipeline_manager.py --db sensor_data.db get

# Change pipeline type
uv run -s pipeline_manager.py --db sensor_data.db set filtered --by "operations_team"

# View execution history
uv run -s pipeline_manager.py --db sensor_data.db history --limit 20
```

### 5. Integration with Uploader

The uploader now automatically:
1. Reads pipeline type from the database at the start of each cycle
2. Tracks execution start/completion
3. Records any errors that occur

## Pipeline Type Mapping

| Old Config Setting | New Pipeline Type | Target Table Suffix | S3 Bucket |
|-------------------|-------------------|---------------------|-----------|
| `processing_mode: raw` | `raw` | `_raw` | `raw` |
| `enable_sanitize: true` | `schematized` | `_schematized` | `schematized` |
| `enable_filter: true` | `filtered` | `_filtered` | `filtered` |
| `enable_aggregate: true` | `emergency` | `_emergency` | `emergency` |

## API Usage

### Python API

```python
from pipeline_manager import PipelineManager, PipelineType

# Initialize manager
manager = PipelineManager("sensor_data.db")

# Get current pipeline
config = manager.get_current_pipeline()
print(f"Current pipeline: {config.pipeline_type.value}")

# Change pipeline
manager.set_pipeline(
    pipeline_type=PipelineType.EMERGENCY,
    updated_by="automation_script",
    config_json={"threshold": 100}
)

# Track execution
exec_id = manager.start_execution()
# ... do work ...
manager.complete_execution(exec_id, records_processed=500)
```

### REST API (Future Enhancement)

Consider exposing pipeline management via a REST API for remote control:

```bash
# Get current pipeline
curl http://uploader-host:8080/api/pipeline

# Change pipeline
curl -X PUT http://uploader-host:8080/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"type": "emergency", "updated_by": "incident_response"}'
```

## Monitoring

Monitor pipeline changes and performance:

```sql
-- Recent pipeline changes
SELECT * FROM pipeline_config ORDER BY updated_at DESC;

-- Execution performance by pipeline type
SELECT 
    pipeline_type,
    COUNT(*) as executions,
    AVG(records_processed) as avg_records,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failures
FROM pipeline_executions
WHERE started_at > datetime('now', '-7 days')
GROUP BY pipeline_type;

-- Recent failures
SELECT * FROM pipeline_executions 
WHERE status = 'failed' 
ORDER BY started_at DESC 
LIMIT 10;
```

## Rollback Procedure

If you need to rollback to config-based pipeline selection:

1. Re-add `processing_mode` to your config file
2. Use the previous version of the uploader
3. The database tables will be ignored but remain for future use

## Best Practices

1. **Change Control**: Always specify `updated_by` when changing pipelines
2. **Monitoring**: Set up alerts on pipeline execution failures
3. **Testing**: Test pipeline changes in development first
4. **Documentation**: Document why pipeline changes are made
5. **Backup**: Regular backups of the SQLite database now include configuration

## Troubleshooting

### Common Issues

**Issue**: "No active pipeline configuration found"
- **Solution**: Run `pipeline_manager.py set raw` to initialize

**Issue**: Database locked errors
- **Solution**: Ensure WAL mode is enabled (automatic) and increase busy timeout

**Issue**: Pipeline changes not taking effect
- **Solution**: Check that the uploader is reading from the correct database

### Debug Mode

Enable detailed logging to troubleshoot:

```bash
export LOG_LEVEL=DEBUG
uv run -s sqlite_to_databricks_uploader.py --config config.yaml
```

## Security Considerations

1. **Access Control**: Limit who can change pipeline types
2. **Audit Trail**: Review pipeline_executions regularly
3. **Validation**: The system enforces valid pipeline types
4. **Backup**: Include pipeline tables in backup procedures

## Future Enhancements

- Web UI for pipeline management
- Scheduled pipeline type changes
- Pipeline-specific alerting rules
- Performance metrics dashboard
- Integration with incident management systems