# Timestamp Tracking Feature

## Overview

The BigQuery log processor now includes automatic timestamp tracking to prevent duplicate log processing. This feature maintains a record of the last processed log timestamp and ensures that only new logs are processed on subsequent runs.

## How It Works

### 1. Timestamp File
- **Location**: `bigquery-uploader/last_batch_timestamp.json`
- **Format**: JSON with timestamp, last updated time, and description
- **Persistence**: Survives between runs and system restarts

### 2. Automatic Filtering
- On startup, the system checks for the timestamp file
- If found, only logs with timestamps newer than the last processed timestamp are loaded
- If not found (first run), all logs are processed

### 3. Timestamp Updates
- After each successful chunk processing, the maximum timestamp is tracked
- At the end of processing, the timestamp file is updated with the latest processed timestamp
- Updates only occur if new data was actually processed

## Supported Pipeline Modes

| Mode | Timestamp Tracking | Notes |
|------|-------------------|-------|
| `raw` | ❌ No | Raw mode doesn't parse timestamps |
| `schematized` | ✅ Yes | Uses parsed Apache log timestamps |
| `sanitized` | ✅ Yes | Uses parsed Apache log timestamps |
| `aggregated` | ✅ Yes | Uses time_window or emergency log timestamps |

## File Format

The `last_batch_timestamp.json` file contains:

```json
{
  "last_batch_timestamp": "2024-01-15T13:30:00+00:00",
  "last_updated": "2025-06-21T18:20:59.285264+00:00",
  "description": "Tracks the latest log timestamp processed to prevent duplicate uploads"
}
```

## Benefits

### 1. Prevents Duplicate Processing
- Eliminates reprocessing of already-uploaded logs
- Reduces BigQuery costs and processing time
- Maintains data integrity

### 2. Incremental Processing
- Only processes new log entries
- Perfect for scheduled/cron jobs
- Handles log rotation seamlessly

### 3. Fail-Safe Recovery
- If a run fails midway, the next run continues from the last successful timestamp
- No data loss or duplication
- Automatic recovery from interruptions

## Log Timestamp Format

The system expects Apache Common Log Format timestamps:
```
[15/Jan/2024:12:30:45 +0000]
```

- **Format**: `[DD/MMM/YYYY:HH:MM:SS ±HHMM]`
- **Location**: Column 3 (0-indexed) in space-delimited Apache logs
- **Timezone**: Fully supported with proper offset handling

## Usage Examples

### First Run
```bash
# No timestamp file exists - processes all logs
./bigquery_uploader.py

# Output:
# INFO - No previous batch timestamp found - this appears to be the first run
# INFO - Processed 1000 rows from all available logs
# INFO - Updated batch timestamp tracking to: 2024-01-15T13:30:00+00:00
```

### Subsequent Runs
```bash
# Timestamp file exists - only processes new logs
./bigquery_uploader.py

# Output:
# INFO - Found previous timestamp: 2024-01-15T13:30:00+00:00
# INFO - Filtering logs newer than: 2024-01-15T13:30:00+00:00
# INFO - Processed 50 rows from new logs
# INFO - Updated batch timestamp tracking to: 2024-01-15T14:15:00+00:00
```

## Configuration

No additional configuration required. The feature is automatically enabled for compatible pipeline modes.

### Environment Variables
- **GOOGLE_APPLICATION_CREDENTIALS**: BigQuery credentials (required)
- **PROJECT_ID**: BigQuery project ID (required)
- **CONFIG_FILE**: Path to configuration file (optional)

## Testing

### Unit Tests
```bash
# Run comprehensive timestamp tracking tests
./tests/test_timestamp_tracking.py
```

### Demo
```bash
# Interactive demonstration of timestamp tracking
./tests/demo_timestamp_tracking.py
```

## Troubleshooting

### Common Issues

#### 1. Timestamp File Corruption
**Symptoms**: Error reading timestamp file
**Solution**: Delete `last_batch_timestamp.json` to reset (will reprocess all logs)

#### 2. Clock Skew
**Symptoms**: New logs not being processed
**Solution**: Ensure system clocks are synchronized

#### 3. Timezone Mismatches
**Symptoms**: Incorrect filtering behavior
**Solution**: Verify log timestamps include proper timezone offsets

### Debug Information

Enable debug logging to see timestamp filtering details:
```bash
export LOG_LEVEL=DEBUG
./bigquery_uploader.py
```

## Implementation Details

### Timestamp Comparison
- Uses string comparison on formatted Apache timestamps
- Format: `[DD/MMM/YYYY:HH:MM:SS ±HHMM]`
- Lexicographic ordering works correctly for chronological filtering

### Memory Efficiency
- Timestamp tracking adds minimal memory overhead
- Only stores single timestamp value per processing run
- No impact on chunk-based processing

### Error Handling
- Graceful fallback if timestamp file is corrupted
- Continues processing even if timestamp update fails
- Logs all timestamp-related operations for debugging

## Migration

### Existing Deployments
- **Automatic**: No changes needed to existing configurations
- **First Run**: Will process all existing logs and create timestamp file
- **Subsequent Runs**: Will automatically use timestamp filtering

### Rollback
To disable timestamp tracking:
1. Delete `last_batch_timestamp.json`
2. Revert to previous version of `bigquery_uploader.py`

## Performance Impact

- **Startup**: Minimal (~1ms to read timestamp file)
- **Processing**: Reduces rows processed by filtering at DuckDB level
- **Storage**: Single small JSON file per deployment
- **Network**: Reduces BigQuery API calls by eliminating duplicates

## Security Considerations

- Timestamp file contains no sensitive information
- Uses same directory permissions as the application
- No network communication for timestamp tracking
- Fully local state management

## Future Enhancements

### Planned Features
- [ ] Timestamp tracking for custom log formats
- [ ] Multiple timestamp file support for parallel processing
- [ ] Compression for large timestamp files
- [ ] Integration with external state stores (Redis, etc.)

### API Extensions
- [ ] REST API for timestamp management
- [ ] Metrics endpoint for monitoring
- [ ] Manual timestamp reset capabilities