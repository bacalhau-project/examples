# Dockerfile
FROM python:3.12

# Set the working directory
WORKDIR /app

RUN apt update && apt install -y \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG PRESIDIO_VERSION="2.2.357"

# Install Presdio
RUN pip install --upgrade pip
RUN pip install --only-binary :all: presidio_analyzer==$PRESIDIO_VERSION
RUN pip install --only-binary :all: presidio_anonymizer==$PRESIDIO_VERSION
RUN python -m spacy download en_core_web_lg

# Container metadata following OCI (Open Container Initiative) spec
LABEL org.opencontainers.image.source="https://github.com/bacalhau-project/examples/utility_containers/presidio" \
      org.opencontainers.image.description="Presidio enabled container with Spacy English Core Model" \
      org.opencontainers.image.version="${PRESIDIO_VERSION}" \
      org.opencontainers.image.created="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.documentation="https://github.com/bacalhau-project/examples/tree/main/utility_containers/presidio"

