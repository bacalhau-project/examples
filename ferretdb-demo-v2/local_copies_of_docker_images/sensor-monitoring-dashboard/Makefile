IMAGE_NAME ?= ghcr.io/bacalhau-project/examples/sensor-monitoring-dashboard
TAG ?= 2504291030
FULL_IMAGE ?= $(IMAGE_NAME):$(TAG)

build:
	docker build -t $(IMAGE_NAME):latest .
	docker tag $(IMAGE_NAME):latest $(FULL_IMAGE)

push: build
	docker push $(FULL_IMAGE)

# cleanup local image (optional)
clean:
	docker rmi $(FULL_IMAGE)
	docker rmi $(IMAGE_NAME):latest

.PHONY: build push clean
