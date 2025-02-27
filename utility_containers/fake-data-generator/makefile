# Image URL to use all building/pushing image targets
REGISTRY ?= ghcr.io
OWNER ?= bacalhau-project
IMG_NAME ?= data-generator
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
build:  ## Build the Docker image for local architecture only
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
test: test-generate test-stream ## Run all tests

.PHONY: test-generate
test-generate: ## Test the generate command
	@echo "Testing generate command..."
	@rm -rf test/generate
	@mkdir -p test/generate/json
	@mkdir -p test/generate/csv
	@mkdir -p test/generate/timeseries
	@mkdir -p test/generate/all
	@mkdir -p test/generate/rotation

	@echo "Testing JSON generation..."
	@docker run --rm -v $(PWD)/test/generate/json:/data ${IMG}:${VERSION} generate \
		--count 10 \
		--type transaction \
		--format json
	@echo "Verifying JSON files..."
	@if [ ! -f test/generate/json/transaction_events.json ]; then \
		echo "Error: Transaction events JSON file not found"; \
		exit 1; \
	fi
	@if ! jq . test/generate/json/transaction_events.json >/dev/null 2>&1; then \
		echo "Error: Invalid JSON format"; \
		exit 1; \
	fi

	@echo "Testing CSV generation..."
	@docker run --rm -v $(PWD)/test/generate/csv:/data ${IMG}:${VERSION} generate \
		--count 10 \
		--type transaction \
		--format csv
	@echo "Verifying CSV files..."
	@if [ ! -f test/generate/csv/transaction_events.csv ]; then \
		echo "Error: Transaction events CSV file not found"; \
		exit 1; \
	fi

	@echo "Testing time-series generation..."
	@docker run --rm -v $(PWD)/test/generate/timeseries:/data ${IMG}:${VERSION} generate \
		--type transaction \
		--days 1

	@echo "Testing rotation intervals..."
	@docker run --rm -v $(PWD)/test/generate/rotation:/data ${IMG}:${VERSION} generate \
		--type transaction \
		--days 2 \
		--count 100 \
		--rotate-interval hour \
		--format json
	@echo "Verifying hourly rotation..."
	@file_count=$$(ls test/generate/rotation/transaction_events_*.json 2>/dev/null | wc -l); \
	if [ $$file_count -lt 24 ]; then \
		echo "Error: Expected at least 24 hourly files, got $$file_count"; \
		exit 1; \
	fi
	@# Skip first and last files when checking counts
	@files=$$(ls test/generate/rotation/transaction_events_*.json | sort); \
	first_file=$$(echo "$$files" | head -n1); \
	last_file=$$(echo "$$files" | tail -n1); \
	for file in $$files; do \
		if [ "$$file" != "$$first_file" ] && [ "$$file" != "$$last_file" ]; then \
			if ! jq . "$$file" >/dev/null 2>&1; then \
				echo "Error: Invalid JSON in $$file"; \
				exit 1; \
			fi; \
			events=$$(jq '. | length' "$$file"); \
			if [ $$events -lt 85 ] || [ $$events -gt 115 ]; then \
				echo "Error: Expected ~100 events per hour, got $$events in $$(basename $$file)"; \
				exit 1; \
			fi; \
		fi; \
	done

	@echo "Testing all types generation..."
	@docker run --rm -v $(PWD)/test/generate/all:/data ${IMG}:${VERSION} generate \
		--count 10 \
		--type all \
		--format json
	@echo "Verifying all type files..."
	@for type in transaction security web_access customer; do \
		if [ ! -f test/generate/all/$${type}_events.json ]; then \
			echo "Error: $$type events file not found"; \
			exit 1; \
		fi; \
		if ! jq . test/generate/all/$${type}_events.json >/dev/null 2>&1; then \
			echo "Error: Invalid JSON in $$type events"; \
			exit 1; \
		fi; \
	done

	@echo "All generate tests passed!"

.PHONY: test-stream
test-stream: ## Test the stream command
	@echo "Testing stream command..."
	@rm -rf test/stream
	@mkdir -p test/stream/json
	@mkdir -p test/stream/csv
	@mkdir -p test/stream/all
	@mkdir -p test/stream/rotation

	@echo "Testing JSONL streaming..."
	@docker run --rm -v $(PWD)/test/stream/json:/data ${IMG}:${VERSION} stream \
		--rate 10 \
		--type transaction \
		--duration 2 \
		--format jsonl
	@echo "Verifying JSON stream..."
	@if [ ! -f test/stream/json/transaction_events.jsonl ]; then \
		echo "Error: Transaction stream JSON file not found"; \
		exit 1; \
	fi
	@# Verify each line is valid JSON
	@while read -r line; do \
		if ! echo "$$line" | jq . >/dev/null 2>&1; then \
			echo "Error: Invalid JSON line in stream"; \
			exit 1; \
		fi; \
	done < test/stream/json/transaction_events.jsonl
	@# Count lines to verify rate
	@lines=$$(wc -l < test/stream/json/transaction_events.jsonl); \
	if [ $$lines -lt 15 ]; then \
		echo "Error: Expected at least 15 events (2 seconds at 10/sec), got $$lines"; \
		exit 1; \
	fi

	@echo "Testing stream rotation..."
	@docker run --rm -v $(PWD)/test/stream/rotation:/data ${IMG}:${VERSION} stream \
		--rate 10 \
		--type transaction \
		--duration 180 \
		--rotate-interval minute \
		--format jsonl
	@echo "Verifying minute rotation..."
	@file_count=$$(ls test/stream/rotation/transaction_events_*.jsonl 2>/dev/null | wc -l); \
	if [ $$file_count -lt 2 ]; then \
		echo "Error: Expected at least 2 minute files, got $$file_count"; \
		exit 1; \
	fi
	@# Skip first and last files when checking counts
	@files=$$(ls test/stream/rotation/transaction_events_*.jsonl | sort); \
	first_file=$$(echo "$$files" | head -n1); \
	last_file=$$(echo "$$files" | tail -n1); \
	for file in $$files; do \
		if [ "$$file" != "$$first_file" ] && [ "$$file" != "$$last_file" ]; then \
			if ! jq . "$$file" >/dev/null 2>&1; then \
				echo "Error: Invalid JSON in $$file"; \
				exit 1; \
			fi; \
			lines=$$(wc -l < "$$file"); \
			if [ $$lines -lt 300 ]; then \
				echo "Error: Expected at least 300 events per file (30s at 10/sec), got $$lines in $$(basename $$file)"; \
				exit 1; \
			fi; \
		fi; \
	done

	@echo "Testing CSV streaming..."
	@docker run --rm -v $(PWD)/test/stream/csv:/data ${IMG}:${VERSION} stream \
		--rate 10 \
		--type transaction \
		--duration 2 \
		--format csv
	@echo "Verifying CSV stream..."
	@if [ ! -f test/stream/csv/transaction_events.csv ]; then \
		echo "Error: Transaction stream CSV file not found"; \
		exit 1; \
	fi

	@echo "Testing multi-type streaming..."
	@docker run --rm -v $(PWD)/test/stream/all:/data ${IMG}:${VERSION} stream \
		--rate 10 \
		--type all \
		--duration 2 \
		--format jsonl
	@echo "Verifying multi-type streams..."
	@for type in transaction security web_access customer; do \
		if [ ! -f test/stream/all/$${type}_events.jsonl ]; then \
			echo "Error: $$type stream file not found"; \
			exit 1; \
		fi; \
		if ! jq . test/stream/all/$${type}_events.jsonl >/dev/null 2>&1; then \
			echo "Error: Invalid JSON in $$type stream"; \
			exit 1; \
		fi; \
	done
	@# Verify total events across all files matches expected rate
	@total_events=0; \
	for type in transaction security web_access customer; do \
		events=$$(wc -l < test/stream/all/$${type}_events.jsonl); \
		total_events=$$((total_events + events)); \
	done; \
	if [ $$total_events -lt 15 ]; then \
		echo "Error: Expected at least 15 total events (2 seconds at 10/sec), got $$total_events"; \
		exit 1; \
	fi

	@echo "All stream tests passed!"

.PHONY: clean
clean: ## Clean up test data
	rm -rf test/