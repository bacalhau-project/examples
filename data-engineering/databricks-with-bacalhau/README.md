<!-- markdownlint-disable MD041 MD013 MD024 -->
# Bacalhau to Databricks Lakehouse Pipeline

This repository implements a continuous data pipeline that:

1. Reads sensor data from local SQLite databases (e.g., on edge nodes or Bacalhau compute nodes)
2. Incrementally extracts new records using a Python uploader.
3. Appends these records directly to a Delta Lake table in cloud storage (AWS S3 or Azure Data Lake Storage Gen2).
4. Enables scalable data analysis and processing on the Databricks Lakehouse Platform.

Key components:

- **Python Uploader**: A script (`uploader/sqlite_to_delta_uploader.py`) designed to be run with `uv run`. It:
  - Can automatically detect the SQLite table and its timestamp column via schema introspection.
  - Tracks the last-upload timestamp using a state file to ensure incremental processing.
  - Can perform optional local data processing (sanitization, filtering, aggregation) before upload.
  - Appends new rows directly to a specified Delta Lake table using the `deltalake` Python library.
- **Local Data Processing**: The uploader includes placeholder functions for common data processing tasks:
    - `sanitize_data`: For cleaning or transforming data.
    - `filter_data`: For selecting specific rows based on criteria.
    - `aggregate_data`: For performing aggregations (e.g., sum, average) over data.
    These functions can be enabled and configured via YAML, environment variables, or CLI arguments. Currently, they are placeholders and would need to be extended with specific logic for actual data manipulation.
- **Containerization**: A `uploader/Dockerfile` providing a multi-stage build that:

  - Caches Python dependencies efficiently in a builder stage.
  - Produces a minimal runtime image for the uploader.

- **Configuration**: `uploader-config.yaml.example` demonstrates how to configure SQLite database paths, the target Delta Lake table URI (`storage_uri` for S3, ADLS, or local paths), state directory, upload interval, and local processing steps.
- **Launcher Script**: An example `start-uploader.sh` shows how to run the uploader container, typically mounting the configuration file and necessary data volumes.
- **Databricks Integration**: Includes SQL snippets for setting up Delta Lake tables and examples for using the Databricks CLI (via Docker) for management tasks.

For the detailed architecture, migration checklist, and design rationale, please refer to [REARCHITECTURE.md](REARCHITECTURE.md).

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
│   └── sqlite_to_delta_uploader.py # UV-run script for incremental export
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
sqlite: "/data/sensor.db" # Example path

# Delta Lake table URI (e.g., S3, ADLS, or local file path like file:///data/delta/sensor_readings)
# This was previously referred to as table_path.
storage_uri: "s3://<your-bucket>/delta/bacalhau_results/sensor_readings"

# (Optional) Name of the SQLite table to read from. Auto-detected if not provided.
# table: "sensor_data"
# (Optional) Name of the timestamp column. Auto-detected if not provided.
# timestamp_col: "event_timestamp"

# Directory inside container for state file (last upload timestamp)
state_dir: "/state" # Example path

# Upload interval in seconds
interval: 300

# --- Local Data Processing ---
# Enable or disable local data processing steps. Configurations are JSON strings.
enable_sanitize: false
sanitize_config: "{}" # Example: '{\"column_to_clean\": \"pattern_to_remove\"}'

enable_filter: false
filter_config: "{}"   # Example: '{\"numeric_column\": {\">\": 100}}'

enable_aggregate: false
aggregate_config: "{}" # Example: '{\"group_by\": [\"category\"], \"aggregations\": {\"value\": \"sum\"}}'
```

You can override any value with environment variables (CLI arguments also take precedence):

- `SQLITE_PATH` (overrides `sqlite`)
- `STORAGE_URI` (overrides `storage_uri`, previously `TABLE_PATH`)
- `TABLE_NAME` (overrides `table`)
- `TIMESTAMP_COL` (overrides `timestamp_col`)
- `STATE_DIR` (overrides `state_dir`)
- `UPLOAD_INTERVAL` (overrides `interval`)
- `ENABLE_SANITIZE`, `SANITIZE_CONFIG` (JSON string)
- `ENABLE_FILTER`, `FILTER_CONFIG` (JSON string)
- `ENABLE_AGGREGATE`, `AGGREGATE_CONFIG` (JSON string)

Command-line arguments (e.g., `--sqlite`, `--storage-uri`, `--enable-sanitize`, `--sanitize-config`) will override both environment variables and YAML configuration.

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

```code
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

### Querying the Delta Table with Spark

Once data is populated in your Delta Lake table, you can query it using Spark in your Databricks environment (e.g., in a Databricks notebook).

Here's a basic PySpark example:

```python
# Example: Querying the Delta table in a Databricks notebook

# Make sure your Spark session has access to the catalog where the table resides.
# Replace <CATALOG_NAME> with your actual catalog name (e.g., 'main', 'hive_metastore', 'dev').
catalog_name = "<CATALOG_NAME>" 
spark.sql(f"USE CATALOG {catalog_name}")

# Define the schema and table name 
# (assuming it was created as per previous SQL examples, e.g., in 'bacalhau_results' schema)
schema_name = "bacalhau_results"
table_name_short = "sensor_readings"
full_table_name = f"{schema_name}.{table_name_short}" # or f"{catalog_name}.{schema_name}.{table_name_short}" if not using USE CATALOG

# Read the Delta table into a Spark DataFrame
print(f"Attempting to read Delta table: {full_table_name}")
df = spark.read.table(full_table_name)

# Display some data
print(f"Displaying top 10 rows from {full_table_name}:")
df.show(10)

# Perform a count
record_count = df.count()
print(f"Total records in '{full_table_name}': {record_count}")

# Example query: Find average temperature (assuming a 'temperature' column exists)
# You might need to cast the column if it's not already a numeric type
if 'temperature' in df.columns:
    from pyspark.sql.functions import avg
    print(f"Calculating average temperature from {full_table_name}:")
    avg_temp_df = df.agg(avg("temperature"))
    avg_temp_df.show()
else:
    print(f"Column 'temperature' not found in {full_table_name}. Skipping average temperature calculation.")

# Example query: Find the latest timestamp (assuming a 'timestamp' column exists)
if 'timestamp' in df.columns:
    from pyspark.sql.functions import max
    print(f"Finding the latest timestamp in {full_table_name}:")
    latest_timestamp_df = df.agg(max("timestamp"))
    latest_timestamp_df.show()
else:
    print(f"Column 'timestamp' not found in {full_table_name}. Skipping latest timestamp calculation.")
```

Replace `<CATALOG_NAME>` with the actual catalog you are using. This script demonstrates reading the table, showing sample data, counting records, and performing simple aggregations. You can adapt these queries for more complex analysis and visualization within your Databricks notebooks.

---

## Further Reading

- [REARCHITECTURE.md](REARCHITECTURE.md): Detailed re-architecture plan and checklist.
- `uploader-config.yaml.example`: Example config template.
- `docs/databricks-s3-connect.md`: Guide for configuring Databricks S3 connectivity.
