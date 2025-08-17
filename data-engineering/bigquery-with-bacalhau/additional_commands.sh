#!/bin/bash
# setup_bigquery_sensor_pipeline.sh - Setup BigQuery connectivity for sensor data pipeline
# This script configures the machine with BigQuery credentials and sensor uploader service

set -e

echo "[$(date)] Starting BigQuery sensor pipeline setup"

# Configuration variables - REPLACE THESE WITH YOUR ACTUAL VALUES
PROJECT_ID="bq-2501151036"
DATASET="log_analytics"
SERVICE_ACCOUNT_KEY_BASE64="ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAiYnEtMjUwMTE1MTAzNiIsCiAgInByaXZhdGVfa2V5X2lkIjogImNmZjVkODI4ZGVjNmJiMTkzNTQ4ODU4ZWZmNmJhMTljYThlYTliYjMiLAogICJwcml2YXRlX2tleSI6ICItLS0tLUJFR0lOIFBSSVZBVEUgS0VZLS0tLS1cbk1JSUV2Z0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktnd2dnU2tBZ0VBQW9JQkFRQ1hydzZ6SCtTK2xEekxcbllEdUJ5czhid0N6KzRrTC9ZSGZGczAzcmp1cjU2NVpLWmRQYjhvN1BUUDMreDFRWUpFenZsZFlsZ1ZKUzJ1U3NcbmJVOHNoSDhSVUl6UjZoWWpMdXhxVno3cCt3MzVKRGlTdmNwYU5jcExwZnE1dDl6WEJzWjZIakRxK0ZBYllzbHNcbnpVcm84OUpTVEhFazd0Y21tNSthc3c4RitPeWJqeTdBWTRIaDF2MStyend5andqVzR3dTRKRzBWRGhiZ2lVQVJcblRtM3UrSXFacUdqL0hqMis1dWdQRU5GWnQyTnVWT2orYWcyeG9IdWx3Q09iS1AyVE9KVHUwNHBaamJEZHhpR2RcbnlOZHJrcitnNlRPNTBSMldlbTVhakhXbFppVDArUnU5VGhTVktGeWlSNFpUekdhZ1MwMEZSVEhONjkrL3E4VVNcbitma091eFd4QWdNQkFBRUNnZ0VBQzFhSnhBQnFqZ2RSR3dla3N4RTRsWE95T1ZRcTIyRjMybmFLYU1Uc1VnV1dcbjNKVkxkb21sUEtBZDdVVXpoMEZ4WWNoQ3MxZDlFcFhybVdyclMrSFVpTFFMYnFadmhLNDlmRDVzeExzZ0lvTWZcblduS20xVUxuamV1SWVBampFRXlnbWVDM1dkejVTZTdDclNnVVJTRHlrL1hFVUZVdERtVDhFMmwyZ2tVRzFLTE1cbkRLQkZoRWpCQ0xkVWlqNFlGVDEwSS83eFBPSkw1YXZrN2FGQ21ubm8rSUFHRWJvaFN4YlNBQWt3L3hOd2pkUjFcbmh6Y3lSaGFiYkFTTUZEQUdBRktEa01SZFJXbmY2cjBuT1pMV0hBVmdrK1lMTnAyY29oQm95c0JvWTI1N3VsYWtcbk1vZUhBc3o5NWZEYlhMVDhNZHNmdjNkeVB1Zk1yREtGOXdDZFNEZE4xUUtCZ1FES2hxMFA3VjdrdXdQbzlYN3JcbmoxUGtXYUgyU05WSWpKTmNLN3V0bm1DTVBOTnZDQUc4SU1vWGJRRzhGbTVtU1U0YW9EMkExYmt3aUN1Rnp4Zllcbjl3cmkvdkZPMldyb1F5R3RaOWVFaGZnV3laZnoxM3lqc1hwWVdDSS93QjNPQUpIcjY0RTM3UFN0Ymh4NUV2a3lcbmYvUHlhNElnMVlqbkpVT3BqVm1KODU0S1hRS0JnUUMvdTg1TEpucXF1UjdEWk5tL3NaYlhqQ0J4Q0VQS3FKUFZcbjQrclIvZXVtRTdrVWVTVkNMWURSeWswQjR4N0lsYnZjdDNpNjc1VytjV1FxLytvelpPYk1zUTlYbzk5MUxsSUxcbmE4MzgyUjE0UkFWdUdTSENkWDM3eXlRd3RFOXM1ajkzK3E0NU04aVNITTc0VWduOUNwa2tQMUdubzNPWkkvNEtcbmZBVWxtYnNMWlFLQmdRQ0RRdjV2MEQwc3FqbENoN3FYR2ZJWmtpNXkzWW0rMTcyNmcyM0VmVjIrQnI1U3ZESERcbnFNelNtZ2dCeTlnSjI0RVBxTU96K05GcUx4ZG1SbThDWkR0ZUhEWnlFR0JGNFJ5MnN4THdCWlJoMEk3M3I3Wk1cbnNmN0Z1M21YTUFFaFB5VlVidkwxT0ZMdEJPelhYQUMvUmticDI5d2ZROGJUYVVlTllOdWptWTNZMFFLQmdRQ1FcbloxTXMySE5FeDUzNnphY09NQ09LZmRnbEtYTmRXKy9VQlE5alR0bS9RRldCck9nNTJtbU9GODQ5NEovYnRLSkRcbnpzOFlBOEFGS2dPbU93NVozT0hUUW50cXAxcHlPQXZFM0ZITTRIeklpbnFJZkZjbnpUT3dnMFBqaHJuWEsrYWJcbloycjJYQ0R3b3MvaXlHOExiSU1BZ012djlUUG9IK3FDWFB2SFlPdzEzUUtCZ0dYOVFtcDhkVitvQUpOVjJWdkRcbkNJV2RZdStWMUk5aVdmdjd3Z1BoYzlldTd0MGtXODhyMGlVc0JKYkNnOE12WTN6MzA2NzV4bXFlWnFEWUEwSU9cbmNUQ0hzdzEvcSs2dW9TMm12U25UbE1yRmx6dHM3K3pYcnh0cElISDF3ZDVrdkM4VDR1ZmdGZ3pnQ0tmSVVGa21cbnFTVVFpSGdhSWt2RCsxeW1GNEIvcVB5OFxuLS0tLS1FTkQgUFJJVkFURSBLRVktLS0tLVxuIiwKICAiY2xpZW50X2VtYWlsIjogImJhY2FsaGF1LWJpZ3F1ZXJ5QGJxLTI1MDExNTEwMzYuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJjbGllbnRfaWQiOiAiMTE0MjA4MzQ3MDY1Mjg5OTcwMzM2IiwKICAiYXV0aF91cmkiOiAiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLAogICJ0b2tlbl91cmkiOiAiaHR0cHM6Ly9vYXV0aDIuZ29vZ2xlYXBpcy5jb20vdG9rZW4iLAogICJhdXRoX3Byb3ZpZGVyX3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vb2F1dGgyL3YxL2NlcnRzIiwKICAiY2xpZW50X3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vcm9ib3QvdjEvbWV0YWRhdGEveDUwOS9iYWNhbGhhdS1iaWdxdWVyeSU0MGJxLTI1MDExNTEwMzYuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJ1bml2ZXJzZV9kb21haW4iOiAiZ29vZ2xlYXBpcy5jb20iCn0K"
NODE_ID="sensor-node-$(hostname -s)"
REGION="us-central1"

# Create necessary directories
echo "[$(date)] Creating required directories"
sudo mkdir -p /bacalhau_data/bigquery/{config,credentials,state,logs}
sudo mkdir -p /bacalhau_data/sensor/{config,data,logs,exports}
sudo chown -R ubuntu:ubuntu /bacalhau_data/bigquery /bacalhau_data/sensor

# Decode and install BigQuery credentials
echo "[$(date)] Installing BigQuery credentials"
echo "$SERVICE_ACCOUNT_KEY_BASE64" | base64 -d > /bacalhau_data/bigquery/credentials/gcp-creds.json
chmod 600 /bacalhau_data/bigquery/credentials/gcp-creds.json
chown ubuntu:ubuntu /bacalhau_data/bigquery/credentials/gcp-creds.json

# Create BigQuery uploader configuration
echo "[$(date)] Creating BigQuery uploader configuration"
cat > /bacalhau_data/bigquery/config/config.yaml << EOF
# BigQuery Uploader Configuration for Sensor Data
project_id: "${PROJECT_ID}"
dataset: "${DATASET}"
node_id: "${NODE_ID}"

# SQLite database configuration
database:
  path: "/bacalhau_data/sensor/data/sensor_data.db"
  table: "sensor_readings"
  sync_enabled: true

# Pipeline mode - choose one: raw, schematized, sanitized, aggregated
pipeline_mode: "schematized"

# Processing configuration
chunk_size: 10000
max_retries: 20
base_retry_delay: 1
max_retry_delay: 60
check_interval: 300  # Check every 5 minutes

# Table names
tables:
  raw: "raw_sensor_data"
  schematized: "sensor_readings"
  sanitized: "sensor_readings_sanitized"
  aggregated: "sensor_aggregates"
  anomalies: "sensor_anomalies"

# Metadata
metadata:
  region: "${REGION}"
  provider: "gcp"
  hostname: "$(hostname)"

# Credentials
credentials_path: "/bacalhau_data/bigquery/credentials/gcp-creds.json"
EOF

chown ubuntu:ubuntu /bacalhau_data/bigquery/config/config.yaml
chmod 644 /bacalhau_data/bigquery/config/config.yaml


# Install sensor-generator service (original logic)
if [ -f /opt/uploaded_files/scripts/sensor-generator.service ]; then
    echo "[$(date)] Installing sensor-generator.service"
    sudo cp /opt/uploaded_files/scripts/sensor-generator.service /etc/systemd/system/
    sudo chmod 644 /etc/systemd/system/sensor-generator.service

    # Fix any dependency issues in the service file
    sudo sed -i 's/setup-config.service//g' /etc/systemd/system/sensor-generator.service
    sudo sed -i 's/After=network-online.target docker.service.*$/After=network-online.target docker.service/g' /etc/systemd/system/sensor-generator.service
    sudo sed -i 's/Requires=docker.service.*$/Requires=docker.service/g' /etc/systemd/system/sensor-generator.service

    # Reload systemd and enable the service
    sudo systemctl daemon-reload
    sudo systemctl enable sensor-generator.service
    echo "[$(date)] Sensor generator service enabled"
else
    echo "[$(date)] WARNING: sensor-generator.service not found in uploaded files"
fi

# Copy sensor config if it exists
if [ -f /opt/uploaded_files/config/sensor-config.yaml ]; then
    echo "[$(date)] Copying sensor configuration"
    sudo cp /opt/uploaded_files/config/sensor-config.yaml /opt/sensor/config/
    sudo chown ubuntu:ubuntu /opt/sensor/config/sensor-config.yaml
fi

# Generate node identity if script exists
if [ -f /opt/uploaded_files/scripts/generate_node_identity.py ]; then
    if [ ! -f /opt/sensor/config/node_identity.json ]; then
        echo "[$(date)] Generating node identity"
        cd /opt/uploaded_files/scripts
        /usr/bin/uv run generate_node_identity.py
    else
        echo "[$(date)] Node identity already exists"
    fi
fi

# Test BigQuery connectivity
echo "[$(date)] Testing BigQuery connectivity"
docker run --rm \
    -v /bacalhau_data/bigquery/credentials/gcp-creds.json:/tmp/creds.json:ro \
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/creds.json \
    google/cloud-sdk:alpine \
    gcloud auth activate-service-account --key-file=/tmp/creds.json && \
    bq --project_id="${PROJECT_ID}" ls "${DATASET}" || echo "[$(date)] WARNING: BigQuery connectivity test failed"

# Create helper scripts
echo "[$(date)] Creating helper scripts"

# Status check script
cat > /opt/bigquery/check_status.sh << 'EOF'
#!/bin/bash
echo "=== Sensor Generator Status ==="
systemctl status sensor-generator.service --no-pager || true

echo -e "\n=== BigQuery Uploader Status ==="
systemctl status bigquery-uploader.service --no-pager || true

echo -e "\n=== Database Status ==="
if [ -f /opt/sensor/data/sensor_data.db ]; then
    echo "Database exists at /opt/sensor/data/sensor_data.db"
    echo "Size: $(du -h /opt/sensor/data/sensor_data.db | cut -f1)"
    echo "Unsynced records:"
    sqlite3 /opt/sensor/data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings WHERE synced = 0;" 2>/dev/null || echo "Unable to query database"
else
    echo "Database not found"
fi

echo -e "\n=== Recent Logs ==="
tail -n 10 /opt/bigquery/logs/uploader.log 2>/dev/null || echo "No logs available"
EOF

chmod +x /opt/bigquery/check_status.sh
chown ubuntu:ubuntu /opt/bigquery/check_status.sh

# Reload systemd and enable services
echo "[$(date)] Enabling and starting services"
systemctl daemon-reload


echo "[$(date)] BigQuery sensor pipeline setup completed!"
echo ""
echo "To check status: /opt/bigquery/check_status.sh"
echo "To manually sync: /opt/bigquery/manual_sync.sh"
echo "Logs are at: /opt/bigquery/logs/"
echo ""
echo "IMPORTANT: Update the following in this script before running:"
echo "  - PROJECT_ID: Your GCP project ID"
echo "  - SERVICE_ACCOUNT_KEY_BASE64: Base64-encoded service account JSON"
echo "  - DOCKER_IMAGE: If using a custom image"
echo "  - REGION: Your deployment region"