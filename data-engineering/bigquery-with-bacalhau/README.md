# Data Engineering with Bacalhau

This repository demonstrates how to use Bacalhau for data engineering tasks, combining DuckDB for data processing and BigQuery for data storage.

## Components

1. **DuckDB Processing**: Process and analyze data using DuckDB's SQL capabilities
2. **BigQuery Integration**: Store processed results in Google BigQuery for further analysis

## Prerequisites

1. [Bacalhau client](https://docs.bacalhau.org/getting-started/installation) installed
2. Python 3.10 or higher
3. A Google Cloud Project with BigQuery enabled (or permissions to create one)
4. Service account credentials with appropriate permissions

## Setup

### 1. Install Dependencies

Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Interactive Setup

Run the interactive setup script:
```bash
./setup.py -i
```

The script will guide you through:
1. Project Configuration
   - Enter existing project ID or create new
   - Configure project settings

2. Credentials Setup
   - Create service account (browser will open)
   - Download and configure credentials
   - Set up necessary permissions

3. BigQuery Configuration
   - Configure dataset and table names
   - Set up storage location

The script will:
- Create/configure your Google Cloud project
- Set up service account credentials
- Create BigQuery dataset and table
- Save all settings to config.yaml

### Manual Setup (Alternative)

If you prefer manual setup:

1. Create a service account in Google Cloud Console with these roles:
   - BigQuery Data Editor
   - BigQuery Job User
   - Project Creator (if you want the script to create projects)

2. Download the service account key file (JSON format)

3. Create `config.yaml`:
   ```yaml
   project:
     id: "your-project-id"  # Your Google Cloud project ID
     region: "US"           # Default region for resources
     create_if_missing: true # Whether to create the project if it doesn't exist

   credentials:
     path: "credentials.json"  # Path to your service account key

   bigquery:
     dataset_name: "log_analytics"     # Name of the BigQuery dataset
     table_name: "log_results"         # Name of the results table
     location: "US"                    # Dataset location
   ```

4. Run the setup script:
   ```bash
   ./setup.py
   ```

### 3. Bacalhau Network Setup

Follow the [standard Bacalhau network setup guide](https://docs.bacalhau.org/getting-started/create-private-network).

## Usage

### 1. Simple DuckDB Queries

Run a simple DuckDB query:

```bash
bacalhau docker run -e QUERY="select 1" docker.io/bacalhauproject/duckdb:latest
```

### 2. Processing Logs with BigQuery Integration

Process log files and store results in BigQuery:

```bash
bacalhau docker run \
  --input /path/to/logs:/var/log/logs_to_process \
  --volume /path/to/credentials.json:/bacalhau_node/credentials.json \
  ghcr.io/bacalhau-project/examples/bigquery-processor:latest \
  -- python process.py input.json "SELECT * FROM temp_log_data"
```

### 3. Using YAML Configuration

For more complex setups, use the provided YAML configuration:

```bash
bacalhau job run duckdb_query_job.yaml \
  --template-vars="filename=/bacalhau_data/data.parquet" \
  --template-vars="QUERY=$(cat your_query.sql)"
```

## Data Schema

### BigQuery Table Schema

The `log_results` table in BigQuery has the following schema:

- `projectID`: STRING - Google Cloud project identifier
- `region`: STRING - Deployment region
- `nodeName`: STRING - Node name
- `syncTime`: STRING - Synchronization timestamp
- `remote_log_id`: STRING - Original log identifier
- `timestamp`: STRING - Event timestamp
- `version`: STRING - Log version
- `message`: STRING - Log message content

## Example Queries

### 1. Basic DuckDB Query

```sql
-- simple_query.sql
SELECT COUNT(*) AS row_count FROM yellow_taxi_trips;
```

### 2. Time Window Analysis

```sql
-- window_query.sql
SELECT
    DATE_TRUNC('hour', tpep_pickup_datetime) + 
    INTERVAL (FLOOR(EXTRACT(MINUTE FROM tpep_pickup_datetime) / 5) * 5) MINUTE AS interval_start,
    COUNT(*) AS ride_count
FROM
    yellow_taxi_trips
GROUP BY
    interval_start
ORDER BY
    interval_start;
```

### 3. BigQuery Examples

After setting up your BigQuery integration, you can run example queries using the provided script:

```bash
./run_bigquery_query.py
```

This will run several example queries and show their results:

1. Table Structure - Shows the schema of your log_results table
2. Total Row Count - Counts the total number of log entries
3. Recent Logs - Displays the 5 most recent log entries
4. Logs per Node - Shows how many logs each node has generated

Example output:
```
================================================================================

Querying BigQuery table: your-project-id.log_analytics.log_results

================================================================================

Running query: Table Structure

SQL:
SELECT 
    column_name,
    data_type,
    is_nullable
FROM your-project-id.log_analytics.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = 'log_results'
ORDER BY ordinal_position

Results:
------------------------------------------------------------
column_name  | data_type | is_nullable
------------------------------------------------------------
projectID    | STRING    | YES
region       | STRING    | YES
nodeName     | STRING    | YES
syncTime     | STRING    | YES
remote_log_id| STRING    | YES
timestamp    | STRING    | YES
version      | STRING    | YES
message      | STRING    | YES
------------------------------------------------------------
Total rows: 8

... (more query results follow)
```

You can also run these queries directly in the BigQuery console:
1. Go to https://console.cloud.google.com/bigquery
2. Select your project
3. Click "Compose New Query"
4. Copy any of the SQL queries from the script output

The script uses your config.yaml settings and service account credentials to connect to BigQuery.

## Security Notes

1. Credential Management:
   - Never commit credentials to version control
   - Mount credentials at runtime using Bacalhau volumes
   - Use appropriate IAM roles and permissions
   - Keep your config.yaml file secure and out of version control

2. Data Access:
   - Use principle of least privilege
   - Regularly rotate service account keys
   - Monitor BigQuery access logs

## Environment Variables

- `INPUTFILE`: Path to the input log file
- `QUERY`: DuckDB query to transform the data before sending to BigQuery

## Directory Structure

```
.
├── container/
│   ├── process.py      # Main processing script
│   └── Dockerfile      # Container definition
├── setup.py            # Infrastructure setup script
├── requirements.txt    # Python dependencies
├── config.yaml         # Your configuration (not in version control)
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Demo Instructions

### 1. Initial Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run interactive setup
./setup.py -i

# Make utility scripts executable
chmod +x utility_scripts/*.sh

# Set up tables and service account
./utility_scripts/confirm_table.sh
./utility_scripts/setup_log_uploader.sh
./utility_scripts/setup_aggregation_tables.sh
```

### 2. Basic Log Processing

```bash
# Process logs with basic configuration
bacalhau docker run \
  --input logs:/var/log/logs_to_process \
  --volume log_uploader_credentials.json:/var/logs/logs_to_process/log_uploader_credentials.json \
  ghcr.io/bacalhau-project/examples/bigquery-processor:latest \
  -- python process.py /var/log/logs_to_process/input.json "SELECT * FROM temp_log_data"
```

### 3. Advanced Features

#### Track Cloud Provider
```bash
# Process logs with provider tracking
bacalhau docker run \
  -e CLOUD_PROVIDER=aws \
  --input logs:/var/log/logs_to_process \
  --volume log_uploader_credentials.json:/var/logs/logs_to_process/log_uploader_credentials.json \
  ghcr.io/bacalhau-project/examples/bigquery-processor:latest \
  -- python process.py /var/log/logs_to_process/input.json "SELECT * FROM temp_log_data"
```

#### Enable Log Aggregation
```bash
# Process logs with 5-minute window aggregation
bacalhau docker run \
  -e AGGREGATE_LOGS=true \
  --input logs:/var/log/logs_to_process \
  --volume log_uploader_credentials.json:/var/logs/logs_to_process/log_uploader_credentials.json \
  ghcr.io/bacalhau-project/examples/bigquery-processor:latest \
  -- python process.py /var/log/logs_to_process/input.json "SELECT * FROM temp_log_data"
```

### 4. Verify Results

Check the results in BigQuery tables:

1. Regular Logs:
```sql
SELECT *
FROM `your-project-id.log_analytics.log_results`
ORDER BY timestamp DESC
LIMIT 5
```

2. Aggregated Logs (5-minute windows):
```sql
SELECT *
FROM `your-project-id.log_analytics.log_aggregates`
ORDER BY time_window DESC
LIMIT 5
```

3. Emergency Events:
```sql
SELECT *
FROM `your-project-id.log_analytics.emergency_logs`
ORDER BY timestamp DESC
LIMIT 5
```

### Security Features

1. **Restricted Service Account**:
   - Custom role with minimal permissions
   - Can only write to specific BigQuery tables
   - Cannot modify schema or read data

2. **IP Address Sanitization**:
   - IPv4: Last octet zeroed out
   - IPv6: Last 64 bits zeroed out
   - Automatic sanitization of public IPs

3. **Secure Credential Handling**:
   - Credentials mounted as volume
   - Not exposed through environment variables
   - Separate service account for log uploads

### Environment Variables

- `INPUTFILE`: Path to input log file (optional)
- `QUERY`: DuckDB query for data transformation (optional)
- `CLOUD_PROVIDER`: Cloud provider identifier (e.g., aws, gcp)
- `AGGREGATE_LOGS`: Enable 5-minute window aggregation (true/false)

### Table Schemas

1. **log_results** (Main Table):
   - `project_id`: STRING
   - `region`: STRING
   - `nodeName`: STRING
   - `timestamp`: TIMESTAMP
   - `version`: STRING
   - `message`: STRING
   - `sync_time`: TIMESTAMP
   - `remote_log_id`: STRING
   - `hostname`: STRING
   - `public_ip`: STRING
   - `private_ip`: STRING
   - `alert_level`: STRING
   - `provider`: STRING

2. **log_aggregates** (5-minute windows):
   - `project_id`: STRING
   - `region`: STRING
   - `nodeName`: STRING
   - `provider`: STRING
   - `hostname`: STRING
   - `time_window`: TIMESTAMP
   - `log_count`: INT64
   - `messages`: ARRAY<STRING>

3. **emergency_logs** (Critical Events):
   - `project_id`: STRING
   - `region`: STRING
   - `nodeName`: STRING
   - `provider`: STRING
   - `hostname`: STRING
   - `timestamp`: TIMESTAMP
   - `version`: STRING
   - `message`: STRING
   - `remote_log_id`: STRING
   - `alert_level`: STRING
   - `public_ip`: STRING
   - `private_ip`: STRING
```

This provides a complete, accurate guide for demonstrating all features of the system, including setup, usage, and verification steps.