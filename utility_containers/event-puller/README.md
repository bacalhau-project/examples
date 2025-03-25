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
# Pull the latest image
docker pull bacalhau-project/event-puller:latest

# Run with your environment variables
docker run -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_REGION=your_region \
  -e SQS_QUEUE_URL=your_queue_url \
  bacalhau-project/event-puller:latest
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Required AWS Variables
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/your-queue

# SQS Configuration Options
POLL_INTERVAL=100ms             # Time between SQS polls (default: 100ms)
MAX_MESSAGES=10                 # Maximum messages per poll (default: 10, max: 10)
NUM_WORKERS=5                   # Number of concurrent SQS polling workers (default: 5)
WS_BATCH_SIZE=100               # WebSocket message batch size (default: 100)
BUFFER_SIZE=1000                # Message channel buffer size (default: 1000)
MAX_RETRY_ATTEMPTS=5            # Maximum retry attempts for SQS operations (default: 5)
INITIAL_RETRY_DELAY=100ms       # Initial retry delay for exponential backoff (default: 100ms)
MAX_RETRY_DELAY=5s              # Maximum retry delay (default: 5s)
SQS_VISIBILITY_TIMEOUT=30       # Visibility timeout for received messages (default: 30 seconds)
SQS_WAIT_TIME=0                 # SQS long polling wait time (default: 0, max: 20 seconds)

# Optional Cosmos DB Variables
COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
COSMOS_KEY=your_cosmos_key
COSMOS_DATABASE=your_database_name
COSMOS_CONTAINER=your_container_name
COSMOS_BATCH_SIZE=100
AZURE_REGION=eastus
```

### Building the Dashboard

The application includes a Next.js dashboard for visualization:

```bash
# Navigate to the dashboard directory
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## 🔍 Known Issues and Troubleshooting

### SQS Message Processing Issues

**Issue**: Messages aren't being pulled from the SQS queue correctly or processing is slow.

**Diagnosis**:
1. Check AWS credentials and permissions
2. Look for errors in the logs related to SQS connectivity
3. Examine POLL_INTERVAL and NUM_WORKERS configuration
4. Verify the queue URL is correctly formatted and accessible

**Solution**:
- Ensure AWS credentials have `sqs:ReceiveMessage`, `sqs:DeleteMessage`, and `sqs:GetQueueAttributes` permissions
- Increase `NUM_WORKERS` environment variable for higher throughput
- Adjust `POLL_INTERVAL` or `SQS_WAIT_TIME` for better polling behavior 
- Adjust `MAX_RETRY_ATTEMPTS`, `INITIAL_RETRY_DELAY`, and `MAX_RETRY_DELAY` for better error handling

### Cosmos DB Integration Issues

**Issue**: Events aren't being stored in Cosmos DB.

**Diagnosis**:
1. Check if Cosmos DB integration is enabled in logs
2. Verify database and container exist
3. Test connection with the Azure portal

**Solution**:
- Ensure all Cosmos DB environment variables are set
- Verify container has the right partition key (typically `/region`)
- Check `flushCosmosBatch` function for error handling
- Try adjusting batch size with `COSMOS_BATCH_SIZE` environment variable

### WebSocket Connectivity Issues

**Issue**: Dashboard not receiving real-time updates.

**Solution**:
- Check for browser console errors
- Ensure WebSocket server is running on the specified port
- Verify network firewall rules allow WebSocket connections
- Use the host query parameter to specify the correct server

## 📊 Dashboard Usage

Access the web dashboard at `http://localhost:8080` when the app is running.

For development, you can run the dashboard separately:

```bash
cd dashboard
npm run dev
```

When accessing the development server, use query parameters to connect to your Event Puller instance:

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