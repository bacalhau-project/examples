# Image URL to use all building/pushing image targets
REGISTRY ?= ghcr.io
OWNER ?= bacalhau-project
IMG_NAME ?= word-count
VERSION ?= $(shell date +%y.%m)
IMG = ${REGISTRY}/${OWNER}/${IMG_NAME}

SHELL := /bin/bash

.PHONY: all
all: build test login push

##@ General

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Build

.PHONY: build
build: ## Build the Docker image for local architecture only
	docker buildx build \
		-t ${IMG}:${VERSION} \
		-t ${IMG}:latest \
		--load .

.PHONY: push
push: ## Push the Docker image
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t ${IMG}:${VERSION} \
		-t ${IMG}:latest \
		--push .

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

##@ Testing

.PHONY: test
test:
	@echo "Running tests..."
	chmod +x test.sh
	./test.sh --no-cleanup

.PHONY: clean
clean: ## Clean up test data
	rm -rf test/

.PHONY: version
version: ## Output the current version
	@echo ${VERSION} 