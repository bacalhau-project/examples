# Event Puller Project Guide

## Build & Run Commands
- Build binary: `go build -o bin/event-puller`
- Build container: `./build.sh`
- Run tests: `go test ./...`
- Run single test: `go test -v -run TestName`
- Run application: `go run main.go`
- Format code: `go fmt ./...`
- Lint code: `golangci-lint run`

## Code Style Guidelines
- **Imports**: Standard library first, then third-party packages, with a blank line between groups
- **Formatting**: Follow standard Go formatting with `go fmt`
- **Error Handling**: Always check errors and provide context using fmt.Errorf 
- **Naming**:
  - Use camelCase for variables and PascalCase for exported functions/types
  - Acronyms should be all uppercase (e.g., HTTP, AWS, SQS)
- **Concurrency**: Use context for cancellation, sync.WaitGroup for coordination, channels for communication
- **Constants**: Define constants at package level with UPPERCASE_SNAKE_CASE

## Project Structure
- Main files in root directory
- Separate files for logical components (hub.go, websocket.go)
- AWS SQS integration for message queuing
- Bubble Tea TUI for terminal interface