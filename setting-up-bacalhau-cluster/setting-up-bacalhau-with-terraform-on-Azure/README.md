# Setting Up Your Bacalhau Multi-Region Cluster on GCP 🚀

Welcome to the guide for setting up your own Bacalhau cluster across multiple Google Cloud Platform (GCP) regions! This guide will walk you through creating a robust, distributed compute cluster that's perfect for running your Bacalhau workloads.

## What You'll Build

Think of this as building your own distributed supercomputer! Your cluster will provision compute nodes spread across different GCP regions for global coverage.

## Before You Start

You'll need a few things ready:
- Terraform (version 1.0.0 or newer)
- Google Cloud SDK installed and set up
- An active GCP billing account
- Your organization ID handy
- An SSH key pair for securely accessing your nodes

## Quick Setup Guide

1. First, grab a copy of the example environment file:
   ```bash
   cp env.json.example env.json
   ```

2. Open up `env.json` and fill in your GCP details (more on this below!)

3. Let Terraform get everything ready:
   ```bash
   terraform init --env-file env.json
   ```

4. Launch your cluster:
   ```bash
   terraform apply --env-file env.json
   ```

## Setting Up Your Configuration

The `env.json` file is where all the magic happens. Here's what you'll need to fill in:

### Essential Settings
- `bootstrap_project_id`: Your existing GCP project (just used for setup)
- `base_project_name`: What you want to call your new project
- `gcp_billing_account_id`: Where the charges should go
- `gcp_user_email`: Your GCP email address
- `org_id`: Your organization's ID
- `app_tag`: A friendly name for your resources (like "bacalhau-demo")

### Node Configuration
- `bacalhau_data_dir`: Where job data should be stored
- `bacalhau_node_dir`: Where node configs should live
- `username`: Your SSH username
- `public_key`: Path to your SSH public key

### Location Settings
You can set up nodes in different regions with custom configurations:
```json
"locations": {
  "us-central1": {
    "zone": "us-central1-a",
    "node_count": 3,
    "machine_type": "e2-standard-4"
  }
}
```

## Taking Your Cluster for a Test Drive

Once everything's up and running, let's make sure it works!

First, make sure you have the Bacalhau CLI installed. You can read more about installing the CLI [here](https://docs.bacalhau.org/getting-started/installation).

0. First configure the CLI to use your cluster:
   ```bash
   bacalhau config set -c API.Host=<orchestrator-ip>
   ```

1. Check on the health of your nodes:
   ```bash
   bacalhau node list
   ```

2. If you're using the Expanso Cloud hosted orchestrator (Recommended!), you can look at your nodes on the [Expanso Cloud](https://cloud.expanso.io/networks/) dashboard in real-time.

3. Run a simple test job:
   ```bash
   bacalhau docker run ubuntu echo "Hello from my cluster!" 
   ```

4. Check on your jobs:
   ```bash
   bacalhau list
   ```

5. Get your results:
   ```bash
   bacalhau get <job-id>
   ```

## Troubleshooting Tips

Having issues? Here are some common solutions:

### Deployment Problems
- Double-check your GCP permissions
- Make sure your billing account is active
- Verify that all needed APIs are turned on in GCP

### Node Health Issues
- Look at the logs on a node: `journalctl -u bacalhau-startup.service`
- Check Docker logs on a node: `docker logs <container-id>`
- Make sure that port 4222 isn't blocked

### Job Running Troubles
- Verify your NATS connection settings
- Check if nodes are properly registered
- Make sure compute is enabled in your config

## Cleaning Up

When you're done, clean everything up with:
```bash
terraform destroy --env-file env.json
```

## Need to Check on Things?

If you need to peek under the hood, here's how:

1. Find your node IPs:
   ```bash
   terraform output instance_ips
   ```

2. SSH into a node:
   ```bash
   ssh -i ~/.ssh/id_rsa ubuntu@<public-ip>
   ```

3. Check on Docker:
   ```bash
   docker ps
   ```

4. Go into the container on the node:
   ```bash
   CONTAINER_ID=$(docker ps --filter name=^/bacalhau_node --format '{{.ID}}' | head -n1)
   docker exec -it $CONTAINER_ID /bin/bash
   ```

## Understanding the Configuration Files

Here's what each important file does in your setup:

### Core Files
- `main.tf`: Your main Terraform configuration
- `variables.tf`: Where input variables are defined
- `outputs.tf`: What information Terraform will show you
- `config/config.yaml`: How your Bacalhau nodes are configured
- `scripts/startup.sh`: Gets your nodes ready to run
- `scripts/bacalhau-startup.service`: Manages the Bacalhau service

### Cloud-Init and Docker Setup
- `cloud-init/init-vm.yml`: Sets up your VM environment, installs packages, and gets services running
- `config/docker-compose.yml`: Runs Bacalhau in a privileged container with all the right volumes and health checks

The neat thing is that most of your configuration happens in just one file: `env.json`. Though if you want to get fancy, there's lots more you can customize! 

## Need Help?

If you get stuck or have questions:
- Check out the [official Bacalhau Documentation](https://docs.bacalhau.org/)
- Open an issue in our [GitHub repository](https://github.com/bacalhau-project/bacalhau)
- Join our [Slack](https://bit.ly/bacalhau-project-slack)

We're here to help you get your cluster running smoothly! 🌟


# Azure Specifics 

### Get your locations
```bash
az account list-locations --query "[].{Name:name, DisplayName:displayName}" -o table
```

### Get your VM sizes
```bash
az vm list-sizes --location eastus --query "[].{Name:name, vCPUs:numberOfCores, MemoryGB:memoryInMb, GPUs:gpus}" --output table
```

### Get your subscription ID
```bash
az account show --query "id"
```