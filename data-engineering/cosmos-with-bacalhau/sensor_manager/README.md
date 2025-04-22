# Sensor Manager (Python Implementation)

A Python-based tool for managing sensor simulation and Cosmos DB integration. This implementation replaces the original Bash script with a more maintainable and cross-platform solution.

> **Note**: The original Bash script (`sensor-manager.sh`) is now deprecated and should not be used. Please use this Python implementation via the `sensor_manager.py` script instead.

## Important Usage Notes

### Container Images

The Sensor Manager follows these important principles:

1. **Always use versioned container images**: We always use specific tagged versions of images from the registry (never "latest").
2. **NEVER use 'latest' tags**: Using "latest" tags can lead to inconsistent behavior and unexpected issues.
3. **NEVER use local builds**: Local builds should only be used for development, not for production deployments.
4. **Always use official registry images**: All images are pulled from the official registry (ghcr.io/bacalhau-project).

### Image Versioning

To ensure reproducible deployments, all commands that work with container images enforce versioned tags:

```bash
# RECOMMENDED WAY - explicitly specify the tag 
python -m sensor_manager start --uploader-tag v20230511
```

Even if you don't specify a tag, the system will never use "latest" tags. By default, it will use:

1. The value of the `UPLOADER_TAG` environment variable if set
2. A hardcoded tag version with timestamp format (`v20230511`) otherwise

If "latest" is specified, it will be automatically replaced with the default version. This ensures we always use tagged versions from the registry.

**IMPORTANT**: You must first build and push the image to the registry with the same tag before using it. Use:

```bash
# Build and push with tag matching what you'll use in sensor manager
cd cosmos-uploader && ./build.sh --tag v20230511 --push

# Then use that same tag with sensor manager
python -m sensor_manager start --uploader-tag v20230511
```

The sensor manager will only look for images in the registry and will never use local images.

## Features

- Generate Docker Compose configuration for sensor simulation
- Start/stop sensor simulation with multiple containers
- Monitor sensor status and data uploads
- Build the CosmosUploader image with versioning
- Clean up Docker containers
- Query SQLite databases with sensor data
- View logs from running containers
- Run system diagnostics to check sensor health
- Reset services with fixed configuration
- Clean data from Cosmos DB

## Installation

The Sensor Manager is designed to be run as a Python module without installation. It requires Python 3.11 or higher and uses [uv](https://github.com/astral-sh/uv) for dependency management.

### Prerequisites

- Python 3.11+
- uv package manager
- Docker
- Docker Compose
- SQLite3 (for database queries)

### Running without Installation

You can run the Sensor Manager directly from its directory:

```bash
# Using uv
python -m sensor_manager <command> [options]

# Using direct execution
./sensor_manager/__main__.py <command> [options]
```

### Required Dependencies

The Sensor Manager automatically installs its dependencies using uv:

- pydantic: Data validation and configuration
- pyyaml: YAML file parsing
- jinja2: Templating for Docker Compose files
- docker: Docker API client
- rich: Terminal output formatting

## Usage

### Available Commands

#### compose

Generate a Docker Compose file for sensor simulation:

```bash
python -m sensor_manager compose [options]
```

Options:
- `--output PATH`: Path to output Docker Compose file
- `--config PATH`: Path to configuration file with city information
- `--sensors-per-city NUM`: Number of sensors per city
- `--readings-per-second NUM`: Number of readings per second
- `--anomaly-probability FLOAT`: Probability of anomalies
- `--upload-interval NUM`: Interval for uploader in seconds
- `--archive-format FORMAT`: Format for archived data
- `--sensor-config PATH`: Path to sensor configuration file
- `--compose-config PATH`: Path to config file for uploader container

#### start

Start sensor simulation with configuration:

```bash
python -m sensor_manager start [options]
```

Options:
- `--no-rebuild`: Skip rebuilding the uploader image
- `--project-name NAME`: Specify a custom project name for Docker Compose
- `--no-diagnostics`: Skip running diagnostics after startup
- `--sensor-config PATH`: Path to sensor configuration file
- `--config PATH`: Path to configuration file with city information
- `--max-cities NUM`: Maximum number of cities to use
- `--sensors-per-city NUM`: Number of sensors per city
- `--readings-per-second NUM`: Number of readings per second
- `--anomaly-probability FLOAT`: Probability of anomalies
- `--upload-interval NUM`: Interval for uploader in seconds
- `--archive-format FORMAT`: Format for archived data
- `--compose-config PATH`: Path to config file for uploader container
- `--tag VERSION`: Tag for the uploader image
- `--no-tag`: Don't tag the uploader image

#### stop

Stop all running containers:

```bash
python -m sensor_manager stop [--no-prompt]
```

Options:
- `--no-prompt`: Skip confirmation prompts

#### monitor

Monitor sensor status and data uploads:

```bash
python -m sensor_manager monitor [--plain]
```

Options:
- `--plain`: Disable colored output

#### cleanup

Force cleanup all containers:

```bash
python -m sensor_manager cleanup
```

#### build

Build the CosmosUploader image:

```bash
python -m sensor_manager build [options]
```

Options:
- `--tag VERSION`: Tag for the uploader image (default: auto-generated timestamp)
- `--no-tag`: Don't tag the uploader image

#### reset

Reset services with fixed configuration:

```bash
python -m sensor_manager reset [options]
```

Options:
- `--no-diagnostics`: Skip running diagnostics after reset
- `--sensor-config PATH`: Path to sensor configuration file

#### query

Query SQLite databases for sensor readings:

```bash
python -m sensor_manager query [options]
```

Options:
- `--all`: Query all databases found in the data directory
- `--list`: List all sensors found in the databases
- `--sensor-id ID`: Query specific sensor by ID

#### diagnostics

Run system diagnostics to check health of sensors and uploaders:

```bash
python -m sensor_manager diagnostics
```

#### logs

View logs from running containers:

```bash
python -m sensor_manager logs [options] [service...]
```

Options:
- `--no-follow`: Don't follow log output
- `service...`: Service names to show logs for (leave empty for all services)

#### clean

Delete all data from Cosmos DB:

```bash
python -m sensor_manager clean [options]
```

Options:
- `--dry-run`: Show what would be deleted without actually deleting
- `--yes`: Skip confirmation prompts
- `--config PATH`: Path to configuration file with Cosmos DB settings

This command uses the `utility_scripts/bulk_delete_cosmos.py` script to clean data from Cosmos DB. It reads database connection information from the specified config file and deletes all data from the specified container. Use the `--dry-run` option to see what would be deleted without actually deleting anything.

### Environment Variables

The Sensor Manager also supports configuration through environment variables:

- `COSMOS_ENDPOINT`: Cosmos DB endpoint URL
- `COSMOS_KEY`: Cosmos DB access key
- `COSMOS_DATABASE`: Cosmos DB database name (default: SensorData)
- `COSMOS_CONTAINER`: Cosmos DB container name (default: SensorReadings)
- `SENSORS_PER_CITY`: Number of sensors per city
- `MAX_CITIES`: Maximum number of cities to use
- `READINGS_PER_SECOND`: Number of readings per second
- `ANOMALY_PROBABILITY`: Probability of anomalies
- `UPLOAD_INTERVAL`: Interval for uploader in seconds
- `ARCHIVE_FORMAT`: Format for archived data
- `CONFIG_FILE`: Configuration file for the uploader container
- `UPLOADER_TAG`: Tag to use for the CosmosUploader image
- `NO_COLORS`: Disable colored output (set to any value to enable)

## Examples

### Generate Docker Compose File

```bash
# Always specify the uploader tag to use (make sure it exists in the registry)
python -m sensor_manager compose --sensors-per-city 10 --readings-per-second 2 --uploader-tag v20230511
```

### Start Simulation

```bash
# Always specify the uploader tag to use (make sure it exists in the registry)
python -m sensor_manager start --project-name my-sensors --max-cities 3 --uploader-tag v20230511
```

### Build a Tagged Image

```bash
# Use timestamp-based versioning format
python -m sensor_manager build --tag v20230511
```

### Monitor with Plain Output

```bash
python -m sensor_manager monitor --plain
```

### View Logs for Specific Services

```bash
python -m sensor_manager logs sensor-amsterdam-1 uploader-amsterdam
```

### Query All Databases

```bash
python -m sensor_manager query --all
```

### Reset Services with Custom Config

```bash
python -m sensor_manager reset --sensor-config config/custom-sensor-config.yaml
```

### Clean Cosmos DB (Dry Run)

```bash
python -m sensor_manager clean --dry-run
```

### Run Diagnostics

```bash
python -m sensor_manager diagnostics
```

## Project Structure

The Sensor Manager follows a modular architecture:

```
sensor_manager/
├── __init__.py                # Package initialization
├── __main__.py                # CLI entry point
├── cli/                       # Command-line interface
│   ├── __init__.py
│   ├── commands/              # Command implementations
│   │   ├── __init__.py
│   │   ├── build.py           # Build command
│   │   ├── clean.py           # Clean Cosmos DB command
│   │   ├── cleanup.py         # Cleanup command
│   │   ├── compose.py         # Compose command
│   │   ├── diagnostics.py     # Diagnostics command
│   │   ├── logs.py            # Logs command
│   │   ├── monitor.py         # Monitor command
│   │   ├── query.py           # Query command
│   │   ├── reset.py           # Reset command
│   │   ├── start.py           # Start command
│   │   └── stop.py            # Stop command
│   └── parser.py              # Argument parser
├── config/                    # Configuration management
│   ├── __init__.py
│   └── models.py              # Pydantic models
├── db/                        # Database operations
│   ├── __init__.py
│   └── sqlite.py              # SQLite operations
├── docker/                    # Docker operations
│   ├── __init__.py
│   ├── compose.py             # Docker Compose operations
│   └── manager.py             # Container management
├── templates/                 # Jinja2 templates
│   └── docker-compose.yml.j2  # Docker Compose template
└── utils/                     # Utility functions
    ├── __init__.py
    └── logging.py             # Logging functions
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.