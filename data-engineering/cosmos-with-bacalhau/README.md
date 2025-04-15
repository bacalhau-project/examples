# Cosmos DB with Bacalhau

This project demonstrates how to use Azure Cosmos DB with Bacalhau for data engineering workloads. It includes tools for processing sensor data and uploading it to Cosmos DB using bulk upload capabilities.

## Project Structure

- `src/CosmosUploader/`: Contains the C# application for uploading data to Cosmos DB
- `cosmos-uploader/`: Contains Docker files and entrypoint scripts for containerization
- `config/`: Configuration files for the simulation
- `data/`: Directory where sensor data is stored in SQLite databases

## CosmosDB Uploader

The C# implementation of the CosmosDB uploader provides:

- **Bulk Upload Capabilities**: Uses the CosmosDB .NET SDK's bulk upload feature for efficient data transfer
- **Batch Processing**: Processes data in configurable batch sizes for optimal performance
- **Retry Logic**: Built-in retry mechanism for handling rate limiting and transient errors
- **Data Archiving**: Optional archiving of processed data to Parquet files for long-term storage
- **Continuous Mode**: Can run in continuous mode, polling for new data at configurable intervals

## Getting Started

### Prerequisites

- Docker and Docker Compose
- .NET SDK 7.0 or later (for local development)
- Azure Cosmos DB account
- Bash 4.0 or later (for sensor-manager.sh)

### Configuration

1. Create a config.yaml file in the config directory based on the example.yaml template
2. Update the Cosmos DB connection details in docker-compose.yml or set them as environment variables:
   ```bash
   export COSMOS_ENDPOINT="your-cosmos-endpoint"
   export COSMOS_KEY="your-cosmos-key"
   export COSMOS_DATABASE="SensorData"
   export COSMOS_CONTAINER="SensorReadings"
   ```

### Using the Sensor Manager

The project includes a unified management script `sensor-manager.sh` that handles all aspects of the sensor simulation and Cosmos DB integration:

```bash
# Make the script executable
chmod +x sensor-manager.sh

# Start the sensor simulation
./sensor-manager.sh start

# View logs from all containers
./sensor-manager.sh logs

# Monitor sensor status and data uploads
./sensor-manager.sh monitor

# Query SQLite databases
./sensor-manager.sh query --all
./sensor-manager.sh query Amsterdam 1

# Run system diagnostics
./sensor-manager.sh diagnostics

# Stop all containers
./sensor-manager.sh stop

# Clean up Cosmos DB data
./sensor-manager.sh clean

# Force cleanup of all containers
./sensor-manager.sh cleanup
```

#### Advanced Usage

The sensor manager supports various configuration options:

```bash
# Start with custom configuration
SENSORS_PER_CITY=10 ./sensor-manager.sh start

# Start without rebuilding the uploader image
./sensor-manager.sh start --no-rebuild

# Start with a custom project name
./sensor-manager.sh start --project-name my-sensors

# Clean Cosmos DB with dry run
./sensor-manager.sh clean --dry-run

# Monitor without colors
./sensor-manager.sh monitor --plain
```

For a complete list of commands and options, run:
```bash
./sensor-manager.sh help
```

### Manual Docker Compose Usage

While the sensor manager is the recommended way to run the system, you can also use Docker Compose directly:

```bash
# Build the CosmosDB uploader application and Docker image
cd cosmos-uploader
./build.sh

# Start the entire system
docker-compose up -d
```

### Monitoring

```bash
# View logs from a specific uploader
docker logs uploader-amsterdam -f

# View logs from all uploaders
docker-compose logs -f uploader-amsterdam uploader-beijing uploader-berlin uploader-cairo uploader-chicago
```

## Querying Cosmos DB

The project includes a tool to query Cosmos DB directly from the command line, which is useful for verifying that data is being uploaded correctly:

```bash
# Query the last 5 documents from Amsterdam
./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml --city Amsterdam --limit 5

# Count all documents in the database
./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml --count

# Run a custom query
./cosmos-uploader/cosmosdb-query.sh --config config/config.yaml --query "SELECT * FROM c WHERE c.temperature > 25.0 LIMIT 10"
```

See [cosmos-query-tool.md](docs/cosmos-query-tool.md) for detailed documentation.

## Setting Up Azure Cosmos DB

### Setting Environment Variables

First, set up all the necessary environment variables that will be used throughout the setup process:

```bash
# Azure Resource Configuration
export RESOURCE_GROUP="CosmosDB-RG"
export LOCATION="brazilsouth"
# Add a unique suffix to ensure the Cosmos DB account name is globally unique
export UNIQUE_SUFFIX=$RANDOM
export COSMOS_ACCOUNT_NAME="cosmos-bacalhau-${UNIQUE_SUFFIX}"
export DATABASE_NAME="SensorData"
export CONTAINER_NAME="SensorReadings"
export PARTITION_KEY="/city"
export THROUGHPUT=400
```

### Creating Resources via Azure CLI

1. **Login to Azure**:

```bash
az login
```

2. **Create a Resource Group**:

```bash
az group create --name $RESOURCE_GROUP --location $LOCATION
```

3. **Create a Cosmos DB Account**:

```bash
# Create a Cosmos DB account with a single region
az cosmosdb create \
  --name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --kind GlobalDocumentDB \
  --default-consistency-level Session \
  --enable-automatic-failover false \
  --locations regionName=$LOCATION failoverPriority=0
```

4. **Create a Database**:

```bash
az cosmosdb sql database create \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --name $DATABASE_NAME
```

5. **Create the Container**:

```bash
az cosmosdb sql container create \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --database-name $DATABASE_NAME \
  --name $CONTAINER_NAME \
  --partition-key-path $PARTITION_KEY \
  --throughput $THROUGHPUT
```

6. **Get Connection Information**:

```bash
# Get the endpoint
export COSMOS_ENDPOINT=$(az cosmosdb show --name $COSMOS_ACCOUNT_NAME --resource-group $RESOURCE_GROUP --query documentEndpoint -o tsv)

# Get the primary key (for admin access)
export COSMOS_KEY=$(az cosmosdb keys list --name $COSMOS_ACCOUNT_NAME --resource-group $RESOURCE_GROUP --query primaryMasterKey -o tsv)

echo "Cosmos DB Endpoint: $COSMOS_ENDPOINT"
echo "Cosmos DB Key: $COSMOS_KEY"
```

## Performance Considerations

The C# implementation leverages the Azure CosmosDB .NET SDK's bulk upload capabilities, which provides optimized throughput by:

1. Batching multiple documents into a single network request
2. Managing parallelism with configurable batch sizes
3. Automatically retrying rate-limited requests
4. Tracking request charges for performance monitoring
5. Using proper partitioning strategies for distributed writes

This results in significantly better performance compared to single document uploads, especially for large datasets from multiple sensors.

## Troubleshooting

### Common Issues

1. **Docker Build Issues**:
   - If you encounter issues with the Docker build, check that the paths in the Dockerfile are correct
   - Ensure the .NET SDK version in the Dockerfile matches the version used in the project file
   - Make sure the entrypoint.sh script is properly configured

2. **Cosmos DB Connection Issues**:
   - Verify that the connection string and key are correctly set in the configuration
   - Check that the database and container exist in your Cosmos DB account
   - Ensure that you have sufficient permissions to write to the container

3. **Data Processing Issues**:
   - If you encounter issues with data processing, check the logs for specific error messages
   - Verify that the SQLite databases contain the expected data structure
   - Adjust batch size and processing parameters based on your hardware capabilities

## License

This project is licensed under the MIT License - see the LICENSE file for details.