# Image variables
IMAGE_REPOSITORY := expanso
IMAGE_NAME := nginx-access-log-generator
IMAGE_TAG := $(shell cat VERSION)

# Log generation variables
RATE := 1
OUTPUT_PATH := $(PWD)/loggen-output
OUTPUT_FILE := generated.log

# Build Docker image
build:
	docker build \
		--tag "$(IMAGE_REPOSITORY)/$(IMAGE_NAME):$(IMAGE_TAG)" \
		.
# Build and push Docker image for multiple architectures
build_push:
	docker buildx build --push \
		--platform linux/amd64,linux/arm64 \
		--tag "$(IMAGE_REPOSITORY)/$(IMAGE_NAME):$(IMAGE_TAG)" \
		.

# Convenience target to run the Docker image
run:
	docker run -it \
		-v $(OUTPUT_PATH):/app/output:rw \
		$(IMAGE_REPOSITORY)/$(IMAGE_NAME):$(IMAGE_TAG) --rate $(RATE) --output-log-file /app/output/$(OUTPUT_FILE)


# Bump version
bump_version:
	@awk -F. '{$$NF = $$NF + 1;} 1' OFS=. VERSION > TEMP_VERSION && mv TEMP_VERSION VERSION
	@echo "Version bumped to $$(cat VERSION)"
