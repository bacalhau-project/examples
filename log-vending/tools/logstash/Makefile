# Image variables
IMAGE_REPOSITORY := expanso
IMAGE_NAME := nginx-access-log-agent
IMAGE_TAG := latest

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