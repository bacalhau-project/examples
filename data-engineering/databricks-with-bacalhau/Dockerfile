### Builder stage: install dependencies using uv-run
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app
COPY sqlite_to_databricks_uploader.py ./
# Pre-cache dependencies (UV-run will install required packages)
RUN uv run -s sqlite_to_databricks_uploader.py --help || true

### Runtime stage: lightweight image with pre-installed dependencies
FROM alpine AS runtime
WORKDIR /app
# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# Copy the uploader script
COPY sqlite_to_databricks_uploader.py ./

# Entrypoint
ENTRYPOINT ["uv", "run", "-s", "sqlite_to_databricks_uploader.py"]