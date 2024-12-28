FROM docker:dind

# Install required packages
RUN apk add --no-cache \
    bash \
    curl \
    jq \
    python3 \
    py3-yaml \
    sudo

# Install Bacalhau
COPY scripts/logging.sh scripts/install_uv.sh scripts/100_install_bacalhau.sh /usr/local/bin/
RUN /usr/local/bin/100_install_bacalhau.sh

# Copy configuration scripts
COPY entrypoint.py /entrypoint.py
RUN chmod +x /entrypoint.py

ENTRYPOINT ["/usr/bin/python3", "/entrypoint.py"]
