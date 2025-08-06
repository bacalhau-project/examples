### Builder stage: install dependencies using uv-run
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app
COPY databricks-uploader/sqlite_to_databricks_uploader.py ./
# Pre-cache dependencies (UV-run will install required packages)
RUN uv run -s sqlite_to_databricks_uploader.py --help || true

### Runtime stage: lightweight image with pre-installed dependencies
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
WORKDIR /app

# Install bash for credential sourcing
RUN apt-get update && apt-get install -y bash && rm -rf /var/lib/apt/lists/*

# Copy the uploader script
COPY databricks-uploader/sqlite_to_databricks_uploader.py ./
COPY databricks-s3-uploader-config.yaml ./

# Create a wrapper script that sources credentials
RUN cat > /app/run-uploader.sh << 'EOF'
#!/bin/bash
# Source credentials if they exist
if [ -f /bacalhau_node/aws-credentials.env ]; then
    echo "Loading AWS credentials from /bacalhau_node/aws-credentials.env"
    set -a
    source /bacalhau_node/aws-credentials.env
    set +a
elif [ -f /bacalhau_data/credentials/expanso-s3-env.sh ]; then
    echo "Loading AWS credentials from /bacalhau_data/credentials/expanso-s3-env.sh"
    source /bacalhau_data/credentials/expanso-s3-env.sh
fi

# Export any additional environment variables
export PYTHONUNBUFFERED=1

# Run the uploader with all arguments
exec uv run -s sqlite_to_databricks_uploader.py "$@"
EOF

RUN chmod +x /app/run-uploader.sh

# Entrypoint
ENTRYPOINT ["/app/run-uploader.sh"]