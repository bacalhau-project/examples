# Distributed Log Processing with DuckDB and Bacalhau

## Overview
This project implements a distributed log processing system using DuckDB and Bacalhau. The system consists of three main components:
1. Infrastructure deployment using Terraform
2. Log generation workload
3. Log processing with DuckDB queries

## Prerequisites
- Google Cloud Platform account with billing enabled
- `gcloud` CLI installed and configured
- Terraform installed (v1.0.0+)
- Docker installed and configured
- `bacalhau` CLI installed (`curl -sL https://get.bacalhau.org/install.sh | bash`)

## 1. Infrastructure Deployment

### Setup
1. Create a `.env.json` file in the `terraform` directory with your configuration:
```json
{
  "project_id": "your-gcp-project-id",
  "app_name": "bacalhau",
  "app_tag": "prod",
  "machine_type": "e2-medium",
  "orchestrator_config_path": "node_files/orchestrator-config.yaml",
  "username": "ubuntu",
  "public_key": "~/.ssh/id_rsa.pub",
  "private_key": "~/.ssh/id_rsa",
  "bacalhau_installation_id": "your-installation-id",
  "locations": {
    "europe-west9-a": {
      "region": "europe-west9",
      "storage_location": "EU"
    },
    "us-east4-a": {
      "region": "us-east4",
      "storage_location": "US"
    }
  }
}
```

2. Deploy the infrastructure:
```bash
cd terraform
./deploy.sh init
./deploy.sh destroy # just to be safe
./deploy.sh plan
./deploy.sh apply
```

3. Verify the deployment:
```bash
bacalhau docker run ubuntu echo "Hello World"
```

## 2. Log Generation Deployment

The log generator creates sample logs that will be processed by DuckDB.

1. Deploy the log generator workload:
```bash
bacalhau job run start-logging-container.yaml
```

This will:
- Generate logs in `/var/log/app`
- Rotate logs every 5 minutes
- Copy rotated logs to `/var/log/logs_to_process`
- Keep the last 30 log files

You can verify log generation by checking the processing directory:
```bash
bacalhau docker run ubuntu ls -la /var/log/logs_to_process
```

## 3. Log Processing with DuckDB

The DuckDB processor can run queries across the generated logs.

1. Run a query across all nodes:
```bash
bacalhau create job.yaml
```
**IMPORTANT:  The quotes in the query are different " around the LIKE clause and ' around the timestamp.**


1. Get job results:
```bash
# Get job ID from previous command output
bacalhau describe <JOBID>
bacalhau get <JOBID>
```

1. View results in GCS buckets:
```bash
# List buckets
gcloud storage ls

# List bucket contents
gcloud storage ls gs://<BUCKET_NAME>/

# View results
gcloud storage cat gs://<BUCKET_NAME>/<FILE_NAME>
```

## Query Examples

1. Find all security events:
```sql
SELECT * FROM log_data 
WHERE message LIKE '%[SECURITY]%' 
ORDER BY "@timestamp"
```

2. Count events by category:
```sql
SELECT 
  REGEXP_EXTRACT(message, '\[(.*?)\]') as category,
  COUNT(*) as count 
FROM log_data 
GROUP BY category 
ORDER BY count DESC
```

3. Get latest events:
```sql
SELECT * FROM log_data 
ORDER BY "@timestamp" DESC 
LIMIT 10
```

## Cleanup

To destroy the infrastructure:
```bash
cd terraform
./deploy.sh destroy
```

## Architecture
- Each node generates logs independently
- Logs are rotated every 5 minutes
- DuckDB processes logs at the point of creation
- Results are aggregated in GCS buckets:
  - Regional bucket: `<project-id>-<region>-archive-bucket`
  - Global bucket: `<project-id>-global-archive-bucket`

## Monitoring
- Check log generation:
  ```bash
  bacalhau docker run ubuntu tail -f /var/log/logs_to_process/aperitivo_logs.log.1
  ```
- Monitor job status:
  ```bash
  bacalhau list --wide
  ```