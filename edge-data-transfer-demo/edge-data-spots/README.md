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

This approach ensures you're only looking for AMIs in regions that have suitable spot instances available, and that your configuration includes all viable regions.

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

## Notes

- The region availability script may take several minutes to run as it checks all AWS regions
- If `available_regions.json` is not found, the Ubuntu AMI finder will fall back to a default list of regions
- AWS credentials with EC2 describe permissions are required to run these scripts
- Spot instance pricing is dynamic and may change over time, so it's recommended to run the script periodically to get the latest pricing information 
