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
- Is provisioned in batches or all at once depending on configuration

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

### Region-Specific SQS Proxies

The network implements region-specific SQS proxies to improve scalability:

- **sqs-proxy-us**: Serves US region nodes on port 9091
- **sqs-proxy-eu**: Serves EU region nodes on port 9092
- **sqs-proxy-as**: Serves AS region nodes on port 9093

Each proxy:
- Uses Gunicorn with 4 worker processes for better throughput
- Runs in host network mode for optimal performance
- Has dedicated system resources

### SQS Proxy

The SQS Proxy is a FastAPI application that:

- Receives HTTP POST requests from edge nodes
- Forwards valid JSON messages to Amazon SQS
- Provides a health check endpoint
- Can be deployed either as a Bacalhau service job or alongside the Docker Compose setup

### SQS Puller

The SQS Puller retrieves messages from Amazon SQS and processes them. In this demo, it simply logs messages to stdout but could be extended to:

- Process data
- Trigger alerts
- Store data in a database

## 🛠️ Development

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

## 🔄 Message Flow

1. SQS Publisher generates a message with configuration-based parameters
2. Message is sent as JSON to the region-specific SQS Proxy via HTTP POST
3. SQS Proxy forwards the message to Amazon SQS
4. SQS Puller retrieves the message from Amazon SQS
5. SQS Puller processes the message (currently logs to stdout)

## 🔢 Scaling Considerations

The system architecture supports large-scale deployments with several optimizations:

- **Flexible Provisioning Modes**: Choose between batch provisioning or all-at-once deployment
- **Host Network Mode**: Critical services use host network mode for optimal performance
- **Multiple Workers**: Each SQS Proxy uses Gunicorn with 4 worker processes
- **Region-Specific Proxies**: Traffic is distributed across region-specific proxies
- **Controlled Reconnection**: Nodes are reconnected with controlled delays to prevent flood
- **Resource Limits**: Edge nodes have specified CPU and memory limits
- **File Descriptor Limits**: All services have appropriate ulimit settings

## ⚠️ Known Limitations

- **Configuration Updates**: Configuration is set at job startup and cannot be changed during execution. To change configuration, you need to stop and redeploy the job.
- **Direct File Access**: WASM modules have limited filesystem access through Bacalhau.
- **Network Performance**: At extremely high node counts (>500), you may need additional host optimizations.
- **All-at-Once Mode**: When using all-at-once mode for very large deployments (1000+ nodes), ensure your host is properly optimized using the provided script.

For setup instructions and running the demo, please refer to the [GUIDE.md](GUIDE.md) file.