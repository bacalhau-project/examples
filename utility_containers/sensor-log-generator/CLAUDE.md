# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands
- Build Docker image: `docker build -t sensor-simulator .`
- Run with Docker: `docker run -v $(pwd)/data:/app/data -e SENSOR_ID=CUSTOM001 -e SENSOR_LOCATION="Custom Location" sensor-simulator`
- Run directly: `uv run main.py --config config.yaml --identity node_identity.json`
- Generate identity template: `uv run main.py --generate-identity`
- Build multi-platform images: `./build.sh`
- Test container: `./test_container.sh`
- Run tests: `uv run pytest tests/`
- Keep existing database on startup: `docker run -v $(pwd)/data:/app/data -e PRESERVE_EXISTING_DB=true sensor-simulator`

## Code Style Guidelines
- Python 3.11+ with type annotations (from typing import Dict, Optional, etc.)
- Google-style docstrings for functions and classes
- 4-space indentation following PEP 8
- Modular architecture with clear separation of concerns
- Exception handling with specific error logging
- Configuration loaded from YAML and JSON files
- Environment variables prefixed with SENSOR_
- Comprehensive error handling with retry logic and graceful degradation
- Logging with different levels and both file and console output

## Identity File Formats
The system supports both legacy flat and new nested identity formats:

### Legacy Format (backward compatible)
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

### New Format (enhanced metadata)
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