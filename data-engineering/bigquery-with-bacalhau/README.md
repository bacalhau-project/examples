# Data Engineering with Bacalhau

Welcome to an exciting journey into distributed data processing! This repository demonstrates how to leverage Bacalhau to transform your data engineering pipelines, showing you how to process logs across multiple clouds while maintaining data privacy and efficiency.

## What You'll Learn

Watch logs flow from 20+ nodes across multiple clouds (AWS, GCP, Azure) into BigQuery, while learning:
1. How to process data where it lives (at the edge!)
2. Progressive data handling techniques
3. Privacy-preserving data processing
4. Smart aggregation for efficient storage

## Prerequisites

1. [Bacalhau client](https://docs.bacalhau.org/getting-started/installation) installed
2. A Google Cloud Project with BigQuery enabled
3. Service account credentials with BigQuery access
4. A running Bacalhau cluster with nodes across different cloud providers
   - Follow the [standard Bacalhau network setup guide](https://docs.bacalhau.org/getting-started/create-private-network)
   - Ensure nodes are properly configured across your cloud providers (AWS, GCP, Azure). You can see more about setting up your nodes [here](https://docs.bacalhau.org/getting-started/setting-up-nodes)
   - If you're using the Expanso Cloud hosted orchestrator (Recommended!), you can look at your nodes on the [Expanso Cloud](https://cloud.expanso.io/networks/) dashboard in real-time.

## Components

1. **DuckDB Processing**: Process and analyze data using DuckDB's SQL capabilities
2. **BigQuery Integration**: Store processed results in Google BigQuery for further analysis

## Before You Start

0. Make sure you have configured your config file to have the correct BigQuery project and dataset. You can do this by copying the config.yaml.example file to config.yaml and editing the values to match your BigQuery project and dataset.

```bash
# BigQuery Configuration
project:
  id: "bacalhau-and-bigquery"  # Required: Your Google Cloud project ID
  region: "US"           # Optional: Default region for resources
  create_if_missing: true # Whether to create the project if it doesn't exist

credentials:
  path: "credentials.json"  # Path to service account credentials

bigquery:
  dataset_name: "log_analytics"     # Name of the BigQuery dataset
  table_name: "log_results"         # Name of the results table
  location: "US"                    # Dataset location 
```

1. Ensure your Google Cloud service account has these roles:
   - BigQuery Data Editor
   - BigQuery Job User

2. Have your service account key file (JSON format) ready

3. Configure your BigQuery settings:
   - Create a dataset for log analytics
   - Note your project ID and dataset name

We have provided some utility scripts to help you set up your BigQuery project and tables. You can run the following commands to set up your project and tables:

```bash
./utility_scripts/setup.py -i # Interactive setup to set up your BigQuery project and tables. Will go through and create the necessary bigquery projects.

./utility_scripts/confirm_tables.sh 
# Confirms your BigQuery project and dataset, and creates the tables if they don't exist with the correct schema. This will also zero out the tables if they already exist, so be careful! (Useful for debugging)

./utility_scripts/distribute_credentials.sh # Distributes the credentials to /bacalhau_data on all nodes in a Bacalhau network.

./utility_scripts/setup_log_uploader.sh # Ensures the service account specified in log_uploader_credentials.json has the necessary permissions to write to BigQuery tables from the Bacalhau nodes.

./utility_scripts/sample_tables.sh # Creates sample tables in BigQuery for testing.

./utility_scripts/check_permissions.sh # Checks the permissions of the service account specified in log_uploader_credentials.json to ensure it has the necessary permissions to write to BigQuery tables from the Bacalhau nodes.
```

One more thing to set up is the log faker on the nodes. This will generate logs for you to work with. You can run the following command to start the log faker:

```bash
bacalhau job run start-logging-container.yaml
```

Give it a couple of minutes to start up and then you can start processing the logs.

## Demo Walkthrough

Let's walk through each stage of the demo, seeing how we can progressively improve our data processing pipeline!

### Stage 1: Raw Power - Basic Log Upload 🚀

Let's start by looking at the raw logs.

```bash
# Let's look at the raw logs
bacalhau docker run alpine cat /var/log/app/access.log
```

That will print out the logs to stdout, which we can then read from the job.

After running the job, you will see a job id, something like this:

```bash
To get more details about the run, execute:
        bacalhau job describe j-01480df3-476e-4fdd-a297-0fc41cb10710

To get more details about the run executions, execute:
        bacalhau job executions j-01480df3-476e-4fdd-a297-0fc41cb10710
```

When you run the `describe` command, you will see the details of the job, including the output of the log information.

Now let's upload the raw logs to BigQuery. This is the simplest approach - just get the data there:

```bash
bacalhau job run bigquery_export_job.yaml --template-vars=python_file_b64=$(cat bigquery-exporter/log_process_0.py | base64)
```

This will upload the python script to all the nodes which, in turn, will upload the raw logs from all nodes to BigQuery. When you check BigQuery, you'll see:
- Millions of rows uploaded (depends on how many nodes you have and how long you let it run)
- Each log line as raw text
- No structure or parsing

To query the logs, you can use the following SQL:

```sql
PROJECT_ID=$(yq '.bigquery.project_id' config.yaml)
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.log_analytics.raw_logs\` LIMIT 5" 
```

### Stage 2: Adding Structure - Making Sense of Chaos 📊

Now let's do something more advanced, by parsing those logs into structured data before upload:

```bash
bacalhau job run bigquery_export_job.yaml --template-vars=python_file_b64=$(cat bigquery-exporter/log_process_1.py | base64)
```

Your logs are now parsed into fields like:
- IP Address
- Timestamp
- HTTP Method
- Endpoint
- Status Code
- Response Size

To query the logs, you can use the following SQL:

```sql
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.log_analytics.log_results\` LIMIT 5" 
```

### Stage 3: Privacy First - Responsible Data Handling 🔒

Now let's handle the data responsibly by sanitizing PII (like IP addresses):

```bash
bacalhau job run bigquery_export_job.yaml --template-vars=python_file_b64=$(cat bigquery-exporter/log_process_2.py | base64)
```

This:
- Zeros out the last octet of IPv4 addresses
- Zeros out the last 64 bits of IPv6 addresses
- Maintains data utility while ensuring compliance

Again, to query the logs, you can use the following SQL:

```sql
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.log_analytics.log_results\` LIMIT 5" 
```

Notice that the IP addresses are now sanitized.

### Stage 4: Smart Aggregation - Efficiency at Scale 📈

Finally, let's be smart about what we upload:

```bash
bacalhau job run bigquery_export_job.yaml --template-vars=python_file_b64=$(cat bigquery-exporter/log_process_3.py | base64)
```

This creates two streams:
1. Aggregated normal logs:
   - Grouped in 5-minute windows
   - Counts by status code
   - Average response sizes
   - Total requests per endpoint

2. Real-time emergency events:
   - Critical errors
   - Security alerts
   - System failures

To query  the logs, you can use the following SQL:

```sql
-- See your aggregated logs
SELECT * FROM \`$PROJECT_ID.log_analytics.log_aggregates\`
ORDER BY time_window DESC LIMIT 5;

-- Check emergency events
SELECT * FROM \`$PROJECT_ID.log_analytics.emergency_logs\`
ORDER BY timestamp DESC LIMIT 5;
```

## What's Next?

Now that you've seen the power of distributed processing with Bacalhau:
1. Try processing your own log files
2. Experiment with different aggregation windows
3. Add your own privacy-preserving transformations
4. Scale to even more nodes!

Remember: The real power comes from processing data where it lives, rather than centralizing everything first. Happy distributed processing! 🚀

### Table Schemas

1. **log_results** (Main Table):
   - `project_id`: STRING - Project identifier
   - `region`: STRING - Deployment region
   - `nodeName`: STRING - Node name
   - `timestamp`: TIMESTAMP - Event time
   - `version`: STRING - Log version
   - `message`: STRING - Log content
   - `sync_time`: TIMESTAMP - Upload time
   - `remote_log_id`: STRING - Original log ID
   - `hostname`: STRING - Source host
   - `public_ip`: STRING - Sanitized public IP
   - `private_ip`: STRING - Internal IP
   - `alert_level`: STRING - Event severity
   - `provider`: STRING - Cloud provider

2. **log_aggregates** (5-minute windows):
   - `project_id`: STRING - Project identifier
   - `region`: STRING - Deployment region
   - `nodeName`: STRING - Node name
   - `provider`: STRING - Cloud provider
   - `hostname`: STRING - Source host
   - `time_window`: TIMESTAMP - Aggregation window
   - `log_count`: INT64 - Events in window
   - `messages`: ARRAY<STRING> - Event details

3. **emergency_logs** (Critical Events):
   - `project_id`: STRING - Project identifier
   - `region`: STRING - Deployment region
   - `nodeName`: STRING - Node name
   - `provider`: STRING - Cloud provider
   - `hostname`: STRING - Source host
   - `timestamp`: TIMESTAMP - Event time
   - `version`: STRING - Log version
   - `message`: STRING - Alert details
   - `remote_log_id`: STRING - Original log ID
   - `alert_level`: STRING - Always "EMERGENCY"
   - `public_ip`: STRING - Sanitized public IP
   - `private_ip`: STRING - Internal IP