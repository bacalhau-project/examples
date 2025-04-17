.PHONY: run

IMAGE_NAME=ghcr.io/bacalhau-project/examples/edge-data-transfer-frontend
TAG=250417
FULL_IMAGE=$(IMAGE_NAME):$(TAG)

build:
	docker build -t $(FULL_IMAGE) .

push:
	docker push $(FULL_IMAGE)
