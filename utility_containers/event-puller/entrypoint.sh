#!/bin/sh

echo "🔍 Starting entrypoint script..."

# System information
echo "📊 System Information:"
echo "  Architecture: $(uname -m)"
echo "  OS: $(uname -s)"
echo "  Kernel: $(uname -r)"
echo "  CPU Info: $(cat /proc/cpuinfo | grep "model name" | head -n1 | cut -d':' -f2 || echo "Not available")"

# Check if we're in the right directory
echo "📂 Current directory: $(pwd)"
echo "📂 Directory contents:"
ls -la

# Check if the binary exists and is executable
if [ ! -f "/app/event-puller" ]; then
    echo "❌ Error: Binary not found at /app/event-puller"
    exit 1
fi

if [ ! -x "/app/event-puller" ]; then
    echo "❌ Error: Binary at /app/event-puller is not executable"
    exit 1
fi

# Check binary architecture
echo "🔍 Binary information:"
file /app/event-puller

# Check if ENV_FILE is set
if [ -z "$ENV_FILE" ]; then
    echo "❌ Error: ENV_FILE environment variable is not set"
    echo "Please set ENV_FILE to the path of your environment file"
    echo "Example: Set ENV_FILE=/app/.env when running the container"
    exit 1
fi

echo "📄 ENV_FILE is set to: $ENV_FILE"

# Check if the env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: Environment file not found at $ENV_FILE"
    echo "Please ensure the environment file exists and is mounted correctly"
    echo "The environment file should be mounted to the path specified in ENV_FILE"
    exit 1
fi

echo "✅ Environment file found at $ENV_FILE"
echo "📄 Environment file contents (excluding sensitive data):"
grep -v "KEY\|SECRET\|PASSWORD" "$ENV_FILE" || true

# Display all environment variables (excluding sensitive data)
echo "🌍 Environment variables (excluding sensitive data):"
env | grep -v "KEY\|SECRET\|PASSWORD" || true

# Run the binary with additional debugging
echo "🚀 Starting event-puller..."
exec /app/event-puller 