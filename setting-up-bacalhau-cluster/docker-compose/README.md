# Bacalhau Docker Compose Configurations

This directory contains Docker Compose configurations for setting up Bacalhau clusters in both single-region and multi-region deployments.

## Directory Structure

```
docker-compose/
├── multi-region/
│ ├── config/
│ │ ├── compute-eu.yaml
│ │ ├── compute-us.yaml
│ │ └── orchestrator.yaml
│ └── docker-compose.yml
└── single-region/
├── config/
│ ├── compute.yaml
│ └── orchestrator.yaml
└── docker-compose.yml
```

## Single Region Setup

The single-region configuration provides a simple Bacalhau cluster with:

- 1 orchestrator node
- 10 compute nodes
- Storage object storage
- A client container for interacting with the cluster

### Usage

```bash
cd single-region
docker compose up -d
```

### Components

- **Orchestrator**: Manages job scheduling and cluster coordination
- **Compute Nodes**: Execute jobs (10 replicas)
- **Storage**: S3-compatible object storage for job results (MinIO)
- **Client**: Interactive container for submitting jobs

### Ports

- Orchestrator: 8438 (API), 1234 (API), 4222 (NATS)
- Storage: 9000 (API), 9001 (Console)

## Multi-Region Setup

The multi-region configuration simulates a geographically distributed cluster with:

- 1 global orchestrator
- 3 compute nodes in US region
- 3 compute nodes in EU region
- 3 Storage instances (global, US region, EU region)
- A client container for interacting with the cluster

### Usage

```bash
cd multi-region
docker compose up -d
```

### Components

- **Orchestrator**: Global orchestrator for all regions
- **Compute Nodes**:
  - US Region: 3 nodes (compute-us-1, compute-us-2, compute-us-3)
  - EU Region: 3 nodes (compute-eu-1, compute-eu-2, compute-eu-3)
- **Storage Instances**:
  - Global: Used by orchestrator for job results (Port 9000/9001)
  - US Region: Used by US compute nodes (Port 9002/9003)
  - EU Region: Used by EU compute nodes (Port 9004/9005)
- **Client**: Interactive container for submitting jobs

### Networks

- `bacalhau-network`: Global network for orchestrator communication
- `us-region`: Network for US region components
- `eu-region`: Network for EU region components

### Ports

- Orchestrator: 8438 (API), 1234 (API), 4222 (NATS)
- Storage Global: 9000 (API), 9001 (Console)
- Storage US: 9002 (API), 9003 (Console)
- Storage EU: 9004 (API), 9005 (Console)

## Common Configuration

Both setups share these environment variables:

- `MINIO_ROOT_USER`: minioadmin
- `MINIO_ROOT_PASSWORD`: minioadmin
- `AWS_ACCESS_KEY_ID`: minioadmin
- `AWS_SECRET_ACCESS_KEY`: minioadmin

## Interacting with the Cluster

To interact with either cluster:

1. Connect to the client container:

```bash
docker compose exec client sh
```

2. Submit jobs using the Bacalhau CLI:

```bash
bacalhau job list
bacalhau job run ...
```

## Cleanup

To stop and remove the cluster, including all volumes and orphaned containers:

```bash
docker compose down -v --remove-orphans
```

This will:

- Stop all containers
- Remove all containers
- Remove all volumes 
- Remove any orphaned containers
- Remove all networks
