# 🌐 Access Log Generator

A sophisticated, highly configurable tool that generates realistic web server access logs using state machine-based user behavior simulation. Perfect for testing log analysis tools, developing monitoring systems, stress testing data pipelines, or learning about web traffic patterns.

## Key Features

- **Realistic User Behavior**: State machine simulates authentic user sessions (login, browsing, logout, abandonment)
- **NCSA Format**: Generates standard Combined Log Format compatible with most analysis tools
- **Configurable Traffic Patterns**: Define hourly/daily traffic variations
- **Error Simulation**: Realistic 4xx/5xx error rates by page type
- **Pre-warming**: Generate historical data for immediate testing
- **High Performance**: Token bucket rate limiting for precise throughput control
- **Log Rotation**: Built-in rotation with compression support
- **Multi-format Output**: Access logs, error logs, and system logs

## Backstory

This container/project was born out of a need to create realistic, high-quality web server access logs for testing and development purposes. As we were trying to stress test [Bacalhau](https://bacalhau.org) and [Expanso](https://expanso.io), we needed high volumes of realistic access logs so that we could show how flexible and scalable they were. I looked around for something simple, but configurable, to generate this data couldn't find anything.  Thus, this container/project was born.

## 🚀 Quick Start

### Run with Docker (recommended):
```bash
# Using docker compose (recommended)
docker compose up

# Or run directly with docker
docker run -v ./logs:/var/log/app -v ./config:/app/config \
  -e LOG_GENERATOR_CONFIG_PATH=/app/config/docker-config.yaml \
  ghcr.io/bacalhau-project/access-log-generator:latest

# Run in detached mode
docker compose up -d

# Run with environment variable overrides
docker run -v ./logs:/var/log/app \
  -e RATE_PER_SECOND=0.5 \
  -e PRE_WARM=false \
  -e DEBUG=true \
  ghcr.io/bacalhau-project/access-log-generator:latest
```

### Run directly with Python (3.12+):
```bash
# Use the default config (writes to ./logs directory)
./access-log-generator.py config/config.yaml

# Or run without specifying config (uses default path)
./access-log-generator.py

# With environment variable overrides
RATE_PER_SECOND=0.1 PRE_WARM=false ./access-log-generator.py
```

### Available Config Files:
- `config/config.yaml` - Default config for local development (writes to ./logs)
- `config/docker-config.yaml` - Config for Docker containers (writes to /var/log/app)
- `config/sample_config.yaml` - Example with extended options and documentation

### Build the container:
```bash
# Multi-platform build (AMD64 and ARM64)
./build.sh
```

## 📝 Configuration

The generator uses a comprehensive YAML configuration. Configuration can be provided via:

1. Base64-encoded YAML in `LOG_GENERATOR_CONFIG_YAML_B64` env var
2. Direct YAML in `LOG_GENERATOR_CONFIG_YAML` env var  
3. File path in `LOG_GENERATOR_CONFIG_PATH` env var
4. Command-line argument
5. Default: `config/config.yaml`

### Environment Variable Overrides

These environment variables override values in the configuration file:

| Variable | Description | Example |
|----------|-------------|---------|
| `RATE_PER_SECOND` | Override the session generation rate | `0.5` (decimal allowed) |
| `PRE_WARM` | Enable/disable pre-warming | `true`, `false`, `1`, `0` |
| `DEBUG` | Enable/disable debug output | `true`, `false`, `1`, `0` |
| `LOG_DIR_OVERRIDE` | Override the log output directory | `/tmp/logs` |

### Key Configuration Sections:

```yaml
output:
  directory: "/var/log/app"  # Where to write logs
  rate: 2                    # Sessions per second (NOT logs per second!)
  debug: false               # Show debug output
  pre_warm: false            # Generate 24h of historical data
  log_rotation:
    enabled: true
    max_size_mb: 100         # Rotate when file reaches this size
    when: "h"                # or "midnight" for daily
    interval: 1
    backup_count: 5
    compress: true           # gzip old logs

# User behavior state machine
state_transitions:
  START:
    LOGIN: 0.7             # 70% of users log in
    DIRECT_ACCESS: 0.3     # 30% go directly to content
  LOGIN:
    BROWSING: 0.9          # 90% proceed to browse
    ABANDON: 0.1           # 10% abandon after login
  BROWSING:
    LOGOUT: 0.4            # 40% log out properly
    ABANDON: 0.3           # 30% abandon session
    ERROR: 0.05            # 5% hit errors
    BROWSING: 0.25         # 25% keep browsing

# Page navigation patterns
navigation:
  home:
    "/": 0.2
    "/about": 0.3
    "/products": 0.4
    "/search": 0.1

# Error simulation
error_rates:
  global_500_rate: 0.02    # 2% server errors
  product_404_rate: 0.1    # 10% product not found
  cart_abandonment_rate: 0.5
  high_error_pages:
    - path: "/api/flaky"
      error_rate: 0.3      # 30% error rate

# Session parameters
session:
  min_browsing_duration: 10   # Minimum session duration in seconds
  max_browsing_duration: 300  # Maximum session duration in seconds
  page_view_interval: 5       # Average time between page views

# Traffic patterns (hourly multipliers)
traffic_patterns:
  - time: "0-6"
    multiplier: 0.1        # Night: 10% of base rate
  - time: "6-9"
    multiplier: 0.3        # Morning: 30% of base rate
  - time: "9-12"
    multiplier: 0.7        # Late morning: 70% of base rate
  - time: "12-15"
    multiplier: 1.0        # Afternoon: 100% of base rate
  - time: "15-18"
    multiplier: 0.8        # Early evening: 80% of base rate
  - time: "18-21"
    multiplier: 0.5        # Evening: 50% of base rate
  - time: "21-24"
    multiplier: 0.2        # Late night: 20% of base rate
```

## 🔍 Understanding the Rate Parameter

**IMPORTANT**: The `rate` parameter controls **sessions per second**, not logs per second!

- `rate: 2` means 2 new user sessions start per second
- Each session generates multiple log entries over its lifetime
- A session can last 10-300 seconds (configurable)
- Each session generates a log entry every 2-10 seconds during browsing

**Example calculation with default settings:**
- Rate: 2 sessions/second
- Average session duration: ~155 seconds
- Page views per session: ~25 (one every ~6 seconds)
- Steady-state concurrent sessions: ~310
- **Actual log output: ~50-100 logs/second**

To reduce log volume:
- Lower the `rate` (e.g., `0.1` for minimal traffic)
- Reduce `max_browsing_duration`
- Increase `page_view_interval`

## 📊 Generated Logs

The generator creates three types of logs:

### 1. Access Log (`access.log`)
NCSA Combined Log Format compatible with Apache/Nginx:
```
192.168.1.100 - john_doe [10/Oct/2024:13:55:36 +0000] "GET /products/laptop HTTP/1.1" 200 5432 "http://www.example.com/index.html" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### 2. Error Log (`error.log`)
Apache-style error format for 4xx/5xx responses:
```
[Thu Oct 10 13:55:36.123456 2024] [error] [client 192.168.1.100] File does not exist: /var/www/html/favicon.ico
```

### 3. System Log (`system.log`)  
Internal generator status and session tracking:
```
2024-10-10T13:55:36.123456Z INFO session_manager New session started: session_id=abc123
```

### Log Schema Documentation

Generate detailed schema documentation:
```bash
# JSON format
python log_schema_outputter.py --format json

# Markdown format
python log_schema_outputter.py --format markdown --output schemas.md

# YAML format
python log_schema_outputter.py --format yaml
```

## 🔧 Advanced Usage

### Environment Variables
```bash
# Provide config as base64-encoded YAML
export LOG_GENERATOR_CONFIG_YAML_B64=$(base64 < my-config.yaml)

# Or provide config directly
export LOG_GENERATOR_CONFIG_YAML="output:\n  rate: 100\n  directory: /logs"

# Or specify config file path
export LOG_GENERATOR_CONFIG_PATH=/path/to/config.yaml

# Override specific settings
export RATE_PER_SECOND=0.5
export PRE_WARM=false
export DEBUG=true
export LOG_DIR_OVERRIDE=/custom/log/path
```

### Docker Compose
```yaml
version: '3.8'
services:
  log-generator:
    image: ghcr.io/bacalhau-project/access-log-generator:latest
    volumes:
      - ./logs:/var/log/app
      - ./config:/app/config
    environment:
      - LOG_GENERATOR_CONFIG_PATH=/app/config/custom-config.yaml
      - RATE_PER_SECOND=0.1
      - PRE_WARM=false
```

### Performance Tuning
- **High Volume**: Increase `rate` for more concurrent sessions
- **Low Volume**: Use decimal rates like `0.1` for minimal traffic
- **Disk Space**: Built-in monitoring cleans old logs when space is low
- **Memory**: Batch writes during pre-warm minimize memory usage
- **Pre-warming**: Generates 24 hours of historical data at maximum speed

## 🧪 Testing

Run the unit tests:
```bash
# Run all unit tests (excludes integration tests by default)
pytest tests/

# Run all tests including integration tests
pytest tests/ -m ""

# Run only unit tests explicitly
pytest tests/ -m "not integration"

# Run with coverage
python -m coverage run -m pytest tests/
python -m coverage report

# Run specific test class
python -m unittest tests.test_access_log_generator.TestNCSALogFormat -v
```

### Test Coverage

The test suite includes:
- **Configuration validation** - Ensures valid YAML structure and values
- **NCSA format compliance** - Validates log output matches standard format
- **Traffic patterns** - Tests hourly multiplier logic
- **Session states** - Verifies state machine implementation

## 📈 Analyzing Generated Logs

The NCSA format works with standard tools:

```bash
# Apache/Nginx log analyzers
goaccess access.log

# AWStats
awstats.pl -config=mysite -LogFile=access.log

# Simple grep analysis
grep ' 404 ' access.log | wc -l  # Count 404s
grep ' 500 ' access.log | wc -l  # Count 500s

# GoAccess real-time analyzer
tail -f access.log | goaccess -
```

## 🏗️ Architecture

### State Machine
The generator uses a sophisticated state machine to simulate realistic user behavior:
- **START** → LOGIN (70%) or DIRECT_ACCESS (30%)
- **LOGIN** → BROWSING (90%) or ABANDON (10%)  
- **BROWSING** → Continue browsing, logout, abandon, or error
- **ERROR/ABANDON/LOGOUT** → END

### Rate Control
Token bucket algorithm ensures precise session generation rates with configurable traffic patterns. The actual log output rate depends on:
- Number of concurrent sessions
- Session duration
- Page view frequency
- Traffic pattern multipliers

### Session Management
- Unique session IDs track user journeys
- Realistic session durations (configurable)
- Page view intervals (configurable)
- Concurrent session processing

### Disk Space Management
- Automatic monitoring of available disk space
- Deletes oldest log files when space falls below 1GB
- Configurable check intervals (default: 5 minutes)

## 🤝 Contributing

Contributions welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit pull requests
- Share your use cases
- Add new traffic patterns or behaviors

## 📜 License

MIT License - feel free to use in your projects!