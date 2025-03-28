# Frontend Setup with Bacalhau Environment

This project uses Bacalhau as its backend service. The following instructions will guide you through setting up your environment, installing dependencies, and running the development server.

## Prerequisites

- **Node.js and npm:** Ensure that you have Node.js and npm installed on your machine.
- **Local Bacalhau Installation:** For the application to work, you need to have Bacalhau installed locally. Follow the instructions provided in the [Bacalhau documentation](https://docs.bacalhau.org/) to install it.

## Environment Setup

Before starting the frontend, you must set up your Bacalhau environment by configuring the following environment variables:

```bash
export BACALHAU_API_HOST=api.your-expanso.cloud
export BACALHAU_API_TLS_USETLS=true
```

Also setup your cloud token to the bacalhau config
