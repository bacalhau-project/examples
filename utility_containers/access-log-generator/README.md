# 🌐 Access Log Generator

A smart, configurable tool that generates realistic web server access logs. Perfect for testing log analysis tools, developing monitoring systems, or learning about web traffic patterns.

## 🚀 Quick Start

1. Run with Docker (recommended):
```bash
# Pull and run the latest version
docker run -v ./logs:/var/log/app -v ./config:/app/config \
  docker.io/bacalhauproject/access-log-generator:latest
```

2. Or run directly with Python (3.11+):
```bash
# Install dependencies
pip install -r requirements.txt

# Run the generator
python access-log-generator.py config/config.yaml
```

## 📝 Configuration

The generator uses a YAML config file to control behavior. Here's a simple example:

```yaml
output:
  directory: "/var/log/app"  # Where to write logs
  rate: 10                   # Base logs per second
  debug: false              # Show debug output
  pre_warm: true           # Generate historical data on startup

# How users move through your site
state_transitions:
  START:
    LOGIN: 0.7             # 70% of users log in
    DIRECT_ACCESS: 0.3     # 30% go directly to content
  
  BROWSING:
    LOGOUT: 0.4            # 40% log out properly
    ABANDON: 0.3           # 30% abandon session
    ERROR: 0.05            # 5% hit errors
    BROWSING: 0.25         # 25% keep browsing

# Traffic patterns throughout the day
traffic_patterns:
  - time: "0-6"            # Midnight to 6am
    multiplier: 0.2        # 20% of base traffic
  - time: "7-9"            # Morning rush
    multiplier: 1.5        # 150% of base traffic
  - time: "10-16"          # Work day
    multiplier: 1.0        # Normal traffic
  - time: "17-23"          # Evening
    multiplier: 0.5        # 50% of base traffic
```

## 📊 Generated Logs

The generator creates three types of logs:
- `access.log` - Main NCSA-format access logs
- `error.log` - Error entries (4xx, 5xx status codes)
- `system.log` - Generator status messages

Example access log entry:
```
180.24.130.185 - - [20/Jan/2025:10:55:04] "GET /products HTTP/1.1" 200 352 "/search" "Mozilla/5.0"
```

## 🛠 Features

- Realistic user behavior simulation
- Time-based traffic patterns
- Automatic log rotation
- Error scenario injection
- Session tracking
- Configurable rates and patterns

## 🔧 Advanced Usage

Override the log directory:
```bash
python access-log-generator.py config.yaml --log-dir-override ./logs
```

Common configurations:
```bash
# High traffic simulation
docker run -v ./logs:/var/log/app -e RATE=100 access-log-generator

# Development testing
docker run -v ./logs:/var/log/app -e DEBUG=true access-log-generator
```

## 📈 Analyzing Logs

The generated logs work great with standard analysis tools:

```bash
# Quick stats with DuckDB
python logs/test_duckdb_queries.py

# Or use with any log analyzer
tail -f logs/access.log | goaccess
```

## 🤝 Contributing

Contributions welcome! Feel free to:
- Open issues for bugs or suggestions
- Submit pull requests
- Share your use cases

## 📜 License

MIT License - feel free to use in your projects! 