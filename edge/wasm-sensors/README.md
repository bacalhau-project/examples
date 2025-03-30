# WASM Sensors for Bacalhau Edge Deployment

This project demonstrates how to use Bacalhau to deploy and manage WebAssembly-based sensors on edge devices. It showcases a complete pipeline from data generation on edge nodes to message processing in a central service.

## 📋 Overview

The WASM Sensors project demonstrates:

1. **Edge-to-Cloud Communication** - WebAssembly applications running on edge nodes communicate with centralized services
2. **Configuration Management** - Methods to update and manage configuration of running applications
3. **Message Queue Integration** - Use of SQS for reliable message passing between components
4. **Hybrid Deployment Model** - Mix of WebAssembly modules for edge and Docker containers for central services
5. **Large-Scale Deployment** - Support for high-density node deployments across multiple regions

## 🏗️ Bacalhau Network Layout

The Docker Compose network setup establishes a comprehensive Bacalhau environment with the following components:

### Orchestrator

- Central coordinator for the Bacalhau network
- Manages job scheduling and distribution
- Uses host network mode for optimal performance
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
- Is provisioned in batches to prevent overwhelming the orchestrator

### Web Services Compute Node

- Dedicated node for running centralized web services
- Labeled as `type=web-services`
- Runs in privileged mode to support Docker-in-Docker
- Hosts the SQS Proxy and SQS Puller when deployed as Bacalhau service jobs

### Supporting Services

- **Region-Specific SQS Proxies**:
   - **sqs-proxy-us**: Direct service running on port 9091 (host network)
   - **sqs-proxy-eu**: Direct service running on port 9092 (host network)
   - **sqs-proxy-as**: Direct service running on port 9093 (host network)
   - Each proxy uses multiple workers for improved throughput
- **SQS Puller**: Direct service processing messages from SQS

### Client Node

- Interactive shell for interacting with the Bacalhau network
- Configured to connect to the orchestrator
- Useful for submitting jobs and monitoring status

### Network Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        bacalhau-edge Network                             │
│                                                                         │
│  ┌─────────────┐        ┌──────────────┐     ┌──────────────┐           │
│  │             │        │              │     │              │           │
│  │ Orchestrator│◄───────┤ Edge Compute ├────►│ Web Services │           │
│  │(Host network)│        │    Nodes     │     │    Node      │           │
│  │             │        │              │     │              │           │
│  └─────────────┘        └──────────────┘     └──────────────┘           │
│        ▲                                            ▲                   │
│        │                                            │                   │
│        │                                            │                   │
│  ┌─────┴─────┐       ┌───────────────┐      ┌──────┴───────┐           │
│  │           │       │               │      │              │           │
│  │  Client   │       │  SQS Pullers  │      │  SQS Proxies │           │
│  │           │       │(Host network) │      │(Host network)│           │
│  └───────────┘       └───────────────┘      └──────────────┘           │
│                                                    │                    │
│                                                    │                    │
│                                                    ▼                    │
│                                      ┌──────────────────────────┐       │
│                                      │                          │       │
│                                      │  Region-Specific Proxies │       │
│                                      │  US: 9091, EU: 9092, AS: 9093 │       │
│                                      │                          │       │
│                                      └──────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
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

### Region-Specific SQS Proxies

The network now implements region-specific SQS proxies to improve scalability:

- **sqs-proxy-us**: Serves US region nodes on port 9091
- **sqs-proxy-eu**: Serves EU region nodes on port 9092
- **sqs-proxy-as**: Serves AS region nodes on port 9093

Each proxy:
- Uses Gunicorn with 4 worker processes for better throughput
- Runs in host network mode for optimal performance
- Has dedicated system resources

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

**Important Note**: The SQS Proxy URL varies depending on the deployment method and region:

- When deployed via Docker Compose:
   - US region: `http://host.docker.internal:9091`
   - EU region: `http://host.docker.internal:9092`
   - AS region: `http://host.docker.internal:9093`
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

### Host System Optimization

For large-scale deployments, run the optimization script to configure your host system:

```bash
sudo bash optimize-for-containers.sh
```

This script performs the following optimizations:

- Increases file descriptor limits for containers
- Adjusts kernel parameters for high-density networking
- Optimizes connection tracking and memory settings
- Configures Docker daemon for improved concurrency
- Properly sizes ARP caches and TCP buffers

A reboot is recommended after running the script.

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

   The network will start in stages:
   - Core services (orchestrator, web-services, sqs-proxies) start first
   - Edge nodes are then provisioned in batches to prevent overwhelming the orchestrator
   - Each region is provisioned sequentially for controlled deployment

2. Deploy to US region with red color and rocket emoji:

   ```bash
   bacalhau job run -E "REPLICAS" --id-only --wait=false jobs/deploy-us-v1.yaml
   ```

   This will deploy the SQS Publisher to US edge nodes with red color and rocket emoji 🚀.

3. Deploy to EU region with blue color and satellite emoji:

   ```bash
   bacalhau job run -E "REPLICAS" --id-only --wait=false jobs/deploy-eu-v1.yaml
   ```

   This will deploy the SQS Publisher to EU edge nodes with blue color and satellite emoji 📡.

4. Deploy to AS region with green color and light bulb emoji:

   ```bash
   bacalhau job run -E "REPLICAS" --id-only --wait=false jobs/deploy-as-v1.yaml
   ```

   This will deploy the SQS Publisher to AS edge nodes with green color and light bulb emoji 💡.

5. Update US deployment with new configuration (purple color and lightning emoji):

   ```bash
   bacalhau job run -E "REPLICAS" --id-only --wait=false jobs/deploy-us-v2.yaml
   ```

   This will deploy a new version of the SQS Publisher to US nodes with purple color and lightning emoji ⚡.

6. Disconnect EU region:

   ```bash
   ./demo.sh disconnect_region "eu"
   ```

   This will stop the EU deployment while preserving container identity.

7. Deploy new configuration to EU (yellow color and battery emoji):

   ```bash
   bacalhau job run -E "REPLICAS" --id-only --wait=false jobs/deploy-eu-v2.yaml
   ```

   This will deploy a new version of the SQS Publisher to EU nodes with yellow color and battery emoji 🔋.

8. Reconnect EU region:

   ```bash
   ./demo.sh reconnect_region "eu"
   ```

   This will restart the EU deployment in controlled batches, maintaining node identity.

This demo shows how to deploy and update the SQS Publisher across different regions, with each region having its own unique visual identity through colors and emojis.

### Deployment Options

#### Option 1: Deploy using Docker Compose Services

The provided Docker Compose file already includes region-specific SQS Proxies and SQS Puller services, running on ports:

- SQS Proxy US: `9091`
- SQS Proxy EU: `9092`
- SQS Proxy AS: `9093`
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

Deploy the SQS Publisher WebAssembly module targeting the region-specific Docker Compose SQS Proxy:

```bash
# US region with specific color and emoji
bacalhau job run -V proxy=http://host.docker.internal:9091 -V color="#FF5733" -V emoji=0 jobs/sqs-publisher.yaml

# EU region with random color and emoji
bacalhau job run -V proxy=http://host.docker.internal:9092 -V color="-1" -V emoji=-1 jobs/sqs-publisher.yaml

# AS region with specific color and emoji
bacalhau job run -V proxy=http://host.docker.internal:9093 -V color="#33FF57" -V emoji=2 jobs/sqs-publisher.yaml
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

You can test the region-specific SQS Proxies with simple curl commands:

```bash
# US region proxy
curl -X POST http://localhost:9091/send \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-03-26T12:00:00Z","data":{"test":"Hello from US!"}}'

# EU region proxy
curl -X POST http://localhost:9092/send \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-03-26T12:00:00Z","data":{"test":"Hello from EU!"}}'

# AS region proxy
curl -X POST http://localhost:9093/send \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-03-26T12:00:00Z","data":{"test":"Hello from AS!"}}'
```

### Health Check

To verify the SQS Proxies are running properly:

```bash
# US region health check
curl http://localhost:9091/health

# EU region health check
curl http://localhost:9092/health

# AS region health check
curl http://localhost:9093/health
```

Each should return:

```json
{ "status": "healthy" }
```

## 🔄 Message Flow

1. SQS Publisher generates a message with configuration-based parameters
2. Message is sent as JSON to the region-specific SQS Proxy via HTTP POST
3. SQS Proxy forwards the message to Amazon SQS
4. SQS Puller retrieves the message from Amazon SQS
5. SQS Puller processes the message (currently logs to stdout)

## 🔢 Scaling Considerations

The updated system architecture supports large-scale deployments with several optimizations:

- **Batch Provisioning**: Nodes are provisioned in controlled batches (default 10 at a time)
- **Host Network Mode**: Critical services use host network mode for optimal performance
- **Multiple Workers**: Each SQS Proxy uses Gunicorn with 4 worker processes
- **Region-Specific Proxies**: Traffic is distributed across region-specific proxies
- **Controlled Reconnection**: Nodes are reconnected with controlled delays to prevent flood
- **Resource Limits**: Edge nodes have specified CPU and memory limits
- **File Descriptor Limits**: All services have appropriate ulimit settings

To further tune the scaling parameters:

```bash
# Set larger batch size for faster provisioning (with more capable hardware)
export BATCH_SIZE=25

# Customize region-specific node counts
export US_REPLICAS=30
export EU_REPLICAS=20
export AS_REPLICAS=15

# Control reconnection timing (milliseconds between batches)
export MS_BETWEEN_RECONNECT=500

# Start the network with all customizations
./demo.sh start_network
```

## ⚠️ Known Limitations

- **Configuration Updates**: Configuration is set at job startup and cannot be changed during execution. To change configuration, you need to stop and redeploy the job.
- **Direct File Access**: WASM modules have limited filesystem access through Bacalhau.
- **Network Performance**: At extremely high node counts (>500), you may need additional host optimizations.

### Environment Variables

When working with the job templates directly, you can use the following variables:

- `REPLICAS`: Number of job instances to deploy per region (default: `3`)
- `US_REPLICAS`, `EU_REPLICAS`, `AS_REPLICAS`: Region-specific override for replica count
- `BATCH_SIZE`: Number of nodes to provision in parallel (default: `10`)
- `MS_BETWEEN_RECONNECT`: Milliseconds to wait between node reconnections (default: `250`)

You can set these variables when running the job or starting the network:

```bash
# Deploy with 5 replicas
bacalhau job run -E "REPLICAS=5" jobs/deploy-us-v1.yaml

# Start network with custom configuration
REPLICAS=10 BATCH_SIZE=8 ./demo.sh start_network
```

If you're using the Docker Compose network, make sure your system has enough resources to handle the load when using multiple replicas. Each replica will have its own resource limits as defined in the job YAML files.