# Running Databricks Uploader with Docker

## Quick Start

### 1. Pull the Latest Image
```bash
docker pull ghcr.io/bacalhau-project/databricks-uploader:latest
```

### 2. Run the Uploader

#### Option A: Using the Helper Script (Recommended)
```bash
# Start in background
./docker-run-helper.sh start

# View logs
./docker-run-helper.sh logs

# Check status
./docker-run-helper.sh status

# Stop the uploader
./docker-run-helper.sh stop

# Clean up containers
./docker-run-helper.sh clean
```

#### Option B: Direct Docker Run
```bash
# Run in foreground (see output directly)
docker run --rm -it \
  -v $(pwd)/databricks-uploader-config.yaml:/app/config.yaml:ro \
  -v $(pwd)/credentials:/bacalhau_data/credentials:ro \
  -v $(pwd)/sample-sensor/data/sensor_data.db:/app/sensor_data.db \
  -v $(pwd)/state:/app/state \
  ghcr.io/bacalhau-project/databricks-uploader:latest \
  python sqlite_to_databricks_uploader.py \
    --config /app/config.yaml \
    --sqlite-path /app/sensor_data.db \
    --state-dir /app/state

# Or run in background (detached)
docker run \
  --name databricks-uploader \
  --restart unless-stopped \
  -v $(pwd)/databricks-uploader-config.yaml:/app/config.yaml:ro \
  -v $(pwd)/credentials:/bacalhau_data/credentials:ro \
  -v $(pwd)/sample-sensor/data/sensor_data.db:/app/sensor_data.db \
  -v $(pwd)/state:/app/state \
  ghcr.io/bacalhau-project/databricks-uploader:latest \
  python sqlite_to_databricks_uploader.py \
    --config /app/config.yaml \
    --sqlite-path /app/sensor_data.db \
    --state-dir /app/state
```

## Managing Pipeline Types

### Using the Helper Script
```bash
# Get current pipeline type
./docker-run-helper.sh pipeline get

# Set pipeline type
./docker-run-helper.sh pipeline set raw
./docker-run-helper.sh pipeline set schematized
./docker-run-helper.sh pipeline set filtered
./docker-run-helper.sh pipeline set emergency

# View history
./docker-run-helper.sh pipeline history
```

### Using Docker Directly
```bash
# Get current pipeline
docker run --rm \
  -v $(pwd)/sample-sensor/data/sensor_data.db:/data/sensor_data.db \
  ghcr.io/bacalhau-project/databricks-pipeline-manager:latest \
  python pipeline_controller.py --db /data/sensor_data.db get

# Set pipeline type
docker run --rm \
  -v $(pwd)/sample-sensor/data/sensor_data.db:/data/sensor_data.db \
  ghcr.io/bacalhau-project/databricks-pipeline-manager:latest \
  python pipeline_controller.py --db /data/sensor_data.db set filtered --by operator
```

## Required Files Structure

```
databricks-with-bacalhau/
├── databricks-uploader-config.yaml    # Main configuration
├── credentials/
│   └── expanso-s3-env.sh             # AWS credentials
├── databricks-uploader/
│   └── sensor_data.db                 # SQLite database
├── state/                             # Upload state tracking
│   └── *.json                         # State files per table
└── docker-run-helper.sh              # Helper script
```

## Configuration

### Volume Mounts Explained

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./databricks-uploader-config.yaml` | `/app/config.yaml` | Configuration file |
| `./credentials/` | `/bacalhau_data/credentials/` | AWS credentials directory |
| `./sample-sensor/data/sensor_data.db` | `/app/sensor_data.db` | SQLite database |
| `./state/` | `/app/state/` | Upload progress tracking |

### Environment Variables (Alternative to Config File)

If you prefer environment variables over the config file:

```bash
docker run --rm \
  -e DATABRICKS_HOST=your-host.databricks.com \
  -e DATABRICKS_TOKEN=your-token \
  -e DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse \
  -e DATABRICKS_CATALOG=expanso_databricks_workspace \
  -e DATABRICKS_DATABASE=sensor_readings \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -v $(pwd)/sample-sensor/data/sensor_data.db:/app/sensor_data.db \
  -v $(pwd)/state:/app/state \
  ghcr.io/bacalhau-project/databricks-uploader:latest
```

## Monitoring

### View Logs
```bash
# Using helper script
./docker-run-helper.sh logs

# Using docker directly
docker logs databricks-uploader-container -f
```

### Check Container Status
```bash
# Using helper script
./docker-run-helper.sh status

# Using docker directly
docker ps --filter name=databricks-uploader-container
```

## Troubleshooting

### Container Won't Start
1. Check configuration file exists: `ls -la databricks-uploader-config.yaml`
2. Verify credentials: `ls -la credentials/expanso-s3-env.sh`
3. Check Docker logs: `docker logs databricks-uploader`

### No Data Being Uploaded
1. Check pipeline type: `./docker-run-helper.sh pipeline get`
2. Verify database has data: `sqlite3 sample-sensor/data/sensor_data.db "SELECT COUNT(*) FROM sensor_data;"`
3. Check state files: `ls -la state/`
4. Review logs for errors: `./docker-run-helper.sh logs`

### Cleanup Stuck Containers
```bash
# Use the helper script
./docker-run-helper.sh clean

# Or manually
docker stop databricks-uploader-container
docker rm databricks-uploader-container
```

### Permission Issues
```bash
# Fix permissions on mounted volumes
chmod 644 databricks-uploader-config.yaml
chmod 600 credentials/expanso-s3-env.sh
chmod 644 sample-sensor/data/sensor_data.db
chmod 755 state/
```

## Building the Image Locally

If you need to build the image yourself:

```bash
# Build databricks-uploader
cd databricks-uploader
./build.sh --tag my-version --push

# Build pipeline-manager
cd ../pipeline-manager
./build.sh --tag my-version --push
```

## Production Deployment

For production, consider:

1. **Use specific image tags** instead of `latest`
2. **Set resource limits** in docker run:
   ```bash
   docker run -d \
     --memory="512m" \
     --cpus="0.5" \
     --name databricks-uploader-container \
     ghcr.io/bacalhau-project/databricks-uploader:v1.0.0
   ```
3. **Configure logging** to external system
4. **Use secrets management** for credentials
5. **Set up monitoring** and alerting
6. **Use orchestration** (Kubernetes, ECS, etc.)