# Python Sensor Manager Usage Guide

This guide demonstrates how to use the new Python-based Sensor Manager tool.

## Installation

No installation is needed. The tool runs directly with Python 3.11+ using `uv` to manage dependencies.

## Basic Usage

The main entry point is the `__main__.py` file in the `sensor_manager` directory. Here's how you run commands:

```bash
# General syntax
python -m sensor_manager <command> [options]
```

## Available Commands

### Generate Docker Compose Configuration

The `compose` command generates a Docker Compose file for the sensor simulation:

```bash
# Basic usage
python -m sensor_manager compose

# With custom settings
python -m sensor_manager compose \
  --output my-docker-compose.yml \
  --config config/config.yaml \
  --sensors-per-city 3 \
  --readings-per-second 2 \
  --anomaly-probability 0.1
```

### Starting Sensor Simulation

The `start` command handles the whole process of starting the sensor simulation:

```bash
# Basic start with defaults
python -m sensor_manager start

# Start with custom settings
python -m sensor_manager start \
  --project-name my-sensors \
  --sensors-per-city 3 \
  --no-diagnostics \
  --config config/config.yaml
```

### Stopping Sensor Simulation

The `stop` command stops all running containers:

```bash
# Stop all containers
python -m sensor_manager stop

# Stop without prompt to remove project reference
python -m sensor_manager stop --no-prompt
```

### Monitoring Sensors

The `monitor` command shows the current status of sensors and data:

```bash
# Show monitoring dashboard
python -m sensor_manager monitor

# Show without colors
python -m sensor_manager monitor --plain

# Use with watch for continuous monitoring
watch -n 5 python -m sensor_manager monitor
```

### Cleaning Up Containers

The `cleanup` command forcibly removes all sensor and uploader containers:

```bash
# Force remove all containers
python -m sensor_manager cleanup
```

## Environment Variables

The following environment variables affect the behavior of the commands:

- `COSMOS_ENDPOINT`: Azure Cosmos DB endpoint URL
- `COSMOS_KEY`: Azure Cosmos DB access key
- `COSMOS_DATABASE`: Database name (default: "SensorData")
- `COSMOS_CONTAINER`: Container name (default: "SensorReadings")
- `SENSORS_PER_CITY`: Number of sensors per city (default: 5)
- `MAX_CITIES`: Maximum number of cities to use (default: 5)
- `READINGS_PER_SECOND`: Number of readings per second (default: 1)
- `ANOMALY_PROBABILITY`: Probability of anomalies (default: 0.05)
- `UPLOAD_INTERVAL`: Interval for uploading data in seconds (default: 30)
- `ARCHIVE_FORMAT`: Format for archived data (default: "Parquet")

These can be set in a `.env` file or exported directly in the shell.

## Example Workflow

Here's a typical workflow using the tool:

```bash
# 1. Start the sensor simulation
python -m sensor_manager start --sensors-per-city 3

# 2. Monitor the sensors
python -m sensor_manager monitor

# 3. Stop the simulation when done
python -m sensor_manager stop

# 4. Clean up if needed
python -m sensor_manager cleanup
```

## Demo Script

Here's a demo script that shows the full workflow:

```bash
#!/bin/bash

# Make sure we have clean environment
python -m sensor_manager cleanup

# Generate Docker Compose file
echo "Generating Docker Compose file..."
python -m sensor_manager compose --sensors-per-city 2

# Start the sensors
echo "Starting sensor simulation..."
export COSMOS_ENDPOINT="your-endpoint-here"
export COSMOS_KEY="your-key-here"
python -m sensor_manager start --no-diagnostics

# Monitor for a while
echo "Monitoring sensors for 30 seconds..."
python -m sensor_manager monitor
sleep 30

# Stop the sensors
echo "Stopping sensor simulation..."
python -m sensor_manager stop --no-prompt

# Clean up
echo "Cleaning up..."
python -m sensor_manager cleanup

echo "Demo complete!"
```

## Comparing with Bash Version

The Python version offers several advantages over the Bash version:

1. **Better code organization**: Clean separation of concerns
2. **Type safety**: Type hints for better IDE support
3. **Better error handling**: More robust error handling
4. **Cross-platform**: Works on all platforms that support Python
5. **Extensibility**: Easier to add new features
6. **Object-oriented design**: Proper encapsulation of functionality