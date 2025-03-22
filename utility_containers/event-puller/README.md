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

### Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your configuration
3. Build and run the application:

```bash
# Build
go build -o bin/event-puller

# Run
./bin/event-puller
```

### Configuration

This application is configured through environment variables, which can be set in a `.env` file:

#### Required Environment Variables

- `SQS_QUEUE_URL`: The URL of the SQS queue to monitor
- `AWS_REGION`: The AWS region of the SQS queue
- `AWS_ACCESS_KEY_ID`: AWS access key with permissions to read from SQS
- `AWS_SECRET_ACCESS_KEY`: AWS secret key

#### Optional Cosmos DB Environment Variables

- `COSMOS_ENDPOINT`: Your Cosmos DB endpoint URL
- `COSMOS_KEY`: Your Cosmos DB access key
- `COSMOS_DATABASE`: The database name in Cosmos DB
- `COSMOS_CONTAINER`: The container name in Cosmos DB
- `COSMOS_BATCH_SIZE`: Number of messages to batch before writing (default: 100)
- `AZURE_REGION`: Azure region for partitioning data

### Usage

Once running, the application provides:

1. A TUI (Terminal User Interface) showing queue status and recent messages
2. A web interface at http://localhost:8080 for monitoring events
3. Background processing to store events in Cosmos DB (if configured)

## Development

### Build

```bash
go build -o bin/event-puller
```

### Run

```bash
./bin/event-puller
```

## Architecture

This application consists of several components:

1. **SQS Listener**: Continuously polls the SQS queue for new messages
2. **Web Interface**: Displays real-time updates via WebSockets
3. **Terminal UI**: Provides command-line monitoring and queue management
4. **Cosmos DB Writer**: Efficiently writes events to Cosmos DB with batching

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See the LICENSE file for details.