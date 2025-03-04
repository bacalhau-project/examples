# Cosmos DB with Bacalhau

This project demonstrates how to use Azure Cosmos DB with Bacalhau for data engineering workloads. It includes tools for processing log data and uploading it to Cosmos DB, with support for both standard processing and data cleaning operations.

## Project Structure

- `cosmos-uploader/`: Contains the Docker image for the Cosmos DB uploader
  - `Dockerfile`: Defines the Docker image for the uploader
  - `entrypoint.sh`: Entry point script for the Docker container
  - `process_logs.py`: Python script for processing logs and uploading to Cosmos DB
  - `requirements.txt`: Python dependencies for the uploader
  - `config.yaml`: Sample configuration file for the uploader
- `cosmos_export_job.yaml`: Bacalhau job definition for standard log processing
- `cosmos_export_clean_job.yaml`: Bacalhau job definition for data cleaning
- `cosmomigration.md`: Documentation for migrating from PostgreSQL to Azure Cosmos DB

## Getting Started

### Prerequisites

- Azure Cosmos DB account
- Azure CLI
- Docker
- Bacalhau CLI

### Setting Up Azure Cosmos DB

#### Setting Environment Variables

First, set up all the necessary environment variables that will be used throughout the setup process:

```bash
# Azure Resource Configuration
export RESOURCE_GROUP="CosmosDB-RG"
export LOCATION="brazilsouth"
# Add a unique suffix to ensure the Cosmos DB account name is globally unique
export UNIQUE_SUFFIX=$RANDOM
export COSMOS_ACCOUNT_NAME="cosmos-bacalhau-${UNIQUE_SUFFIX}"
export DATABASE_NAME="LogDatabase"
export CONTAINER_NAME="global-telemetry"
export PARTITION_KEY="/region"
export THROUGHPUT=400

# Service Principal Configuration (for nodes)
export SP_NAME="cosmos-uploader-sp"

# Role Definitions
export WRITE_ROLE_NAME="CosmosWriteOnlyRole"
export READWRITE_ROLE_NAME="CosmosReadWriteRole"

# Docker Image Configuration
export DOCKER_IMAGE="ghcr.io/bacalhau-project/cosmos-uploader:latest"

# Input/Output Paths
export LOCAL_LOG_PATH="/bacalhau_data"
export CONTAINER_LOG_PATH="/var/log/app"
export LOG_FILENAME="access.log"

# Processing Configuration
export CHUNK_SIZE=500000
export BATCH_SIZE=1000
export MAX_WORKERS=10
```

#### Creating Resources via Azure CLI

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
# Note: We're not using zone redundancy or multiple regions to avoid compatibility issues
az cosmosdb create \
  --name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --kind GlobalDocumentDB \
  --default-consistency-level Session \
  --enable-automatic-failover false \
  --locations regionName=$LOCATION failoverPriority=0

# If you want to add a secondary region later (optional):
# az cosmosdb update \
#   --name $COSMOS_ACCOUNT_NAME \
#   --resource-group $RESOURCE_GROUP \
#   --locations regionName=$LOCATION failoverPriority=0 \
#   --locations regionName=westus2 failoverPriority=1
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

#### Setting Up Access Control

1. **Create a Role for Write-Only Access** (for nodes):

```bash
# Create write-only role definition
cat > role-definition.json << EOF
{
  "RoleName": "$WRITE_ROLE_NAME",
  "Type": "CustomRole",
  "AssignableScopes": ["/"],
  "Permissions": [
    {
      "DataActions": [
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/create"
      ]
    }
  ]
}
EOF

az cosmosdb sql role definition create \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --body @role-definition.json

# Store the role definition ID
export WRITE_ROLE_ID=$(az cosmosdb sql role definition list \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[?roleName=='$WRITE_ROLE_NAME'].id" -o tsv)
```

2. **Create a Role for Read-Write Access** (for admins):

```bash
# Create read-write role definition
cat > readwrite-role-definition.json << EOF
{
  "RoleName": "$READWRITE_ROLE_NAME",
  "Type": "CustomRole",
  "AssignableScopes": ["/"],
  "Permissions": [
    {
      "DataActions": [
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/readChangeFeed",
        "Microsoft.DocumentDB/databaseAccounts/readMetadata"
      ]
    }
  ]
}
EOF

az cosmosdb sql role definition create \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --body @readwrite-role-definition.json

# Store the role definition ID
export READWRITE_ROLE_ID=$(az cosmosdb sql role definition list \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[?roleName=='$READWRITE_ROLE_NAME'].id" -o tsv)
```

3. **Assign Write-Only Role to a Service Principal** (for nodes):

```bash
# Create a service principal if you don't have one
echo "Creating service principal..."
SP_OUTPUT=$(az ad sp create-for-rbac --name "$SP_NAME" --output json)
echo "Service principal created."

# Extract the appId directly using Azure CLI's built-in JSON parsing
export SP_APP_ID=$(az ad sp list --display-name "$SP_NAME" --query "[0].appId" -o tsv)
echo "Service Principal App ID: $SP_APP_ID"

# Get the service principal object ID directly by display name
export SP_OBJECT_ID=$(az ad sp list --display-name "$SP_NAME" --query "[0].id" -o tsv)
echo "Service Principal Object ID: $SP_OBJECT_ID"

# If the above doesn't work, try getting the object ID directly from the enterprise application
if [ -z "$SP_OBJECT_ID" ]; then
  echo "Trying alternative method to get Object ID..."
  export SP_OBJECT_ID=$(az ad app show --id "$SP_APP_ID" --query "objectId" -o tsv)
  echo "Service Principal Object ID (alternative method): $SP_OBJECT_ID"
fi

# Verify we have a valid Object ID before proceeding
if [ -z "$SP_OBJECT_ID" ]; then
  echo "ERROR: Could not retrieve Service Principal Object ID. Please create the service principal manually."
  echo "You can create a service principal in the Azure Portal and set SP_OBJECT_ID manually."
  exit 1
fi

# Assign the role
echo "Assigning role to service principal..."
az cosmosdb sql role assignment create \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --role-definition-id $WRITE_ROLE_ID \
  --principal-id $SP_OBJECT_ID \
  --scope "/dbs/$DATABASE_NAME/colls/$CONTAINER_NAME"
echo "Role assigned successfully."
```

4. **Assign Read-Write Role to an Admin User**:

```bash
# Get your user object ID
echo "Getting current user object ID..."
export ADMIN_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
echo "Admin Object ID: $ADMIN_OBJECT_ID"

# Assign the role
echo "Assigning role to admin user..."
az cosmosdb sql role assignment create \
  --account-name $COSMOS_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --role-definition-id $READWRITE_ROLE_ID \
  --principal-id $ADMIN_OBJECT_ID \
  --scope "/dbs/$DATABASE_NAME/colls/$CONTAINER_NAME"
echo "Role assigned successfully."
```

5. **Get Connection Information**:

```bash
# Get the endpoint
export COSMOS_ENDPOINT=$(az cosmosdb show --name $COSMOS_ACCOUNT_NAME --resource-group $RESOURCE_GROUP --query documentEndpoint -o tsv)

# Get the primary key (for admin access)
export COSMOS_KEY=$(az cosmosdb keys list --name $COSMOS_ACCOUNT_NAME --resource-group $RESOURCE_GROUP --query primaryMasterKey -o tsv)

echo "Cosmos DB Endpoint: $COSMOS_ENDPOINT"
echo "Cosmos DB Key: $COSMOS_KEY"
```

6. **Update Configuration File**:

```bash
# Create a config file from the template with the correct values
cat > config.yaml << EOF
# Azure Cosmos DB Configuration
cosmos:
  # Connection details
  endpoint: "$COSMOS_ENDPOINT"
  key: "$COSMOS_KEY"
  database_name: "$DATABASE_NAME"
  container_name: "$CONTAINER_NAME"
  partition_key: "$PARTITION_KEY"
  
  # Connection settings
  connection:
    mode: "direct"  # Options: direct, gateway
    protocol: "Https"  # Options: Https, Tcp
    retry_total: 10
    retry_backoff_max: 30
    max_retry_attempts: 10
    max_retry_wait_time: 30
  
  # Performance settings
  performance:
    preferred_regions: []  # List of preferred regions, e.g. ["East US", "West US"]
    enable_endpoint_discovery: true
    bulk_execution: true

# Logging configuration
logging:
  level: "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
# Processing configuration
processing:
  chunk_size: $CHUNK_SIZE  # Number of lines to process in a chunk
  batch_size: $BATCH_SIZE  # Number of documents to upload in a single batch
  max_workers: $MAX_WORKERS  # Maximum number of worker threads
  clean_mode: false  # Whether to perform additional data cleaning
EOF
```

### Building and Pushing the Docker Image

```bash
# Build the Docker image
docker build -t $DOCKER_IMAGE ./cosmos-uploader

# Push the Docker image to a registry
docker push $DOCKER_IMAGE
```

### Running Jobs

#### Standard Processing Job

```bash
# Encode the configuration file as base64
export CONFIG_B64=$(base64 -w 0 cosmos-uploader/config.yaml)
export PYTHON_B64=$(base64 -w 0 cosmos-uploader/process_logs.py)

# Run the job
bacalhau docker run \
  --input-volumes $LOCAL_LOG_PATH:$CONTAINER_LOG_PATH \
  --env CONFIG_FILE_B64=$CONFIG_B64 \
  --env PYTHON_FILE_B64=$PYTHON_B64 \
  --env INPUT_FILE=$CONTAINER_LOG_PATH/$LOG_FILENAME \
  --env CHUNK_SIZE=$CHUNK_SIZE \
  --env BATCH_SIZE=$BATCH_SIZE \
  --env MAX_WORKERS=$MAX_WORKERS \
  --env CLEAN_MODE=false \
  $DOCKER_IMAGE
```

#### Data Cleaning Job

```bash
# Encode the configuration file as base64
export CONFIG_B64=$(base64 -w 0 cosmos-uploader/config.yaml)
export PYTHON_B64=$(base64 -w 0 cosmos-uploader/process_logs.py)

# Run the job
bacalhau docker run \
  --input-volumes $LOCAL_LOG_PATH:$CONTAINER_LOG_PATH \
  --env CONFIG_FILE_B64=$CONFIG_B64 \
  --env PYTHON_FILE_B64=$PYTHON_B64 \
  --env INPUT_FILE=$CONTAINER_LOG_PATH/$LOG_FILENAME \
  --env CHUNK_SIZE=$CHUNK_SIZE \
  --env BATCH_SIZE=$BATCH_SIZE \
  --env MAX_WORKERS=$MAX_WORKERS \
  --env CLEAN_MODE=true \
  $DOCKER_IMAGE
```
### Running Performance Benchmarks

The project includes a benchmarking tool to measure Cosmos DB performance:

```bash
# Install benchmark dependencies
pip install -r benchmark_requirements.txt

# Run the benchmark
python benchmark_cosmos.py --config cosmos-uploader/config.yaml --output benchmark_results
```

## Performance Considerations

- Adjust `CHUNK_SIZE`, `BATCH_SIZE`, and `MAX_WORKERS` based on your workload and available resources
- Use bulk execution for better performance with large datasets
- Consider using preferred regions in the configuration to reduce latency
- Monitor RU consumption in Azure Cosmos DB and adjust throughput as needed

## Monitoring and Logging

The uploader provides detailed logging of the processing and upload operations, including:
- Progress updates
- Processing rates
- Success and failure counts
- Error details

## Troubleshooting

### Common Issues

1. **Account Name Already Taken**:
   - Cosmos DB account names must be globally unique across all Azure
   - If you encounter "Dns record for X under zone Document is already taken", try a different account name
   - The script above generates a random suffix to help avoid this issue

2. **Zone Redundancy Not Supported**:
   - Not all regions support zone redundancy
   - If you encounter "Zone Redundant Accounts are not supported in X Location", remove the `isZoneRedundant=true` flag
   - The updated command above uses a simpler configuration that works in all regions

3. **Service Principal Creation Failures**:
   - If you encounter issues creating the service principal, you may need additional permissions
   - Try using an existing service principal or contact your Azure administrator

4. **Role Assignment Failures**:
   - Role assignments may take a few minutes to propagate
   - If you encounter permission issues, wait a few minutes and try again

5. **Region Capacity Issues**:
   - Some regions like East US and West US 2 may experience high demand and capacity constraints
   - If you encounter a "ServiceUnavailable" error mentioning "high demand in [region]", try one of these alternative regions with typically lower utilization:
     - Brazil South
     - Canada East
     - Australia Central
     - South Africa North
     - UAE North
   - To change the region, update the `LOCATION` environment variable:
     ```bash
     export LOCATION="brazilsouth"  # Alternative region with typically lower utilization
     ```
   - You can list all available Azure regions for your subscription with:
     ```bash
     az account list-locations --query "[].{DisplayName:displayName, Name:name}" -o table
     ```
   - You can also request increased quota for specific regions by following the link in the error message (https://aka.ms/cosmosdbquota)
   - Note that using a distant region may increase latency for your application

6. **JSON Escaping Issues with Azure CLI**:
   - If you see errors like "'Permissions'" when using JSON in the `--body` parameter
   - This is typically caused by shell interpretation of quotes and variable expansion in JSON strings
   - The solution is to write the JSON to a file first and then reference it with `@filename`
   - The commands in this README use this approach to avoid escaping issues
   - If you're still having problems, try using double quotes for JSON and escape internal quotes:
     ```bash
     az cosmosdb sql role definition create \
       --account-name $COSMOS_ACCOUNT_NAME \
       --resource-group $RESOURCE_GROUP \
       --body "{\"roleName\": \"$WRITE_ROLE_NAME\", ...}"
     ```

7. **Role Definition Format Issues**:
   - If you encounter "'Permissions'" errors even when using a file-based approach
   - The issue may be with the JSON structure itself - Azure CLI expects specific capitalization
   - Use `RoleName`, `Type`, `AssignableScopes`, `Permissions`, and `DataActions` (with capital letters)
   - Alternatively, you can use built-in roles instead of creating custom ones:
     ```bash
     # List available built-in roles
     az cosmosdb sql role definition list --account-name $COSMOS_ACCOUNT_NAME --resource-group $RESOURCE_GROUP
     
     # Use built-in Data Contributor role (has ID 00000000-0000-0000-0000-000000000002)
     az cosmosdb sql role assignment create \
       --account-name $COSMOS_ACCOUNT_NAME \
       --resource-group $RESOURCE_GROUP \
       --role-definition-id 00000000-0000-0000-0000-000000000002 \
       --principal-id $ADMIN_OBJECT_ID \
       --scope "/dbs/$DATABASE_NAME/colls/$CONTAINER_NAME"
     ```

8. **Service Principal and Role Assignment Issues**:
   - If you encounter errors with service principal creation or identification:
     - The Azure CLI commands for service principals have changed over time and may behave differently across versions
     - Use the Azure CLI's built-in query capabilities instead of text processing tools like `grep` or `jq`
     - Try using `--display-name` instead of `--filter` when querying service principals
     - If you get empty results, the service principal might not be fully propagated yet - wait a minute and try again
   - If all automated approaches fail, use this completely manual approach:
     ```bash
     # 1. Create the service principal in the Azure Portal
     # 2. Navigate to Azure Active Directory > App registrations > All applications
     # 3. Find your service principal by name and note its Object ID
     # 4. Set the Object ID manually
     export SP_OBJECT_ID="00000000-0000-0000-0000-000000000000"  # Replace with your SP's Object ID
     
     # 5. Assign the role manually
     az cosmosdb sql role assignment create \
       --account-name $COSMOS_ACCOUNT_NAME \
       --resource-group $RESOURCE_GROUP \
       --role-definition-id $WRITE_ROLE_ID \
       --principal-id $SP_OBJECT_ID \
       --scope "/dbs/$DATABASE_NAME/colls/$CONTAINER_NAME"
     ```
   - For production environments, consider using managed identities instead of service principals:
     ```bash
     # Assign role to a managed identity (e.g., for an Azure Function)
     export MANAGED_IDENTITY_ID=$(az identity show --name myManagedIdentity --resource-group myResourceGroup --query principalId -o tsv)
     
     az cosmosdb sql role assignment create \
       --account-name $COSMOS_ACCOUNT_NAME \
       --resource-group $RESOURCE_GROUP \
       --role-definition-id $WRITE_ROLE_ID \
       --principal-id $MANAGED_IDENTITY_ID \
       --scope "/dbs/$DATABASE_NAME/colls/$CONTAINER_NAME"
     ```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 