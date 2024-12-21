# Multi-Cloud Log Processing with DuckDB and Bacalhau

## Overview
This example demonstrates how to process logs across multiple cloud providers using DuckDB and Bacalhau. The system deploys nodes across AWS, GCP, Azure, and Oracle Cloud, enabling distributed log processing and analysis with results aggregated in a central location.

## Prerequisites
- Cloud provider accounts and credentials:
  - Google Cloud Platform with billing enabled
  - AWS account with appropriate IAM permissions
  - Azure subscription
  - Oracle Cloud account
- CLI tools installed and configured:
  - `gcloud` CLI
  - `aws` CLI
  - `az` CLI
  - `oci` CLI
- Terraform (v1.0.0+)
- Bacalhau CLI
- Docker

## Quick Start

1. Configure cloud provider credentials:
```bash
# AWS
aws configure
# GCP
gcloud auth application-default login
# Azure
az login
# Oracle Cloud
oci setup config
```

2. Review and customize variables:
```bash
cp tf/variables.tf.example tf/variables.tf
# Edit tf/variables.tf with your configuration
```

3. Deploy infrastructure:
```bash
cd tf
./bulk-deploy.sh
```

4. Configure environment:
```bash
# Load node configuration
source ./node-config.sh

# Verify deployment
bacalhau node list
```

5. Start log processing:
```bash
# Deploy log generator
bacalhau job submit start-logging-container.yaml

# Process logs
bacalhau job run process-logs.yaml
```

6. View results:
```bash
# Results are stored in cloud-specific buckets and
# aggregated in the central GCP bucket
gsutil ls gs://${CENTRAL_BUCKET}/
```

For detailed instructions and advanced usage, see [PAGE.md](./PAGE.md).

## Architecture
- Nodes deployed across multiple cloud providers
- Each node generates and processes logs locally
- Results stored in provider-specific buckets
- Central aggregation in GCP bucket
- Cross-cloud networking via provider gateways

## Cleanup
```bash
cd tf
./bulk-deploy.sh destroy
```
