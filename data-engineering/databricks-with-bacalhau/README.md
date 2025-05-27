<!-- markdownlint-disable MD041 MD013 MD024 -->
# Bacalhau to Databricks Lakehouse Pipeline

This repository implements a continuous data pipeline that:

1. Reads sensor data from local SQLite databases (e.g., on edge nodes or Bacalhau compute nodes).
2. Incrementally extracts new records using a Python uploader.
3. Performs optional local data processing (sanitization, filtering, aggregation).
4. Appends these records directly to a table within a Databricks workspace using the Databricks SQL Connector.
5. Enables scalable data analysis and processing on the Databricks Lakehouse Platform.

Key components:

- **Python Uploader**: A script (`uploader/sqlite_to_databricks_uploader.py`) designed to be run with `uv run`. It:
  - Connects directly to a Databricks SQL warehouse or All-Purpose Cluster.
  - Can automatically detect the source SQLite table and its timestamp column via schema introspection.
  - Tracks the last-upload timestamp using a state file to ensure incremental processing.
  - Can perform optional local data processing (sanitization, filtering, aggregation) before upload.
  - Inserts new rows into a specified Databricks table using the `databricks-sql-connector` Python library.
- **Local Data Processing**: The uploader includes placeholder functions for common data processing tasks:
    - `sanitize_data`: For cleaning or transforming data.
    - `filter_data`: For selecting specific rows based on criteria.
    - `aggregate_data`: For performing aggregations (e.g., sum, average) over data.
    These functions can be enabled and configured via YAML, environment variables, or CLI arguments. Currently, they are placeholders and would need to be extended with specific logic for actual data manipulation.
- **Containerization**: A `uploader/Dockerfile` providing a multi-stage build that:

  - Caches Python dependencies efficiently in a builder stage.
  - Produces a minimal runtime image for the uploader.

- **Configuration**: `uploader-config.yaml.example` demonstrates how to configure SQLite database paths, Databricks connection parameters (host, HTTP path, token, database, table), state directory, upload interval, and local processing steps.
- **Launcher Script**: An example `start-uploader.sh` shows how to run the uploader container, typically mounting the configuration file and necessary data volumes.
- **Databricks Integration**: The uploader directly interacts with Databricks. SQL snippets for managing tables can be run in Databricks notebooks or SQL Editor.

For the original (now outdated) architecture involving Delta Lake as an intermediate step, please refer to [REARCHITECTURE.md](REARCHITECTURE.md). This document has not been updated to reflect the direct Databricks upload architecture.

---

## Prerequisites

- Docker Engine (19.03+)
- (Optional) Python 3.11 and the `uv` CLI for local testing
- A Databricks workspace with a SQL warehouse or All-Purpose Cluster.
- A target database and table within Databricks.
- Databricks Personal Access Token (PAT) for authentication.

## Directory Layout

```text
./
├── uploader/                      # Python uploader and Dockerfile
│   └── sqlite_to_databricks_uploader.py # UV-run script for incremental export
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
# --- Databricks Connection Parameters ---
# It is STRONGLY recommended to use environment variables for sensitive data like tokens.
databricks_host: "your-workspace.azuredatabricks.net"
databricks_http_path: "/sql/1.0/warehouses/your_sql_warehouse_http_path"
# databricks_token: "dapixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Prefer DATABRICKS_TOKEN env var
databricks_database: "your_database"
databricks_table: "your_table"

# --- SQLite Source Parameters ---
sqlite_path: "/data/sensor.db"
sqlite_table_name: "sensor_data" # Or auto-detected if commented out
# timestamp_col: "event_timestamp" # Or auto-detected if commented out

# --- Uploader Control Parameters ---
state_dir: "/state"
interval: 300

# --- Local Data Processing ---
# (See uploader-config.yaml.example for detailed examples of YAML structures)
enable_sanitize: false
sanitize_config: {}

enable_filter: false
filter_config: {}

enable_aggregate: false
aggregate_config: {}
```

Key environment variables for overriding configuration (CLI arguments also take precedence):

- `SQLITE_PATH` (overrides `sqlite_path` in YAML)
- `SQLITE_TABLE_NAME` (overrides `sqlite_table_name` in YAML)
- `TIMESTAMP_COL` (overrides `timestamp_col` in YAML)
- `STATE_DIR` (overrides `state_dir` in YAML)
- `UPLOAD_INTERVAL` (overrides `interval` in YAML)
- `DATABRICKS_HOST`
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_TOKEN` (**Recommended method for providing the token**)
- `DATABRICKS_DATABASE`
- `DATABRICKS_TABLE`
- `ENABLE_SANITIZE`, `SANITIZE_CONFIG` (JSON string for env var)
- `ENABLE_FILTER`, `FILTER_CONFIG` (JSON string for env var)
- `ENABLE_AGGREGATE`, `AGGREGATE_CONFIG` (JSON string for env var)

Command-line arguments (e.g., `--sqlite`, `--databricks-host`, `--databricks-table`) will override both environment variables and YAML configuration.

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

## Debugging with Query Mode

The uploader script includes a `--run-query` CLI flag that allows you to directly query your target Databricks table for debugging or inspection. This mode requires Databricks connection parameters to be configured (e.g., via `uploader-config.yaml` or environment variables). It will execute the query and then exit, without starting the continuous upload process.

**1. Get Table Information:**

To get general information about your Databricks table and database, use `"INFO"` as the query string:

```bash
python uploader/sqlite_to_databricks_uploader.py --config uploader-config.yaml --run-query "INFO"
```

This will display:

- **Tables in Database**: A list of tables in the configured `databricks_database`.
- **Description for Table**: Detailed schema and metadata for the configured `databricks_table`.
- **Row Count for Table**: The total number of rows in the `databricks_table`.

**2. Query Table Data (General SQL):**

You can execute SQL queries directly against your Databricks table. Ensure your query uses fully qualified table names (e.g., `your_database.your_table`) or that the default database context is correctly set via `databricks_database`.

Example:

```bash
python uploader/sqlite_to_databricks_uploader.py --config uploader-config.yaml --run-query "SELECT * FROM your_database.your_table LIMIT 10"
```
This will display the first 10 rows of `your_database.your_table`.

For more complex querying or data manipulation, use dedicated analytics tools like Databricks SQL Editor or Spark notebooks.

## Databricks Table Setup

Before running the uploader, you need to ensure the target database and table exist in your Databricks workspace and that the table schema is compatible with the data from your SQLite source. The uploader script will attempt to insert data based on matching column names.

**1. Create Database (if it doesn't exist):**
Use the Databricks SQL Editor or a notebook:
```sql
CREATE DATABASE IF NOT EXISTS your_database_name;
```

**2. Create Table (Example):**
The table schema should match the columns in your SQLite database that you intend to upload. Data type mapping will be handled by the Databricks SQL connector, but ensure they are compatible (e.g., SQLite `TEXT` to Databricks `STRING`, SQLite `REAL` to Databricks `DOUBLE` or `FLOAT`, SQLite `INTEGER` to Databricks `INT` or `BIGINT`).

Example DDL for a table (execute in Databricks SQL Editor or notebook):
```sql
CREATE TABLE IF NOT EXISTS your_database_name.your_table_name (
    id BIGINT,
    device_id STRING,
    timestamp TIMESTAMP,
    temperature DOUBLE,
    humidity DOUBLE,
    -- Add other columns as per your SQLite schema
    PRIMARY KEY (id) -- Optional: Define primary keys if applicable
);
```
**Note:** The uploader script itself does not create the table or schema. You are responsible for defining the target table structure in Databricks.

## Managing Tables via Databricks CLI (Docker)

The Databricks CLI can be used for various workspace management tasks. Ensure it is configured with your workspace host and token.

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

### Querying the Table with Spark

Once data is populated in your Databricks table by the uploader, you can query it using Spark in your Databricks environment (e.g., in a Databricks notebook).

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

- [REARCHITECTURE.md](REARCHITECTURE.md): Original (now outdated) re-architecture plan.
- `uploader-config.yaml.example`: Example config template for the uploader.
- `docs/databricks-s3-connect.md`: (May be less relevant now) Guide for configuring Databricks S3 connectivity, primarily for external tables.
