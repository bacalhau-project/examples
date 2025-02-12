# Image URL to use all building/pushing image targets
REGISTRY ?= ghcr.io
OWNER ?= bacalhau-project
IMG_NAME ?= duckdb
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
test: test-partitioning test-s3 ## Run all tests

.PHONY: test-s3
test-s3: ## Test S3 connectivity (requires AWS credentials)
	@echo "Testing S3 connectivity..."
	@if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then \
		echo "Skipping S3 tests - AWS credentials not set"; \
		exit 0; \
	else \
		docker run --rm \
			-e AWS_ACCESS_KEY_ID \
			-e AWS_SECRET_ACCESS_KEY \
			${IMG}:${VERSION} \
			"SELECT COUNT(*) FROM read_csv('s3://aws-data-analytics-workshops/shared_datasets/titanic/titanic_train.csv')" > test/s3_test.txt; \
		if ! grep -q "[1-9][0-9]*" test/s3_test.txt; then \
			echo "Error: Failed to read from S3"; \
			exit 1; \
		fi \
	fi

.PHONY: test-partitioning
test-partitioning:  ## Test partitioning functionality
	mkdir -p test/hash
	echo '{"id": 1}' > test/hash/1.json
	echo '{"id": 2}' > test/hash/2.json
	echo '{"id": 3}' > test/hash/3.json

	# Verify file listing for partition 0
	docker run --rm -e BACALHAU_PARTITION_COUNT=3 -e BACALHAU_PARTITION_INDEX=0 -v $(PWD)/test:/data \
		${IMG}:${VERSION} -c "SELECT * FROM partition_by_hash('/data/hash/*.json')" \
		| tee test/hash_part0.txt
	@grep -q "1.json" test/hash_part0.txt || (echo "Error: Expected file 1.json in partition 0" && exit 1)
	@grep -q "3.json" test/hash_part0.txt || (echo "Error: Expected file 3.json in partition 0" && exit 1)
	@test $$(grep "json" test/hash_part0.txt | wc -l) -eq 2 || (echo "Error: Expected exactly 2 files in partition 0" && exit 1)

	# Verify data reading for partition 0
	docker run --rm -e BACALHAU_PARTITION_COUNT=3 -e BACALHAU_PARTITION_INDEX=0 -v $(PWD)/test:/data \
		${IMG}:${VERSION} -c \
		"SET VARIABLE partitioned_files=(SELECT LIST(file) FROM partition_by_hash('/data/hash/*.json')); \
		 SELECT * FROM read_json(getvariable('partitioned_files'))" \
		| tee test/hash_content0.txt
	@grep -q "1" test/hash_content0.txt || (echo "Error: Expected id 1 in partition 0" && exit 1)
	@grep -q "3" test/hash_content0.txt || (echo "Error: Expected id 3 in partition 0" && exit 1)
	@! grep -q "2" test/hash_content0.txt || (echo "Error: Unexpected id 2 in partition 0" && exit 1)

	# Test regex-based partitioning
	mkdir -p test/regex
	for letter in a b c; do \
		for num in 1 2 3; do \
			echo "{\"value\": \"$${letter}_$${num}\"}" > "test/regex/data_$${letter}_$${num}.json"; \
		done \
	done

	# Verify files in partition 0
	docker run --rm -e BACALHAU_PARTITION_COUNT=3 -e BACALHAU_PARTITION_INDEX=1 -v $(PWD)/test:/data \
		${IMG}:${VERSION} -c \
		"SELECT * FROM partition_by_regex('/data/regex/*.json', 'data_([a-c])_\d+\.json')" \
		| tee test/regex_part0.txt
	 @grep -q "data_a_1.json" test/regex_part0.txt || (echo "Error: Expected data_a_1.json in partition 0" && exit 1)
	 @grep -q "data_a_2.json" test/regex_part0.txt || (echo "Error: Expected data_a_2.json in partition 0" && exit 1)
	 @grep -q "data_a_3.json" test/regex_part0.txt || (echo "Error: Expected data_a_3.json in partition 0" && exit 1)
	 @test $$(grep "json" test/regex_part0.txt | wc -l) -eq 3 || (echo "Error: Expected exactly 3 files in partition 0" && exit 1)

	# Test date-based partitioning
	mkdir -p test/date
	# Create one file per month
	for month in {1..12}; do \
		mpad=$$(printf "%02d" $$month); \
		echo "{\"date\": \"2024-$${mpad}-01\"}" > "test/date/data_2024$${mpad}01.json"; \
	done
	# Extra files for January
	echo '{"date": "2024-01-02"}' > test/date/data_20240102.json
	echo '{"date": "2024-01-03"}' > test/date/data_20240103.json

	# Verify files in partition 0
	docker run --rm -e BACALHAU_PARTITION_COUNT=2 -e BACALHAU_PARTITION_INDEX=0 -v $(PWD)/test:/data \
		${IMG}:${VERSION} -c \
		"SELECT * FROM partition_by_date('/data/date/*.json', 'data_(\d{4})(\d{2})(\d{2})\.json', part:='month')" \
		| tee test/date_part0.txt
	@grep -q "20240101" test/date_part0.txt || (echo "Error: Expected 20240101 file in partition 0" && exit 1)
	@grep -q "20240102" test/date_part0.txt || (echo "Error: Expected 20240102 file in partition 0" && exit 1)
	@grep -q "20240103" test/date_part0.txt || (echo "Error: Expected 20240103 file in partition 0" && exit 1)
	@grep -q "20240401" test/date_part0.txt || (echo "Error: Expected 20240401 file in partition 0" && exit 1)
	@grep -q "20240501" test/date_part0.txt || (echo "Error: Expected 20240501 file in partition 0" && exit 1)
	@grep -q "20240701" test/date_part0.txt || (echo "Error: Expected 20240701 file in partition 0" && exit 1)
	@grep -q "20240801" test/date_part0.txt || (echo "Error: Expected 20240801 file in partition 0" && exit 1)
	@grep -q "20240901" test/date_part0.txt || (echo "Error: Expected 20240901 file in partition 0" && exit 1)
	@grep -q "20241101" test/date_part0.txt || (echo "Error: Expected 20241101 file in partition 0" && exit 1)
	@test $$(grep "json" test/date_part0.txt | wc -l) -eq 9 || (echo "Error: Expected exactly 9 months in partition 0" && exit 1)

	# Verify files in partition 1
	docker run --rm -e BACALHAU_PARTITION_COUNT=2 -e BACALHAU_PARTITION_INDEX=1 -v $(PWD)/test:/data \
		${IMG}:${VERSION} -c \
		"SELECT * FROM partition_by_date('/data/date/*.json', 'data_(\d{4})(\d{2})(\d{2})\.json', part:='month')" \
		| tee test/date_part1.txt
	@grep -q "20240201" test/date_part1.txt || (echo "Error: Expected 20240201 file in partition 0" && exit 1)
	@grep -q "20240301" test/date_part1.txt || (echo "Error: Expected 20240301 file in partition 0" && exit 1)
	@grep -q "20240601" test/date_part1.txt || (echo "Error: Expected 20240601 file in partition 0" && exit 1)
	@grep -q "20241001" test/date_part1.txt || (echo "Error: Expected 20241001 file in partition 0" && exit 1)
	@grep -q "20241201" test/date_part1.txt || (echo "Error: Expected 20241201 file in partition 0" && exit 1)
	@test $$(grep "json" test/date_part1.txt | wc -l) -eq 5 || (echo "Error: Expected exactly 5 months in partition 0" && exit 1)


	# Verify quarterly partitioning
	docker run --rm -e BACALHAU_PARTITION_COUNT=4 -e BACALHAU_PARTITION_INDEX=0 -v $(PWD)/test:/data \
		${IMG}:${VERSION} -c \
		"SELECT * FROM partition_by_date('/data/date/*.json', 'data_(\d{4})(\d{2})(\d{2})\.json', part:='quarter')" \
		| tee test/date_quarter_part0.txt
	@grep -q "20240401" test/date_quarter_part0.txt || (echo "Error: Expected 20240401 file in partition 0" && exit 1)
	@grep -q "20240501" test/date_quarter_part0.txt || (echo "Error: Expected 20240501 file in partition 0" && exit 1)
	@grep -q "20240601" test/date_quarter_part0.txt || (echo "Error: Expected 20240601 file in partition 0" && exit 1)
	@echo "All partitioning tests passed!"

.PHONY: clean
clean: ## Clean up test data
	rm -rf test/

.PHONY: size
size: ## Show detailed image size breakdown
	@docker history ${IMG}:${VERSION} --human --format "{{.Size}}\t{{.CreatedBy}}"

.PHONY: test-distribution
test-distribution:  ## Test partition distribution patterns
	mkdir -p test/distribution

	# Create test files
	@echo "Creating test files..."
	# Sequential files (1-100)
	for i in {1..100}; do \
		ipad=$$(printf "%03d" $$i); \
		echo "{\"id\": $$i}" > "test/distribution/seq_$${ipad}.json"; \
	done
	# Date-based files (2 years of daily data)
	for year in 2023 2024; do \
		for month in {01..12}; do \
			mpad=$$(printf "%02d" $$month); \
			for day in {01..28}; do \
				dpad=$$(printf "%02d" $$day); \
				echo "{\"date\": \"$$year-$$mpad-$$dpad\"}" > "test/distribution/date_$${year}$${mpad}$${dpad}.json"; \
			done \
		done \
	done
	# Text-based files (combinations)
	for x in {a..z}; do \
		for y in {1..4}; do \
			ypad=$$(printf "%02d" $$y); \
			echo "{\"text\": \"$$x$$ypad\"}" > "test/distribution/text_$${x}_$${ypad}.json"; \
		done \
	done

	@echo "Analyzing hash-based distribution..."
	@for p in 2 3 4 5; do \
		echo "With $$p partitions:"; \
		for i in $$(seq 0 $$(($$p-1))); do \
			count=$$(docker run --rm -e BACALHAU_PARTITION_COUNT=$$p -e BACALHAU_PARTITION_INDEX=$$i \
				-v $(PWD)/test:/data ${IMG}:${VERSION} -noheader --list -c \
				"SELECT COUNT(*) FROM partition_by_hash('/data/distribution/seq_*.json')" | grep -o '[0-9]\+'); \
			echo "Partition $$i: $$count files"; \
		done \
	done

	@echo "Analyzing regex-based distribution..."
	@for p in 2 3 4 5; do \
		echo "With $$p partitions:"; \
		for i in $$(seq 0 $$(($$p-1))); do \
			count=$$(docker run --rm -e BACALHAU_PARTITION_COUNT=$$p -e BACALHAU_PARTITION_INDEX=$$i \
				-v $(PWD)/test:/data ${IMG}:${VERSION} -noheader --list -c \
				"SELECT COUNT(*) FROM partition_by_regex('/data/distribution/text_*.json', 'text_([a-z])_\d+')" | grep -o '[0-9]\+'); \
			echo "Partition $$i: $$count files"; \
		done \
	done

	@echo "Analyzing date-based distribution..."
	@for p in 2 3 4; do \
		for part in month quarter year; do \
			echo "With $$p partitions (by $$part):"; \
			for i in $$(seq 0 $$(($$p-1))); do \
				count=$$(docker run --rm -e BACALHAU_PARTITION_COUNT=$$p -e BACALHAU_PARTITION_INDEX=$$i \
					-v $(PWD)/test:/data ${IMG}:${VERSION} -noheader --list -c \
					"SELECT COUNT(*) FROM partition_by_date('/data/distribution/date_*.json', 'date_(\d{4})(\d{2})(\d{2})\.json', part:='$$part')" | grep -o '[0-9]\+'); \
				echo "Partition $$i: $$count files"; \
			done \
		done \
	done

	@echo "Distribution analysis complete!"