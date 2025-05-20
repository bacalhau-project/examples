.PHONY: run

IMAGE_NAME ?= ghcr.io/bacalhau-project/examples/satelitte-dashboard
TAG ?= 250521
FULL_IMAGE ?= $(IMAGE_NAME):$(TAG)

build:
	docker build -t $(IMAGE_NAME):latest .
	docker tag $(IMAGE_NAME):latest $(FULL_IMAGE)

push:
	docker push $(FULL_IMAGE)
