# Dockerfile
FROM ubuntu:24.04

# Create non-root user
RUN useradd -m -s /bin/bash duckdb

# Install DuckDB CLI and other necessary utilities
RUN apt-get update && apt-get install -y \
    unzip \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Place this after apt-get so it doesn't bust the cache
ARG DUCKDB_VERSION="v1.2.0"
ARG TARGETPLATFORM

# Set DUCKDB_PLATFORM based on TARGETPLATFORM
RUN case "$TARGETPLATFORM" in \
      "linux/amd64") \
        DUCKDB_PLATFORM="linux-amd64" ;; \
      "linux/arm64") \
        DUCKDB_PLATFORM="linux-aarch64" ;; \
      *) \
        echo "Unsupported platform: $TARGETPLATFORM"; \
        exit 1 ;; \
    esac && \
    wget -O duckdb_cli.zip "https://github.com/duckdb/duckdb/releases/download/${DUCKDB_VERSION}/duckdb_cli-${DUCKDB_PLATFORM}.zip" \
    && unzip duckdb_cli.zip -d /usr/local/bin \
    && rm duckdb_cli.zip

# Install and load extensions
RUN duckdb -c "\
    INSTALL httpfs; LOAD httpfs; \
    INSTALL aws; LOAD aws; \
    INSTALL json; LOAD json; \
    INSTALL parquet; LOAD parquet; \
    "

# Copy runtime init SQL file to .duckdbrc
COPY init.sql /home/duckdb/.duckdbrc
RUN chown duckdb:duckdb /home/duckdb/.duckdbrc

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /data
RUN chown duckdb:duckdb /data

USER duckdb

ENTRYPOINT ["/entrypoint.sh"]
CMD ["SELECT 1;"]


LABEL org.opencontainers.image.source="https://github.com/bacalhau-project/examples/utility_containers/duckdb"
LABEL org.opencontainers.image.description="DuckDB container with partitioning support"
LABEL org.opencontainers.image.version="${DUCKDB_VERSION}"