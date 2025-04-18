# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands
- Build Docker image: `docker build -t sensor-simulator .`
- Run with Docker: `docker run -v $(pwd)/data:/app/data -e SENSOR_ID=CUSTOM001 -e SENSOR_LOCATION="Custom Location" sensor-simulator`
- Run directly: `python main.py --config config.yaml --identity node_identity.json`
- Build multi-platform images: `./build.sh`
- Test container: `./test_container.sh`

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