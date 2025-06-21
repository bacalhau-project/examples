# Unified Log Processor

The unified log processor (`log_processor_unified.py`) combines all four processing modes into a single, configuration-driven application.

## Features

- **Single Entry Point**: One script handles all processing modes
- **Configuration-Driven**: All settings controlled via JSON config file
- **Auto-Reload**: Watches config file for changes
- **Progressive Pipeline**: Each mode builds on previous ones
  - `raw`: Minimal processing, preserves original logs
  - `schematized`: Structured parsing of Apache logs
  - `sanitized`: Schematized + IP anonymization
  - `aggregated`: Sanitized + hourly aggregates + emergency events

## Configuration

The processor **requires** a YAML configuration file at `/bacalhau_data/config.yaml` (or `CONFIG_PATH` env var). The job will fail if the config file is not present.

### Complete Configuration Example

```yaml
pipeline_mode: sanitized
chunk_size: 500000
max_retries: 20
base_retry_delay: 1
max_retry_delay: 60
check_interval: 30
project_id: bq-2501151036
dataset: log_analytics
credentials_path: /var/log/app/log_uploader_credentials.json
input_paths:
  - /var/log/app/access.log
tables:
  raw: raw_logs
  schematized: log_results
  sanitized: log_results
  aggregated: log_aggregates
  emergency: emergency_logs
node_id: bacalhau-node
metadata:
  region: us-central1
  provider: gcp
  hostname: bacalhau-cluster
```

### Pipeline Modes

1. **raw**: Uploads raw log lines with minimal processing
   - Output: `raw_line`, `upload_time`

2. **schematized**: Parses logs into structured fields
   - Output: IP, timestamp, HTTP method/path/status, bytes, user agent, etc.

3. **sanitized**: Same as schematized + IP anonymization
   - IPv4: Zeroes last octet (192.168.1.100 → 192.168.1.0)
   - IPv6: Preserves /64 network

4. **aggregated**: Includes all sanitization + creates:
   - Hourly aggregates with status counts and byte statistics
   - Emergency event extraction (status >= 500)

### Configuration Fields

- **pipeline_mode**: Processing mode (raw/schematized/sanitized/aggregated)
- **chunk_size**: Number of rows to process at once
- **check_interval**: Seconds between config file checks
- **max_retries**: Maximum retry attempts for BigQuery operations
- **project_id**: Google Cloud project ID
- **dataset**: BigQuery dataset name
- **credentials_path**: Path to service account JSON file
- **input_paths**: Array of glob patterns for input log files
- **tables**: Table names for each processing mode
- **node_id**: Identifier for this processing node
- **metadata**: Additional metadata (region, provider, hostname)

## Usage

### Local Testing

```bash
# Create config file
cat > config.yaml <<EOF
pipeline_mode: sanitized
chunk_size: 10000
project_id: your-project
credentials_path: /path/to/credentials.json
input_paths:
  - /path/to/logs/*.log
EOF

# Run with config
export CONFIG_PATH="config.yaml"
python log_processor_unified.py
```

### Bacalhau Deployment

1. Upload the configuration file:
```bash
./utility_scripts/upload_config.sh bigquery-exporter/config.yaml
```

2. Deploy the processor:
```bash
./utility_scripts/manage_unified_processor.sh deploy
```

Or manually:
```bash
# Upload config first
bacalhau job run utility_scripts/upload_config.yaml

# Then run processor
bacalhau job run bigquery_export_unified.yaml \
  --template-vars="python_file_b64=$(cat bigquery-exporter/log_processor_unified.py | base64)"
```

### Dynamic Configuration Updates

The processor checks the config file every `check_interval` seconds. To change modes:

1. Update the config file:
```bash
# Change from raw to sanitized mode
yq eval '.pipeline_mode = "sanitized"' -i config.yaml
```

2. The processor will automatically detect the change and run with new settings

## Environment Variables

Environment variables can override config file values:

- `CONFIG_PATH`: Path to config file (default: `/bacalhau_data/config.yaml`)
- `PROJECT_ID`: Overrides `project_id` in config
- `DATASET`: Overrides `dataset` in config
- `CREDENTIALS_FILE`: Overrides `credentials_path` in config
- `GOOGLE_APPLICATION_CREDENTIALS`: Overrides `credentials_path` in config
- `NODE_ID`: Overrides `node_id` in config
- `REGION`: Overrides `metadata.region` in config
- `PROVIDER`: Overrides `metadata.provider` in config
- `HOSTNAME`: Overrides `metadata.hostname` in config

Note: The Bacalhau job automatically sets `NODE_ID` and `HOSTNAME` from node information.

## Monitoring

The processor logs all activities:
- Configuration changes
- Processing progress
- Failed chunks
- Emergency events (when in aggregated mode)

Check logs with:
```bash
bacalhau logs <job-id>
```

## Best Practices

1. Start with `raw` mode to preserve original data
2. Progress to `schematized` for structured analysis
3. Enable `sanitized` for privacy compliance
4. Use `aggregated` for dashboards and alerting

## Troubleshooting

If uploads fail:
1. Check BigQuery permissions with `utility_scripts/check_permissions.sh`
2. Verify table schemas match expected format
3. Check logs for specific chunk failures
4. Ensure credentials are properly distributed