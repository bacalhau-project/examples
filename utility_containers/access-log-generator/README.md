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

1. Run with Docker (recommended):

```bash
# Using docker compose (recommended)
docker compose up

# Or run directly with docker
docker run -v ./logs:/var/log/app -v ./config:/app/config \
  ghcr.io/bacalhau-project/access-log-generator:latest
```

1. Or run directly with Python (3.11+):

```bash
# Run the generator
uv run access-log-generator.py
```

## 📝 Configuration

The generator uses a comprehensive YAML configuration. Configuration can be provided via:

1. Base64-encoded YAML in `LOG_GENERATOR_CONFIG_YAML_B64` env var
2. Direct YAML in `LOG_GENERATOR_CONFIG_YAML` env var  
3. File path in `LOG_GENERATOR_CONFIG_PATH` env var
4. Command-line argument
5. Default: `config/config.yaml`

### Key Configuration Sections:

```yaml
output:
  directory: "/var/log/app"  # Where to write logs
  rate: 10                   # Base logs per second
  debug: false              # Show debug output
  pre_warm: true           # Generate 24h of historical data
  log_rotation:
    enabled: true
    when: "midnight"       # or "H" for hourly
    interval: 1
    backup_count: 7
    compress: true        # gzip old logs

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
  index:
    "/about": 0.3
    "/products": 0.5
    "/search": 0.2
  products:
    "/product/{id}": 0.6
    "/cart": 0.3
    "/search": 0.1

# Error simulation
error_rates:
  global_500_rate: 0.001   # 0.1% server errors
  product_404_rate: 0.05   # 5% product not found
  cart_abandonment_rate: 0.3
  high_error_pages:
    "/api/flaky": 0.2     # 20% error rate

# Traffic patterns (hourly multipliers)
traffic_patterns:
  hourly:
    "0-6": 0.1             # Night: 10% traffic
    "6-9": 0.8             # Morning: 80% traffic  
    "9-17": 1.0            # Work day: 100% traffic
    "17-22": 0.6           # Evening: 60% traffic
    "22-24": 0.3           # Late night: 30% traffic
```

## 📊 Generated Logs

The generator creates three types of logs:

- `access.log` - Main NCSA-format access logs
- `error.log` - Error entries (4xx, 5xx status codes)
- `system.log` - Generator status messages

Example access log entry:

```text
180.24.130.185 - - [20/Jan/2025:10:55:04] "GET /products HTTP/1.1" 200 352 "/search" "Mozilla/5.0"
```

## 🔧 Advanced Usage

Override the log directory:

```bash
uv run access-log-generator.py config.yaml --log-dir-override ./logs
```

### Docker Compose
```yaml
version: '3.8'
services:
  log-generator:
    image: docker.io/bacalhauproject/access-log-generator:latest
    volumes:
      - ./logs:/var/log/app
      - ./config:/app/config
    environment:
      - LOG_GENERATOR_CONFIG_PATH=/app/config/custom-config.yaml
```

### Performance Tuning
- **High Volume**: Increase `rate` and use pre-warming for bulk generation
- **Disk Space**: Built-in monitoring cleans old logs when space is low
- **Memory**: Batch writes during pre-warm minimize memory usage

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
# Quick stats with DuckDB
uv run test_duckdb_queries.py
```

## 🏗️ Architecture

### State Machine
The generator uses a sophisticated state machine to simulate realistic user behavior:
- **START** → LOGIN (70%) or DIRECT_ACCESS (30%)
- **LOGIN** → BROWSING (90%) or ABANDON (10%)  
- **BROWSING** → Continue browsing, logout, abandon, or error
- **ERROR/ABANDON/LOGOUT** → END

### Rate Control
Token bucket algorithm ensures precise log generation rates with configurable traffic patterns.

### Session Management
- Unique session IDs track user journeys
- Realistic session durations (30s - 5min default)
- Page view intervals (2-10s default)

## 🤝 Contributing

Contributions welcome! Feel free to:

- Open issues for bugs or suggestions
- Submit pull requests
- Share your use cases
- Add new traffic patterns or behaviors

## 📜 License

MIT License - feel free to use in your projects!
