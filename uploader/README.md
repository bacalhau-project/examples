# IPFS Uploader
Simple container for uploading to IPFS by downloading from a URL and uploading to Estuary.

## Build
Build with the following command (necessary for multi-platform builds):
```bash
TAG=v0.9.4
mkdir -p $(pwd)/inputs && cp -fR testdata/* $(pwd)/inputs && rm -rf $(pwd)/outputs/*
INPUT_PATH=$(pwd)/inputs OUTPUT_PATH=$(pwd)/outputs go run main.go  
```

## Build Container
```
docker buildx build --push --platform linux/amd64,linux/arm/v6,linux/arm/v7,linux/arm64/v8 -t docker.io/bacalhauproject/uploader:$TAG .
```

## Run  
Run with the following command:
```bash
TAG=v0.9.4
URL=https://raw.githubusercontent.com/filecoin-project/bacalhau/main/README.md
bacalhau docker run -e URL=$URL docker.io/bacalhauproject/uploader:$TAG
```