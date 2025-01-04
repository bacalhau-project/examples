# Setting Up Your Bacalhau Multi-Region Cluster on Azure 🚀

Welcome to the guide for setting up your own Bacalhau cluster across multiple Azure regions! This guide will walk you through creating a robust, distributed compute cluster that's perfect for running your Bacalhau workloads.

## What You'll Build

Think of this as building your own distributed supercomputer! Your cluster will provision compute nodes spread across different Azure regions for global coverage.

## Before You Start

You'll need a few things ready:
- Terraform (version 1.0.0 or newer)
- Azure CLI installed and set up
- An active Azure subscription
- Your subscription ID handy
- An SSH key pair for securely accessing your nodes

## Quick Setup Guide

0. First, set up an orchestrator node. We recommend using [Expanso Cloud](https://cloud.expanso.io/) for this! But you can always set up your own - follow the instructions [here](https://docs.bacalhau.org/getting-started/create-private-network#start-initial-orchestrator-node).

1. First, create a `terraform.tfvars.json` file with your Azure details:
   ```bash
   cp terraform.tfvars.example.json terraform.tfvars.json
   ```

2. Open up `terraform.tfvars.json` and fill in your Azure details:
   ```json
    "subscription_id": "f67231aa-8387-498b-9ca3-EXAMPLE",
    "app_tag": "bacalhau-cluster",
    "resource_group_region": "eastus",
    "username": "bacalhau-runner",
    "public_key": "~/.ssh/id_rsa.pub",
    "bacalhau_data_dir": "/bacalhau_data",
    "bacalhau_node_dir": "/bacalhau_node",
    "bacalhau_config_file_path": "./config/config.yaml",
   
    "locations": {
        "eastus": {
            "machine_type": "Standard_D4_v4",
            "node_count": 1
        }
   }
   ```

3. Let Terraform get everything ready:
   ```bash
   terraform init
   ```

4. Launch your cluster:
   ```bash
   terraform apply
   ```

## Understanding the Configuration

The infrastructure is organized into modules:
- **Network**: Creates VNets and subnets in each region
- **Security Group**: Sets up NSGs with rules for SSH, HTTP, and NATS
- **Instance**: Provisions VMs with cloud-init configuration

## Taking Your Cluster for a Test Drive

Once everything's up and running, let's make sure it works!

1. First, make sure you have the Bacalhau CLI installed. You can read more about installing the CLI [here](https://docs.bacalhau.org/getting-started/installation).

1. Setup your configuration to point at your orchestrator node:
   ```bash
   bacalhau config set -c API.Host=<ip-address-of-orchestrator>
   ```

2. Check on the health of your nodes:
   ```bash
   bacalhau node list
   ```

3. Run a simple test job:
   ```bash
   bacalhau docker run docker.io/bacalhauproject/hello-world
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
- Double-check your Azure permissions
- Make sure your subscription is active
- Verify that all needed resource providers are registered

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
terraform destroy
```

## Need to Check on Things?

If you need to peek under the hood, here's how:

1. Find your node IPs:
   ```bash
   terraform output deployment_status
   ```

2. SSH into a node:
   ```bash
   ssh -i ~/.ssh/id_rsa <username>@<public-ip>
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

### Modules
- `modules/network`: Handles VNet and subnet creation
- `modules/securityGroup`: Manages network security groups
- `modules/instance`: Provisions VMs with cloud-init

### Cloud-Init and Docker Setup
- `cloud-init/init-vm.yml`: Sets up your VM environment, installs packages, and gets services running
- `config/docker-compose.yml`: Runs Bacalhau in a privileged container with all the right volumes and health checks

## Azure Specific Commands

For ensuring that you have configured your Azure CLI correctly, here are some commands you can use:

### Get available Azure locations
```bash
az account list-locations --query "[].{Name:name, DisplayName:displayName}" -o table
```

### Get available VM sizes in a region
```bash
az vm list-sizes --location eastus --query "[].{Name:name, vCPUs:numberOfCores, MemoryGB:memoryInMb, GPUs:gpus}" --output table
```

### Get your subscription ID
```bash
az account show --query "id"
```

## Need Help?

If you get stuck or have questions:
- Check out the [official Bacalhau Documentation](https://docs.bacalhau.org/)
- Open an issue in our [GitHub repository](https://github.com/bacalhau-project/bacalhau)
- Join our [Slack](https://bit.ly/bacalhau-project-slack)

We're here to help you get your cluster running smoothly! 🌟
