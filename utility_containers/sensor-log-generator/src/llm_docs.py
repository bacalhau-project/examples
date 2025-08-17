"""
Generate LLM-ready documentation for the sensor simulator.
"""

import json
from pathlib import Path
from typing import Dict, Any


def generate_llm_documentation() -> str:
    """
    Generate comprehensive LLM documentation for the sensor simulator.
    
    Returns:
        str: Complete LLM-ready documentation as a formatted string
    """
    return """# Sensor Log Generator - Complete LLM Reference Documentation

## System Overview

The sensor-log-generator is a sophisticated industrial sensor simulation system that generates realistic environmental sensor data with configurable anomalies. It simulates temperature, humidity, pressure, vibration, and voltage measurements with Gaussian distributions and five types of anomalies (spike, trend, pattern, missing_data, noise).

## Quick Start Commands

```bash
# Generate identity template
uv run main.py --generate-identity

# Run with config and identity files
uv run main.py --config config.yaml --identity node_identity.json

# Docker run
docker run -v $(pwd)/data:/app/data -e SENSOR_ID=SENSOR001 sensor-simulator

# Build Docker image
docker build -t sensor-simulator .

# Run tests
uv run pytest tests/
```

## Database Schema (SQLite)

```sql
CREATE TABLE sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    temperature REAL,
    humidity REAL,
    pressure REAL,
    vibration REAL,
    voltage REAL,
    status_code INTEGER,
    anomaly_flag INTEGER,
    anomaly_type TEXT,
    synced INTEGER DEFAULT 0,
    firmware_version TEXT,
    model TEXT,
    manufacturer TEXT,
    serial_number TEXT,
    manufacture_date TEXT,
    location TEXT,
    latitude REAL,
    longitude REAL,
    original_timezone TEXT,
    deployment_type TEXT,
    installation_date TEXT,
    height_meters REAL,
    orientation_degrees REAL,
    instance_id TEXT,
    sensor_type TEXT
);
```

## Configuration File Format (config.yaml)

```yaml
version: 2  # 1 for legacy, 2 for enhanced features

database:
  path: "data/sensor_data.db"
  batch_size: 100
  retry_attempts: 3
  retry_delay: 1.0
  wal_mode: true
  backup:
    enabled: false
    interval: 3600
    path: "data/backups"

logging:
  level: "INFO"
  file: "logs/sensor.log"
  console: true
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

simulation:
  readings_per_second: 1.0
  runtime_seconds: 3600
  batch_interval: 10
  checkpoint:
    enabled: true
    interval: 60
    file: "data/checkpoint.json"

normal_parameters:
  temperature:
    mean: 22.0
    std_dev: 2.0
    min_value: -10.0
    max_value: 50.0
  humidity:
    mean: 60.0
    std_dev: 10.0
    min_value: 0.0
    max_value: 100.0
  pressure:
    mean: 101325.0
    std_dev: 500.0
    min_value: 95000.0
    max_value: 105000.0
  vibration:
    mean: 0.5
    std_dev: 0.1
    min_value: 0.0
    max_value: 10.0
  voltage:
    mean: 24.0
    std_dev: 0.5
    min_value: 20.0
    max_value: 28.0

anomalies:
  enabled: true
  probability: 0.05
  types:
    spike:
      enabled: true
      probability: 0.3
      multiplier_min: 1.5
      multiplier_max: 3.0
    trend:
      enabled: true
      probability: 0.25
      duration_readings: 20
      max_change_percent: 50
    pattern:
      enabled: true
      probability: 0.2
      frequency: 0.1
      amplitude: 5.0
    missing_data:
      enabled: true
      probability: 0.15
      duration_readings: 5
    noise:
      enabled: true
      probability: 0.1
      noise_factor: 0.15

monitoring:  # v2+ only
  enabled: true
  port: 8080
  host: "0.0.0.0"
  endpoints:
    health: "/healthz"
    metrics: "/metricz"
    status: "/statusz"
    samples: "/samplez"
    db_stats: "/db_stats"

dynamic_reload:  # v2+ only
  enabled: true
  watch_config: true
  watch_identity: true
  check_interval: 5

location:
  use_random: false
  coordinate_variation: 0.001
  update_interval: 3600
```

## Identity File Formats

### Legacy Format (Flat Structure)
```json
{
  "id": "SENSOR_NY_123456",
  "location": "New York",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "timezone": "America/New_York",
  "manufacturer": "SensorTech",
  "model": "TempSensor Pro",
  "firmware_version": "1.2.0"
}
```

### New Format (Nested Structure)
```json
{
  "sensor_id": "SENSOR_CO_DEN_8548",
  "location": {
    "city": "Denver",
    "state": "CO",
    "coordinates": {
      "latitude": 39.733741,
      "longitude": -104.990653
    },
    "timezone": "America/Denver",
    "address": "Denver, CO, USA"
  },
  "device_info": {
    "manufacturer": "DataLogger",
    "model": "AirData-Plus",
    "firmware_version": "DLG_v3.15.21",
    "serial_number": "DataLogger-578463",
    "manufacture_date": "2025-03-24"
  },
  "deployment": {
    "deployment_type": "mobile_unit",
    "installation_date": "2025-03-24",
    "height_meters": 8.3,
    "orientation_degrees": 183
  },
  "metadata": {
    "instance_id": "i-04d485582534851c9",
    "sensor_type": "environmental_monitoring"
  }
}
```

## Environment Variables

- `CONFIG_FILE`: Override config file path
- `IDENTITY_FILE`: Override identity file path
- `SENSOR_ID`: Override sensor identifier
- `SENSOR_LOCATION`: Override location string
- `SQLITE_TMPDIR`: SQLite temp directory for containers

## Measurement Types and Ranges

| Measurement | Unit | Default Mean | Default StdDev | Min | Max |
|------------|------|--------------|----------------|-----|-----|
| Temperature | °C | 22.0 | 2.0 | -10.0 | 50.0 |
| Humidity | % | 60.0 | 10.0 | 0.0 | 100.0 |
| Pressure | Pa | 101325.0 | 500.0 | 95000.0 | 105000.0 |
| Vibration | mm/s² | 0.5 | 0.1 | 0.0 | 10.0 |
| Voltage | V | 24.0 | 0.5 | 20.0 | 28.0 |

## Anomaly Types

1. **Spike**: Sudden value changes (1.5x-3x multiplier)
2. **Trend**: Gradual drift over time (up to 50% change)
3. **Pattern**: Sinusoidal patterns applied to readings
4. **Missing Data**: Simulated sensor outages
5. **Noise**: Increased random variation (10-15% noise factor)

## API Endpoints (v2 Config)

- `GET /healthz`: Health check (200 OK or 503 Service Unavailable)
- `GET /metricz`: JSON metrics (total readings, anomalies, errors)
- `GET /statusz`: Current status and configuration
- `GET /samplez`: Last 10 sensor readings
- `GET /db_stats`: Database statistics and performance metrics

## Collector Script (collector.py)

Aggregates data from multiple sensor databases:
- Scans directories recursively for .db files
- Batch collection with configurable size
- Sync tracking with `synced` flag
- HTTP POST to central API endpoint
- Automatic retry with exponential backoff

Usage:
```bash
uv run collector.py --data-dir ./data --api-url http://api.example.com/ingest --batch-size 1000
```

## Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  sensor-simulator:
    image: sensor-simulator:latest
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - SENSOR_ID=SENSOR_001
      - SENSOR_LOCATION=Production Floor A
      - SQLITE_TMPDIR=/tmp
    restart: unless-stopped
```

## Bacalhau Job Specification

```yaml
name: sensor-data-generator
type: batch
count: 1
tasks:
  - name: generate-sensor-data
    engine:
      type: docker
      params:
        image: sensor-simulator:latest
        entrypoint: ["python", "main.py"]
        workingDirectory: /app
        environmentVariables:
          - SENSOR_ID=BACALHAU_SENSOR_001
          - SQLITE_TMPDIR=/tmp
    resources:
      cpu: "1"
      memory: "1Gi"
    timeouts:
      executionTimeout: 3600
    resultPaths:
      - name: sensor-data
        path: /app/data
```

## Code Structure

```
sensor-log-generator/
├── main.py                 # Entry point
├── collector.py            # Data aggregation script
├── src/
│   ├── simulator.py        # Core simulation engine
│   ├── database.py         # SQLite operations
│   ├── anomaly.py          # Anomaly generation
│   ├── config.py           # Configuration management
│   ├── location.py         # Location/GPS handling
│   ├── monitor.py          # HTTP monitoring server
│   └── enums.py            # Valid enumeration values
├── tests/                  # Comprehensive test suite
├── config/
│   ├── config.yaml         # Main configuration
│   └── node-identity.json  # Sensor identity
└── data/                   # Database and checkpoint files
```

## Python Dependencies

```toml
[dependencies]
numpy = ">=1.24.0"
psutil = ">=5.9.0"
pyyaml = ">=6.0"
requests = ">=2.31.0"
pydantic = ">=2.0.0"
tenacity = ">=8.2.0"
```

## Command-Line Arguments

```
main.py [options]
  --config PATH          Config file path (default: config/config.yaml)
  --identity PATH        Identity file path (default: config/identity.json)
  --output-schema        Output database schema as JSON
  --generate-identity    Generate identity template
  --llm-docs            Output this LLM documentation
```

## Performance Characteristics

- Batch insert: 100 records per transaction
- Memory usage: ~50-100MB typical
- CPU usage: <5% for 1 reading/second
- Database size: ~1MB per 10,000 readings
- SQLite WAL mode for concurrent access
- Thread-safe operations

## Error Handling

- Automatic retry with exponential backoff
- Graceful degradation on sensor failures
- Checkpoint recovery on restart
- Database corruption detection
- Configuration validation with Pydantic
- Comprehensive logging at all levels

## Testing

Run complete test suite:
```bash
uv run pytest tests/ -v
```

Test coverage includes:
- Anomaly generation algorithms
- Configuration validation
- Database operations
- Checkpoint/recovery
- Corruption handling
- Location generation
- Monitor API endpoints
- Simulator core logic

## Use Cases

1. **Development**: Mock sensor data for application development
2. **Testing**: Generate test data for data pipelines
3. **Training**: ML model training with realistic sensor patterns
4. **Monitoring**: Test monitoring and alerting systems
5. **Load Testing**: High-volume data generation
6. **Anomaly Detection**: Train anomaly detection algorithms
7. **Demo/POC**: Demonstrate data processing capabilities

## Advanced Features

- Dynamic configuration reloading without restart
- Random city selection from 50+ major cities
- GPS coordinate fuzzing for realistic variation
- Population-based city weighting
- Firmware-specific anomaly patterns
- Manufacturer-specific behavior modeling
- Thread-safe concurrent operations
- Memory-efficient batch processing
- Container-optimized SQLite settings

## Integration Points

- HTTP REST API for monitoring
- SQLite database for persistence
- JSON checkpoint files for recovery
- Syslog-compatible logging
- Environment variable configuration
- Docker volume mounts
- Kubernetes ConfigMaps/Secrets
- Bacalhau distributed compute

This sensor simulator provides enterprise-grade industrial sensor data generation with sophisticated anomaly patterns, comprehensive configuration, and production-ready monitoring capabilities."""


def save_llm_documentation(output_path: str = "llm_docs.txt") -> None:
    """
    Save the LLM documentation to a file.
    
    Args:
        output_path: Path where the documentation should be saved
    """
    docs = generate_llm_documentation()
    Path(output_path).write_text(docs)
    print(f"LLM documentation saved to {output_path}")


def print_llm_documentation() -> None:
    """
    Print the LLM documentation to stdout.
    """
    print(generate_llm_documentation())