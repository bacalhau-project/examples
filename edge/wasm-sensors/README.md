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
│  │           │                               │  (8080/9090) │   │
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
- **Color**: Hex color code for visual identification or "-1" for random color
- **Emoji**: Index of emoji to use (-1 for random)

The configuration is set at startup and remains constant throughout the job's execution.

### Message Schema

The SQS Publisher sends messages with the following JSON schema:

```json
{
  "job_id": "bacalhau-job-id", // The Bacalhau job ID of the publisher
  "execution_id": "execution-id", // The Bacalhau execution ID
  "hostname": "edge-node-1", // The hostname of the edge node
  "job_submission_time": 1711449600, // Unix timestamp of when the Bacalhau job was submitted
  "icon_name": "😀", // An emoji from the supported list
  "timestamp": "2025-03-26T12:34:56Z", // ISO 8601 timestamp in UTC
  "color": "#FF5733", // Hex color code
  "sequence": 42, // Sequential message counter
  "region": "us" //  Region from environment
}
```

### Message Fields:

- **job_id**: The Bacalhau job ID that identifies the publisher job
- **execution_id**: The Bacalhau execution ID for the specific execution instance
- **hostname**: The hostname of the edge node sending the message
- **job_submission_time**: Unix timestamp of when the Bacalhau job was submitted
- **icon_name**: An emoji from a predefined list of supported emojis
- **timestamp**: ISO 8601 formatted timestamp in UTC
- **color**: Hex color code (can be specified or random)
- **sequence**: Incrementing counter for each message sent by this publisher instance
- **region**: AWS region read from the REGION environment variable

### Legacy Implementation

The `legacy` directory contains an initial implementation attempt to support updating configuration files at runtime using WebAssembly. This approach was ultimately not pursued due to limitations with the current wazero-based executor. Instead, we now use direct job configuration updates.

The legacy implementation included:

- `config-reader`: Attempted to read configuration files at runtime
- `config-updater`: Attempted to update configuration files at runtime
- `dir-lister`: Utility for listing directory contents
- `sqs-publisher`: Previous version of the message publisher

### SQS Proxy

The SQS Proxy is a FastAPI application that:

- Receives HTTP POST requests from edge nodes
- Forwards valid JSON messages to Amazon SQS
- Provides a health check endpoint
- Can be deployed either as a Bacalhau service job or alongside the Docker Compose setup

**Important Note**: The SQS Proxy URL varies depending on the deployment method:

- When deployed via Docker Compose: `http://bacalhau-edge-sqs-proxy-1:9090`
- When deployed as a Bacalhau service job: `http://bacalhau-edge-web-services-1:8080`

Make sure to use the appropriate URL when deploying the SQS Publisher jobs.

### SQS Puller

The SQS Puller retrieves messages from Amazon SQS and processes them. In this demo, it simply logs messages to stdout but could be extended to:

- Process data
- Trigger alerts
- Store data in a database

Like the SQS Proxy, it can be deployed either as a Bacalhau service job or alongside Docker Compose.

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

### Complete Demo Scenario

This scenario demonstrates the message flow and deployment behavior across different regions:

1. Start the network:

   ```bash
   export REPLICAS=3  # Set number of replicas per region
   ./demo.sh start_network
   ```

2. Deploy to US region with red color and rocket emoji:

   ```bash
   ./demo.sh deploy "us" "#FF0000" 0
   ```

   This will deploy the SQS Publisher to US edge nodes with red color and rocket emoji 🚀.

3. Deploy to EU region with blue color and satellite emoji:

   ```bash
   ./demo.sh deploy "eu" "#0000FF" 1
   ```

   This will deploy the SQS Publisher to EU edge nodes with blue color and satellite emoji 📡.

4. Deploy to AS region with green color and light bulb emoji:

   ```bash
   ./demo.sh deploy "as" "#00FF00" 2
   ```

   This will deploy the SQS Publisher to AS edge nodes with green color and light bulb emoji 💡.

5. Update US deployment with new configuration (purple color and lightning emoji):

   ```bash
   ./demo.sh deploy "us" "#800080" 3
   ```

   This will deploy a new version of the SQS Publisher to US nodes with purple color and lightning emoji ⚡.

6. Disconnect EU region:

   ```bash
   ./demo.sh disconnect_region "eu"
   ```

   This will stop the EU deployment.

7. Deploy new configuration to EU (yellow color and battery emoji):

   ```bash
   ./demo.sh deploy "eu" "#FFFF00" 4
   ```

   This will deploy a new version of the SQS Publisher to EU nodes with yellow color and battery emoji 🔋.

8. Reconnect EU region:

   ```bash
   ./demo.sh reconnect_region "eu"
   ```

   This will restart the EU deployment.

This demo shows how to deploy and update the SQS Publisher across different regions, with each region having its own unique visual identity through colors and emojis.

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
# With specific color and emoji
bacalhau job run -V proxy=http://bacalhau-edge-sqs-proxy-1:9090 -V color="#FF5733" -V emoji=0 jobs/sqs-publisher.yaml

# With random color and emoji
bacalhau job run -V proxy=http://bacalhau-edge-sqs-proxy-1:9090 -V color="-1" -V emoji=-1 jobs/sqs-publisher.yaml
```

To target the Bacalhau service job SQS Proxy instead:

```bash
bacalhau job run -V proxy=http://bacalhau-edge-web-services-1:8080 -V color="#FF5733" -V emoji=0 jobs/sqs-publisher.yaml
```

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
{ "status": "healthy" }
```

## 🔄 Message Flow

1. SQS Publisher generates a message with configuration-based parameters
2. Message is sent as JSON to the SQS Proxy via HTTP POST
3. SQS Proxy forwards the message to Amazon SQS
4. SQS Puller retrieves the message from Amazon SQS
5. SQS Puller processes the message (currently logs to stdout)

## ⚠️ Known Limitations

- **Configuration Updates**: Configuration is set at job startup and cannot be changed during execution. To change configuration, you need to stop and redeploy the job.
- **Direct File Access**: WASM modules have limited filesystem access through Bacalhau.

### Environment Variables

The demo script uses the following environment variables:

- `PROXY_URL`: URL of the SQS proxy service (default: `http://bacalhau-edge-sqs-proxy-1:9090`)
- `REPLICAS`: Number of edge nodes and job instances per region (default: `3`)

This single `REPLICAS` variable controls both:

- The number of edge nodes per region in the Docker Compose setup
- The number of job instances deployed per region

You can set these variables before running the demo script:

```bash
export PROXY_URL="http://custom-proxy:9090"
export REPLICAS=5
./demo.sh deploy_us
```

Or set them inline with the command:

```bash
PROXY_URL="http://custom-proxy:9090" REPLICAS=5 ./demo.sh deploy_us
```

Note: When using multiple replicas per region, make sure your system has enough resources to handle the increased load. Each replica will have its own resource limits as defined in the Docker Compose file.
