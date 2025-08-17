# Docker Setup for BigQuery Uploader

This directory contains the Docker configuration for the BigQuery Uploader, a unified log processor that supports raw, schematized, sanitized, and aggregated processing modes for uploading logs to Google BigQuery.

## Prerequisites

- Docker 20.10+ installed
- Docker Compose 1.29+ (optional, for docker-compose usage)
- Google Cloud service account credentials JSON file
- A valid configuration YAML file

## Building the Docker Image

### Quick Build

```bash
./build.sh
```

### Build with Options

```bash
# Build with custom image name and tag
./build.sh --name my-uploader --tag v1.0.0

# Build without cache
./build.sh --no-cache

# Build for specific platform
./build.sh --platform linux/amd64

# Build and push to registry
./build.sh --registry docker.io/myusername --push
```

### Manual Docker Build

```bash
docker build -t bigquery-uploader:latest .
```

## Running the Container

### Basic Run Command

```bash
docker run \
  -e CONFIG_FILE=/app/config.yaml \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  -v $(pwd)/logs:/bacalhau_data:ro \
  bigquery-uploader:latest
```

### With All Environment Variables

```bash
docker run \
  -e CONFIG_FILE=/app/config.yaml \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -e PROJECT_ID=your-gcp-project-id \
  -e DATASET=log_analytics \
  -e NODE_ID=node-001 \
  -e REGION=us-central1 \
  -e LOG_FILE=/bacalhau_data/access.log \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  -v $(pwd)/logs:/bacalhau_data:ro \
  -v $(pwd)/last_batch_timestamp.json:/app/last_batch_timestamp.json \
  bigquery-uploader:latest
```

### Using Docker Compose

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to YAML configuration file inside container | `/app/config.yaml` |

### Optional Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON | `/app/credentials.json` |
| `CREDENTIALS_FILE` | Alternative to GOOGLE_APPLICATION_CREDENTIALS | `/app/credentials.json` |
| `CREDENTIALS_PATH` | Another alternative for credentials | `/app/credentials.json` |
| `PROJECT_ID` | Override GCP project ID from config | `my-gcp-project` |
| `DATASET` | Override BigQuery dataset from config | `log_analytics` |
| `NODE_ID` | Override node identifier from config | `node-001` |
| `REGION` | Override region metadata from config | `us-central1` |
| `LOG_FILE` | Override input log file path | `/bacalhau_data/access.log` |

## Volume Mounts

### Required Mounts

| Host Path | Container Path | Mode | Description |
|-----------|----------------|------|-------------|
| `./config.yaml` | `/app/config.yaml` | Read-only | Configuration file |
| `./logs` | `/bacalhau_data` | Read-only | Log files directory |

### Recommended Mounts

| Host Path | Container Path | Mode | Description |
|-----------|----------------|------|-------------|
| `./credentials.json` | `/app/credentials.json` | Read-only | GCP service account |
| `./last_batch_timestamp.json` | `/app/last_batch_timestamp.json` | Read-write | Timestamp tracking |

## Configuration File Format

The configuration file should follow this structure:

```yaml
project_id: "your-gcp-project-id"
dataset: "log_analytics"
node_id: "node-001"

input_paths:
  - "/bacalhau_data/access.log"
  - "/bacalhau_data/error.log"

pipeline:
  mode: "sanitized"  # Options: raw, schematized, sanitized, aggregated
  
processing:
  chunk_size: 10000
  max_retries: 20
  
metadata:
  region: "us-central1"
  environment: "production"
```

## Security Considerations

The Docker image implements several security best practices:

1. **Non-root user**: Runs as `appuser` (UID 1000) instead of root
2. **Read-only filesystem**: Can be run with read-only root filesystem
3. **No new privileges**: Prevents privilege escalation
4. **Minimal base image**: Uses Python slim image to reduce attack surface
5. **Health checks**: Built-in health check to verify service status

### Running with Enhanced Security

```bash
docker run \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  --tmpfs /tmp:noexec,nosuid,size=100m \
  -e CONFIG_FILE=/app/config.yaml \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  -v $(pwd)/logs:/bacalhau_data:ro \
  bigquery-uploader:latest
```

## Troubleshooting

### Container won't start

1. Check that all required files exist:
   ```bash
   ls -la config.yaml credentials.json logs/
   ```

2. Verify Docker image was built successfully:
   ```bash
   docker images bigquery-uploader
   ```

3. Check container logs:
   ```bash
   docker logs <container_id>
   ```

### Permission denied errors

Ensure the log files are readable by UID 1000:
```bash
chmod -R 644 logs/
```

### BigQuery authentication fails

1. Verify credentials file is valid JSON:
   ```bash
   cat credentials.json | jq .
   ```

2. Check that the service account has required permissions:
   - BigQuery Data Editor
   - BigQuery Job User

3. Ensure GOOGLE_APPLICATION_CREDENTIALS points to the correct path inside the container

### Out of memory errors

Increase Docker memory limits:
```bash
docker run --memory=4g --memory-swap=4g ...
```

Or adjust chunk_size in configuration:
```yaml
processing:
  chunk_size: 5000  # Reduce from default 10000
```

## Integration with Bacalhau

To use this container with Bacalhau, create a job specification:

```yaml
name: bigquery-log-processor
type: batch
count: 1
tasks:
  - name: process-logs
    engine:
      type: docker
      params:
        image: bigquery-uploader:latest
        entrypoint:
          - python
          - bigquery_uploader.py
        environmentVariables:
          - CONFIG_FILE=/app/config.yaml
          - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
    inputSources:
      - source:
          type: localDirectory
          params:
            sourcePath: /path/to/logs
        target: /bacalhau_data
      - source:
          type: localDirectory
          params:
            sourcePath: /path/to/config
        target: /app/config
    resources:
      cpu: 2000m
      memory: 4Gi
```

## Performance Tuning

### Memory Optimization

For large log files, tune these parameters in your config:

```yaml
processing:
  chunk_size: 5000      # Smaller chunks use less memory
  use_categorical: true # Enable categorical data types for repeated values
```

### Processing Speed

For faster processing with more memory available:

```yaml
processing:
  chunk_size: 50000     # Larger chunks process faster
  parallel_uploads: 4   # Enable parallel BigQuery uploads
```

## Monitoring

### Health Check

The container includes a health check that verifies all required Python packages are importable:

```bash
docker inspect --format='{{json .State.Health}}' <container_id> | jq
```

### Resource Usage

Monitor CPU and memory usage:

```bash
docker stats <container_id>
```

### Application Logs

The application logs to stdout/stderr. View with:

```bash
docker logs -f <container_id>
```

To save logs to a file:

```bash
docker logs <container_id> > uploader.log 2>&1
```
