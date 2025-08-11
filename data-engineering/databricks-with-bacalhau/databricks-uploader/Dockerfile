FROM python:3.11-slim

# Install uv for Python package management
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy all Python scripts
COPY *.py ./

# Install Python dependencies using uv
RUN uv pip install --system \
    databricks-sql-connector>=3.0.0 \
    python-dotenv>=1.0.0 \
    boto3>=1.26.0 \
    pyyaml>=6.0 \
    watchdog>=3.0.0

# Create directories for runtime
RUN mkdir -p /app/state /bacalhau_data/credentials

# Default entrypoint
ENV PYTHONUNBUFFERED=1

# Default entrypoint
ENTRYPOINT ["python", "-u", "sqlite_to_databricks_uploader.py"]

# Default command (can be overridden)
CMD ["--config", "/app/config.yaml"]