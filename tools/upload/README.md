# Bacalhau Uploader Container

This application is packaged as a container to make it easier for Bacalhau users to upload their data. It supports uploading from several different sources.

## How It Works

Bacalhau automatically publishes any data located in the `/outputs` directory (by default) to Filecoin via Estuary. Using the Filecoin network ensures that the data is stored resiliently.

This container is a glorified `cp -r /inputs /outputs` command passed to a Bacalhau job. But it contains some extra bells and whistles to download from other places.

## Usage

### Uploading Data from a URL

```bash
TAG=v0.9.4
URL=https://raw.githubusercontent.com/filecoin-project/bacalhau/main/README.md
bacalhau docker run -e URL=$URL docker.io/bacalhauproject/uploader:$TAG
```

### Uploading Data from S3

**TODO**

## Building

This container is automatically built and published to Github container registry, using the github action located in `.github/workflows/uploader.yml`.