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

1. First, create a `terraform.tfvars` file with your Azure details:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Open up `terraform.tfvars` and fill in your Azure details:
   ```hcl
   subscription_id = "your-subscription-id"
   app_tag = "bacalhau-demo"
   username = "your-ssh-username"
   public_key = "~/.ssh/id_rsa.pub"
   resource_group_region = "eastus"
   
   locations = {
     "eastus" = {
       machine_type = "Standard_D4s_v3"
       node_count   = 3
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

2. Check on the health of your nodes:
   ```bash
   bacalhau node list
   ```

3. Run a simple test job:
   ```bash
   bacalhau docker run ubuntu echo "Hello from my Azure cluster!" 
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

## Need Help?

If you get stuck or have questions:
- Check out the [official Bacalhau Documentation](https://docs.bacalhau.org/)
- Open an issue in our [GitHub repository](https://github.com/bacalhau-project/bacalhau)
- Join our [Slack](https://bit.ly/bacalhau-project-slack)

We're here to help you get your cluster running smoothly! 🌟

## Azure Specific Commands

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
