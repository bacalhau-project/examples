# Event Puller

A high-performance SQS queue monitor and Cosmos DB event processor.

## Features

- Monitor AWS SQS queues in real-time
- Process and display events via a web UI
- Push events to Azure Cosmos DB NoSQL API for high-volume storage
- Support for multiple regions and partitioning

## Getting Started

### Prerequisites

- Go 1.23 or higher
- AWS Account with SQS queue
- Azure Account with Cosmos DB NoSQL (optional)
- Node.js and npm (optional, for dashboard development)

### Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure your environment variables
3. Build and run the application:

```bash
# Build
go build -o bin/event-puller

# Run
./bin/event-puller
```

Once running, you'll see:
- A Terminal UI showing queue status and messages
- A web interface at http://localhost:8080 for monitoring
- Background processing to Cosmos DB (if configured)

### Dashboard Development

The Next.js dashboard provides a modern web UI for monitoring events:

```bash
# Go to dashboard directory
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

When running in development mode, configure the dashboard to connect to your Event Puller instance by adding the `host` query parameter to the URL:

```
http://localhost:3000/?host=localhost&port=8080
```

For production deployment, the dashboard is automatically built and included with the application when using the build script.

## Configuration

### Environment Variables

The application is configured through environment variables in your `.env` file:

**Required SQS Variables:**
- `SQS_QUEUE_URL`: URL of the SQS queue to monitor
- `AWS_REGION`: AWS region of the SQS queue
- `AWS_ACCESS_KEY_ID`: AWS access key with SQS permissions
- `AWS_SECRET_ACCESS_KEY`: AWS secret key

**Optional Cosmos DB Variables:**
- `COSMOS_ENDPOINT`: Cosmos DB endpoint URL
- `COSMOS_KEY`: Cosmos DB access key
- `COSMOS_DATABASE`: Database name
- `COSMOS_CONTAINER`: Container name
- `COSMOS_BATCH_SIZE`: Batch size (default: 100)
- `AZURE_REGION`: Azure region for partitioning

## Setting Up Azure Cosmos DB

### Finding Existing Cosmos DB Settings

If you already have a Cosmos DB account:

```bash
# Login to Azure
az login

# List resource groups and find yours
az group list --output table
RESOURCE_GROUP="your-resource-group-name"

# List Cosmos DB accounts in your resource group
az cosmosdb list --resource-group $RESOURCE_GROUP --output table
COSMOS_ACCOUNT_NAME="your-cosmos-account-name"

# List databases
az cosmosdb sql database list \
    --account-name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --output table
DATABASE_NAME="your-database-name"

# List containers
az cosmosdb sql container list \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name $DATABASE_NAME \
    --resource-group $RESOURCE_GROUP \
    --output table
CONTAINER_NAME="your-container-name"

# Get connection information
COSMOS_ENDPOINT=$(az cosmosdb show \
    --name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query documentEndpoint \
    --output tsv)
echo "Cosmos DB Endpoint: $COSMOS_ENDPOINT"

COSMOS_KEY=$(az cosmosdb keys list \
    --name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query primaryMasterKey \
    --output tsv)
echo "Cosmos DB Key retrieved"

# Save to .env file
cat << EOF >> .env
COSMOS_ENDPOINT=$COSMOS_ENDPOINT
COSMOS_KEY=$COSMOS_KEY
COSMOS_DATABASE=$DATABASE_NAME
COSMOS_CONTAINER=$CONTAINER_NAME
AZURE_REGION=$(az account show --query location -o tsv)
EOF
```

### Creating a New Cosmos DB Account

If you need to create a new account:

```bash
# Login and set variables
az login
RESOURCE_GROUP="your-resource-group"
COSMOS_ACCOUNT_NAME="your-cosmos-account-name"
LOCATION="eastus"
DATABASE_NAME="event-database"
CONTAINER_NAME="events"
PARTITION_KEY="/region"

# Create resource group if needed
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Cosmos DB account
az cosmosdb create \
    --name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --kind GlobalDocumentDB \
    --default-consistency-level Session \
    --locations regionName=$LOCATION

# Create database and container
az cosmosdb sql database create \
    --account-name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --name $DATABASE_NAME

az cosmosdb sql container create \
    --account-name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --database-name $DATABASE_NAME \
    --name $CONTAINER_NAME \
    --partition-key-path $PARTITION_KEY \
    --throughput 400

# Get connection information and save to .env
COSMOS_ENDPOINT=$(az cosmosdb show \
    --name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query documentEndpoint \
    --output tsv)

COSMOS_KEY=$(az cosmosdb keys list \
    --name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query primaryMasterKey \
    --output tsv)

cat << EOF >> .env
COSMOS_ENDPOINT=$COSMOS_ENDPOINT
COSMOS_KEY=$COSMOS_KEY
COSMOS_DATABASE=$DATABASE_NAME
COSMOS_CONTAINER=$CONTAINER_NAME
AZURE_REGION=$LOCATION
EOF
```

## Testing with Sample Messages

Send test messages to your SQS queue:

```bash
# Set AWS variables
AWS_PROFILE="default"
AWS_REGION="us-east-1"
QUEUE_URL="your-sqs-queue-url"

# Send multiple test messages
for i in {1..10}; do
  cat > test_message.json << EOF
  {
    "vm_name": "vm-$i",
    "container_id": "container-$i",
    "icon_name": "$(echo -e "\U1F680")",
    "color": "#$(openssl rand -hex 3)",
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"
  }
EOF

  aws sqs send-message \
      --queue-url $QUEUE_URL \
      --message-body "$(cat test_message.json)" \
      --region $AWS_REGION \
      --profile $AWS_PROFILE
  
  echo "Sent message $i"
  sleep 0.2
done
```

## Monitoring and Querying Cosmos DB

### Querying Data

```bash
# Set variables
COSMOS_ACCOUNT_NAME="your-cosmos-account-name"
RESOURCE_GROUP="your-resource-group"
DATABASE_NAME="your-database"
CONTAINER_NAME="your-container"

# Count documents
az cosmosdb sql query \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name $DATABASE_NAME \
    --container-name $CONTAINER_NAME \
    --resource-group $RESOURCE_GROUP \
    --query-text "SELECT COUNT(1) AS total FROM c" \
    --output table

# Get recent events by region
az cosmosdb sql query \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name $DATABASE_NAME \
    --container-name $CONTAINER_NAME \
    --resource-group $RESOURCE_GROUP \
    --query-text "SELECT c.id, c.vm_name, c.container_id, c.region, c.timestamp FROM c WHERE c.region = 'eastus' ORDER BY c.event_time DESC OFFSET 0 LIMIT 10" \
    --output table
```

## Troubleshooting

### Common SQS Issues

- **Permission Denied**: Ensure AWS credentials have `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:DeleteMessageBatch`, and `sqs:GetQueueAttributes` permissions
- **Queue Not Found**: Verify your SQS_QUEUE_URL is correct
- **Rate Limiting**: Reduce NUM_WORKERS or implement backoff

### Common Cosmos DB Issues

- **Authentication Errors**: Check COSMOS_KEY and COSMOS_ENDPOINT format
- **Container Not Found**: Verify database and container names
- **Rate Limiting**: Consider increasing throughput (RU/s)

### Viewing Logs

```bash
# View error logs
cat logs/error.log

# Real-time log viewing
tail -f logs/error.log
```

## License

See the LICENSE file for details.