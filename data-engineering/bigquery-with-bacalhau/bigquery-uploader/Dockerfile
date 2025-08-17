# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies in a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage - minimal runtime image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application files
COPY bigquery_uploader.py .

# Create directory for log files
RUN mkdir -p /bacalhau_data

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONFIG_FILE=/app/config.yaml

# Health check to ensure the Python environment is working
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import sys; import duckdb; import pandas; import google.cloud.bigquery; sys.exit(0)" || exit 1

# Labels for better container management
LABEL maintainer="BigQuery Uploader Team" \
    description="Unified log processor for BigQuery upload with support for raw, schematized, sanitized, and aggregated processing" \
    version="1.0.0"

# The application expects these environment variables:
# Required:
# - CONFIG_FILE: Path to YAML configuration file (default: /app/config.yaml)
#
# Optional overrides:
# - LOG_FILE or log_file: Override input_paths from config with a single log file path
# - GOOGLE_APPLICATION_CREDENTIALS or CREDENTIALS_FILE or CREDENTIALS_PATH: Path to BigQuery service account credentials
# - PROJECT_ID: Override project_id from config
# - DATASET: Override dataset from config
# - NODE_ID: Override node_id from config
# - REGION: Override metadata.region from config

# Run the Python script
ENTRYPOINT ["python", "bigquery_uploader.py"]
