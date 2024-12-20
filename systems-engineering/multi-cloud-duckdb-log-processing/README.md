# Multi-Cloud Bacalhau Log Processing

## Overview
In this guide, we will deploy Bacalhau nodes across multiple cloud providers (AWS, GCP, Azure, and Oracle Cloud) and demonstrate how to run log processing jobs across multiple clouds simultaneously.

## Prerequisites
- AWS, GCP, Azure, and Oracle Cloud accounts with appropriate credentials
- Terraform installed locally
- Bacalhau CLI installed locally

## Deployment
1. Configure your cloud provider credentials
2. Review and customize the variables in `tf/variables.tf`
3. Run `./bulk-deploy.sh` to create/switch to a terraform workspace for every zone

## Environment Setup
After successful Terraform deployment, set up the environment variables:

```bash
export BACALHAU_NODE_CLIENTAPI_HOST=$(terraform output -raw ip_address)
export BACALHAU_IPFS_SWARM_ADDRESSES=$BACALHAU_NODE_IPFS_SWARMADDRESSES
```

## Verify Deployment
Check if all deployed nodes are in the network:
```bash
bacalhau node list
```

Test the network with a simple job across all nodes:
```bash
bacalhau docker run --target=all ubuntu echo hello
```

## Run Log Processing Jobs
Run the log processing job across all nodes:
```bash
bacalhau create job_multizone.yaml
```

Before downloading results, verify port access:
```bash
nc -zv $BACALHAU_NODE_CLIENTAPI_HOST 45337
```

Fetch job results (replace `<JOB_ID>` with your job ID):
```bash
bacalhau get <JOB_ID>
```
