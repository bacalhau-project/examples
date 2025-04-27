REGISTRY ?= ghcr.io
OWNER ?= bacalhau-project
IMAGE_NAME ?= nginx-access-log-query
IMAGE_TAG ?= $(shell cat VERSION)

.PHONY: help login build build_push version

# Display help information
help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

# Login to GitHub Container Registry
login:
	@echo "Logging into GitHub Container Registry..."
	@if [ -z "${GITHUB_PAT}" ]; then \
		echo "Error: GITHUB_PAT environment variable is not set"; \
		exit 1; \
	fi
	@if [ -z "${GITHUB_USERNAME}" ]; then \
		echo "Error: GITHUB_USERNAME environment variable is not set"; \
		exit 1; \
	fi
	@echo "${GITHUB_PAT}" | docker login ${REGISTRY} -u ${GITHUB_USERNAME} --password-stdin

# Build Docker image
build:
	docker build \
		--tag "$(REGISTRY)/$(OWNER)/$(IMAGE_NAME):$(IMAGE_TAG)" \
		.
# Build and push Docker image for multiple architectures
build_push:
	docker buildx build --push \
		--platform linux/amd64,linux/arm64 \
		--tag "$(REGISTRY)/$(OWNER)/$(IMAGE_NAME):$(IMAGE_TAG)" \
		.

# Output the current version
version:
	@echo ${IMAGE_TAG}
