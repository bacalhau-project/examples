.PHONY: run

build:
	 docker build -t edge-demo-frontend .

run-container:
	docker run --name edge-transfer-demo -p 3000:3000 \
	  -e BACALHAU_API_HOST= \
	  -e BACALHAU_API_TLS_USETLS=true \
	  -e BACALHAU_TOKEN= \
	  edge-demo-frontend
