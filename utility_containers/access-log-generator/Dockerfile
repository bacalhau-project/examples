FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Add /root/.local/bin to PATH
ENV PATH="/root/.local/bin:$PATH"

# Create and activate virtual environment
RUN uv venv /root/.venv --seed --python 3.12
ENV VIRTUAL_ENV=/root/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install packages in the virtual environment
RUN uv pip install --upgrade pip

COPY access-log-generator.py /app/access-log-generator.py
COPY config/docker-config.yaml /app/config/config.yaml

# Set working directory
WORKDIR /app

# Set default configuration path
ENV LOG_GENERATOR_CONFIG_PATH=/app/config/config.yaml

# Create logs directory
RUN mkdir -p /logs
VOLUME /logs

RUN uv run -s access-log-generator.py --exit

CMD ["uv", "run", "-s", "access-log-generator.py"]