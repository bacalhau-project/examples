FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Set environment variables for uv
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_BOOTSTRAP=1

# Copy application code and dependency definitions
COPY main.py .
COPY src/ ./src/

# Create a virtual environment and install dependencies
RUN uv venv && . .venv/bin/activate && uv run -s main.py --exit

# --- Final Stage ---
FROM cgr.dev/chainguard/python:latest-amd64

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /.venv

# Copy the application code
COPY main.py .
COPY src/ ./src/

# Make the startup script executable
RUN chmod +x /app/src/startup.sh

# Activate the virtual environment and run the application
ENV PATH="/app/.venv/bin:$PATH"
CMD ["/app/src/startup.sh"]