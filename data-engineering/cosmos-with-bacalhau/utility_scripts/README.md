# Utility Scripts

This directory contains various utility scripts for managing and working with the cosmos-with-bacalhau project.

## Bulk Delete Cosmos DB Script

`bulk_delete_cosmos.py` is a Python script that performs bulk deletion of data from an Azure Cosmos DB container. It uses a CosmosDB stored procedure to efficiently delete documents in batches.

### Usage

You can run this script directly:

```bash
# Run with dry-run to see what would be deleted without actually deleting
python3 utility_scripts/bulk_delete_cosmos.py --dry-run

# Delete all data 
python3 utility_scripts/bulk_delete_cosmos.py

# Specify a different database or container
python3 utility_scripts/bulk_delete_cosmos.py --database MyDatabase --container MyContainer

# Load credentials from a config file
python3 utility_scripts/bulk_delete_cosmos.py --config config/config.yaml
```

Or through the sensor-manager.sh script:

```bash
# Run with dry-run to see what would be deleted without actually deleting
./sensor-manager.sh clean --dry-run

# Delete all data (with confirmation prompt)
./sensor-manager.sh clean

# Delete all data (skipping confirmation prompt)
./sensor-manager.sh clean --yes
```

### How It Works

1. The script creates a stored procedure in CosmosDB that can efficiently delete documents
2. It finds all unique partition key values (cities) in your container
3. For each partition key, it executes the stored procedure to delete all documents
4. Provides a summary of deleted documents

### Requirements

- Python 3.11 or higher (specified in script header)
- Azure Cosmos DB SDK for Python (`azure-cosmos`)
- PyYAML for config file parsing
- Connection details can be provided via:
  - Command-line arguments (`--database`, `--container`)
  - Environment variables:
    - `COSMOS_ENDPOINT`: Your Cosmos DB endpoint URL
    - `COSMOS_KEY`: Your Cosmos DB access key 
    - `COSMOS_DATABASE`: Database name
    - `COSMOS_CONTAINER`: Container name
  - Configuration file (YAML format) specified with `--config`

When multiple sources are provided, the script prioritizes:
1. Command-line arguments
2. Config file values
3. Environment variables
4. Default values