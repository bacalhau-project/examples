# Databricks Pipeline Deployment Guide

## Overview

This guide covers the deployment of the Databricks data pipeline with Bacalhau integration. The pipeline processes sensor data from SQLite databases, validates it, and routes it to appropriate S3 buckets and Databricks tables.

## Prerequisites

### System Requirements

- Python 3.11 or higher
- UV package manager (`pip install uv`)
- AWS CLI configured with appropriate credentials
- Databricks workspace with SQL endpoint
- Bacalhau node (optional, for distributed processing)

### Required Permissions

#### AWS Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:CreateBucket",
        "s3:PutBucketVersioning",
        "s3:PutBucketEncryption",
        "s3:PutLifecycleConfiguration"
      ],
      "Resource": [
        "arn:aws:s3:::*-databricks-*",
        "arn:aws:s3:::*-databricks-*/*"
      ]
    }
  ]
}
```

#### Databricks Permissions
- SQL endpoint access
- Table creation and write permissions
- Database access for target schemas

## Environment Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd databricks-with-bacalhau/databricks-uploader
```

### 2. Install Dependencies

All scripts use UV with inline dependencies, so no virtual environment setup is required:

```bash
# Install UV if not already installed
pip install uv

# Verify UV installation
uv --version
```

### 3. Configuration Files

#### Create S3 Buckets

```bash
cd ../scripts
./create-s3-buckets.sh \
  --prefix your-company \
  --region us-east-1 \
  --create-folders
```

This creates the following buckets:
- `{prefix}-databricks-raw-{region}`
- `{prefix}-databricks-schematized-{region}`
- `{prefix}-databricks-filtered-{region}`
- `{prefix}-databricks-emergency-{region}`
- `{prefix}-databricks-aggregated-{region}`

#### Main Configuration (databricks-uploader-config.yaml)

```yaml
# Databricks connection
databricks:
  host: ${DATABRICKS_HOST}
  http_path: ${DATABRICKS_HTTP_PATH}
  token: ${DATABRICKS_TOKEN}
  database: ${DATABRICKS_DATABASE:-default}

# SQLite source
sqlite:
  path: ${SQLITE_PATH:-sensor_data.db}
  table_name: ${SQLITE_TABLE_NAME:-sensor_data}
  timestamp_col: ${TIMESTAMP_COL:-timestamp}

# Processing settings
processing:
  state_dir: ${STATE_DIR:-state}
  upload_interval: ${UPLOAD_INTERVAL:-60}
  batch_size: ${BATCH_SIZE:-500}
  once: ${ONCE:-false}

# S3 settings
s3:
  bucket_prefix: ${S3_BUCKET_PREFIX}
  region: ${S3_REGION:-us-east-1}
  buckets:
    raw: ${S3_BUCKET_RAW}
    schematized: ${S3_BUCKET_SCHEMATIZED}
    filtered: ${S3_BUCKET_FILTERED}
    emergency: ${S3_BUCKET_EMERGENCY}
    aggregated: ${S3_BUCKET_AGGREGATED}
```

#### Validation Specification (sensor_validation_spec.yaml)

The validation rules are externalized in this file. Update as needed for your sensor types:

```yaml
version: "1.0"
name: "Wind Turbine Sensor Validation"

fields:
  temperature:
    type: float
    required: true
    min: 50.0
    max: 80.0
    unit: "°C"
    emergency_thresholds:
      low: 52.0
      high: 75.0
  # Add more fields as needed
```

#### Logging Configuration (logging_config.yaml)

```yaml
# Log levels per component
log_levels:
  default: INFO
  databricks_uploader: DEBUG
  validation: INFO
  s3_uploader: INFO
  retry_handler: WARNING

# Rotation settings
rotation:
  max_bytes: 10485760  # 10MB
  backup_count: 5
  
# Alert thresholds
alerts:
  error_rate_threshold: 0.05  # 5% error rate
  error_count_threshold: 100
  check_interval: 300  # 5 minutes
```

#### Retry Configuration (retry_config.yaml)

Configure retry behavior for different components:

```yaml
default:
  max_attempts: 3
  initial_wait: 1.0
  max_wait: 60.0
  exponential_base: 2.0
  jitter: true
  circuit_breaker_enabled: false

components:
  databricks:
    max_attempts: 5
    initial_wait: 2.0
    circuit_breaker_enabled: true
    failure_threshold: 3
    recovery_timeout: 300
```

### 4. Environment Variables

Create a `.env` file or export these variables:

```bash
# Databricks
export DATABRICKS_HOST='your-workspace.cloud.databricks.com'
export DATABRICKS_HTTP_PATH='/sql/1.0/endpoints/your-endpoint'
export DATABRICKS_TOKEN='your-access-token'
export DATABRICKS_DATABASE='sensor_data'

# AWS
export AWS_REGION='us-east-1'
export S3_BUCKET_PREFIX='your-company'

# Processing
export STATE_DIR='/var/lib/databricks-pipeline/state'
export UPLOAD_INTERVAL=300  # 5 minutes
export BATCH_SIZE=1000

# Logging
export LOG_DIR='/var/log/databricks-pipeline'
export LOG_LEVEL='INFO'
```

## Deployment Steps

### 1. Local Testing

Before deploying to production, test locally:

```bash
# Test database connection
./test_direct_insert.py

# Test validation
./test_pydantic_validation.py

# Test S3 routing
./test_s3_pipeline_routing.py

# Test pipeline manager
./test_pipeline_manager.py

# Run smoke tests
./sqlite_to_databricks_uploader.py --smoke-test
```

### 2. Production Deployment

#### Option A: Systemd Service (Recommended)

Create `/etc/systemd/system/databricks-pipeline.service`:

```ini
[Unit]
Description=Databricks Pipeline Service
After=network.target

[Service]
Type=simple
User=databricks
Group=databricks
WorkingDirectory=/opt/databricks-pipeline
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/etc/databricks-pipeline/env
ExecStart=/usr/local/bin/uv run -s /opt/databricks-pipeline/sqlite_to_databricks_uploader.py --config /etc/databricks-pipeline/config.yaml
Restart=always
RestartSec=10
StandardOutput=append:/var/log/databricks-pipeline/service.log
StandardError=append:/var/log/databricks-pipeline/service-error.log

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable databricks-pipeline
sudo systemctl start databricks-pipeline
sudo systemctl status databricks-pipeline
```

#### Option B: Docker Deployment

Create a Dockerfile:

```dockerfile
FROM python:3.11-slim

# Install UV
RUN pip install uv

# Create non-root user
RUN useradd -m -u 1000 pipeline

# Create directories
RUN mkdir -p /app /data /logs /state && \
    chown -R pipeline:pipeline /app /data /logs /state

# Copy application
WORKDIR /app
COPY --chown=pipeline:pipeline . .

# Make scripts executable
RUN chmod +x *.py

USER pipeline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import json; import sys; \
    with open('/state/pipeline_status.json') as f: \
      status = json.load(f); \
      sys.exit(0 if status.get('healthy', False) else 1)"

# Run the pipeline
CMD ["uv", "run", "-s", "sqlite_to_databricks_uploader.py", "--config", "/config/config.yaml"]
```

Docker Compose:

```yaml
version: '3.8'

services:
  pipeline:
    build: .
    restart: unless-stopped
    volumes:
      - ./config:/config:ro
      - ./data:/data
      - ./logs:/logs
      - ./state:/state
    environment:
      - DATABRICKS_HOST
      - DATABRICKS_HTTP_PATH
      - DATABRICKS_TOKEN
      - AWS_ACCESS_KEY_ID
      - AWS_SECRET_ACCESS_KEY
      - AWS_REGION
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  monitoring:
    build: .
    command: ["uv", "run", "-s", "monitoring_dashboard.py"]
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./state:/state:ro
      - ./logs:/logs:ro
    environment:
      - DATABRICKS_HOST
      - DATABRICKS_HTTP_PATH
      - DATABRICKS_TOKEN
```

#### Option C: Kubernetes Deployment

Create a ConfigMap for configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: databricks-pipeline-config
data:
  config.yaml: |
    databricks:
      host: ${DATABRICKS_HOST}
      http_path: ${DATABRICKS_HTTP_PATH}
      database: sensor_data
    # ... rest of config
```

Create a Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: databricks-pipeline
spec:
  replicas: 1
  selector:
    matchLabels:
      app: databricks-pipeline
  template:
    metadata:
      labels:
        app: databricks-pipeline
    spec:
      containers:
      - name: pipeline
        image: your-registry/databricks-pipeline:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        env:
        - name: DATABRICKS_TOKEN
          valueFrom:
            secretKeyRef:
              name: databricks-secrets
              key: token
        volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        - name: state
          mountPath: /state
        - name: logs
          mountPath: /logs
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import json; with open('/state/pipeline_status.json') as f: exit(0 if json.load(f).get('healthy', False) else 1)"
          initialDelaySeconds: 30
          periodSeconds: 30
      volumes:
      - name: config
        configMap:
          name: databricks-pipeline-config
      - name: state
        persistentVolumeClaim:
          claimName: pipeline-state
      - name: logs
        persistentVolumeClaim:
          claimName: pipeline-logs
```

### 3. Monitoring Setup

Deploy the monitoring dashboard:

```bash
# Systemd service for monitoring
sudo cp monitoring-dashboard.service /etc/systemd/system/
sudo systemctl enable monitoring-dashboard
sudo systemctl start monitoring-dashboard

# Access dashboard at http://server-ip:8000
```

### 4. Bacalhau Integration

For distributed processing with Bacalhau:

```bash
# Create Bacalhau job specification
cat > pipeline-job.yaml <<EOF
name: databricks-pipeline
type: batch
spec:
  engine: docker
  docker:
    image: your-registry/databricks-pipeline:latest
    environment:
      - BACALHAU_JOB_ID
      - BACALHAU_NODE_ID
  inputs:
    - source:
        type: s3
        params:
          bucket: your-input-bucket
          key: sensor_data.db
      target: /data/sensor_data.db
  outputs:
    - source: /logs
      target:
        type: s3
        params:
          bucket: your-logs-bucket
          key: logs/
EOF

# Submit job to Bacalhau
bacalhau job run pipeline-job.yaml
```

## Operational Procedures

### 1. Pipeline Management

```bash
# Check pipeline status
uv run -s pipeline_manager.py --db /data/sensor.db get

# Change pipeline type
uv run -s pipeline_manager.py --db /data/sensor.db set filtered --by "operations"

# View pipeline history
uv run -s pipeline_manager.py --db /data/sensor.db history --limit 50
```

### 2. Log Monitoring

```bash
# View real-time logs
tail -f /var/log/databricks-pipeline/*.log

# Monitor errors
./log_monitor.py monitor --log-dir /var/log/databricks-pipeline

# Search logs
./log_monitor.py search "ERROR.*databricks" --hours 24

# Analyze performance
./log_monitor.py analyze --hours 24
```

### 3. Health Checks

Create a health check script:

```python
#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

def check_pipeline_health():
    """Check pipeline health status."""
    status_file = Path("/state/pipeline_status.json")
    
    if not status_file.exists():
        print("ERROR: Pipeline status file not found")
        sys.exit(1)
        
    with open(status_file) as f:
        status = json.load(f)
        
    # Check last update time
    last_update = datetime.fromisoformat(status.get("last_update", ""))
    age = datetime.now(timezone.utc) - last_update
    
    if age > timedelta(minutes=10):
        print(f"ERROR: Pipeline stale - last update {age.total_seconds():.0f}s ago")
        sys.exit(1)
        
    # Check error rate
    error_rate = status.get("error_rate", 0)
    if error_rate > 0.05:  # 5% threshold
        print(f"ERROR: High error rate - {error_rate:.1%}")
        sys.exit(1)
        
    print(f"OK: Pipeline healthy - {status.get('records_processed', 0)} records processed")
    sys.exit(0)

if __name__ == "__main__":
    check_pipeline_health()
```

### 4. Backup and Recovery

```bash
# Backup state
tar -czf state-backup-$(date +%Y%m%d-%H%M%S).tar.gz /var/lib/databricks-pipeline/state/

# Backup logs
tar -czf logs-backup-$(date +%Y%m%d-%H%M%S).tar.gz /var/log/databricks-pipeline/

# Restore state
tar -xzf state-backup-20240101-120000.tar.gz -C /
```

## Troubleshooting

### Common Issues

#### 1. Connection Errors

```bash
# Test Databricks connection
python -c "
from databricks import sql
conn = sql.connect(
    server_hostname='$DATABRICKS_HOST',
    http_path='$DATABRICKS_HTTP_PATH',
    access_token='$DATABRICKS_TOKEN'
)
print('Connection successful')
conn.close()
"

# Test S3 access
aws s3 ls s3://${S3_BUCKET_PREFIX}-databricks-raw-${AWS_REGION}/
```

#### 2. Performance Issues

```bash
# Check resource usage
top -p $(pgrep -f sqlite_to_databricks_uploader)

# Monitor network
iftop -i eth0

# Check disk I/O
iotop -p $(pgrep -f sqlite_to_databricks_uploader)
```

#### 3. Data Quality Issues

```bash
# Validate data manually
./sqlite_to_json_transformer_pydantic.py \
  --db-path /data/sensor_data.db \
  --output /tmp/validated.json \
  --table sensor_data

# Check validation errors
jq '.validation_errors[]' /tmp/validated.json | head -20
```

### Debug Mode

Enable debug logging:

```bash
# Set debug level
export LOG_LEVEL=DEBUG

# Run with verbose output
./sqlite_to_databricks_uploader.py --config config.yaml --verbose

# Enable SQL query logging
export DATABRICKS_LOG_QUERIES=true
```

## Performance Tuning

### 1. Batch Size Optimization

```yaml
# Start with default
processing:
  batch_size: 500

# For high-volume:
processing:
  batch_size: 2000
  
# For low-latency:
processing:
  batch_size: 100
```

### 2. Parallel Processing

```bash
# Run multiple instances with partitioning
PARTITION_COUNT=4
for i in {0..3}; do
  BACALHAU_PARTITION_INDEX=$i \
  BACALHAU_PARTITION_COUNT=$PARTITION_COUNT \
  ./sqlite_to_databricks_uploader.py --config config.yaml &
done
```

### 3. Memory Optimization

```python
# Add to scripts if needed
import gc

# After processing large batches
gc.collect()
```

## Security Considerations

### 1. Secrets Management

Use AWS Secrets Manager or similar:

```bash
# Store secrets
aws secretsmanager create-secret \
  --name databricks-pipeline/prod \
  --secret-string '{
    "databricks_token": "your-token",
    "databricks_host": "your-host"
  }'

# Retrieve in script
aws secretsmanager get-secret-value \
  --secret-id databricks-pipeline/prod \
  --query SecretString \
  --output text
```

### 2. Network Security

- Use VPC endpoints for S3 access
- Whitelist Databricks IP ranges
- Enable SSL/TLS for all connections

### 3. Access Control

```bash
# Create dedicated user
sudo useradd -r -s /bin/false databricks-pipeline

# Set file permissions
sudo chown -R databricks-pipeline:databricks-pipeline /opt/databricks-pipeline
sudo chmod 750 /opt/databricks-pipeline
sudo chmod 640 /etc/databricks-pipeline/*
```

## Maintenance

### Daily Tasks

1. Check pipeline health status
2. Review error logs for anomalies
3. Verify data quality metrics
4. Monitor resource usage

### Weekly Tasks

1. Analyze performance trends
2. Review and optimize batch sizes
3. Clean up old log files
4. Update validation rules if needed

### Monthly Tasks

1. Review and update documentation
2. Test disaster recovery procedures
3. Audit access logs
4. Update dependencies

## Support

For issues or questions:

1. Check logs in `/var/log/databricks-pipeline/`
2. Review monitoring dashboard at `http://localhost:8000`
3. Run health check script
4. Contact: support@your-company.com