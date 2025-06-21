# Introduction

This example demonstrates how to build a sophisticated distributed log processing pipeline using [Bacalhau](https://bacalhau.org/), Google [BigQuery](https://cloud.google.com/bigquery), and [DuckDB](https://duckdb.org/). You'll learn how to process and analyze logs across distributed nodes, with progressively more advanced techniques for handling, sanitizing, and aggregating log data.

The combination of Bacalhau and BigQuery offers several key advantages:
- Process logs directly where they are generated, eliminating the need for centralized collection
- Scale processing across multiple nodes in different cloud providers
- Leverage BigQuery's powerful analytics capabilities for processed data
- Implement privacy-conscious data handling and efficient aggregation strategies
- Automatic timestamp tracking prevents duplicate processing and enables incremental updates

Through this tutorial, you'll evolve from basic log collection to implementing a production-ready system with privacy protection and smart aggregation. Whether you're handling application logs, system metrics, or security events, this pipeline provides a robust foundation for distributed log analytics.

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

## Unified Configuration-Driven Processor

We also provide a unified log processor that combines all four processing modes into a single, configuration-driven application. This allows you to:

- Switch between processing modes without changing code
- Automatically watch for configuration updates
- Maintain a single deployment while adjusting behavior

### Using the Unified Processor

```bash
# Deploy the unified processor
./utility_scripts/manage_unified_processor.sh deploy

# Update configuration to switch modes
./utility_scripts/manage_unified_processor.sh run sanitized

# Check job status
./utility_scripts/manage_unified_processor.sh status <job-id>
```

The unified processor supports these pipeline modes:
- **raw**: Minimal processing, preserves original logs
- **schematized**: Structured parsing of Apache logs
- **sanitized**: Schematized + IP anonymization
- **aggregated**: Sanitized + hourly aggregates + emergency events

See [UNIFIED_PROCESSOR.md](bigquery-exporter/UNIFIED_PROCESSOR.md) for detailed configuration options.

## Testing

Comprehensive tests are available in the `tests/` directory:

```bash
# Run quick smoke tests
python tests/test_smoke.py

# Run full test suite
cd tests && ./run_tests.sh

# Run specific test categories
pytest tests/test_unified_processor.py::TestConfigurationHandling -v
pytest tests/test_integration.py -v -s  # Requires BigQuery credentials
```

The tests verify:
- Configuration loading and validation
- BigQuery connectivity (read-only operations)
- Utility functions and error handling
- Integration with real BigQuery endpoints

See [tests/README.md](tests/README.md) for detailed testing information.

## Debugging and Local Testing

For debugging the unified log processor locally, you have several options from simple command-line execution to a comprehensive debugging suite.

### Quick Start: Debug Suite (Recommended)

The easiest way to get started with debugging is using our comprehensive debug suite:

```bash
# Interactive setup - walks you through configuration
./debug_suite.sh setup

# Run all validation tests
./debug_suite.sh test

# Run the processor with generated logs
./debug_suite.sh run --generate --mode sanitized --project your-gcp-project-id

# Validate your environment and configuration
./debug_suite.sh validate

# Clean up debug files when done
./debug_suite.sh clean
```

### Manual Setup

For more control, you can run the processor directly from the command line:

### Step 1: Create a config file
First, copy the template config and customize it:

```bash
cp demo-network/files/config.template.yaml debug-config.yaml
```

Edit `debug-config.yaml` with your settings:
```yaml
pipeline_mode: sanitized
chunk_size: 10000
project_id: your-gcp-project-id
dataset: log_analytics
credentials_path: /path/to/your/service-account-key.json
input_paths:
  - ./logs/access.log
```

### Step 2: Generate test logs
Create some test log data:

```bash
# Create logs directory
mkdir -p logs

# Generate test logs using Docker
docker run --rm -v ./logs:/logs \
  -e NO_ERROR_LOG=true \
  -e NO_SYSTEM_LOG=true \
  -e LOG_DIR_OVERRIDE=/logs \
  ghcr.io/bacalhau-project/access-log-generator:latest
```

### Step 3: Run the processor

**Option A: Use the debugging script (Recommended)**
```bash
# Generate logs and run in sanitized mode
./debug_local.sh --generate --mode sanitized --project your-gcp-project-id

# Or use existing logs with custom config
./debug_local.sh --config custom-config.yaml --logs-dir ./my-logs
```

**Option B: Run manually**
```bash
# Set up your environment variables
export CONFIG_FILE=./debug-config.yaml

# Run the uploader directly
cd bigquery-uploader
uv run --no-project bigquery_uploader.py
```

Example with actual paths:
```bash
CONFIG_FILE=/Users/username/bacalhau-examples/data-engineering/bigquery-with-bacalhau/debug-config.yaml \
uv run --no-project bigquery_uploader.py
```

### Common Environment Variables

- `CONFIG_FILE`: Required. Path to your YAML configuration file
- `CREDENTIALS_PATH` or `CREDENTIALS_FILE`: Path to your BigQuery service account credentials JSON
- `LOG_FILE` or `LOG_DIR`: Override input paths from config with specific log file locations
- `PROJECT_ID`: Override the BigQuery project ID from config
- `DATASET`: Override the BigQuery dataset name from config
- `NODE_ID`: Override the node identifier
- `REGION`: Override the region metadata
- `PROVIDER`: Override the cloud provider metadata
- `HOSTNAME`: Override the hostname metadata

### Debugging Tips

1. **File Not Found Errors**: The uploader will now immediately crash with a clear error message if log files are not found, rather than continuing to process empty chunks
2. **BigQuery Connection Issues**: Check your credentials path and ensure your service account has the necessary permissions
3. **Config File Issues**: Verify your config.yaml file exists and has the correct structure
4. **Local Log Generation**: Use the log generator to create test data:
   ```bash
   docker run --rm -v ./logs:/logs -e NO_ERROR_LOG=true -e NO_SYSTEM_LOG=true -e LOG_DIR_OVERRIDE=/logs ghcr.io/bacalhau-project/access-log-generator:latest
   ```

### Testing and Validation

#### Debug Suite Commands
```bash
# Run comprehensive test suite (includes fail-fast tests)
./debug_suite.sh test

# Validate environment and configuration
./debug_suite.sh validate --config your-config.yaml

# Interactive setup with guided configuration
./debug_suite.sh setup
```

#### Manual Testing
To verify that the fail-fast behavior is working correctly, you can run the included test script:

```bash
# Test that the processor fails fast when no log files are found
python3 test_failfast.py
```

This test script will:
- Create temporary directories and config files
- Test the processor with missing log files (should fail fast)
- Test the processor with existing log files (should start processing)
- Validate that error messages are clear and immediate

Expected output for missing files:
```
FATAL: No log files found matching patterns: ['/var/log/app/access.log']
Error: IO Error: No files found that match the pattern "/var/log/app/access.log"
Please check that log files exist at the specified paths and try again.
Fatal error encountered: No log files found matching patterns: ['/var/log/app/access.log']. Cannot proceed with processing.
Exiting immediately - this error cannot be recovered from.
```

#### Quick Demo
To see the fail-fast behavior in action without requiring BigQuery dependencies:

```bash
# Run a demonstration of the fail-fast behavior
python3 demo_failfast.py
```

This demo shows:
- How the processor behaves when files exist (continues processing)
- How the processor behaves when files are missing (fails fast)
- How the main loop exits immediately on fatal errors

#### Debug Suite Features
The debug suite (`debug_suite.sh`) provides:
- **Interactive setup**: Guided configuration creation with credential detection
- **Comprehensive testing**: Validates fail-fast behavior and processor functionality
- **Environment validation**: Checks prerequisites and configuration files
- **Automated log generation**: Creates realistic test data using Docker
- **Clean execution**: Manages temporary files and provides clear status messages

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