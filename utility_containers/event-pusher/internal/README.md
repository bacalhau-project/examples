# Event Pusher Internal Packages

This directory contains the internal packages for the Event Pusher application, organized according to Go best practices.

## Package Structure

### HTTP Package
Location: `internal/http/`

The HTTP package provides abstractions and implementations for making HTTP requests across different environments:

- `client.go`: Core HTTP client interface and default implementation
- `mock_client.go`: Mock HTTP client for testing
- `mock_responses.go`: Sample HTTP responses for testing
- `wasm.go`: WebAssembly-specific HTTP client (only built with `wasm` tag)
- `wasm_shim/`: Compatibility shim for non-WASM builds

### Messages Package
Location: `internal/messages/`

The Messages package handles message generation and sending to different targets:

- `types.go`: Message structure and generation utilities
- `sqs.go`: AWS SQS message sending functionality
- `mock_sqs.go`: Mock SQS client for testing

### Utils Package
Location: `internal/utils/`

The Utils package provides common utility functions used across the application:

- `utils.go`: Environment variable handling, header parsing, etc.

## Testing

Each package includes tests in their respective `test/` subdirectories:

- `internal/http/test/`: HTTP client tests
- `internal/utils/test/`: Utilities tests

Additionally, integration tests are available in the `test/` directory at the project root.

## Usage

These packages are used by the main application and are not intended to be imported by external code. For examples of how to use these packages, see the application's main code.