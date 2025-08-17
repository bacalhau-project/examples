FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

RUN mkdir -p /app

WORKDIR /app

# Set environment variables for uv
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY uv.lock* .

# Install Python 3.12 and create virtual environment
RUN uv python install 3.12
RUN uv venv /.venv --python 3.12

# Install dependencies and compile bytecode
RUN uv sync --frozen --compile-bytecode

# Copy application code
COPY main.py .
COPY collector.py .
COPY src/ ./src/

# Pre-compile Python files to bytecode
RUN uv run python -m compileall -b main.py collector.py src/

# Run the application using the pre-installed environment
ENTRYPOINT ["uv", "run", "--no-sync", "main.py"]