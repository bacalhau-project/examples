# Image variables
IMAGE_REPOSITORY := expanso
IMAGE_NAME := nginx-access-log-agent
IMAGE_TAG := $(shell cat VERSION)

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

# Bump version
bump_version:
	@awk -F. '{$$NF = $$NF + 1;} 1' OFS=. VERSION > TEMP_VERSION && mv TEMP_VERSION VERSION
	@echo "Version bumped to $$(cat VERSION)"
