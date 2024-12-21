FROM docker:dind

# Install required packages
RUN apk add --no-cache bash curl

# Install Bacalhau
RUN curl -sL https://get.bacalhau.org/install.sh | bash

# Copy configuration scripts
COPY entrypoint.sh /entrypoint.sh
COPY scripts/105_install_run_bacalhau.sh /usr/local/bin/run-bacalhau

RUN chmod +x /entrypoint.sh /usr/local/bin/run-bacalhau

ENTRYPOINT ["/entrypoint.sh"]
