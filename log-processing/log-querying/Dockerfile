# Use a base image with Bash and standard utilities
FROM ubuntu:22.04

# Install DuckDB CLI and other necessary utilities
RUN apt-get update && apt-get install -y \
    unzip \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Place this after apt-get so it doesn't bust the cache
ARG DUCKDB_VERSION="v0.9.1"
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

# Copy the Bash script into the container
COPY entrypoint.sh /

# Make the script executable
RUN chmod +x /entrypoint.sh

# Set the entrypoint and default command
ENTRYPOINT ["/entrypoint.sh"]
CMD []
