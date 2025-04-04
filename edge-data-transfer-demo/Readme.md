# Edge Data Transfer Demo

## Requirements

- [Docker](https://www.docker.com/get-started) (version 20.10 or higher)
- A `.env` file containing the necessary environment variables (see Configuration section)

## Configuration

Before running the project, create a `.env` file in the root directory (where the `docker-compose.yml` file is located) with the following content:

```env
BACALHAU_TOKEN=your_token
BACALHAU_API_HOST=api_host
BACALHAU_API_TLS_USETLS=true
```

### Note: You can obtain the `BACALHAU_TOKEN` and `BACALHAU_API_HOST` from Expanso Cloud.

# Building and Running
Build the images and start the containers:

Run the following command in the project’s root directory:
```bash
docker-compose up
```

Access the application:
Once the application is running, open your browser and navigate to:
http://localhost:3000
