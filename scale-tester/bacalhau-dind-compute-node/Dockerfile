FROM docker:dind

# Install required packages
RUN apk add --no-cache bash curl jq python3 sudo

# Install Bacalhau
COPY scripts/logging.sh scripts/install_uv.sh scripts/100_install_bacalhau.sh /usr/local/bin/
RUN /usr/local/bin/100_install_bacalhau.sh

# Copy configuration scripts
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
