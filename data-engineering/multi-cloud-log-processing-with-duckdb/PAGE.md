# Multi-Cloud Log Processing with DuckDB

DuckDB is a powerful analytical database that excels at processing and analyzing structured data. When combined with Bacalhau's distributed computing capabilities, it becomes an effective tool for processing logs across multiple cloud environments. This example demonstrates how to use DuckDB with Bacalhau to analyze log data distributed across different cloud regions.

## Overview

In this tutorial, you'll learn:
- How to process log data using DuckDB in a distributed environment
- How to run SQL queries across multiple cloud regions
- How to handle compressed log files efficiently
- How to analyze security-related log entries across your infrastructure

## Prerequisites

Before you begin, make sure you have:
- [Bacalhau client installed](https://docs.bacalhau.org/getting-started/installation)
- Basic understanding of SQL queries
- Access to multiple cloud regions (for multi-cloud deployment)

## Understanding the Components

### Log Generator

The example includes a log generator that simulates realistic log entries from different services:
- Authentication service
- Application stack
- Database service

Each log entry contains:
- Unique identifier
- Timestamp
- Version information
- Message with service name and category (INFO, WARN, CRITICAL, SECURITY)

### DuckDB Processor

The DuckDB processor is designed to:
- Read JSON-formatted log files (including compressed .gz files)
- Create in-memory tables for efficient querying
- Execute custom SQL queries on the log data
- Output results in JSON format

### Multi-Cloud Configuration

The deployment configuration enables:
- Running nodes across different cloud providers
- Secure communication between nodes using Tailscale
- Local directory mounting for log access
- Concurrent job execution across regions

## Step-by-Step Guide

### 1. Setting Up the Environment

First, deploy Bacalhau nodes across multiple cloud regions:

```bash
# Clone the examples repository
git clone https://github.com/bacalhau-project/examples.git
cd examples/multi-cloud-duckdb-log-processing

# Set up Tailscale (required for multi-cloud communication)
# Follow instructions in README.md to configure Tailscale
```

### 2. Deploying Across Multiple Clouds

The deployment process is automated using Terraform:

```bash
# Deploy nodes across specified regions
./bulk-deploy.sh

# Set up environment variables
cd tf/aws/ && source bacalhau.run
export BACALHAU_NODE_CLIENTAPI_HOST=$(jq -r '.outputs.ip_address.value' terraform.tfstate.d/ca-central-1/terraform.tfstate)
export BACALHAU_IPFS_SWARM_ADDRESSES=$BACALHAU_NODE_IPFS_SWARMADDRESSES
cd ../../
```

### 3. Running the Log Processing Job

The example includes a pre-configured job that searches for security-related log entries:

```bash
# Verify node connectivity
bacalhau node list

# Submit the log processing job
bacalhau create job_multizone.yaml
```

The job configuration (`job_multizone.yaml`) specifies:
- DuckDB container image
- Input log file location
- SQL query to execute
- Output directory for results

### 4. Analyzing Results

After the job completes:

```bash
# Check job status
bacalhau job list --id-filter ${JOB_ID}

# Download results
bacalhau job get ${JOB_ID} --output-dir results

# View the processed data
cat results/stdout
```

## Advanced Usage

### Custom SQL Queries

You can modify the SQL query in `job_multizone.yaml` to perform different analyses:

```sql
-- Count log entries by service
SELECT DISTINCT message, COUNT(*) as count
FROM log_data
GROUP BY message
ORDER BY count DESC

-- Find critical errors in a time range
SELECT * FROM log_data
WHERE message LIKE '%[CRITICAL]%'
  AND "@timestamp" BETWEEN '2024-01-01' AND '2024-01-02'
```

### Working with Compressed Logs

The DuckDB processor automatically handles gzipped log files:

```bash
# Process compressed logs
bacalhau docker run \
  expanso/duckdb \
  python3 /process.py /var/log/logs_to_process/logs.gz \
  "SELECT * FROM log_data WHERE message LIKE '%[CRITICAL]%'"
```

### Scaling Across Regions

To process logs from specific regions:

```bash
# Target specific regions
bacalhau docker run \
  --target=region:us-east-1,region:eu-west-1 \
  expanso/duckdb \
  python3 /process.py /var/log/logs_to_process/logs.gz \
  "SELECT * FROM log_data"
```

## Troubleshooting

Common issues and solutions:

1. **Node Connectivity**
   - Ensure Tailscale is properly configured
   - Verify node status with `bacalhau node list`

2. **Job Failures**
   - Check job logs: `bacalhau job logs ${JOB_ID}`
   - Verify input file paths and permissions

3. **Performance Issues**
   - Consider using smaller date ranges in queries
   - Add appropriate WHERE clauses to filter data

## Next Steps

- Explore different SQL queries for log analysis
- Implement custom log parsing logic
- Set up automated log processing pipelines
- Configure alerts based on query results

## Additional Resources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [Bacalhau Documentation](https://docs.bacalhau.org/)
- [SQL Query Examples](https://duckdb.org/docs/sql/introduction)
