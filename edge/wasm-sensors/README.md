# WASM Sensors for Bacalhau Edge Deployment

This project demonstrates how to use Bacalhau to deploy and manage WebAssembly-based sensors on edge devices. It showcases a complete pipeline from data generation on edge nodes to message processing in a central service.

## 📋 Overview

The WASM Sensors project demonstrates:

1. **Edge-to-Cloud Communication** - WebAssembly applications running on edge nodes communicate with centralized services
2. **Configuration Management** - Methods to update and manage configuration of running applications
3. **Message Queue Integration** - Use of SQS for reliable message passing between components
4. **Hybrid Deployment Model** - Mix of WebAssembly modules for edge and Docker containers for central services

## 🏗️ Bacalhau Network Layout

The Docker Compose network setup establishes a comprehensive Bacalhau environment with the following components:

### Orchestrator
- Central coordinator for the Bacalhau network
- Manages job scheduling and distribution
- Exposes NATS port (4222) for communication with compute nodes
- Exposes WebUI port (8438) for monitoring and management

### Edge Compute Nodes
The setup includes multiple edge compute nodes organized by geographical regions:
- **edge-us**: Edge nodes simulating US region deployment
- **edge-eu**: Edge nodes simulating European region deployment
- **edge-as**: Edge nodes simulating Asian region deployment

Each edge compute node:
- Is labeled with its region and type (e.g., `region=us,type=edge`)
- Has access to WASM modules from the host system
- Connects to the orchestrator for job coordination

### Web Services Compute Node
- Dedicated node for running centralized web services
- Labeled as `type=web-services`
- Runs in privileged mode to support Docker-in-Docker
- Hosts the SQS Proxy and SQS Puller when deployed as Bacalhau service jobs

### Supporting Services
- **SQS Proxy**: Direct service running on port 9090
- **SQS Puller**: Direct service processing messages from SQS

### Client Node
- Interactive shell for interacting with the Bacalhau network
- Configured to connect to the orchestrator
- Useful for submitting jobs and monitoring status

### Network Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                      bacalhau-edge Network                      │
│                                                                 │
│  ┌─────────────┐        ┌──────────────┐     ┌──────────────┐   │
│  │             │        │              │     │              │   │
│  │ Orchestrator│◄───────┤ Edge Compute ├────►│ Web Services │   │
│  │   (4222)    │        │    Nodes     │     │    Node      │   │
│  │             │        │              │     │              │   │
│  └─────────────┘        └──────────────┘     └──────────────┘   │
│        ▲                                            ▲           │
│        │                                            │           │
│        │                                            │           │
│  ┌─────┴─────┐                               ┌──────┴───────┐   │
│  │           │                               │              │   │
│  │  Client   │                               │  SQS Proxy   │   │
│  │           │                               │   (9090)     │   │
│  └───────────┘                               └──────────────┘   │
│                                                     ▲           │
│                                                     │           │
│                                                     ▼           │
│                                              ┌──────────────┐   │
│                                              │              │   │
│                                              │  SQS Puller  │   │
│                                              │              │   │
│                                              └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 🧩 Components

### SQS Publisher (WASM)

The SQS Publisher is a WebAssembly module that generates simulated sensor data and sends it to the SQS Proxy. It can be configured with parameters:

- **Interval**: Time between messages (in seconds)
- **Color**: Hex color code for visual identification
- **RandomOff**: Whether to use deterministic or random icons

It reads its configuration from a YAML file that can be updated while the job is running.

### Message Schema

The SQS Publisher sends messages with the following JSON schema:

```json
{
  "job_id": "bacalhau-job-id",        // The Bacalhau job ID of the publisher
  "execution_id": "execution-id",      // The Bacalhau execution ID 
  "icon_name": "🚀",                   // An emoji representing the message
  "timestamp": "2025-03-26T12:34:56Z", // ISO 8601 timestamp in UTC
  "color": "#FF5733",                  // Hex color code from configuration
  "sequence": 42                       // Sequential message counter
}
```

### Message Fields:

- **job_id**: The Bacalhau job ID that identifies the publisher job
- **execution_id**: The Bacalhau execution ID for the specific execution instance
- **icon_name**: An emoji selected from a predefined list (random or fixed depending on the `randomOff` configuration)
- **timestamp**: ISO 8601 formatted timestamp in UTC
- **color**: Hex color code specified in the configuration
- **sequence**: Incrementing counter for each message sent by this publisher instance

These messages are sent to the SQS Proxy, which forwards them to Amazon SQS. The SQS Puller then retrieves and processes these messages from the queue.

### SQS Proxy

The SQS Proxy is a FastAPI application that:
- Receives HTTP POST requests from edge nodes
- Forwards valid JSON messages to Amazon SQS
- Provides a health check endpoint
- Can be deployed either as a Bacalhau service job or alongside the Docker Compose setup

**Important Note**: The SQS Proxy is available at two different ports:
- Port `8080` when deployed as a Bacalhau service job
- Port `9090` when deployed via Docker Compose

### SQS Puller

The SQS Puller retrieves messages from Amazon SQS and processes them. In this demo, it simply logs messages to stdout but could be extended to:
- Process data
- Trigger alerts
- Store data in a database

Like the SQS Proxy, it can be deployed either as a Bacalhau service job or alongside Docker Compose.

### Config Updater

The Config Updater is a WASM module that can update the SQS Publisher's configuration file. Due to limitations in Bacalhau v1.7.0, it cannot directly update a running job's configuration. To apply changes:

1. Use Config Updater to modify the configuration file
2. Stop the current SQS Publisher job
3. Deploy a new SQS Publisher job that will use the updated configuration

## 🚀 Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [TinyGo](https://tinygo.org/getting-started/) for building WebAssembly modules
- [Bacalhau CLI](https://docs.bacalhau.org/getting-started/installation)
- AWS account with SQS access

### Initial Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/bacalhau-project/wasm-sensors.git
   cd wasm-sensors
   ```

2. Create an SQS queue in your AWS account

3. Configure your environment:
   ```bash
   cp network/.env.template network/.env
   ```
   Edit `network/.env` and add your AWS credentials and SQS queue URL.

4. Start the Bacalhau network:
   ```bash
   cd network
   docker-compose up -d
   ```

### Deployment Options

#### Option 1: Deploy using Docker Compose Services

The provided Docker Compose file already includes the SQS Proxy and SQS Puller services, running on ports:
- SQS Proxy: `9090`
- SQS Puller: logs to Docker Compose logs

#### Option 2: Deploy using Bacalhau Service Jobs

Deploy the SQS Proxy as a Bacalhau service job:
```bash
bacalhau job run -V queue_url=wasm-sensors-demo jobs/sqs-proxy.yaml
```

Deploy the SQS Puller as a Bacalhau service job:
```bash
bacalhau job run -V queue_url=wasm-sensors-demo jobs/sqs-puller.yaml
```

### Deploy the SQS Publisher to Edge Nodes

Deploy the SQS Publisher WebAssembly module targeting the Docker Compose SQS Proxy:
```bash
bacalhau job run -V proxy=http://bacalhau-edge-sqs-proxy-1:9090 jobs/sqs-publisher.yaml
```

To target the Bacalhau service job SQS Proxy instead:
```bash
bacalhau job run -V proxy=http://bacalhau-edge-web-services-1:8080 jobs/sqs-publisher.yaml
```

### Update Configuration

To update the configuration (note: currently doesn't work with Bacalhau v1.7.0):
```bash
bacalhau job run -V color="#FEFEFE" jobs/config-updater.yaml
```

As noted earlier, you'll need to restart the SQS Publisher job for these changes to take effect.

## 🛠️ Development

### Development Notes

The Docker images for this project are already built and published to GitHub Container Registry. You can use them directly without building locally.

If you need to make changes to the code and rebuild the images, you can use the following commands:

#### Building WASM Modules

All WASM modules are built using TinyGo:

```bash
make build-wasm
```

#### Building Docker Images

```bash
make build-docker
```

#### Pushing Docker Images

```bash
# Set your GitHub container registry credentials
export GITHUB_USERNAME=your-username
export GITHUB_PAT=your-personal-access-token

# Login to the registry
make login

# Push the images
make push
```

## 📊 Testing

### Testing the SQS Proxy

You can test the SQS Proxy with a simple curl command:

```bash
curl -X POST http://localhost:9090/send \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-03-26T12:00:00Z","data":{"test":"Hello from curl!"}}'
```

### Health Check

To verify the SQS Proxy is running properly:

```bash
curl http://localhost:9090/health
```

This should return:
```json
{"status":"healthy"}
```

## 🔄 Message Flow

1. SQS Publisher generates a message with configuration-based parameters
2. Message is sent as JSON to the SQS Proxy via HTTP POST
3. SQS Proxy forwards the message to Amazon SQS
4. SQS Puller retrieves the message from Amazon SQS
5. SQS Puller processes the message (currently logs to stdout)

## ⚠️ Known Limitations

- **Configuration Updates**: Due to Bacalhau v1.7.0 limitations, you cannot dynamically update a running job's configuration. You need to stop and redeploy the job.
- **Direct File Access**: WASM modules have limited filesystem access through Bacalhau.

