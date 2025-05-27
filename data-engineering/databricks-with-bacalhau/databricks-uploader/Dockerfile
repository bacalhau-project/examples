### Builder stage: install dependencies using uv-run
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app
COPY upload_sqlite_to_s3.py ./
# Pre-cache dependencies (UV-run will install required packages)
RUN uv run -s upload_sqlite_to_s3.py --help || true

### Runtime stage: lightweight image with pre-installed dependencies
FROM alpine AS runtime
WORKDIR /app
# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# Copy the uploader script
COPY upload_sqlite_to_s3.py ./

# Entrypoint
ENTRYPOINT ["uv", "run", "-s", "upload_sqlite_to_s3.py"]