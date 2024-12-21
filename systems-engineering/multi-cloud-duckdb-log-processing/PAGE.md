# Multi-Cloud Log Processing with DuckDB and Bacalhau

This example demonstrates how to leverage Bacalhau's distributed computing capabilities to process logs across multiple cloud providers simultaneously using DuckDB. By deploying nodes across AWS, GCP, Azure, and Oracle Cloud, you can analyze log data efficiently regardless of where it originates.

## Overview

In this tutorial, you'll learn:
- How to deploy Bacalhau nodes across multiple cloud providers
- How to process log data using DuckDB in a multi-cloud environment
- How to handle cloud-specific storage and authentication
- How to aggregate results in a central location
- How to manage cross-cloud networking and security

## Prerequisites

Before you begin, make sure you have:
- [Bacalhau client installed](https://docs.bacalhau.org/getting-started/installation)
- Terraform (v1.0.0+) installed
- Access to cloud provider accounts:
  - Google Cloud Platform with billing enabled
  - AWS account with appropriate IAM permissions
  - Azure subscription
  - Oracle Cloud account
- Cloud provider CLI tools configured:
  - `gcloud` CLI
  - `aws` CLI
  - `az` CLI
  - `oci` CLI
- Basic understanding of SQL queries
- Docker installed locally

## Understanding the Components

### Multi-Cloud Infrastructure

The deployment spans across multiple cloud providers:
- AWS EC2 instances with S3 storage
- GCP Compute Engine with Cloud Storage
- Azure Virtual Machines with Blob Storage
- Oracle Cloud Infrastructure with Object Storage

Each node includes:
- Unique provider-specific metadata in `/etc/NODE_INFO`
- Local storage for log processing
- Cloud-specific storage client libraries
- Secure network configuration

### Log Generator

The log generator creates sample logs that simulate real-world scenarios:
- Authentication events
- Application metrics
- Database operations
- Security incidents

Each log entry contains:
- Timestamp
- Event ID
- Service identifier
- Message severity
- Cloud provider information

### DuckDB Processor

The DuckDB processor is designed to:
- Read logs from local storage
- Process data using SQL queries
- Upload results to cloud-specific storage
- Aggregate findings in a central GCP bucket

## Step-by-Step Guide

### 1. Setting Up Cloud Provider Authentication

Configure authentication for each cloud provider:

```bash
# AWS Configuration
aws configure

# GCP Configuration
gcloud auth application-default login

# Azure Configuration
az login

# Oracle Cloud Configuration
oci setup config
```

### 2. Deploying the Infrastructure

1. Configure variables in `tf/variables.tf`:
```hcl
variable "app_tag" {
  description = "Tag for resources"
  default     = "bacalhau-multi"
}

# Cloud-specific configurations follow
```

2. Deploy using the provided script:
```bash
cd tf
./bulk-deploy.sh
```

This script:
- Creates Terraform workspaces for each region
- Deploys infrastructure across providers
- Configures networking and security
- Sets up storage buckets

### 3. Running the Log Generator

Deploy the log generator across all nodes:
```bash
bacalhau job submit start-logging-container.yaml
```

The generator will:
- Create logs in `/var/log/app`
- Rotate logs every 5 minutes
- Store processed logs in `/var/log/logs_to_process`
- Include cloud provider metadata

### 4. Processing Logs with DuckDB

Execute queries across all nodes:
```bash
bacalhau job run process-logs.yaml
```

Results will be:
- Stored in provider-specific buckets
- Aggregated in a central GCP bucket
- Available for cross-cloud analysis

## Advanced Usage

### Custom SQL Queries

Modify queries in `process-logs.yaml`:

```sql
-- Count events by cloud provider
SELECT
  REGEXP_EXTRACT(message, 'provider=(\w+)') as cloud_provider,
  COUNT(*) as event_count
FROM log_data
GROUP BY cloud_provider
ORDER BY event_count DESC;

-- Find security events across clouds
SELECT * FROM log_data
WHERE message LIKE '%[SECURITY]%'
  AND "@timestamp" > CURRENT_TIMESTAMP - INTERVAL 1 HOUR
ORDER BY "@timestamp";
```

### Cloud-Specific Features

#### AWS
- Use IAM roles for S3 access
- Configure VPC endpoints for improved security
- Enable S3 versioning for audit trails

#### GCP
- Utilize Cloud Storage lifecycle policies
- Enable Cloud Audit Logging
- Configure VPC Service Controls

#### Azure
- Use Managed Identities for authentication
- Enable Blob Storage soft delete
- Configure Virtual Network service endpoints

#### Oracle Cloud
- Use Instance Principals for authentication
- Enable Object Storage versioning
- Configure Security Lists for network access

## Monitoring and Maintenance

### Health Checks
```bash
# List all nodes
bacalhau node list

# Check node status
bacalhau node info <NODE_ID>
```

### Log Verification
```bash
# View logs on specific node
bacalhau docker run --target=<NODE_ID> ubuntu tail -f /var/log/logs_to_process/latest.log
```

### Storage Management
```bash
# List buckets across providers
aws s3 ls
gsutil ls
az storage container list
oci os bucket list
```

## Cleanup

Remove all resources:
```bash
cd tf
./bulk-deploy.sh destroy
```

This will:
- Terminate all compute instances
- Remove storage buckets
- Clean up networking resources
- Delete security groups

## Troubleshooting

Common issues and solutions:

1. Cross-Cloud Networking
   - Verify security group rules
   - Check network connectivity
   - Ensure proper DNS resolution

2. Storage Access
   - Verify IAM/role permissions
   - Check storage endpoint configuration
   - Validate authentication credentials

3. Log Processing
   - Check local storage permissions
   - Verify DuckDB query syntax
   - Ensure proper cloud client configuration
