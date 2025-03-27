# Image names and tags
REGISTRY ?= ghcr.io
OWNER ?= bacalhau-project
PREFIX ?= wasm-sensors
PROXY_IMAGE ?= $(PREFIX)-sqs-proxy
PULLER_IMAGE ?= $(PREFIX)-sqs-puller
VERSION ?= $(shell date +%y.%m)

# Full image names
PROXY_FULL_NAME = $(REGISTRY)/$(OWNER)/$(PROXY_IMAGE)
PULLER_FULL_NAME = $(REGISTRY)/$(OWNER)/$(PULLER_IMAGE)

SHELL := /bin/bash

.PHONY: all build push clean login help

all: build

##@ General

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Build

build: build-docker build-wasm

build-docker: build-proxy build-puller

build-proxy: ## Build the proxy Docker image for local architecture
	docker buildx build \
		-t $(PROXY_FULL_NAME):$(VERSION) \
		-t $(PROXY_FULL_NAME):latest \
		--load \
		-f containers/docker/sqs-proxy/Dockerfile containers/docker/sqs-proxy

build-puller: ## Build the puller Docker image for local architecture
	docker buildx build \
		-t $(PULLER_FULL_NAME):$(VERSION) \
		-t $(PULLER_FULL_NAME):latest \
		--load \
		-f containers/docker/sqs-puller/Dockerfile containers/docker/sqs-puller

##@ Push

push: push-docker

push-docker: push-proxy push-puller

push-proxy: ## Push the proxy Docker image for all architectures
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t $(PROXY_FULL_NAME):$(VERSION) \
		-t $(PROXY_FULL_NAME):latest \
		--push \
		-f containers/docker/sqs-proxy/Dockerfile containers/docker/sqs-proxy

push-puller: ## Push the puller Docker image for all architectures
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t $(PULLER_FULL_NAME):$(VERSION) \
		-t $(PULLER_FULL_NAME):latest \
		--push \
		-f containers/docker/sqs-puller/Dockerfile containers/docker/sqs-puller

##@ WASM

build-wasm: build-sqs-publisher

build-sqs-publisher: ## Build the SQS publisher WASM module
	@echo "Building SQS publisher WASM module..."
	@cd containers/wasm/sqs-publisher && tinygo build -o ../../../network/modules/publisher.wasm -target wasi .
	@echo "SQS publisher WASM build completed successfully!"

##@ Legacy WASM

build-legacy: build-legacy-config-updater build-legacy-config-reader build-legacy-dir-lister build-legacy-sqs-publisher

build-legacy-config-updater: ## Build the legacy config updater WASM module
	@echo "Building legacy config updater WASM module..."
	@cd containers/wasm/legacy/config-updater && tinygo build -o ../../../../network/modules/legacy/config-updater.wasm -target wasi .
	@echo "Legacy config updater WASM build completed successfully!"

build-legacy-config-reader: ## Build the legacy config reader WASM module
	@echo "Building legacy config reader WASM module..."
	@cd containers/wasm/legacy/config-reader && tinygo build -o ../../../../network/modules/legacy/config-reader.wasm -target wasi .
	@echo "Legacy config reader WASM build completed successfully!"

build-legacy-dir-lister: ## Build the legacy directory lister WASM module
	@echo "Building legacy directory lister WASM module..."
	@cd containers/wasm/legacy/dir-lister && tinygo build -o ../../../../network/modules/legacy/dir-lister.wasm -target wasi .
	@echo "Legacy directory lister WASM build completed successfully!"

build-legacy-sqs-publisher: ## Build the legacy SQS publisher WASM module
	@echo "Building legacy SQS publisher WASM module..."
	@cd containers/wasm/legacy/sqs-publisher && tinygo build -o ../../../../network/modules/legacy/sqs-publisher.wasm -target wasi .
	@echo "Legacy SQS publisher WASM build completed successfully!"

##@ Development

.PHONY: login
login: ## Login to GitHub Container Registry
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

##@ Cleanup

clean: ## Clean up (no-op for now)
	@echo "Clean target is currently a no-op"

##@ Version

.PHONY: version
version: ## Output the current version
	@echo ${VERSION} 