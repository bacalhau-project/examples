# Image URL to use all building/pushing image targets
REGISTRY ?= ghcr.io
OWNER ?= bacalhau-project
IMG_NAME ?= presidio
VERSION ?= $(shell date +%y.%m)
IMG = ${REGISTRY}/${OWNER}/${IMG_NAME}

# Get the currently used golang install path (in GOPATH/bin, unless GOBIN is set)
SHELL := /bin/bash

.PHONY: all
all: build

##@ General

# The help target prints out all targets with their descriptions organized
# beneath their categories. The categories are represented by '##@' and the
# target descriptions by '##'. The awk command is responsible for reading the
# entire set of makefiles included in this invocation, looking for lines of the
# file as xyz: ## something, and then pretty-format the target and help. Then,
# if there's a line with ##@ something, that gets pretty-printed as a category.
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

.PHONY: version
version: ## Output the current version
	@echo ${VERSION}

.PHONY: tag
tag: ## Create a new git tag for release
	git tag -a ${VERSION} -m "Release ${VERSION}"
	git push origin ${VERSION}

##@ Testing

.PHONY: test
test: test-anonymizer ## Run all tests

.PHONY: test-anonymizer
test-anonymizer: ## Test Presidio Anonymizer
	@echo "Testing Presidio Anonymizer..."
	@docker run --rm ${IMG}:${VERSION} python3 -c 'from presidio_anonymizer import AnonymizerEngine; \
from presidio_analyzer import AnalyzerEngine; \
text = "My phone number is 212-555-5555"; \
analyzer = AnalyzerEngine(); \
results = analyzer.analyze(text=text, language="en"); \
anonymizer = AnonymizerEngine(); \
anonymized_text = anonymizer.anonymize(text=text, analyzer_results=results).text; \
print("Original text:", text); \
print("Anonymized text:", anonymized_text); \
assert "212-555-5555" not in anonymized_text, "Anonymization failed"; \
print("✓ Presidio Anonymizer test passed")'

.PHONY: clean
clean: ## Clean up test data
	rm -rf test/

.PHONY: size
size: ## Show detailed image size breakdown
	@docker history ${IMG}:${VERSION} --human --format "{{.Size}}\t{{.CreatedBy}}"
