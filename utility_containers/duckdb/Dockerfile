# Dockerfile
FROM ubuntu:24.04

# Install DuckDB CLI and other necessary utilities
RUN apt-get update && apt-get install -y \
    unzip \
    wget \
    ca-certificates \
    && apt-get clean \
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

# Install extensions
RUN duckdb -c "\
    INSTALL httpfs; \
    INSTALL aws; \
    "

# Initialize DuckDB configuration
# .duckdbrc will be executed whenever DuckDB starts
COPY init.sql /root/.duckdbrc

# Set up container entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["SELECT 1;"]

# Container metadata following OCI (Open Container Initiative) spec
LABEL org.opencontainers.image.source="https://github.com/bacalhau-project/examples/utility_containers/duckdb" \
      org.opencontainers.image.description="DuckDB container with partitioning support" \
      org.opencontainers.image.version="${DUCKDB_VERSION}" \
      org.opencontainers.image.created="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.documentation="https://github.com/bacalhau-project/examples/tree/main/utility_containers/duckdb"