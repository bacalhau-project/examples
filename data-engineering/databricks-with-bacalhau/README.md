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
├── .env                           # Environment variables
└── README.md                      # This file
```

## Environment Variables
```bash
S3_BUCKET_NAME=YOUR_S3_BUCKET_NAME
AWS_REGION=YOUR_AWS_REGION
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
DATABRICKS_HOST=https://YOUR_DATABRICKS_HOST
DATABRICKS_TOKEN=YOUR_DATABRICKS_TOKEN
```


## Configuration
Copy `uploader-config.yaml.example` to `uploader-config.yaml` and customize:
```yaml
# Path inside container to the SQLite DB
sqlite: "/root/sensor.db"

# Delta Lake table URI (e.g., S3 path or ADLS path)
table_path: "s3://YOUR_S3_BUCKET_NAME/delta/sensor_readings"

# Directory inside container for state file (last upload timestamp)
state_dir: "/root"

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

## Delta Lake Table Setup on Databricks

Before running the uploader, you need to create the target Delta Lake table and the schema (database) it belongs to in your Databricks workspace.

You can execute the following SQL commands in a Databricks notebook or using the Databricks SQL Editor.

**Accessing the SQL Editor:**

Navigate to the SQL Editor in your Databricks workspace using a URL like this (replace `<your-databricks-workspace-url>` with your actual workspace URL, e.g., `dbc-a1b2-c3d4.cloud.databricks.com`):

```
https://<your-databricks-workspace-url>/sql/editor
```

**SQL Commands:**

Execute the following SQL. Remember to replace:
- `<CATALOG_NAME>` with the name of your desired Unity Catalog catalog (e.g., `main`, `dev`).
- `<S3_BUCKET_NAME>` with the actual name of your S3 bucket where the Delta table data will be stored.

```sql
-- Ensure the sch ema (database) exists within your chosen catalog
CREATE SCHEMA IF NOT EXISTS <CATALOG_NAME>.bacalhau_results;

-- Create the external Delta table pointing to your S3 location
-- The uploader script will create the table schema upon first write if it doesn't exist,
-- but explicitly defining it here ensures the location is correctly set up.
CREATE TABLE IF NOT EXISTS <CATALOG_NAME>.bacalhau_results.sensor_readings
USING DELTA
LOCATION 's3://$S3_BUCKET_NAME/delta/bacalhau_results/sensor_readings';
```

**Note:** The `LOCATION` should point to the *specific directory* where the `sensor_readings` table data will reside within your `bacalhau_results` structure in S3.

## Managing Tables via Databricks CLI (Docker)

The following commands use the official Databricks CLI running inside a Docker container to interact with your Databricks workspace, for example, to list tables or inspect storage after the table has been created and populated.

These commands mount your local `.databrickscfg` file into the container. This file is the standard configuration file for the Databricks CLI and should contain your Databricks workspace host URL and a personal access token (PAT) to authenticate the CLI calls. It typically looks like this:

```ini
[DEFAULT]
host  = https://<your-databricks-workspace-url>
token = <your-databricks-personal-access-token>
```

Make sure this file exists in your home directory (`~`) and contains valid credentials for the workspace you want to interact with. **Treat the token like a password and keep it secure.**

Note: Table creation itself is not supported directly via the CLI flags used here. You should create the table using SQL commands in a Databricks notebook or SQL editor as shown in the [Delta Lake Table Setup on Databricks](#delta-lake-table-setup-on-databricks) section, or by using other tools like the Databricks Terraform provider or SDKs.

```bash
# List tables in the schema
docker run --rm \
  -v $(pwd)/.databrickscfg:/root/.databrickscfg:ro \
  ghcr.io/databricks/cli:latest \
  schemas list bacalhau_sensor_readings_workspace

# Inspect the storage path where the table data resides
❯ docker run --rm \
  -v $(pwd)/.databrickscfg:/root/.databrickscfg:ro \
  ghcr.io/databricks/cli:latest \
  tables list bacalhau_sensor_readings_workspace default
```

---

## Further Reading
- [REARCHITECTURE.md](REARCHITECTURE.md): Detailed re-architecture plan and checklist.
- `uploader-config.yaml.example`: Example config template.
- `docs/databricks-s3-connect.md`: Guide for configuring Databricks S3 connectivity.