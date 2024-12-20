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
cd examples/system-engineering/duckdb-log-processing
```

### 2. Deploying a Bacalhau cluster

This example requires a Bacalhau cluster to be set up. There is a terraform setup in this example to help with setup, or you could use your own.

You will need to make sure the `.env.json` file is setup correctly.

```bash
cd terraform

# We're going to destroy to start just to make sure.
./deploy.sh destroy && ./deploy.sh plan && ./deploy.sh apply

cd ..
```

If you use your own Bacalhau cluster, you need to make sure to have the following configuration settings:

```
NameProvider: "uuid"
Compute:
  Enabled: true
  AllowListedLocalPaths:
    - /var/log/logs_to_process:rw
JobAdmissionControl:
  AcceptNetworkedJobs: true
```

### 3. Running the Log Processing Job

The example includes a pre-configured job that creates for security-related log entries:

```bash
# Verify node connectivity
bacalhau node list

# Submit the log processing job
bacalhau job submit start-logging-container.yaml
```

### 4. Analyzing Results

After the job starts, it will generate logs and rotate them every 5 minutes in the `/var/log/logs_to_process` directory. We can then use DuckDB to process these logs.

To do so, we will run the job.yaml file.

```bash
# Submit the log processing job
bacalhau job run process-logs.yaml
```

To get the results, we will describe the results:

```bash
# Describe the job to get the results
bacalhau job describe ${JOB_ID}
```

It should output something like the following:
```bash
Output truncated
Execution e-de9d3994:
Files available to process in: /var/log/logs_to_process
--------------------
/var/log/logs_to_process/aperitivo_logs.log.20241220-170001
/var/log/logs_to_process/aperitivo_logs.log.20241220-170502
/var/log/logs_to_process/aperitivo_logs.log.20241220-171001
/var/log/logs_to_process/aperitivo_logs.log.20241220-171502
/var/log/logs_to_process/aperitivo_logs.log.20241220-172001


Environment Variables
INPUT_DIR = /var/log/logs_to_process (default: /var/log/logs_to_process)
INPUTFILE = None
QUERY = SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY "@timestamp"
Processing latest file
Processing file: /var/log/logs_to_process/aperitivo_logs.log.20241220-172001
Debug: First few rows of data:
                                     id  ...                                            message
0  865bb4a3-8706-4c1d-984d-72a6229f32ac  ...  AppStack [CRITICAL] skeleton nitriry musketrie...
1  a854784f-ccca-42a4-ac7b-79ba9ca59e57  ...  Auth [SECURITY] unrebelliously telekinetic ban...
2  98b359db-241b-49ac-b1b9-ca2b5b0b33c3  ...  Auth [SECURITY] manchus shafted imprecant tekt...
3  00e17a9f-85e8-4517-bf35-1fab4d9ee978  ...  Database [WARN] aport renovation misquotation ...
4  0109a886-dbc6-4f8b-9ad7-d07485629ef9  ...  Auth [WARN] porella heparinizing octavic dojo ...

[5 rows x 4 columns]
Executing query: SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY "@timestamp"
Bucket name: gs://log-processing-project-us-east1-b-archive-bucket

{'log-processing-project-us-east1-b-archive-bucket': '[{"id":"a854784f-ccca-42a4-ac7b-79ba9ca59e57","@timestamp":"2024-12-20T16:57:56.516260Z","@version":"1.1","message":"Auth [SECURITY] unrebelliously telekinetic bandores objected orange"},{"id":"98b359db-241b-49ac-b1b9-ca2b5b0b33c3","@timestamp":"2024-12-20T16:57:56.807478Z","@version":"1.1","message":"Auth [SECURITY] manchus shafted imprecant tektites emporial"},{"id":"9ada8d95-05d1-4ba9-a1bc-bf810674e2e3","@timestamp":"2024-12-20T16:57:58.112852Z","@version":"1.1","message":"AppStack [SECURITY] powderman subtlely cerements o
...
```

The last part of the output will show the results of the query. In this case, we also upload the results to a Google Cloud Storage bucket, but this is optional.

You can access these buckets and the content inside them with the following (assuming you have gsutil installed):
```bash
gsutil ls gs://log-processing-project-us-east1-b-archive-bucket
gsutil cp gs://log-processing-project-us-east1-b-archive-bucket/your-file.json .
```

## Advanced Usage

### Custom SQL Queries

You can modify the SQL query in `process-logs.yaml` to perform different analyses:

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

### Scaling Across Regions

To process logs from specific regions:

**NOTE: The @timestamp field must be with double quotes, and the LIKE clause must be with single quotes.**

```yaml
Tasks:
  - Engine:
      Params:
        EnvironmentVariables:
          - QUERY=SELECT * FROM log_data WHERE message LIKE '%[SECURITY]%' ORDER BY "@timestamp"
          - INPUT_PATH=/var/log/logs_to_process
        Image: docker.io/bacalhauproject/duckdb-query:202412181847
        Parameters:
          - --latest
        WorkingDirectory: ""
      Type: docker
    Name: sample-job
    InputSources:
      - Source:
          Type: "localDirectory"
          Params:
            SourcePath: "/var/log/logs_to_process"
            ReadWrite: true
        Target: "/var/log/logs_to_process"
    Network:
      Type: Full
    Publisher:
      Type: ""
    Resources:
      CPU: 250m
      Memory: 250m
    Timeouts: {}
Type: ops
```

