FROM ghcr.io/bacalhau-project/bacalhau:v1.7.0-dind
WORKDIR /backend

ARG BUILD_DATE
LABEL org.opencontainers.image.created="${BUILD_DATE}"

RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    unzip \
    mc \
    vim \
    nano \
    openssh-client

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY scripts/ ./

RUN ssh-keygen -t rsa -b 4096 -N "" -f /root/.ssh/id_rsa
