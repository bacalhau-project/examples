# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Generator
```bash
# Run with default config (config/config.yaml)
./access-log-generator.py

# Run with explicit config
python access-log-generator.py config/config.yaml

# Run with Docker
docker run -v ./logs:/var/log/app -v ./config:/app/config \
  docker.io/bacalhauproject/access-log-generator:latest
```

### Testing
```bash
# Run all unit tests
python -m unittest discover tests/ -v

# Run with pytest
pytest tests/ -v

# Run specific test class
python -m unittest tests.test_access_log_generator.TestNCSALogFormat -v

# Run with coverage
python -m coverage run -m pytest tests/
python -m coverage report
```

### Building and Publishing
```bash
# Build multi-platform Docker image
./build.sh

# Build without pushing
./build.sh --no-push

# Build specific platform
docker buildx build --platform linux/amd64 -t access-log-generator .
```

### Schema Documentation
```bash
# Generate log schema documentation
python log_schema_outputter.py --format json
python log_schema_outputter.py --format markdown --output schemas.md
python log_schema_outputter.py --format yaml
```

## Architecture Overview

### Core Components

1. **State Machine (SessionState)**: Simulates realistic user behavior through states:
   - START → LOGIN or DIRECT_ACCESS
   - LOGIN → BROWSING or ABANDON
   - BROWSING → Continue, LOGOUT, ABANDON, or ERROR
   - Terminal states: END

2. **AccessLogGenerator**: Main class that orchestrates log generation
   - Manages user sessions with unique IDs
   - Implements token bucket rate limiting
   - Handles pre-warming (historical data generation)
   - Monitors disk space and cleans old logs

3. **Configuration System**:
   - Validates YAML configuration structure
   - Supports multiple input methods (file, env vars, base64)
   - Traffic patterns use list format: `[{time: "0-6", multiplier: 0.1}, ...]`
   - Hours must be 0-23 (not 24)

4. **Log Formats**:
   - **access.log**: NCSA Combined Format
   - **error.log**: Apache-style error format
   - **system.log**: Custom format for generator status

### Key Design Patterns

1. **Generator Pattern**: User sessions yield log entries over time
2. **Token Bucket**: Precise rate limiting for log generation
3. **State Machine**: Realistic user behavior simulation
4. **Batch Processing**: Efficient pre-warm data generation

### Important Implementation Details

- Uses `uv` for dependency management (inline script dependencies)
- Python 3.12+ required
- Faker library generates realistic IPs and user agents
- Thread-based disk space monitoring
- Automatic log rotation with gzip compression
- Real-time session processing with configurable delays

### Configuration Validation Rules

- All sections required: output, state_transitions, navigation, error_rates, session, traffic_patterns
- State transition probabilities must sum to 1.0
- Traffic patterns must cover all 24 hours
- Time ranges use 0-23 format (midnight = 0)
- Rate must be positive number
- Directory paths must be strings

### Testing Approach

- Mock external dependencies (pytz, faker) for unit tests
- Use tempfile for test output directories
- Validate configuration structure and constraints
- Test edge cases (invalid rates, missing sections)
- Clean up test artifacts in tearDown methods