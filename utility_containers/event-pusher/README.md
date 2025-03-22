# Event Pusher WASM Module

A WebAssembly module written in Go (TinyGo) that continuously sends event messages to an AWS SQS queue. The module runs as a standalone application that continues running until it completes sending the specified number of messages or runs indefinitely.

## Project Status

This project has been recently reorganized to improve maintainability and simplify the codebase structure. Key improvements include:

- Streamlined the code structure by consolidating duplicative code
- Moved from a multi-package structure to a more integrated design
- Improved the testing framework with consistent patterns
- Maintained backward compatibility with existing workflows
- Enhanced configuration handling with YAML-based configuration

## Features

- Runs continuously, pushing events at regular intervals
- Generates random container IDs and emoji icons
- Configurable via environment variables
- Validates hex color codes
- Formats messages with timestamps
- Sends messages to AWS SQS using direct HTTP requests (no AWS SDK dependency)
- Runs as a standalone WebAssembly module for optimal resource efficiency

## Prerequisites

- [Go](https://golang.org/doc/install) and [TinyGo](https://tinygo.org/getting-started/install/) for building
- [Wasmtime](https://wasmtime.dev/) as the WebAssembly runtime
- [Docker](https://www.docker.com/get-started) (optional, for container builds)
- [Kubernetes](https://kubernetes.io/) (optional, for deployment)

## Building and Running

### Running Locally as a Go Binary

1. Build the Go binary:
```bash
go build -o event-pusher .
```

2. Create a config.yaml file (or use one of the example configs):
```yaml
# HTTP Mode Example
method: "GET"
url: "https://httpbin.org/get"
mode: "http"
```

3. Run the application:
```bash
# Using the default config.yaml in the current directory
./event-pusher

# Using a specific config file
./event-pusher /path/to/your-config.yaml
```

### Building and Running With WebAssembly

1. Build the WASM modules:
```bash
./build_wasm.sh
```

This builds several versions:
- `bin/event-pusher.wasm`: Full version with HTTP support (requires WASI preview2)
- `bin/event-pusher-nohttp.wasm`: Simulation-only version that works with standard wasmtime

2. Run locally with wasmtime:
```bash
# Using a config file with wasmtime
wasmtime --dir=. ./bin/event-pusher.wasm -- config.yaml
```

### Running on Bacalhau

Bacalhau supports running WASM modules across a distributed network. You can run the event-pusher on Bacalhau as follows:

1. Build the WASM module:
```bash
./build_wasm.sh
```

2. Run on Bacalhau using environment variables (legacy support):
```bash
# Simple HTTP request
bacalhau wasm run --target all -e HTTP_URL=https://httpbin.org/json -e HTTP_METHOD=GET bin/main.wasm

# With additional parameters
bacalhau wasm run --target all \
  -e HTTP_URL=https://httpbin.org/json \
  -e HTTP_METHOD=GET \
  -e HTTP_HEADERS="Accept: application/json" \
  bin/main.wasm

# Event pusher in simulation mode
bacalhau wasm run --target all \
  -e SIMULATE=true \
  -e MAX_MESSAGES=10 \
  -e COLOR="#FF5500" \
  -e VM_NAME="bacalhau-node" \
  bin/main.wasm
```

Note: Even though we've moved to a configuration file approach, the application still supports environment variables for backward compatibility with existing Bacalhau workflows.

3. Run on Bacalhau with config file:
```bash
# Create a config file
cat > bacalhau-config.yaml << EOL
method: "GET"
url: "https://httpbin.org/json"
mode: "http"
EOL

# Submit the job with the config file
bacalhau wasm run --target all -i bacalhau-config.yaml:/app/config.yaml bin/main.wasm
```

4. For SQS event pushing (simulation mode):
```bash
# Create a simulation config
cat > sqs-config.yaml << EOL
simulate: true
max_messages: 10
vm_name: "bacalhau-node"
color: "#FF5500"
mode: "event-pusher"
EOL

# Submit the job
bacalhau wasm run --target all -i sqs-config.yaml:/app/config.yaml bin/main.wasm
```

With Bacalhau, you can run the event-pusher across a distributed network of compute nodes, making it ideal for tasks like load testing or distributed event generation.

### Docker Container

1. Build a Docker container:
```bash
./build_container.sh
```

2. Create custom config files for different scenarios:

**HTTP Mode (http-config.yaml):**
```yaml
method: "GET"
url: "https://httpbin.org/get"
headers: "Accept: application/json"
mode: "http"
```

**SQS Event Pusher Mode (sqs-config.yaml):**
```yaml
region: "us-west-2"
access_key: "<your-access-key>"
secret_key: "<your-secret-key>"
queue_url: "<your-queue-url>"
color: "#3366FF"
vm_name: "docker-container"
simulate: false
mode: "event-pusher"
```

**Simulation Mode (simulation-config.yaml):**
```yaml
simulate: true
max_messages: 5
vm_name: "my-test-container"
mode: "event-pusher"
```

3. Run the container with your config file:
```bash
# For HTTP mode
docker run -v $(pwd)/http-config.yaml:/app/config.yaml event-pusher:latest

# For SQS mode with AWS credentials
docker run -v $(pwd)/sqs-config.yaml:/app/config.yaml event-pusher:latest

# For simulation mode (no AWS credentials needed)
docker run -v $(pwd)/simulation-config.yaml:/app/config.yaml event-pusher:latest
```

4. Advanced usage with custom config path:
```bash
# Specify config path explicitly
docker run -v $(pwd)/myconfig.yaml:/configs/custom.yaml event-pusher:latest /configs/custom.yaml
```

### Kubernetes Deployment

1. Create a ConfigMap for your configuration:
```bash
# Create a simulation config for testing
cat > k8s-config.yaml << EOL
simulate: true
max_messages: 0
vm_name: "k8s-pod"
color: "#3366FF"
random_off: false
max_interval_seconds: 5
mode: "event-pusher"
EOL

# Create the ConfigMap
kubectl create configmap event-pusher-config --from-file=config.yaml=k8s-config.yaml
```

2. For production with AWS credentials, create a Secret:
```bash
kubectl create secret generic aws-credentials \
  --from-literal=access_key=<your-access-key> \
  --from-literal=secret_key=<your-secret-key>
```

3. Edit the `deploy-pusher.yaml` file to use ConfigMap and Secret:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-pusher
spec:
  replicas: 1
  selector:
    matchLabels:
      app: event-pusher
  template:
    metadata:
      labels:
        app: event-pusher
    spec:
      containers:
      - name: event-pusher
        image: event-pusher:latest
        volumeMounts:
        - name: config-volume
          mountPath: /app/config.yaml
          subPath: config.yaml
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
      volumes:
      - name: config-volume
        configMap:
          name: event-pusher-config
```

4. For production deployment with AWS credentials:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: event-pusher-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: event-pusher-prod
  template:
    metadata:
      labels:
        app: event-pusher-prod
    spec:
      containers:
      - name: event-pusher
        image: event-pusher:latest
        volumeMounts:
        - name: config-volume
          mountPath: /app/config.yaml
          subPath: config.yaml
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        envFrom:
        - secretRef:
            name: aws-credentials
      volumes:
      - name: config-volume
        configMap:
          name: event-pusher-config
```

5. Apply the deployment:
```bash
kubectl apply -f deploy-pusher.yaml
```

6. To update the configuration:
```bash
# Update ConfigMap in-place
kubectl create configmap event-pusher-config --from-file=config.yaml=k8s-config.yaml -o yaml --dry-run=client | kubectl replace -f -

# Restart the pods to pick up the new config
kubectl rollout restart deployment/event-pusher
```

## Configuration

The application uses a `config.yaml` file for all configuration settings. A sample configuration file is provided in the repository as `config.yaml`.

### Configuration File Location

The application looks for `config.yaml` in the following locations:
1. Current working directory
2. Directory where the executable is located

If no configuration file is found, default values are used.

### Environment Variable Fallback

For backward compatibility (especially with Bacalhau), if no config file is found, the application will check for configuration in environment variables:

| Config Parameter | Environment Variable |
|------------------|---------------------|
| `method` | `HTTP_METHOD` |
| `url` | `HTTP_URL` |
| `headers` | `HTTP_HEADERS` |
| `body` | `HTTP_BODY` |
| `region` | `AWS_REGION` |
| `access_key` | `AWS_ACCESS_KEY_ID` |
| `secret_key` | `AWS_SECRET_ACCESS_KEY` |
| `queue_url` | `SQS_QUEUE_URL` |
| `color` | `COLOR` |
| `vm_name` | `VM_NAME` |
| `max_interval_seconds` | `MAX_INTERVAL_SECONDS` |
| `random_off` | `RANDOM_OFF` |
| `max_messages` | `MAX_MESSAGES` |
| `simulate` | `SIMULATE` |
| `mode` | `MODE` |

Note: Environment variables are only used if no valid config file is found.

### Example Configuration Files

#### HTTP Mode Configuration (http-config.yaml)
```yaml
# HTTP Mode Configuration
method: "GET"
url: "https://httpbin.org/get"
headers: "Accept: application/json\nUser-Agent: event-pusher"
body: ""
mode: "http"
```

#### Event Pusher Mode Configuration (event-pusher-config.yaml)
```yaml
# Event Pusher Mode Configuration
region: "us-west-2"
access_key: ""
secret_key: ""
queue_url: ""
color: "#FF5500"
vm_name: "test-vm"
max_interval_seconds: 2
random_off: false
max_messages: 10
simulate: true
mode: "event-pusher"
```

Run with a specific configuration file:
```bash
./event-pusher /path/to/your-config.yaml
```

### Configuration Parameters

#### HTTP Mode Settings
- `method`: HTTP method (GET, POST, PUT, DELETE) - default: "GET"
- `url`: HTTP URL to send requests to
- `headers`: HTTP headers in format "Key1: Value1\nKey2: Value2"
- `body`: HTTP request body

#### Event Pusher Mode Settings
- `region`: AWS region for SQS - default: "us-west-2"
- `access_key`: AWS access key ID
- `secret_key`: AWS secret access key
- `queue_url`: URL of the SQS queue to send messages to
- `color`: Hex color code (e.g., "#FF0000") - default: "#000000"
- `vm_name`: Virtual machine name - default: "default"
- `max_interval_seconds`: Maximum interval between messages in seconds - default: 5
- `random_off`: Turn off randomization if set to true - default: false
- `max_messages`: Maximum number of messages to send before exiting (0 means unlimited) - default: 0
- `simulate`: Simulate sending messages without making actual API calls - default: false

#### General Settings
- `mode`: Application mode ("auto", "http", "event-pusher") - default: "auto"
  - "auto" mode determines the appropriate mode based on the provided configuration
  - "http" mode forces HTTP request mode
  - "event-pusher" mode forces event pushing mode

## Message Format

The application sends JSON messages with the following format:

```json
{
  "vm_name": "myVM",
  "icon_name": "🚀",
  "timestamp": "2023-04-13T17:47:24Z",
  "color": "#FF0000",
  "container_id": "a1b2c3d4"
}
```

## Implementation Details

The application implements AWS SQS message sending directly using HTTP requests without depending on the AWS SDK. It:

1. Constructs the proper AWS Signature V4 for authentication
2. Formats the SQS request parameters
3. Makes direct HTTP POST requests to the SQS endpoint
4. Includes message deduplication and group ID for FIFO queues

### Code Organization

The codebase follows Go best practices with a clear separation of concerns:

#### Directory Structure
- `internal/http/`: HTTP client implementations and mocks
- `internal/utils/`: Utility functions for environment variables and parsing
- Root directory: Main application code and tests

#### Main Files
- `main.go`: Main application and runtime functionality
- `messages.go`: Message types and generator functions
- `messages_mock.go`: Mock implementations for testing
- `integrated_tests.go`: Integration tests for HTTP functionality
- `main_integration_test.go`: WASM HTTP module integration tests
- `run_tests.sh`: Test runner script

#### Recent Reorganization
The codebase has been reorganized to improve maintainability:
- Removed the duplicated `pkg/` directory to eliminate code duplication
- Moved message functionality from `internal/messages` to root-level files
- Consolidated tests into the main package for better integration
- Removed the separate `test/` directory
- Ensured backward compatibility with existing workflows

## Testing

### Testing Architecture

The project uses an integrated testing approach, with tests organized as follows:

- **Unit Tests**: For individual components in both root and internal packages
- **Integration Tests**: In `integrated_tests.go` for testing HTTP and SQS functionality
- **WASM Module Tests**: In `main_integration_test.go` for testing WebAssembly functionality

### Running Tests

Run all tests with the provided test script:

```bash
./run_tests.sh
```

This script handles environment variable setup and runs all tests across the entire project.

To run specific tests:

```bash
./run_tests.sh TestBasicHTTPIntegration
./run_tests.sh TestHTTPIntegration
```

### Unit Tests

Run the basic unit tests for core functionality:

```bash
go test ./...
```

To run tests for specific packages:

```bash
go test ./internal/http/...
go test ./internal/utils/...
```

### HTTP Integration Testing

The application includes integration tests for HTTP functionality. By default, these tests are skipped unless specific environment variables are set:

```bash
# Enable HTTP integration tests
export ENABLE_HTTP_INTEGRATION_TEST=true
export HTTP_URL=https://httpbin.org/get
export HTTP_METHOD=GET
export HTTP_HEADERS="Accept: application/json"

# Run HTTP integration tests
go test -v -run TestBasicHTTPIntegration
```

### WASM HTTP Integration Testing

There are also tests for the WebAssembly HTTP module integration:

```bash
# Run WASM HTTP integration tests
go test -v -run TestHTTPIntegration
```

### SQS Message Testing

Tests for SQS message sending functionality using a mock SQS implementation:

```bash
# Enable SQS testing
export ENABLE_SQS_TEST=true
export SIMULATE=true
export AWS_REGION=us-west-2
export SQS_QUEUE_URL=https://sqs.us-west-2.amazonaws.com/123456789012/test-queue

# Run SQS tests
go test -v -run TestSQSMessageSending
```

### Test Configuration

For running tests, you can set environment variables to control test behavior. The tests include simulation options to avoid making actual HTTP or SQS API calls.

### Test Environment

Tests can use a `.env` file in the root directory for setting up test variables. The `run_tests.sh` script automatically loads this file if present.

## License

See the [LICENSE](LICENSE) file for details.