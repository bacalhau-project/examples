# SQLite Migration Guide

This guide explains the architectural changes made to support reading from SQLite databases instead of Apache log files.

## Overview

The BigQuery uploader has been updated to read sensor data from a SQLite database instead of parsing Apache-style log files. This change provides better data structure, query capabilities, and integration with the sensor simulator system.

## Key Architectural Changes

### 1. Data Source
- **Before**: Read Apache log files using DuckDB (`/bacalhau_data/*.log`)
- **After**: Query SQLite database (`/bacalhau_data/sensor_data.db`)

### 2. Query Mechanism
- **Before**: DuckDB CSV reader with pattern matching
- **After**: SQLite3 with SQL queries and sync tracking

### 3. Data Model
- **Before**: Apache log entries (IP, timestamp, HTTP method, status codes)
- **After**: Sensor readings (temperature, humidity, pressure, voltage, anomalies)

### 4. Processing Modes

The four processing modes have been adapted for sensor data:

| Mode | Before (Logs) | After (Sensors) |
|------|---------------|-----------------|
| **raw** | Upload raw log lines | Upload sensor readings with minimal processing |
| **schematized** | Parse HTTP fields, extract metadata | Structure sensor data with device/location info |
| **sanitized** | Anonymize IP addresses | Anonymize GPS coordinates and location names |
| **aggregated** | Hourly HTTP status summaries | Hourly sensor metrics + anomaly extraction |

### 5. BigQuery Schema Changes

New schemas optimized for sensor data:
- **raw**: Basic sensor readings with upload metadata
- **schematized**: Full sensor data with device information
- **aggregated**: Time-window aggregations (avg/min/max values)
- **anomalies**: Extracted anomaly events (replaces emergency logs)

### 6. Sync Tracking
- SQLite includes a `synced` boolean flag
- Successfully uploaded records are marked as synced
- Prevents duplicate uploads on subsequent runs

## Migration Steps

### 1. Update Configuration

Replace your log-based configuration with SQLite configuration:

```yaml
# Old configuration
input_paths:
  - "/bacalhau_data/*.log"

# New configuration
database:
  path: "/bacalhau_data/sensor_data.db"
  table: "sensor_readings"
  sync_enabled: true
```

### 2. Update Docker Image

Build the new SQLite-enabled image:

```bash
# Build new image
docker build -f Dockerfile.sqlite -t bigquery-uploader-sqlite:latest .

# Or use docker-compose
docker-compose -f docker-compose.sqlite.yml build
```

### 3. Update Volume Mounts

Change volume mounts from log files to database:

```yaml
# Old volumes
volumes:
  - ./logs:/bacalhau_data:ro

# New volumes
volumes:
  - ./data:/bacalhau_data  # Contains sensor_data.db
  - ./tmp:/tmp            # SQLite temporary files
```

### 4. Update Environment Variables

New environment variables:
- `DATABASE_PATH` or `DATABASE_FILE`: Override database path
- Removed: `LOG_FILE` environment variable

### 5. Run the Migration

1. Stop the old log processor
2. Deploy sensor simulator to generate SQLite database
3. Start the new SQLite processor:

```bash
docker run -v $(pwd)/data:/bacalhau_data \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  -e CONFIG_FILE=/app/config.yaml \
  bigquery-uploader-sqlite:latest
```

## Testing the Migration

Run the included tests to verify SQLite integration:

```bash
# Run SQLite integration tests
python tests/test_sqlite_integration.py

# Test with sample database
./bigquery-uploader/test-sqlite.sh
```

## Performance Considerations

### SQLite Optimizations
- WAL mode enabled for better concurrency
- Pragmas set for container environments
- Proper indexing on timestamp and synced columns

### Memory Usage
- Chunked processing maintained (same as log version)
- Categorical data types for efficient memory usage
- Connection pooling for database access

### Concurrency
- Single writer limitation of SQLite
- Read-only access for multiple processors
- Sync flag prevents race conditions

## Troubleshooting

### Common Issues

1. **"database is locked" errors**
   - Ensure only one writer process
   - Check SQLite busy timeout settings
   - Verify WAL mode is enabled

2. **Missing synced column**
   - Database schema may be outdated
   - Add column: `ALTER TABLE sensor_readings ADD COLUMN synced BOOLEAN DEFAULT 0`

3. **Slow queries**
   - Create index: `CREATE INDEX idx_synced_timestamp ON sensor_readings(synced, timestamp)`
   - Vacuum database periodically

4. **Container permission issues**
   - Ensure database file has proper permissions
   - Use SQLITE_TMPDIR environment variable

## Rollback Plan

If you need to revert to log file processing:

1. Keep the original `bigquery_uploader.py` file
2. Use the original Dockerfile
3. Restore log-based configuration
4. Redeploy with original image

## Benefits of SQLite Architecture

1. **Structured Data**: Proper schema vs. text parsing
2. **Query Flexibility**: SQL queries vs. regex patterns
3. **State Management**: Built-in sync tracking
4. **Data Integrity**: ACID compliance
5. **Integration**: Direct compatibility with sensor simulator
6. **Performance**: Indexed queries vs. full file scans

## Future Enhancements

Potential improvements to consider:
- PostgreSQL support for better concurrency
- Real-time streaming with database triggers
- Partitioned tables for time-series optimization
- Automated archival of synced records