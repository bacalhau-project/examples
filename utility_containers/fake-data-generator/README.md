# Bacalhau Data Generator

A flexible synthetic data generator Docker image designed for Bacalhau demos and testing. Generate realistic data for distributed data warehouses, log processing, and security analysis use cases.

## Features

- Multiple data types: transactions, security events, web access logs, and customer data
- Time-series data generation with business hours patterns
- Regional data distribution with geographic accuracy
- Configurable output formats (JSON, JSONL, CSV)
- Consistent customer profiles across events
- Product catalog with categorized items
- Command-line interface
- Docker-based deployment

## Quick Start

### Building the Image

```bash
docker build -t data-generator .
```

### Basic Usage

1. Generate batch data:

```bash
# Generate 1000 transaction events
docker run -v $(pwd)/data:/data data-generator generate -n 1000 -t transaction

# Generate all types of events
docker run -v $(pwd)/data:/data data-generator generate -n 500
```

2. Generate time-series data:

```bash
# Generate events for last 7 days
docker run -v $(pwd)/data:/data data-generator generate -d 7 -t transaction

# Generate events for specific date range
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    --start-date 2024-01-01 \
    --end-date 2024-01-31

# Generate daily files for last week
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    -d 7 \
    --rotate-interval day

# Generate hourly files for last 2 days
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    -d 2 \
    --rotate-interval hour
```

3. Generate streaming data:

```bash
# Generate continuous stream at 2 events per second
docker run -v $(pwd)/data:/data data-generator stream \
    --rate 2 \
    --type transaction

# Generate stream for 5 minutes
docker run -v $(pwd)/data:/data data-generator stream \
    --rate 1 \
    --duration 300 \
    --type all
```

4. Generate events for specific regions:

```bash
# Generate events for a specific region
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    --region us-east

# Generate events for all US regions (us-east and us-west)
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    --region us

# Generate events for multiple regions
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    --region us-east --region eu-west

# Generate events for all EU and US regions
docker run -v $(pwd)/data:/data data-generator generate \
    -t transaction \
    --region eu --region us
```

Available regions:

- Full names: us-east, us-west, eu-west, ap-south
- Prefixes: us (all US regions), eu (all EU regions), ap (all Asia Pacific regions)

## Command Line Interface

The CLI supports two main commands: `generate` for batch data generation and `stream` for continuous event streaming.

### Generate Command

Generate a batch of synthetic data:

```bash
docker run data-generator generate [OPTIONS]
```

Options:

- `--count, -n`: Number of events to generate (per interval when using --rotate-interval, total count otherwise, default: 100)
- `--output, -o`: Output directory (default: /data)
- `--type, -t`: Event type (transaction/security/web_access/customer/all, default: all)
- `--format, -f`: Output format (json/jsonl/csv, default: jsonl)
- `--region, -r`: Specific regions to generate data for (can specify multiple, supports both full names like 'us-east' and prefixes like 'us' for all US regions)
- `--days, -d`: Generate events for last N days
- `--start-date`: Start date (YYYY-MM-DD or YYYY-MM-DDThh:mm:ss)
- `--end-date`: End date (defaults to now)
- `--rotate-interval`: Split output by interval (minute/hour/day/month)

### Stream Command

Generate a continuous stream of events:

```bash
docker run data-generator stream [OPTIONS]
```

Options:

- `--rate, -r`: Events per second (default: 1.0)
- `--type, -t`: Event type (transaction/security/web_access/customer/all, default: all)
- `--duration, -d`: Duration in seconds, 0 for infinite (default: 0)
- `--output, -o`: Output directory (default: /data)
- `--format, -f`: Output format (json/jsonl/csv, default: jsonl)
- `--region, -r`: Specific regions to generate data for (can specify multiple)
- `--rotate-interval`: Split output by interval (minute/hour/day/month)

## Output Formats

The generator supports three output formats:

1. `json`: Pretty-printed JSON array format

```json
[
  {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-02-02T10:30:00",
    ...
  },
  {
    "event_id": "661f9511-f3ac-52e5-b827-557766551111",
    "timestamp": "2024-02-02T10:31:00",
    ...
  }
]
```

2. `jsonl`: One JSON object per line (default)

```jsonl
{"event_id":"550e8400-e29b-41d4-a716-446655440000","timestamp":"2024-02-02T10:30:00",...}
{"event_id":"661f9511-f3ac-52e5-b827-557766551111","timestamp":"2024-02-02T10:31:00",...}
```

3. `csv`: Comma-separated values with header

```csv
event_id,timestamp,region_name,region_country,...
550e8400-e29b-41d4-a716-446655440000,2024-02-02T10:30:00,us-east,United States,...
661f9511-f3ac-52e5-b827-557766551111,2024-02-02T10:31:00,us-east,United States,...
```

## Data Types

### Transaction Events

Sample transaction event:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-02-02T10:30:00",
  "region_name": "us-east",
  "region_country": "United States",
  "region_timezone": "America/New_York",
  "transaction_id": "123e4567-e89b-12d3-a456-426614174000",
  "customer_id": "987fcdeb-51a2-43d7-9c89-764512781234",
  "customer_email": "john.doe@example.com",
  "customer_type": "premium",
  "product_id": "P1",
  "product_name": "Blue Modern Electronics",
  "product_category": "Electronics",
  "quantity": 2,
  "unit_price": 899.99,
  "subtotal": 1799.98,
  "tax_rate": 0.08,
  "tax_amount": 144.0,
  "total_amount": 1943.98,
  "payment_method": "credit_card",
  "payment_status": "completed",
  "currency": "USD",
  "shipping_method": "express",
  "estimated_delivery": "2024-02-09T10:30:00"
}
```

### Security Events

Sample security event:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-02-02T10:30:00",
  "region_name": "us-east",
  "region_country": "United States",
  "region_timezone": "America/New_York",
  "security_id": "123e4567-e89b-12d3-a456-426614174000",
  "category": "authentication",
  "severity": "HIGH",
  "source_ip": "192.168.1.1",
  "source_user_agent": "Mozilla/5.0...",
  "source_city": "New York",
  "source_country": "United States",
  "source_latitude": 40.7128,
  "source_longitude": -74.006,
  "source_device_os": "Windows",
  "source_device_browser": "Chrome",
  "source_device_type": "desktop",
  "session_id": "abc-123-def-456",
  "target_type": "user",
  "target_id": "user-123",
  "action_type": "login",
  "action_status": "failure",
  "attempt_count": 3
}
```

### Web Access Events

Sample web access event:

```json
{
  "event_id": "998fb12b-9282-4bd3-ac34-ee531539fee1",
  "timestamp": "2025-02-03T07:13:54.066587",
  "region_name": "eu-west",
  "region_country": "Ireland",
  "region_timezone": "Europe/Dublin",
  "http_method": "POST",
  "request": "/products",
  "http_version": "HTTP/2.0",
  "remote_user": null,
  "user_agent": "Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10_10_7 rv:3.0; ak-GH) AppleWebKit/531.13.5 (KHTML, like Gecko) Version/5.0.5 Safari/531.13.5",
  "accept_language": "ka_GE",
  "referer": "https://google.com",
  "client_ip": "2.26.108.153",
  "client_country": "Ireland",
  "client_city": "Port Waynechester",
  "is_mobile": true,
  "is_bot": true,
  "status_code": 200,
  "request_size": 1217,
  "response_size": 40351,
  "response_time": 194.39,
  "session_id": "f0d3186d-ff54-4a18-8ebe-1589ed03cbd8",
  "server_id": "web-2",
  "datacenter": "eu-west",
  "cache_hit": true
}
```

### Customer Data

Sample customer data:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-02-02T10:30:00",
  "region_name": "us-east",
  "region_country": "United States",
  "region_timezone": "America/New_York",
  "customer_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "jane.smith@example.com",
  "phone": "+1-555-0123",
  "first_name": "Jane",
  "last_name": "Smith",
  "birth_date": "1985-06-15",
  "gender": "female",
  "age_group": "35-44",
  "education": "masters",
  "occupation": "Software Engineer",
  "income_range": "100k+",
  "language": "en",
  "nationality": "US",
  "address": {
    "street": "123 Tech Lane",
    "city": "Boston",
    "state": "MA",
    "country": "United States",
    "postal_code": "02108",
    "latitude": 42.3601,
    "longitude": -71.0589,
    "timezone": "America/New_York"
  },
  "preferences": {
    "communication": "email",
    "marketing_opt_in": true
  },
  "account_type": "premium",
  "account_status": "active",
  "registration_date": "2024-01-15T08:30:00",
  "last_login": "2024-02-01T14:20:00",
  "ssn": "027-37-9404",
  "credit_card": {
    "number": "4368240644286981",
    "expiration": "04/29",
    "cvv": "429"
  }
}
```

## Configuration

The generator is configured via `config.json`. Key configuration sections include:

### Regions

- Detailed geographic boundaries for each region
- Associated timezones and countries
- Latitude/longitude ranges for realistic location generation

### Products

- Number of products to generate
- Available product categories
- Price ranges and inventory settings

### Event Settings

- Transaction settings (payment methods, statuses)
- Security event parameters (categories, severities)
- Web access patterns (endpoints, status code distributions)

### Time Patterns

- Business hours definition
- Event frequency patterns for business/non-business hours

## Using with Bacalhau

### Basic Data Generation

```bash
# Generate sample data
bacalhau docker run \
    data-generator:latest \
    -- generate --count 10000 --type all
```

### Regional Data Generation

```bash
# Generate data for specific regions
for region in us-east us-west eu-west ap-south; do
    bacalhau docker run \
        data-generator:latest \
        -- generate \
        --count 5000 \
        --type transaction \
        --region $region
done
```

## Building and Pushing the Image

The project includes a Makefile to simplify building and pushing the image. The version is automatically generated based on the current year and month (YY.MM).

### Environment Setup

Set required environment variables:

```bash
export GITHUB_PAT=your_github_pat
export GITHUB_USERNAME=your_github_username
```

### Basic Usage

1. Login to GitHub Container Registry:

```bash
make login
```

2. Build multi-architecture image:

```bash
make build
```

3. Build and push image with tags:

```bash
make push
```

### Additional Make Commands

- `make build-local`: Build for local architecture only
- `make push-local`: Push local architecture build
- `make version`: Show current version
- `make tag`: Create git tag for release
- `make test`: Run basic test of the image
- `make help`: Show all available commands

## Development

### Project Structure

```
.
├── Dockerfile
├── requirements.txt
├── data_generator.py
├── config.json
└── entrypoint.sh
```

### Adding New Event Types

1. Add event settings to `config.json`
2. Create a new generator class in `data_generator.py`
3. Add the new generator to the DataGenerator class initialization
4. Update the CLI options in the generate and stream function
