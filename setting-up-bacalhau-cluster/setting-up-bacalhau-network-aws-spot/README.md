# AWS Spot Instance Region Finder

This repository contains scripts to help set up a Bacalhau cluster on AWS spot instances by finding the most cost-effective regions and instance types.

## Scripts

### 1. Region Availability Checker (`util/get_available_regions.py`)

This script checks all AWS regions to find those that have spot instances available that meet the minimum requirements for running Docker and one small Python container:
- At least 1 vCPU
- At least 2 GiB of memory

The script:
1. Queries all AWS regions (not just a subset)
2. Checks each region for instance types that meet the minimum requirements
3. Prioritizes smaller, cost-effective instance types (t3, t3a, t4g, t2, a1, m6g, m5, m5a families)
4. Verifies spot instance availability and pricing for suitable instance types
5. Outputs the results to:
   - `available_regions.json` - Comprehensive JSON file with detailed region and instance information
   - `available_regions.py` - Python importable format (for backward compatibility)
6. Displays a summary of the top 5 cheapest regions by default (with an option to show all)

#### Command-line Options

```
usage: get_available_regions.py [-h] [--show-all] [--max-workers MAX_WORKERS]

Find AWS regions with suitable spot instances for Docker and containers

options:
  -h, --help            show this help message and exit
  --show-all            Show all available regions, not just the top 5
  --max-workers MAX_WORKERS
                        Maximum number of parallel workers (default: 10)
```

### 2. Ubuntu AMI Finder (`util/get_ubuntu_amis.py`)

This script finds the latest Ubuntu 22.04 LTS AMI IDs for each available region:
1. Reads the list of available regions from `available_regions.json` (created by the first script)
2. Queries AWS for the latest Ubuntu 22.04 LTS AMI in each region
3. Outputs the results to `ubuntu_amis.csv` with detailed instance information including:
   - Region
   - AMI ID
   - Instance Type
   - vCPUs
   - Memory (GiB)
   - Spot Price ($/hr)

### 3. Config Updater (`util/update_config_with_regions.py`)

This script updates your Bacalhau cluster configuration with the available regions:
1. Reads the list of available regions from `available_regions.json`
2. Loads your existing `config.yaml` file
3. Adds all new regions that aren't already in your configuration
4. Uses recommended instance types from the region details when available
5. Creates a backup of your original configuration
6. Saves the updated configuration with all available regions

## Workflow

The scripts are designed to work together in sequence:

1. First, run `get_available_regions.py` to find regions with suitable spot instances
2. Then, run `get_ubuntu_amis.py` to get the latest Ubuntu AMIs for those regions
3. Finally, run `update_config_with_regions.py` to update your Bacalhau configuration
4. Verify your configuration with `verify_config_architecture.py` to ensure compatibility

This approach ensures you're only looking for AMIs in regions that have suitable spot instances available, and that your configuration includes all viable regions with the correct architecture compatibility between instance types and AMIs.

## Usage

### Prerequisites

1. AWS CLI configured with appropriate credentials
2. Python 3.6+ with required packages

You can run these scripts in two ways:

#### Option 1: Using uv (recommended)

The scripts include dependency metadata for use with [uv](https://github.com/astral-sh/uv), which will automatically install required dependencies:

```bash
# Install uv if you don't have it
pip install uv

# Run scripts directly with uv
uv run -s util/get_available_regions.py
uv run -s util/get_ubuntu_amis.py
uv run -s util/update_config_with_regions.py

# To see all available regions, not just the top 5
uv run -s util/get_available_regions.py --show-all
```

#### Option 2: Using pip

```bash
# Install dependencies manually
pip install boto3 botocore argparse pyyaml

# Run scripts
python util/get_available_regions.py
python util/get_ubuntu_amis.py
python util/update_config_with_regions.py

# To see all available regions, not just the top 5
python util/get_available_regions.py --show-all
```

### Step 1: Find Available Regions with Smallest Suitable Instances

```bash
uv run -s util/get_available_regions.py
```

This will create:
- `available_regions.json` - Comprehensive JSON file with detailed region and instance information
- `available_regions.py` - Python importable format (for backward compatibility)
- A console output showing the top 5 cheapest regions and their smallest suitable instances

Example output:
```
Checking 28 AWS regions for spot availability...
Looking for instances with at least 1 vCPUs and 2 GiB RAM

Found 18 regions with suitable spot instances out of 28 total regions
Available regions saved to: available_regions.json
Python module also saved to: available_regions.py

Top 5 cheapest regions for running Docker with a small Python container:
(Use --show-all to see all 18 available regions)
1. us-east-1 - t3.small - 2 vCPUs, 2.0 GiB RAM, $0.0078/hr
2. us-west-2 - t3a.small - 2 vCPUs, 2.0 GiB RAM, $0.0084/hr
3. eu-west-1 - t3.small - 2 vCPUs, 2.0 GiB RAM, $0.0091/hr
4. ap-southeast-1 - t3.small - 2 vCPUs, 2.0 GiB RAM, $0.0094/hr
5. eu-central-1 - t3.small - 2 vCPUs, 2.0 GiB RAM, $0.0098/hr
```

### Step 2: Get Ubuntu AMIs for Available Regions

```bash
uv run -s util/get_ubuntu_amis.py
```

This will create:
- `ubuntu_amis.csv` - CSV file with region, AMI ID, and instance details

Example CSV content:
```
Region,AMI ID,Instance Type,vCPUs,Memory (GiB),Spot Price ($/hr)
us-east-1,ami-0c7217cdde317cfec,t3.small,2,2.0,$0.0078
us-west-2,ami-0efcece6bed30fd98,t3a.small,2,2.0,$0.0084
eu-west-1,ami-0694d931cee176e7d,t3.small,2,2.0,$0.0091
```

### Step 3: Update Your Bacalhau Configuration

```bash
uv run -s util/update_config_with_regions.py
```

This will:
- Read your existing `config.yaml` file
- Add all new regions from `available_regions.json`
- Use recommended instance types for each region
- Create a backup of your original configuration at `config.yaml.bak`
- Save the updated configuration with all available regions

Example output:
```
Found 30 available regions in available_regions.json
Loaded configuration from config.yaml
Adding 27 new regions to config.yaml
Created backup of original config at config.yaml.bak
Updated config.yaml with 27 new regions
Total regions in config: 30
```

### Step 4: Verify Architecture Compatibility

```bash
uv run -s util/verify_config_architecture.py
```

This will:
- Check your `config.yaml` for architecture mismatches between instance types and AMIs
- Verify that instance types are supported in their respective regions
- Provide detailed recommendations if issues are found
- Ensure that x86_64 AMIs are used with x86_64 instances and arm64 AMIs with ARM instances

You can also automatically fix common issues with:

```bash
uv run -s util/verify_config_architecture.py --fix
```

The auto-fix option will:
- Create a backup of your current config.yaml
- Replace unsupported instance types with region-specific compatible alternatives
- Apply fixes based on a comprehensive database of instance type compatibility by region
- Re-verify the configuration after making changes

Example output:
```
Loading configuration from config.yaml...
Loading AMI data from ubuntu_amis.json...
Verifying architecture compatibility...
✓ No architecture compatibility issues found!
```

## Notes

- The region availability script may take several minutes to run as it checks all AWS regions
- If `available_regions.json` is not found, the Ubuntu AMI finder will fall back to a default list of regions
- AWS credentials with EC2 describe permissions are required to run these scripts
- Spot instance pricing is dynamic and may change over time, so it's recommended to run the script periodically to get the latest pricing information
- Not all instance types are available in all regions (especially newer regions) - the verify script will help identify unsupported types
- Architecture compatibility is critical - ARM instances (t4g, a1, c6g, etc.) require ARM64 AMIs, while x86 instances (t2, t3, m5, etc.) require x86_64 AMIs

## Quick Setup Guide

To quickly set up a Bacalhau cluster with optimal configuration, run these commands in sequence:

```bash
# 1. Find the lowest price instances with at least 2 CPU and 4GB RAM
uv run -s util/get_available_regions.py --show-all

# 2. Get the compatible Ubuntu AMIs for all regions
uv run -s util/get_ubuntu_amis.py

# 3. Update config.yaml with optimal settings (uses t3.medium or equivalent in each region)
uv run -s util/update_config_with_regions.py

# 4. Verify and automatically fix any remaining compatibility issues
uv run -s util/verify_config_architecture.py --fix --skip-live-check

# Optional: Run with live AWS availability check (requires AWS credentials)
# uv run -s util/verify_config_architecture.py --fix
```

This sequence will:
1. Find appropriate instances with sufficient resources (2 vCPU, 4GB RAM)
2. Fetch correct AMIs for each architecture and region
3. Configure with region-appropriate instance types (t3.medium or t2.medium in most regions)
4. Verify that all instance types are compatible with their regions

The updated scripts now properly identify instance capabilities and ensure you get instances with sufficient resources for running Docker and containers. 

## Managing AWS Spot Instances

Once you have configured your environment, you can use the following commands to manage your AWS spot instances for the Bacalhau cluster:

### Create Spot Instances

To create spot instances based on your configuration:

```bash
# Using uv
uv run -s deploy_spot.py --action create

# Using pip
python deploy_spot.py --action create
```

This will:
- Create VPC infrastructure in each configured region
- Launch spot instances across your configured regions
- Set up security groups and networking
- Install Bacalhau and dependencies via cloud-init

### List Spot Instances

To list all running spot instances:

```bash
# Using uv
uv run -s deploy_spot.py --action list

# Using pip
python deploy_spot.py --action list

# For JSON output
uv run -s deploy_spot.py --action list --format json
```

### Destroy Spot Instances

To terminate all spot instances and clean up resources:

```bash
# Using uv
uv run -s deploy_spot.py --action destroy

# Using pip
python deploy_spot.py --action destroy
```

This will:
- Terminate all running instances
- Delete associated VPCs, security groups, subnets, and internet gateways
- Clean up all AWS resources created by this tool

### Delete Disconnected AWS Nodes

To remove any disconnected Bacalhau nodes that are running on AWS:

```bash
# Using uv
uv run -s deploy_spot.py --action delete_disconnected_aws_nodes

# Using pip
python deploy_spot.py --action delete_disconnected_aws_nodes
```