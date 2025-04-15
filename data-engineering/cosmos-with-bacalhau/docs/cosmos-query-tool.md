# CosmosDB Query Tool

This tool allows you to query Azure Cosmos DB directly from the command line to verify if data is being uploaded correctly.

## Prerequisites

- Azure CLI installed on your machine
- Python 3.x
- Access to an Azure Cosmos DB account

## Installation

The tool is already included in the project. If Azure CLI is not already installed, you can install it following the [official documentation](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli).

## Configuration

There are two ways to configure the tool:

1. **Using a config file**: The tool can read connection parameters from a YAML config file.
2. **Command-line parameters**: You can provide all necessary connection parameters directly.

## Usage

```bash
./cosmos-uploader/cosmosdb-query.sh [OPTIONS]
```

### Options

- `--config CONFIG_FILE` - Path to config YAML file (optional)
- `--endpoint URL` - CosmosDB endpoint URL
- `--key KEY` - CosmosDB access key
- `--database NAME` - Database name
- `--container NAME` - Container name
- `--count` - Count total documents
- `--city CITY` - Filter by city (partition key)
- `--sensor SENSOR_ID` - Filter by sensor ID
- `--limit N` - Limit results (default: 10)
- `--query 'SQL QUERY'` - Execute a custom SQL query
- `--help, -h` - Show help message

### Examples

1. Using config file to count all documents:
   ```bash
   ./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml --count
   ```

2. Filtering by city with a limit:
   ```bash
   ./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml --city Amsterdam --limit 5
   ```

3. Using a custom query:
   ```bash
   ./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml --query "SELECT TOP 5 * FROM c WHERE c.temperature > 25.0"
   ```

4. Providing all parameters directly:
   ```bash
   ./cosmos-uploader/cosmosdb-query.sh --endpoint $COSMOS_ENDPOINT --key $COSMOS_KEY --database SensorData --container SensorReadings --city Amsterdam
   ```

## Troubleshooting

### Azure CLI Authentication

If you encounter authentication issues, make sure you're logged in to Azure:

```bash
az login
```

### Check CosmosDB Extension

The script will attempt to install the required CosmosDB extension if not present. If you experience issues:

```bash
az extension add --name cosmosdb-preview
```

### Command Versions

Depending on your Azure CLI version, the script will attempt multiple command formats if the first one fails.