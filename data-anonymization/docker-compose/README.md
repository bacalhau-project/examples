# Bacalhau Full Deployment Stack

This repository contains a Docker Compose configuration for deploying a complete Bacalhau network consisting of multiple services. The stack includes an orchestrator node, compute nodes, MinIO storage, and a private container registry.

## Stack Components

### 1. MinIO Storage Node (`bacalhau-minio-node`)
- Object storage service compatible with Amazon S3
- Provides storage capabilities for the Bacalhau network
- Runs on port 9000 with console access on port 9001
- Default credentials:
  - Username: `minioadmin`
  - Password: `minioadminpass`

### 2. Container Image Registry (`bacalhau-container-img-registry-node`)
- Private Docker registry for storing container images
- Runs on port 5000
- Uses TLS certificates for secure communication
- Stores images in a local filesystem

### 3. Orchestrator Node (`bacalhau-orchestrator-node`)
- Central coordinator for the Bacalhau network
- Manages job distribution and network coordination
- Runs on port 1234
- Uses custom configuration from `/bacalhau_demo_assets/nodes_configs/1_orchestrator_config.yaml`

### 4. Compute Nodes (`bacalhau-compute-node`)
- Worker nodes that execute Bacalhau jobs
- Deploys 3 replica nodes by default
- Requires privileged mode for container operations
- Connects to the orchestrator node
- Uses custom configuration from `/bacalhau_demo_assets/nodes_configs/2_compute_config.yaml`

### 5. Jumpbox Node (`bacalhau-jumpbox-node`)
- Utility node for interacting with the Bacalhau network
- Provides access to the Bacalhau CLI
- Connected to all other services in the network
- Used for submitting and managing jobs

## Network Configuration
- All services run on a dedicated bridge network (`bacalhau-network`)
- Services communicate using internal DNS names
- Authentication token is shared across services

## Prerequisites
- Docker Engine 20.10.0 or newer
- Docker Compose V2
- At least 8GB of RAM recommended
- Sufficient disk space for container images and data

## Running the Stack

1. Clone the repository, then:
cd [..](..)<repository-directory>

2. Start the stack:
docker compose -f docker-compose/full-bacalhau-deployment.yml up -d

3. Monitor the services:
docker compose -f docker-compose/full-bacalhau-deployment.yml ps

4. View logs:
# All services
docker compose -f docker-compose/full-bacalhau-deployment.yml logs

# Specific service
docker compose -f docker-compose/full-bacalhau-deployment.yml logs bacalhau-orchestrator-node

5. Stop the stack:
docker compose -f docker-compose/full-bacalhau-deployment.yml down

## Health Checks
All services include health checks to ensure proper operation:
- MinIO: Checks HTTP endpoint every 1s
- Registry: Checks TCP connection on port 5000
- Orchestrator & Compute Nodes: Check TCP connection on port 1234
- Services will automatically retry up to 30 times during startup

## Environment Variables
Key environment variables are defined in the common environment section:
- `NETWORK_AUTH_TOKEN`: Authentication token for the network
- `BACALHAU_API_PORT`: API port (default: 1234)
- `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`: MinIO credentials
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: S3 compatible credentials

