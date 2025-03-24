FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy the script
COPY run_command.py .

# Switch to non-root user
USER appuser

# Set the entrypoint
ENTRYPOINT ["uv", "run", "-s", "run_command.py"] 