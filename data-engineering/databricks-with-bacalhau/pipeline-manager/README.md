# Pipeline Manager

Atomic pipeline configuration management for the Databricks S3 uploader pipeline.

## Overview

This container provides atomic read/write operations for managing pipeline configuration in the sensor SQLite database. It ensures no conflicts with the uploader by using:

- WAL (Write-Ahead Logging) mode for better concurrency
- IMMEDIATE transactions for write operations
- Retry logic with exponential backoff for locked database scenarios
- Proper transaction isolation

## Usage

### Local Development

```bash
# View current pipeline
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db get

# Change pipeline type
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db set filtered --by "operations" --reason "Enabling anomaly filtering"

# View history
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db history --limit 20

# Monitor changes in real-time
uv run -s pipeline_controller.py --db ../sample-sensor/data/sensor_data.db monitor
```

### Docker Usage

```bash
# Build the container
docker-compose build

# View current pipeline
docker-compose run --rm pipeline-manager python pipeline_controller.py --db /data/sensor_data.db get

# Change pipeline type
docker-compose run --rm pipeline-manager python pipeline_controller.py --db /data/sensor_data.db set filtered --by "docker_user"

# View history
docker-compose run --rm pipeline-manager python pipeline_controller.py --db /data/sensor_data.db history

# Monitor changes
docker-compose run --rm pipeline-manager python pipeline_controller.py --db /data/sensor_data.db monitor
```

### Kubernetes/Bacalhau Usage

```bash
# One-time pipeline change job
kubectl create job pipeline-change --image=pipeline-manager:latest -- \
  python pipeline_controller.py --db /data/sensor_data.db set aggregated --by "k8s_admin" --reason "Enable aggregation pipeline"

# View current configuration
kubectl run pipeline-check --image=pipeline-manager:latest --rm -it -- \
  python pipeline_controller.py --db /data/sensor_data.db get
```

## Pipeline Types

- `raw`: No processing, all data uploaded (maps to ingestion bucket)
- `schematized`: Schema validation and enrichment (maps to validated bucket)
- `filtered`: Business rule filtering (maps to enriched bucket)
- `aggregated`: Time-window aggregation with anomaly detection (maps to aggregated bucket)

## Database Schema

The pipeline configuration is stored in the `pipeline_config` table:

```sql
CREATE TABLE pipeline_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_type TEXT NOT NULL CHECK(pipeline_type IN ('raw', 'schematized', 'filtered', 'aggregated')),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,
    metadata TEXT  -- JSON field for additional information
)
```

## Atomic Operations

All operations use SQLite's transaction capabilities:

1. **Reads**: Use shared locks, allowing concurrent reads
2. **Writes**: Use IMMEDIATE transactions to acquire write locks
3. **Retries**: Automatic retry with exponential backoff for locked databases
4. **WAL Mode**: Enables readers to not block writers and vice versa

## Integration with Uploader

The S3 uploader reads the pipeline configuration at the start of each batch upload:

```python
# In the uploader
pipeline_type = self._get_pipeline_type(db_path)  # Atomic read
bucket = self._get_bucket_for_scenario(pipeline_type)
```

This ensures:
- No partial reads during configuration changes
- Clear separation of concerns
- No conflicts between configuration changes and uploads

## Monitoring

Use the `monitor` command to watch for pipeline changes in real-time:

```bash
docker-compose run --rm pipeline-manager python pipeline_controller.py --db /data/sensor_data.db monitor
```

This is useful for:
- Debugging pipeline changes
- Audit logging
- Real-time dashboards