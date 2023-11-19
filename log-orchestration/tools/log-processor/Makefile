# Image variables
IMAGE_REPOSITORY := expanso
IMAGE_NAME := nginx-access-log-processor
IMAGE_TAG := $(shell cat VERSION)

# Log processing variables
START := "-1 day"
END :=
QUERY := "SELECT * FROM logs LIMIT 10"
LOG_MOUNT :=
LOG_PATH := "/logs/[!.]*"

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
		-v $(LOG_MOUNT):/logs \
		$(IMAGE_REPOSITORY)/$(IMAGE_NAME):$(IMAGE_TAG) --start-time "$(START)" --end-time "$(END)" --log-path "$(LOG_PATH)" --query "$(QUERY)"


# Bump version
bump_version:
	@awk -F. '{$$NF = $$NF + 1;} 1' OFS=. VERSION > TEMP_VERSION && mv TEMP_VERSION VERSION
	@echo "Version bumped to $$(cat VERSION)"
