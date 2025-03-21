# Bacalhau AWS Spot Instance Cluster Setup Guide

This guide walks you through setting up a Bacalhau compute cluster using AWS spot instances. The scripts in this repository automate finding cost-effective regions, configuring the right instance types, and deploying a complete Bacalhau cluster with minimal effort.

## Prerequisites

Before you begin, make sure you have:

1. **AWS Account and Credentials**: Active AWS account with permissions to create EC2 instances, VPCs, security groups, etc.
2. **AWS CLI Tools**: Installed and configured with valid credentials.
3. **Python 3.9+**: With pip or uv package manager.
4. **SSH Key Pair**: For secure access to your instances. 

## Setup Process

### Step 1: Configure AWS Credentials

Ensure your AWS credentials are properly configured:

```bash
# Configure AWS credentials
aws configure
# or
aws sso login
```

Verify your credentials work correctly:
```bash
aws sts get-caller-identity
```

### Step 2: Clone the Repository

```bash
git clone https://github.com/bacalhau-project/bacalhau-examples.git
cd bacalhau-examples/setting-up-bacalhau-cluster/setting-up-bacalhau-network-aws-spot
```

### Step 3: Install Dependencies

Using uv (recommended):
```bash
pip install uv
```

Or using pip directly:

### Step 4: Create Configuration File

Copy the example configuration:
```bash
cp config.yaml_example config.yaml
```

Edit `config.yaml` to customize your deployment:
```yaml
aws:
  total_instances: 3  # Total instances across all regions
  username: bacalhau-runner  # SSH username
  private_ssh_key_path: ~/.ssh/id_rsa  # Path to your private SSH key
  public_ssh_key_path: ~/.ssh/id_rsa.pub  # Path to your public SSH key
  timeouts:
    api: 30
    spot_fulfillment: 600
    ip_assignment: 300
    provisioning: 600
    
bacalhau:
  orchestrators:
    - nats://<your_orchestrator_url>:4222  # Your Bacalhau orchestrator URL
  token: <your_bacalhau_network_token>  # Network token for authentication
  tls: true  # Enable TLS
```

Ensure your SSH keys have the correct permissions:
```bash
chmod 600 ~/.ssh/id_rsa
```

Additionally, you can add additional commands to the cloud-init script by creating a file called `additional_commands.sh` in the `instance/scripts` directory.

```bash
cp instance/scripts/additional_commands.sh_example instance/scripts/additional_commands.sh
chmod 700 instance/scripts/additional_commands.sh
```

Edit the `additional_commands.sh` file to add your commands.

This could be anything you want to run on the instances after they are deployed:
- Setting secrets
- Installing additional software
- Setting up environment variables

### Step 5: Find Optimal Regions and Instance Types

The scripts will automatically identify regions with available spot capacity and the most cost-effective instance types:

```bash
# Find available regions with suitable spot instances
uv run -s util/get_available_regions.py

# Get Ubuntu AMIs for available regions
uv run -s util/get_ubuntu_amis.py

# Update config.yaml with optimal regions and instances
uv run -s util/update_config_with_regions.py
```

### Step 6: Deploy Your Bacalhau Cluster

With your configuration prepared, deploy the cluster:

```bash
# Create spot instances and deploy Bacalhau
uv run -s deploy_spot.py --action create
```

This will:
1. Create VPC infrastructure in each configured region
2. Launch spot instances with the specified configuration
3. Install and configure Bacalhau on each instance
4. Join the instances to your Bacalhau network

### Step 7: Manage Your Cluster

List running instances (this queries the record in machines.db and then queries AWS to get the latest status):
```bash
uv run -s deploy_spot.py --action list
```

View instance details in a formatted table (only reads from machines.db):
```bash
uv run -s deploy_spot.py --action table
```

When you're done, terminate all instances:
```bash
uv run -s deploy_spot.py --action destroy
```

**Note**: The destroy command may need to be run multiple times to completely clean up all resources. You can also use the dedicated VPC cleanup script:

```bash
uv run -s delete_vpcs.py
```

**Note**: The delete_vpcs.py script will delete all VPCs in the regions specified in the config.yaml file - it may need to be run multiple times to completely clean up all resources, due to AWS API issues with completing the deletion.

## Understanding the Configuration

### Key Configuration Options

- **total_instances**: Controls how many instances will be deployed across all regions
- **node_count**: Can be set to a specific number or "auto" to distribute evenly
- **regions**: Each region section specifies:
  - **ami_id**: The Ubuntu AMI ID (can be "auto" to select based on architecture)
  - **architecture**: Either "x86_64" or "arm64"
  - **machine_type**: EC2 instance type (e.g., "t3.small", "t4g.small")

### Architecture Compatibility

Ensure that your instance types match the AMI architecture:
- x86_64 AMIs require x86_64 instances (e.g., t3.micro, m5.large)
- ARM64 AMIs require ARM instances (e.g., t4g.micro, a1.medium)

The `verify_config_architecture.py` script helps identify and fix incompatibilities.

## Troubleshooting

### Common Issues

1. **AWS Authentication Errors**: Run `aws sso login` to renew credentials

2. **Spot Capacity Not Available**: Try different regions or instance types

3. **Resources Not Fully Cleaned Up**: Run destroy multiple times and use delete_vpcs.py:
   ```bash
   uv run -s deploy_spot.py --action destroy
   uv run -s delete_vpcs.py
   ```

### Viewing Logs

For detailed logging information:
```bash
cat debug_deploy_spot.log
```