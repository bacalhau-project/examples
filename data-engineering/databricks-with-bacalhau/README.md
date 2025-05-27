<!-- markdownlint-disable MD041 MD013 MD024 -->
# Bacalhau to Databricks Lakehouse Pipeline

This repository implements a continuous data pipeline that extracts data from local SQLite databases and uploads it directly to Databricks tables. It's designed for edge computing scenarios or integration with Bacalhau compute nodes.

## Overview

The pipeline:
1. Reads sensor data from local SQLite databases (e.g., on edge nodes or Bacalhau compute nodes)
2. Incrementally extracts new records using a Python uploader.
3. Appends these records directly to a Delta Lake table in Databricks.
4. Enables scalable data analysis and processing on the Databricks Lakehouse Platform.

## Key Features

- **Python Uploader**: A script (e.g., `uploader/sqlite_to_delta_uploader.py`) designed to be run with `uv run`. It:
  - Can automatically detect the SQLite table and its timestamp column via schema introspection.
  - Tracks the last-upload timestamp using a state file to ensure incremental processing.
  - Appends new rows directly to a specified Delta Lake table using the Databricks API.
- **Containerization**: A `uploader/Dockerfile` providing a multi-stage build that:
  - Caches Python dependencies efficiently in a builder stage.
  - Produces a minimal runtime image for the uploader.
- **Configuration**: `uploader-config.yaml.example` demonstrates how to configure SQLite database paths, the target Databricks table, state directory, and upload interval.
- **Launcher Script**: An example `start-uploader.sh` shows how to run the uploader container, typically mounting the configuration file and necessary data volumes.
- **Databricks Integration**: Includes SQL snippets for setting up Delta Lake tables and examples for using the Databricks CLI (via Docker) for management tasks.

For the detailed architecture, migration checklist, and design rationale, please refer to [REARCHITECTURE.md](REARCHITECTURE.md).

---

## Setting Up Databricks SQL CLI Credentials

After authenticating with the Databricks CLI, you'll need to manually create a credentials file for the Databricks SQL CLI.

### 1. Generate a Personal Access Token

> **Note:** You must do this in your Databricks **workspace** (not the account console).

1. Go to your Databricks workspace (URL will look like `https://dbc-xxxx.cloud.databricks.com/`).
2. Click your user icon (profile picture or initials) in the top right corner.
3. Select **User Settings** from the dropdown.
4. In the User Settings page, find the **Access tokens** or **Personal access tokens** section.
5. Click **Generate new token**.
6. Give your token a name and set an expiration if prompted.
7. **Copy the token** and save it securely—you won't be able to see it again!

If you do not see the option to generate a token, you may be in the account console or your admin may have disabled token creation. In that case, contact your Databricks administrator.

### 2. Find the HTTP Path

1. In your Databricks workspace, click **SQL Warehouses** in the left sidebar.
2. Click on your SQL warehouse (or create one if you don't have one).
3. In the warehouse details, look for the **Connection details** section.
4. Copy the value labeled **HTTP Path** (it will look like `/sql/1.0/warehouses/xxxxxxxxxxxxxx`).

### 3. Create the Credentials File

Create or edit the file `~/.databricks/credentials` and add the following, replacing the placeholders with your actual values:

```ini
[credentials]
host_name = "https://dbc-xxxx.cloud.databricks.com"
http_path = "/sql/1.0/warehouses/<your-warehouse-id>"
access_token = "<your-access-token>"
```

- `host_name`: Your workspace URL (from your browser address bar when in the workspace)
- `http_path`: The HTTP Path you copied from the SQL Warehouse
- `access_token`: The token you generated above

**References:**
- [Databricks: Manage personal access tokens](https://docs.databricks.com/en/dev-tools/auth/pat.html)
- [Databricks: Connect using Databricks SQL CLI](https://docs.databricks.com/en/sql/admin/sql-endpoints.html#connect-using-databricks-sql-cli)

---

## Using a .env File for Databricks SQL CLI Configuration

As an alternative to the credentials file, you can use a `.env` file to set the required environment variables for Databricks SQL CLI tools. This method works for both the official `databricks-sql` CLI and the community `dbsqlcli`.

### 1. Create a `.env` File

In your project directory, create a file named `.env` with the following contents (replace the values with your actual Databricks details):

```env
DATABRICKS_HOST=https://dbc-xxxx.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<your-warehouse-id>
DATABRICKS_TOKEN=<your-access-token>
```

- `DBSQLCLI_HOST_NAME`: Your workspace URL (from your browser address bar when in the workspace)
- `DBSQLCLI_HTTP_PATH`: The HTTP Path you copied from the SQL Warehouse
- `DBSQLCLI_TOKEN`: The token you generated above

### 2. Load the .env File in Your Shell

Before running the CLI, load the environment variables:

```bash
export $(grep -v '^#' .env | xargs)
```

### 3. Run the CLI

Now you can run either CLI and it will use the environment variables for authentication:

```bash
# For the official Databricks SQL CLI
 databricks-sql

# For the community dbsqlcli
 dbsqlcli
```

**Note:** If you use a process manager or script, ensure it loads the `.env` file before running the CLI.

---

## Prerequisites

- Docker Engine (19.03+)
- (Optional) Python 3.11 and the `uv` CLI for local testing
- A Databricks workspace
- Databricks access token for API access

## Setting Up Databricks Workspace

1. Install the Databricks CLI:

```bash
brew install databricks-cli
```

1. Create a Databricks workspace in Databricks.

```bash
# Go here to login:
https://accounts.cloud.databricks.com/

# Go here to create a workspace:
https://accounts.cloud.databricks.com/workspaces

# Go here to create a token:
https://accounts.cloud.databricks.com/
```

1. Authenticate with the Databricks CLI using your workspace URL:

```bash
# The workspace URL can be found in your browser when accessing your workspace

databricks auth login --host https://abc-12345678-abcd.cloud.databricks.com
Databricks profile name: abc-12345678-abcd
Profile abc-12345678-abcd was successfully saved
```

1. In the SQL Editor UI (`https://abc-12345678-abcd.cloud.databricks.com/sql/editor/`), configure Unity Catalog:

   ```sql
   -- Create catalog and schema
   CREATE CATALOG IF NOT EXISTS bacalhau_catalog;
   CREATE SCHEMA IF NOT EXISTS bacalhau_catalog.sensor_data;
   ```

1. Create the Delta Lake Table:
   Before running the uploader, you need to create the target Delta Lake table in your Databricks workspace. Execute the following SQL to create the table:

      ```sql
      -- Create managed table
      CREATE TABLE IF NOT EXISTS bacalhau_catalog.sensor_data.readings
      USING DELTA
      TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.autoOptimize.optimizeWrite' = 'true'
      );
      ```

1. Run test script to upload data to the Delta Lake table, and then delete it:

```bash
uv run test-upload
```

## Directory Layout

```text
./
├── uploader/                      # Python uploader and Dockerfile
│   └── upload_sqlite_to_delta.py  # UV-run script for incremental export
│   └── Dockerfile                 # Multi-stage UV-based image
├── uploader-config.yaml.example   # Example configuration
├── start-uploader.sh              # Shell wrapper to launch uploader container
├── REARCHITECTURE.md              # Re-architecture roadmap and checklist
├── docs/                          # Guides (e.g., Databricks connectivity)
├── .env                           # Environment variables
└── README.md                      # This file
```

## Quick Start

### 1. Configuration

Copy the example configuration file:

```bash
# Databricks Configuration
DATABRICKS_HOST=https://YOUR_DATABRICKS_HOST
DATABRICKS_TOKEN=YOUR_DATABRICKS_TOKEN
DATABRICKS_CATALOG=bacalhau_catalog
DATABRICKS_SCHEMA=sensor_data
```

## Configuration

The uploader uses a flexible configuration system with multiple options for setting parameters.

### Table Routing Based on Processing Scenario

The uploader automatically routes data to different tables based on which processing options are enabled:

- **Raw Data** (no processing enabled): Data goes to `raw_<table_name>`
- **Filtered Data** (`enable_filter: true`): Data goes to `filtered_<table_name>`
- **Sanitized/Secure Data** (`enable_sanitize: true`): Data goes to `secure_<table_name>`
- **Aggregated Data** (`enable_aggregate: true`): Data goes to `aggregated_<table_name>`

For example, if your base table name is `sensor_readings`:
- Raw data → `raw_sensor_readings`
- Filtered data → `filtered_sensor_readings`
- Sanitized data → `secure_sensor_readings`
- Aggregated data → `aggregated_sensor_readings`

### Configuration Precedence

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **YAML configuration file**
4. **Default values** (lowest priority)

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

Create a `.env` file for managing environment variables:

You can create a `.env` file in the project's root directory to manage your environment variables for local development. Remember to add `.env` to your `.gitignore` file to prevent committing sensitive information.

```env
# --- Databricks Connection (Required) ---
DATABRICKS_HOST="adb-xxxxxxxxxxxxxxxx.x.azuredatabricks.net"
DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/xxxxxxxxxxxxxxxx"
DATABRICKS_TOKEN="dapixxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Store securely!
DATABRICKS_DATABASE="sensor_data" # Or "your_catalog.sensor_data"
DATABRICKS_TABLE="raw_readings"

# --- SQLite Source Configuration ---
SQLITE_PATH="data/local_sensor_data.db"
# SQLITE_TABLE_NAME="my_sensor_table" # Optional: auto-detected if single table exists
# TIMESTAMP_COL="event_timestamp"     # Optional: auto-detected if common names exist

# --- Script Behavior ---
# STATE_DIR="./state"                 # Optional: Directory for state file
# UPLOAD_INTERVAL=300                 # Optional: Upload interval in seconds
# ONCE=true                           # Optional: Run once and exit

# --- Data Processing (determines target table) ---
# Only enable ONE processing type at a time:
# ENABLE_SANITIZE=true     # Routes to secure_* tables
# ENABLE_FILTER=true       # Routes to filtered_* tables  
# ENABLE_AGGREGATE=true    # Routes to aggregated_* tables
# (If none enabled, routes to raw_* tables)
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

# Databricks table name
table_name: "readings"

# ... (other parameters like state_dir, interval, processing configs are also in uploader-config.yaml.example) ...
```

### Command-Line Arguments

- `SQLITE_PATH`, `TABLE_NAME`, `STATE_DIR`, `UPLOAD_INTERVAL`

---

## Build the Uploader Container

```bash
python sqlite_to_databricks_uploader.py --help
```

For instance, to specify a different SQLite database file and run the uploader only once, you could use:
```bash
python sqlite_to_databricks_uploader.py --config uploader-config.yaml --sqlite /path/to/another/sensor.db --once
```
This command uses the settings from `uploader-config.yaml` but overrides the SQLite path and ensures the script runs only one cycle.

---

## Data Processing Features

The uploader includes optional data processing capabilities that determine which table receives the data:

   ```bash
   chmod +x start-uploader.sh
   ```

2. Run with your config file:

   ```bash
   ./start-uploader.sh uploader-config.yaml
   ```

The uploader will run continuously, appending new records each cycle.

## Managing Tables via Databricks CLI

The following commands use the official Databricks CLI running inside a Docker container to interact with your Databricks workspace:

```bash
# List tables in the schema
docker run --rm \
  -v $(pwd)/.databrickscfg:/root/.databrickscfg:ro \
  ghcr.io/databricks/cli:latest \
  schemas list bacalhau_catalog.sensor_data

# Inspect the table details
docker run --rm \
  -v $(pwd)/.databrickscfg:/root/.databrickscfg:ro \
  ghcr.io/databricks/cli:latest \
  tables list bacalhau_catalog.sensor_data
```

### Querying the Table with Spark

Once data is populated in your Delta Lake table, you can query it using Spark in your Databricks environment:

```python
# Example: Querying the Delta table in a Databricks notebook

# Use the catalog and schema
spark.sql("USE CATALOG bacalhau_catalog")
spark.sql("USE SCHEMA sensor_data")

# Read the Delta table into a Spark DataFrame
df = spark.read.table("readings")

# Display some data
print("Displaying top 10 rows:")
df.show(10)

# Perform a count
record_count = df.count()
print(f"Total records: {record_count}")

# Example query: Find average temperature
if 'temperature' in df.columns:
    from pyspark.sql.functions import avg
    print("Calculating average temperature:")
    avg_temp_df = df.agg(avg("temperature"))
    avg_temp_df.show()
```

---

## Integration with Bacalhau

This uploader is designed to work seamlessly with Bacalhau compute jobs. Example Bacalhau job specification:

```yaml
name: databricks-upload-job
type: batch
compute:
  image: ghcr.io/your-org/databricks-uploader:latest
inputs:
  - source:
      type: localDirectory
      path: /data/sqlite
    target: /data
  - source:
      type: localFile
      path: ./config.yaml
    target: /config.yaml
env:
  DATABRICKS_TOKEN: ${DATABRICKS_TOKEN}
command:
  - "--config"
  - "/config.yaml"
  - "--once"
```

## Docker Deployment

### Building the Image

The included `build.sh` script supports multi-architecture builds:

```bash
# Build for multiple platforms
cd databricks-uploader
export PLATFORMS="linux/amd64,linux/arm64"
./build.sh --tag v1.0.0 --push

# Build for local testing only
./build.sh --tag dev --registry local
```

### Running in Production

Example docker-compose.yml:

```yaml
version: '3.8'
services:
  databricks-uploader:
    image: ghcr.io/your-org/databricks-uploader:latest
    volumes:
      - ./config.yaml:/config.yaml:ro
      - /data/sqlite:/data:ro
      - ./state:/state
    environment:
      - DATABRICKS_TOKEN=${DATABRICKS_TOKEN}
    command: ["--config", "/config.yaml"]
    restart: unless-stopped
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify your Databricks PAT is valid
   - Ensure the token has necessary permissions for all target tables

2. **Table Not Found**
   - Verify all scenario tables exist (raw_*, filtered_*, secure_*, aggregated_*)
   - Check database and table names are correct

3. **No New Records**
   - Check the state file to see the last uploaded timestamp
   - Verify your SQLite data has records newer than this timestamp

4. **Wrong Table Used**
   - Ensure only one processing option is enabled at a time
   - Check logs to confirm which table prefix is being used

## Security Considerations

- **Never commit tokens**: Always use environment variables for sensitive credentials
- **Use read-only mounts**: Mount SQLite databases as read-only in containers
- **Rotate tokens regularly**: Update Databricks PATs periodically
- **Limit token scope**: Use tokens with minimal required permissions
- **Separate tables by sensitivity**: Use the secure_* tables for sanitized sensitive data

## License

This project is part of the Bacalhau examples repository. See the main repository for license information.

## Further Reading

- [REARCHITECTURE.md](REARCHITECTURE.md): Detailed re-architecture plan and checklist.
- `uploader-config.yaml.example`: Example config template.
- `docs/databricks-connect.md`: Guide for configuring Databricks connectivity.
