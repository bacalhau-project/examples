# Frontend Setup with Bacalhau Environment

This project uses Bacalhau as its backend service. The following instructions will guide you through setting up your environment, installing dependencies, and running the development server.

## Prerequisites for local development

- **Node.js and npm:** Ensure that you have Node.js and npm installed on your machine.
- **Local Bacalhau Installation:** For the application to work, you need to have Bacalhau installed locally. Follow the instructions provided in the [Bacalhau documentation](https://docs.bacalhau.org/) to install it.

## Environment Setup

Before starting the frontend, you must set up your Bacalhau environment by configuring the following environment variables:

```bash
export BACALHAU_API_HOST=api.your-expanso.cloud
export BACALHAU_API_TLS_USETLS=true
export BACALHAU_TOKEN=token
```

## Building the Docker Image
To build the Docker image for the application, run the following command in the project's root directory:
```bash
docker build -t edge-demo-frontend .
```

## Running the Application with Docker
After building the image, you can run the application in a Docker container by executing:
```bash
docker run --name edge-transfer-demo -p 3000:3000 \
  -e BACALHAU_API_HOST=<insert_api_address> \
  -e BACALHAU_API_TLS_USETLS=true \
  -e BACALHAU_TOKEN=<insert_token> \
  edge-demo-frontend
```

## Important Note
Before running the container, ensure that:

The `BACALHAU_API_HOST` environment variable is set with a valid API address.
The `BACALHAU_TOKEN` environment variable is set with a valid authentication token.


