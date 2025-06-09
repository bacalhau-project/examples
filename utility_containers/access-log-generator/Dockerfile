# Stage 1: Builder
# Use the uv base image which includes Python and uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Set working directory for the application
WORKDIR /app

# Copy application files first to leverage Docker cache effectively if dependencies change less often
COPY access-log-generator.py access-log-generator.py
COPY log_generator_config.yaml default_config.yaml
COPY requirements.txt requirements.txt

# Create virtual environment using Python 3.13 (to match the base image's Python version)
# The venv will be created at /opt/venv
RUN uv venv /opt/venv --seed --python 3.13

RUN . /opt/venv/bin/activate && \
    uv pip install --upgrade pip && \
    uv pip install -r requirements.txt

# Stage 2: Final execution image
# Use a minimal Python base image for the final stage
FROM python:3.13-slim-bookworm

# Set working directory for the application
WORKDIR /app

# Copy the uv executable from the builder stage
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application files from the builder stage
COPY --from=builder /app/access-log-generator.py /app/access-log-generator.py
COPY --from=builder /app/default_config.yaml /app/default_config.yaml

# Set environment variables
# Add the virtual environment's bin directory to PATH
# Also set VIRTUAL_ENV which some tools might use
ENV VIRTUAL_ENV=/opt/venv
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