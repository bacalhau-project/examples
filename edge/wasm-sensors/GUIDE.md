# WASM Sensors Demo Guide

This guide provides step-by-step instructions for setting up and running the WASM Sensors for Bacalhau Edge Deployment demo.

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

> **Important**: The optimization script and its default values were tested on a powerful server with **32 CPU cores** and **251GB RAM**. If your system has different specifications, you should adjust the values in the script accordingly.

The script performs the following optimizations:

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
   cp .env.template .env
   ```

   Edit `.env` and add your AWS credentials and SQS queue URL.

## Running the Demo

### Complete Demo Scenario

This scenario demonstrates the message flow and deployment behavior across different regions:

1. Start the network:

   ```bash
   # Make sure the network is stopped before starting
   docker compose down
   
   # Option 1: Start with all 300 replicas per region at once
   # This is faster to execute but may put significant load on your system
   docker compose up -d --scale edge-us=300 --scale edge-eu=300 --scale edge-as=300
   
   # Monitor node joining in a separate terminal window with either approach
   watch -n 5 "bacalhau node list --labels type=edge --show labels --wide --hide-header --no-style | grep -o 'region=[a-z]*' | sort | uniq -c"
   
   # Option 2: Start small and scale gradually (potentially more stable)
   # Scale up gradually in batches of 100 per region
   docker compose up -d --scale edge-us=100 --scale edge-eu=100 --scale edge-as=100
   
   # Wait for nodes to join and stabilize, then add more
   docker compose up -d --scale edge-us=200 --scale edge-eu=200 --scale edge-as=200
   
   # Final scaling to reach target of 300 per region
   docker compose up -d --scale edge-us=300 --scale edge-eu=300 --scale edge-as=300
   ```

   This command starts all services, including:
   - Core services (orchestrator, web-services, sqs-proxies)
   - Edge nodes for all regions
   
   Docker Compose dependencies ensure that edge nodes start only after the orchestrator is running.

2. Deploy to US region with red color and rocket emoji:

   ```bash
   bacalhau job run -V count=300 --id-only --wait=false jobs/deploy-us-v1.yaml
   ```

3. Deploy to EU region with blue color and satellite emoji:

   ```bash
   bacalhau job run -V count=300 --id-only --wait=false jobs/deploy-eu-v1.yaml
   ```

4. Deploy to AS region with green color and light bulb emoji:

   ```bash
   bacalhau job run -V count=300 --id-only --wait=false jobs/deploy-as-v1.yaml
   ```

5. Update US deployment with new configuration (purple color and lightning emoji):

   ```bash
   bacalhau job run -V count=300 --id-only --wait=false jobs/deploy-us-v2.yaml
   ```

6. Disconnect (stop) the EU region:

   ```bash
   # Stop all edge-eu containers without removing them
   docker compose pause edge-eu
   ```

7. Deploy new configuration to EU (yellow color and battery emoji):

   ```bash
   bacalhau job run -V count=300 --id-only --wait=false jobs/deploy-eu-v2.yaml
   ```

8. Reconnect (restart) the EU region:

   ```bash
   # Restart all stopped edge-eu containers
   docker compose unpause edge-eu
   ```


## 📊 Health Checks and Testing

Verify the SQS Proxies are running properly:

```bash
# Check proxy health
curl http://localhost:9091/health

# Send a test message
curl -X POST http://localhost:9091/send \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2025-03-26T12:00:00Z","data":{"test":"Hello from test!"}}'
```

The health check should return: `{ "status": "healthy" }`

## Additional Commands and Tips

### Managing the Network

```bash
# Start the network with a specific scale
docker compose up -d --scale edge-us=100 --scale edge-eu=100 --scale edge-as=100

# View running services
docker compose ps

# View logs from a specific service
docker compose logs sqs-puller

# Follow logs in real-time from all services
docker compose logs -f

# Stop the entire network
docker compose down
```

### Managing Regions

```bash
# Stop a specific region
docker compose pause edge-eu

# Restart a stopped region
docker compose unpause edge-eu

# Scale a region up or down
docker compose up -d --scale edge-us=150
```


## Troubleshooting

### Docker Network Issues

When running large numbers of containers, you may occasionally encounter network-related issues, especially when trying to stop the deployment:

#### Problem: Unable to remove networks

If you see errors like `Error response from daemon: network XXX has active endpoints` when running `docker compose down`, even though no containers appear to be running:

```bash
# First, try to force cleanup all containers (including those not in docker compose)
docker rm -f $(docker ps -aq)

# If that doesn't work, restart the Docker service
sudo systemctl restart docker

# Then try docker compose down again
docker compose down
```

#### Problem: Network connectivity between containers

If containers can't connect to each other, especially when using host.docker.internal:

```bash
# Check if host.docker.internal is properly resolved
docker run --rm alpine ping -c 1 host.docker.internal

# If not, ensure your Docker version supports this feature or add it manually 
# to /etc/hosts inside the container
```

#### Problem: Too many open files or connection issues

When deploying a large number of nodes, you might hit system limits:

```bash
# Check current open file limits
cat /proc/sys/fs/file-nr

# Check network connection tracking usage
cat /proc/sys/net/netfilter/nf_conntrack_count
cat /proc/sys/net/netfilter/nf_conntrack_max

# If values are near maximum, run the optimizer script again with adjusted values
sudo bash optimize-for-containers.sh

# Consider rebooting after optimization
sudo reboot
```

If you're using the Docker Compose network, make sure your system has enough resources to handle the load when using multiple replicas. Each replica will have its own resource limits as defined in the job YAML files.