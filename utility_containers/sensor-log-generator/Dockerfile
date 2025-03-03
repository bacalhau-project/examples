FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Set environment variables for uv
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1

# Copy only necessary application code
COPY main.py .
COPY src/ ./src/
COPY config.yaml .
COPY node_identity.json .

# Set environment variables for the application
ENV SENSOR_CONFIG=/app/config.yaml
ENV PYTHONUNBUFFERED=1

# Install dependencies during build using the metadata in main.py
# This ensures dependencies are installed in the container
RUN uv run -s main.py --exit

# Create data directory with proper permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Create startup script to handle cleanup of old data
RUN echo '#!/bin/sh\n\
    # Clean up old database files if they exist\n\
    if [ -f /app/data/sensor_data.db ]; then\n\
    echo "Removing old database file"\n\
    rm -f /app/data/sensor_data.db*\n\
    fi\n\
    \n\
    # Run the application\n\
    exec uv run -s main.py "$@"\n\
    ' > /app/start.sh && chmod +x /app/start.sh

# Volume for persistent data only
VOLUME ["/app/data"]

# Run the application using the startup script
CMD ["/app/start.sh"]