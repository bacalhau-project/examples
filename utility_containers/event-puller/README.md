# Event Puller

A high-performance SQS queue monitor and visualization tool with Cosmos DB integration.

## 🚀 Features

- Real-time processing of AWS SQS queue messages
- Optimized multi-worker processing for high throughput
- Terminal UI for server-side monitoring
- Web dashboard with real-time updates via WebSockets
- Azure Cosmos DB integration for persistent storage
- Support for both standard and FIFO SQS queues
- Batch operations for efficient message handling
- Docker container support for easy deployment

## 🛠️ Installation

### Prerequisites

- Go 1.20 or higher
- AWS Account with SQS queue
- Azure Cosmos DB account (optional)
- Docker (optional, for containerized deployment)

### Building from Source

Clone the repository and build the application:

```bash
# Clone the repository
git clone https://github.com/bacalhau-project/bacalhau-examples.git
cd bacalhau-examples/utility_containers/event-puller

# Build the binary
go build -o bin/event-puller

# Run the application
./bin/event-puller
```

### Using Docker

```bash
# Pull the latest image
docker pull bacalhau-project/event-puller:latest

# Run with your environment variables
docker run -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_REGION=your_region \
  -e SQS_QUEUE_URL=your_queue_url \
  -v $(pwd)/.env:/app/.env \ # Mount .env file with configuration
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

# Build for production
npm run build
```

To configure certain aspects of the dashboard see `constants.ts`.

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

Format code
```sh
npm run format
```

Lint code
```sh
npm run lint
```

## 🧪 Testing with Sample Messages

```bash
# Send a test message
aws sqs send-message \
  --queue-url "https://sqs.us-east-1.amazonaws.com/123456789012/your-queue" \
  --message-body '{
    "vm_name": "test-vm",
    "container_id": "container-123",
    "icon_name": "🚀",
    "color": "#FF5733",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")'"
  }'
```

## 📚 Development Notes

- **Message Processing:** The application uses multiple workers to poll the SQS queue concurrently for maximum throughput.
- **Websocket Updates:** Messages are batched for efficient WebSocket updates to the dashboard.
- **Cosmos DB Integration:** Events are written to Cosmos DB in batches for efficiency.
- **FIFO Queues:** The application handles FIFO queues differently, respecting message order.

## 📝 License

See the [LICENSE](LICENSE) file for details.