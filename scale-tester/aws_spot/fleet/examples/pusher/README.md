# Pusher Job Example

This example demonstrates how to set up a job that pushes events to a monitoring system. It's useful for monitoring the health and performance of your Bacalhau nodes.

## Files

- `job.yaml` - Main job configuration for the event pusher
- `env.yaml` - Environment configuration for the pusher
- `env.txt` - Environment variables (create from env.txt.example)
- `env.txt.b64` - Base64 encoded environment variables

## Setup

1. Configure environment:
```bash
# Copy example config
cp env.txt.example env.txt

# Edit with your settings
vim env.txt

# Create base64 encoded version
base64 env.txt > env.txt.b64
```

2. Deploy the job:
```bash
# Create the job
bacalhau create job.yaml

# Verify it's running
bacalhau list
```

## Configuration

The pusher job requires the following environment variables:

- `PUSHER_ENDPOINT` - Endpoint to push events to
- `PUSHER_TOKEN` - Authentication token
- `PUSHER_INTERVAL` - Push interval in seconds
- `PUSHER_BATCH_SIZE` - Number of events per batch

See `env.txt.example` for a complete list of options.
