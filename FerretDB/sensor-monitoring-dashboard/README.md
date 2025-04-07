# Sensor Monitoring Dashboard

- **Environment Variables:** Sets `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` and `MONGODB_IP` via build arguments.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your machine.
- (Optional) [Docker Compose](https://docs.docker.com/compose/install/) if you want to use the provided `docker-compose.yml`.

## Files

- **Dockerfile:** Contains instructions for building the Docker image.
- **package.json** and **package-lock.json:** NPM configuration files for the Next.js application.
- 
## Environment Variables

Before building the Docker image, make sure to set the required environment variables:

### 1. `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`

- This variable is required to use Google Maps services in the frontend.
- You need to [generate an API key from the Google Cloud Console](https://console.cloud.google.com/apis/credentials) and enable the **Maps JavaScript API**.
- Paste your key into the `.env` file or pass it as a build argument.

### 2. `MONGODB_IP`

- Set this to the IP address or hostname of your FerretDB Node.
- Example: `127.0.0.1`.

#### Create a .env file in the project directory with the following content:
```dotenv
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your_google_maps_api_key
MONGODB_IP=your_mongodb_ip
```

## Start the container using Docker Compose
```bash
docker compose up
```
