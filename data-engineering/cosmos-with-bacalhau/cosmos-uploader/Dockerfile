FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN uv pip install -r requirements.txt

# Copy source code
COPY . .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
