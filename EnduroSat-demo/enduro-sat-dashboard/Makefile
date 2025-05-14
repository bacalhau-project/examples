.PHONY: run

IMAGE_NAME=satelitte-dashboard
TAG=250417
FULL_IMAGE=$(IMAGE_NAME):$(TAG)

build:
	docker build -t $(FULL_IMAGE) .

push:
	docker push $(FULL_IMAGE)
