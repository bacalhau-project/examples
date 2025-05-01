<!-- markdownlint-disable MD041 MD013 MD024 -->
# Bacalhau to Databricks Lakehouse Pipeline

This repository implements a continuous data pipeline that:
1. Reads sensor data from local SQLite databases on edge nodes.
2. Incrementally extracts new records and appends them to a Delta Lake table in cloud storage.
3. Enables scalable data analysis on the Databricks Lakehouse platform.

Key components:
- **Uploader script**: `uploader/upload_sqlite_to_s3.py`, a self-contained UV-run script that:
  - Automatically detects the SQLite table and timestamp column via schema introspection.
  - Tracks the last-upload timestamp in a state file.
  - Appends new rows to a Delta Lake table using the `deltalake` Python library.
- **Docker multi-stage build**: `uploader/Dockerfile` caches dependencies in a builder stage and produces a minimal runtime image.
- **Configuration**: `uploader-config.yaml.example` shows how to configure paths, table URI, state directory, and interval.
- **Launcher**: `start-uploader.sh` wraps the Docker invocation, mounting only the config directory.
- **Delta Lake management**: SQL snippets and Databricks CLI Docker examples to create and list tables.

For design rationale and detailed roadmap, see [REARCHITECTURE.md](REARCHITECTURE.md).

---

## Prerequisites
- Docker Engine (19.03+)
- (Optional) Python 3.11 and the `uv` CLI for local testing
- A Databricks workspace with a catalog/schema for Delta Lake
- Cloud storage account (AWS S3 or Azure Data Lake Storage Gen2)
  - Ensure credentials are configured (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or Azure service principal).

## Directory Layout
```text
./
├── uploader/                      # Python uploader and Dockerfile
│   └── upload_sqlite_to_s3.py     # UV-run script for incremental export
│   └── Dockerfile                 # Multi-stage UV-based image
├── uploader-config.yaml.example   # Example configuration
├── start-uploader.sh              # Shell wrapper to launch uploader container
├── REARCHITECTURE.md               # Re-architecture roadmap and checklist
├── docs/                          # Guides (e.g., Databricks connectivity)
└── README.md                      # This file
```

## Configuration
Copy `uploader-config.yaml.example` to `uploader-config.yaml` and customize:
```yaml
# Path inside container to the SQLite DB
sqlite: "/data/sensor.db"

# Delta Lake table URI (e.g., S3 path or ADLS path)
table_path: "s3://my-bucket/delta/bacalhau_results/sensor_readings"

# Directory inside container for state file (last upload timestamp)
state_dir: "/state"

# Upload interval in seconds
interval: 300
```
You can override any value with environment variables:
- `SQLITE_PATH`, `TABLE_PATH`, `STATE_DIR`, `UPLOAD_INTERVAL`

---

## Build the Uploader Container
```bash
docker build -t uploader-image:latest uploader
```

---

## Running the Uploader
1. Make the launcher script executable:
   ```bash
   chmod +x start-uploader.sh
   ```
2. Run with your config file:
   ```bash
   ./start-uploader.sh uploader-config.yaml
   ```
The uploader will run continuously, appending new records each cycle.

---

## Delta Lake Table Setup on Databricks
In a Databricks notebook or SQL editor, create your schema and table:
```sql
CREATE DATABASE IF NOT EXISTS bacalhau_results
  LOCATION 's3://<your-bucket>/delta/bacalhau_results';

CREATE TABLE IF NOT EXISTS bacalhau_results.sensor_readings
USING DELTA
LOCATION 's3://<your-bucket>/delta/bacalhau_results';
```
For Unity Catalog:
```sql
CREATE SCHEMA IF NOT EXISTS catalog_name.bacalhau_results;
CREATE TABLE IF NOT EXISTS catalog_name.bacalhau_results.sensor_readings
USING DELTA
LOCATION 's3://<your-bucket>/delta/bacalhau_results';
```

---

## Managing Tables via Databricks CLI (Docker)
Ensure your workspace token and host are in `~/.databrickscfg`.
```bash
# Create table in Unity Catalog
docker run --rm -v ~/.databrickscfg:/home/databricks/.databrickscfg:ro \
  databricks/databricks-cli unity-catalog tables create \
    --catalog catalog_name --schema bacalhau_results --name sensor_readings \
    --table-type DELTA --storage-location s3://<your-bucket>/delta/bacalhau_results

# List tables
docker run --rm -v ~/.databrickscfg:/home/databricks/.databrickscfg:ro \
  databricks/databricks-cli unity-catalog tables list \
    --catalog catalog_name --schema bacalhau_results

# Inspect storage path
docker run --rm -v ~/.databrickscfg:/home/databricks/.databrickscfg:ro \
  databricks/databricks-cli fs ls s3://<your-bucket>/delta/bacalhau_results/
```

---

## Further Reading
- [REARCHITECTURE.md](REARCHITECTURE.md): Detailed re-architecture plan and checklist.
- `uploader-config.yaml.example`: Example config template.
- `docs/databricks-s3-connect.md`: Guide for configuring Databricks S3 connectivity.