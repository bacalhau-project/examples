FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

RUN mkdir -p /app

WORKDIR /app

# Set environment variables for uv
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_BOOTSTRAP=1

# Copy application code and dependency definitions
COPY main.py .
COPY src/ ./src/

# Create a virtual environment and install dependencies
# uv will download and install Python 3.12 to /root/.cache/uv/pythons if not available
RUN /usr/local/bin/uv venv /.venv --python 3.12 \
    && . /.venv/bin/activate \
    && /usr/local/bin/uv run --python /.venv/bin/python main.py --exit

# Activate the virtual environment and run the application
ENTRYPOINT ["uv", "run", "main.py"]