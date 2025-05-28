<!-- markdownlint-disable MD041 MD013 MD024 -->
# Bacalhau to Databricks Lakehouse Pipeline

This repository implements a continuous data pipeline that:

1. Reads sensor data from local SQLite databases (e.g., on edge nodes or Bacalhau compute nodes).
2. Incrementally extracts new records using a Python uploader.
3. Performs optional local data processing (sanitization, filtering, aggregation).
4. Appends these records directly to a table within a Databricks workspace using the Databricks SQL Connector.
5. Enables scalable data analysis and processing on the Databricks Lakehouse Platform.

Key components:

- **Python Uploader**: A script (`sqlite_to_databricks_uploader.py`) designed to be run with `uv run`. It:
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
- **Containerization**: A `Dockerfile` (now in the project root) providing a multi-stage build that:

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
├── sqlite_to_databricks_uploader.py # UV-run script for incremental export
├── Dockerfile                 # Multi-stage UV-based image for the uploader
├── build.sh                   # Script to build the uploader Docker image
├── latest-tag                 # File containing the latest Docker image tag
├── uploader-config.yaml.example   # Example configuration
├── start-uploader.sh              # Shell wrapper to launch uploader container
├── REARCHITECTURE.md               # Re-architecture roadmap and checklist
├── docs/                          # Guides (e.g., Databricks connectivity)
├── .env                           # Environment variables
└── README.md                      # This file
```

## Configuration

The uploader script offers a flexible configuration system, allowing parameters to be set via a YAML file, environment variables, or command-line arguments. Understanding the precedence and options is key to tailoring the script to your needs.

**Order of Precedence:**

1.  **Command-Line Arguments**: Highest precedence. Values provided on the command line (e.g., `--sqlite /path/to/db`) override all other settings.
2.  **Environment Variables**: Values set in the environment (e.g., `export DATABRICKS_TOKEN="..."` or via a `.env` file) override settings in the YAML file.
3.  **YAML Configuration File**: Settings defined in the `uploader-config.yaml` file (or a custom file specified with `--config`) are used if not overridden by environment variables or CLI arguments.
4.  **Default Values**: Some parameters have built-in default values in the script if not specified by any other method (e.g., `UPLOAD_INTERVAL` defaults to 300 seconds).

### Environment Variables

Environment variables are particularly useful for sensitive information (like tokens) and for settings that differ across deployment environments (dev, staging, prod). They can be set in your shell or, more commonly for local development, placed in a `.env` file at the root of the project. While this script doesn't automatically load `.env` files, your execution environment (like `uv run` with specific configurations) or a manual `source .env` command can make these variables available.

**Do not commit `.env` files containing sensitive credentials to version control.** Always add `.env` to your `.gitignore` file.

Below is a comprehensive list of environment variables recognized by the uploader:

#### Databricks Connection Parameters (Generally Required)

These are essential for the script to connect to your Databricks workspace and target table.

-   **`DATABRICKS_HOST`**:
    *   **Purpose**: The server hostname of your Databricks workspace.
    *   **Example**: `adb-1234567890123456.7.azuredatabricks.net`
    *   **Finding it**: Look at your Databricks workspace URL; it's the part after `https://`.

-   **`DATABRICKS_HTTP_PATH`**:
    *   **Purpose**: The HTTP Path for your Databricks SQL Warehouse or All-Purpose Cluster. This directs the script to the correct compute resource.
    *   **Example**: `/sql/1.0/warehouses/abcdef1234567890`
    *   **Finding it**: In Databricks, navigate to your SQL Warehouse, go to the "Connection details" tab. The HTTP path is listed there.

-   **`DATABRICKS_TOKEN`**:
    *   **Purpose**: A Databricks Personal Access Token (PAT) or a token for a Service Principal. This is critical for authenticating API calls to Databricks.
    *   **Example**: `dapixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (This is a dummy example; your token will be different).
    *   **Finding it**: PATs can be generated from your User Settings within the Databricks workspace. For Service Principals, tokens are obtained through specific OAuth or token generation processes.
    *   **Security**: **This token is highly sensitive and should be treated like a password.** Using this environment variable is the recommended way to provide the token, rather than hardcoding it in the YAML file or CLI arguments. In production, use secrets management tools (like Azure Key Vault, HashiCorp Vault, AWS Secrets Manager) to store and inject this token securely.

-   **`DATABRICKS_DATABASE`**:
    *   **Purpose**: Specifies the target database (often referred to as a schema) in Databricks where your table is located.
    *   **Example**: `bronze_layer`, `default`, `main.sensordata`
    *   **Note**: If you are using Unity Catalog, you might need to use a three-level namespace like `your_catalog.your_schema` (e.g., `dev_catalog.bronze_data`). Alternatively, ensure your SQL Warehouse's default catalog is set appropriately if you only provide `your_schema`.

-   **`DATABRICKS_TABLE`**:
    *   **Purpose**: The name of the target table within the specified `DATABRICKS_DATABASE` where data will be uploaded.
    *   **Example**: `raw_iot_feed`, `sensor_metrics`

#### SQLite Source and Script Behavior Variables

These variables configure how the script interacts with your local SQLite database and control its operational behavior.

-   **`SQLITE_PATH`**:
    *   **Purpose**: The file path to your source SQLite database. This is required for the uploader's main functionality.
    *   **Example**: `/data/sensor_readings.db` (in a container) or `C:\data\local_metrics.sqlite` (on Windows).

-   **`SQLITE_TABLE_NAME`** (Optional):
    *   **Purpose**: The name of the specific table within the SQLite database from which to read data.
    *   **Example**: `environment_sensors`, `machine_logs`
    *   **Note**: If this is not provided, the script will attempt to auto-detect the table. This is generally successful if your SQLite database contains only one user-defined table. If multiple tables exist, specifying the name is recommended.

-   **`TIMESTAMP_COL`** (Optional):
    *   **Purpose**: The name of the timestamp column within your SQLite table. This column is crucial for incremental data loading, as the script uses it to fetch only records newer than the last successful upload.
    *   **Example**: `event_timestamp`, `created_at`, `MeasurementTime`
    *   **Note**: If not specified, the script tries to auto-detect a suitable timestamp column by looking for common names (e.g., 'timestamp', 'date', 'created_at').

-   **`STATE_DIR`** (Optional):
    *   **Purpose**: The directory where the script stores its state file (`last_upload.json`). This JSON file contains the timestamp of the last record successfully uploaded, enabling incremental processing.
    *   **Default**: `/state` (commonly used in containerized environments). If `/state` is not writable or does not exist, it may fall back to the current working directory or a script-local path; check script logs for confirmation.
    *   **Example**: `/app/state_files` or `data/uploader_status`

-   **`UPLOAD_INTERVAL`** (Optional):
    *   **Purpose**: The time interval, in seconds, between consecutive upload cycles when the script is running in continuous mode (i.e., without the `--once` flag).
    *   **Default**: `300` (which is 5 minutes).
    *   **Example**: `60` (for 1-minute intervals), `3600` (for 1-hour intervals).

-   **`ONCE`** (Optional):
    *   **Purpose**: If set to `true` (case-insensitive comparison) or `1`, the script will perform a single upload cycle and then exit. This is useful for batch processing or scheduled task scenarios. It is equivalent to using the `--once` command-line flag.
    *   **Example**: `ONCE=true`

#### Local Data Processing Variables (Optional)

These variables enable and configure optional data processing steps (sanitization, filtering, aggregation) that occur *before* data is uploaded to Databricks.

-   **`ENABLE_SANITIZE`**: Set to `true` or `1` to enable data sanitization. Defaults to `false`.
-   **`SANITIZE_CONFIG`**: A JSON string that defines the rules for sanitization.
    *   **Example**: `'{"column_to_clean": "pattern_to_remove", "another_column": {"replace_value": "X", "with_value": "Y"}}'`

-   **`ENABLE_FILTER`**: Set to `true` or `1` to enable data filtering. Defaults to `false`.
-   **`FILTER_CONFIG`**: A JSON string that defines the criteria for filtering rows.
    *   **Example**: `'{"numeric_column": {">": 100, "<=": 200}, "string_column_equals": "active_value"}'`

-   **`ENABLE_AGGREGATE`**: Set to `true` or `1` to enable data aggregation. Defaults to `false`.
-   **`AGGREGATE_CONFIG`**: A JSON string that defines how data should be grouped and aggregated.
    *   **Example**: `'{"group_by": ["device_id", "hour_of_day"], "aggregations": {"temperature": "avg", "humidity": "max", "records": "count"}}'`

    **Important Note on `*_CONFIG` variables**: When providing these configuration structures (for `SANITIZE_CONFIG`, `FILTER_CONFIG`, `AGGREGATE_CONFIG`) as environment variables, they **must be valid JSON strings**. If you are using the YAML configuration file (`uploader-config.yaml`), you can and should use native YAML structures for these, as it's generally more readable and easier to manage complex nested structures. Refer to `uploader-config.yaml.example` for YAML structure examples.

### Example `.env` File

You can create a `.env` file in the project's root directory to manage your environment variables for local development. Remember to add `.env` to your `.gitignore` file to prevent committing sensitive information.

```env
# --- Databricks Connection (Required) ---
DATABRICKS_HOST="adb-xxxxxxxxxxxxxxxx.x.azuredatabricks.net"
DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/xxxxxxxxxxxxxxxx"
DATABRICKS_TOKEN="dapixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Store securely!
DATABRICKS_DATABASE="sensor_data" # Or "your_catalog.sensor_data"
DATABRICKS_TABLE="raw_readings"

# --- SQLite Source Configuration (Required if not using YAML/CLI) ---
SQLITE_PATH="data/local_sensor_data.db"
# SQLITE_TABLE_NAME="my_sensor_table" # Optional: auto-detected if single table exists
# TIMESTAMP_COL="event_timestamp"     # Optional: auto-detected if common names exist

# --- Script Behavior ---
# STATE_DIR="."                       # Optional: Directory for state file (defaults to /state or current)
# UPLOAD_INTERVAL=600                 # Optional: Upload interval in seconds (default 300)
# ONCE=true                           # Optional: Run once and exit

# --- Local Data Processing (Optional) ---
# ENABLE_SANITIZE=true
# SANITIZE_CONFIG='{"rules": [{"type": "remove_nulls", "columns": ["temperature"]}]}'
# ENABLE_FILTER=false
# FILTER_CONFIG='{}'
# ENABLE_AGGREGATE=false
# AGGREGATE_CONFIG='{}'
```

### YAML Configuration File

For more complex configurations, especially for the data processing rules (`sanitize_config`, `filter_config`, `aggregate_config`), using a YAML file is recommended due to its support for native nested structures, which are more readable than JSON strings.

Copy the `uploader-config.yaml.example` file to `uploader-config.yaml` and customize it according to your needs. The example file provides a template for all available settings.

```yaml
# Example snippet from uploader-config.yaml.example:
# --- Databricks Connection Parameters ---
databricks_host: "your-workspace.azuredatabricks.net"
databricks_http_path: "/sql/1.0/warehouses/your_sql_warehouse_http_path"
# databricks_token: "dapixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Prefer DATABRICKS_TOKEN env var
databricks_database: "your_database"
databricks_table: "your_table"

# --- SQLite Source Parameters ---
sqlite_path: "/data/sensor.db"
sqlite_table_name: "sensor_data" # Or auto-detected if commented out

# ... (other parameters like state_dir, interval, processing configs are also in uploader-config.yaml.example) ...
```

### Command-Line Arguments

Command-line arguments offer the highest level of precedence and are useful for overriding specific settings for a single execution or for scripting. To see a full list of available arguments and their descriptions, run:

```bash
python sqlite_to_databricks_uploader.py --help
```

For instance, to specify a different SQLite database file and run the uploader only once, you could use:
```bash
python sqlite_to_databricks_uploader.py --config uploader-config.yaml --sqlite /path/to/another/sensor.db --once
```
This command uses the settings from `uploader-config.yaml` but overrides the SQLite path and ensures the script runs only one cycle.

---

## Build the Uploader Container

The `build.sh` script (now in the project root) simplifies building the Docker image. It determines the image tag based on Git context or uses the content of the `latest-tag` file.
```bash
./build.sh
```
Alternatively, you can build manually using `docker build`:
```bash
docker build -t uploader-image:latest .
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
python sqlite_to_databricks_uploader.py --config uploader-config.yaml --run-query "INFO"
```

This will display:
- **Tables in Database**: A list of tables in the configured `databricks_database`.
- **Description for Table**: Detailed schema and metadata for the configured `databricks_table`.
- **Row Count for Table**: The total number of rows in the `databricks_table`.

**2. Query Table Data (General SQL):**

You can execute SQL queries directly against your Databricks table. Ensure your query uses fully qualified table names (e.g., `your_database.your_table`) or that the default database context is correctly set via `databricks_database`.

Example:
```bash
python sqlite_to_databricks_uploader.py --config uploader-config.yaml --run-query "SELECT * FROM your_database.your_table LIMIT 10"
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
