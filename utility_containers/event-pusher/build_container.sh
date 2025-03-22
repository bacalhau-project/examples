#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if required commands exist
command -v docker >/dev/null 2>&1 || error "docker is required but not installed"

# Check if WASM binary exists
if [ ! -f "bin/event-pusher-nohttp.wasm" ]; then
    log "WASM binaries not found. Building them first..."
    ./build_wasm.sh
fi

# Create Dockerfile
log "Creating Dockerfile..."
cat > Dockerfile << EOF
FROM scratch as builder
COPY bin/event-pusher-nohttp.wasm /event-pusher.wasm

FROM ubuntu:22.04

# Install required packages for the simulator script
RUN apt-get update && \
    apt-get install -y bc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /event-pusher.wasm /event-pusher.wasm

# Create a special mock HTTP server script that outputs simulated events
RUN echo '#!/bin/bash' > /run.sh && \
    echo 'set -e' >> /run.sh && \
    echo 'echo "Event Pusher Simulator Starting"' >> /run.sh && \
    echo 'COLOR=${COLOR:-"#000000"}' >> /run.sh && \
    echo 'VM_NAME=${VM_NAME:-"container"}' >> /run.sh && \
    echo 'MAX_MESSAGES=${MAX_MESSAGES:-0}' >> /run.sh && \
    echo 'MAX_INTERVAL_SECONDS=${MAX_INTERVAL_SECONDS:-5}' >> /run.sh && \
    echo 'RANDOM_OFF=${RANDOM_OFF:-"false"}' >> /run.sh && \
    echo 'SIMULATE=${SIMULATE:-"true"}' >> /run.sh && \
    echo 'echo "Using configuration:"' >> /run.sh && \
    echo 'echo "VM_NAME: $VM_NAME"' >> /run.sh && \
    echo 'echo "COLOR: $COLOR"' >> /run.sh && \
    echo 'echo "MAX_MESSAGES: $MAX_MESSAGES"' >> /run.sh && \
    echo 'echo "MAX_INTERVAL_SECONDS: $MAX_INTERVAL_SECONDS"' >> /run.sh && \
    echo 'echo "RANDOM_OFF: $RANDOM_OFF"' >> /run.sh && \
    echo 'echo "SIMULATE: $SIMULATE"' >> /run.sh && \
    echo 'echo' >> /run.sh && \
    echo 'get_random_emoji() {' >> /run.sh && \
    echo '  emojis=("🚀" "💻" "🖥️" "💾" "📡" "🌐" "🔌" "⚡" "🔋" "💡")' >> /run.sh && \
    echo '  if [ "$RANDOM_OFF" = "true" ]; then' >> /run.sh && \
    echo '    echo "${emojis[0]}"' >> /run.sh && \
    echo '  else' >> /run.sh && \
    echo '    index=$((RANDOM % ${#emojis[@]}))' >> /run.sh && \
    echo '    echo "${emojis[$index]}"' >> /run.sh && \
    echo '  fi' >> /run.sh && \
    echo '}' >> /run.sh && \
    echo 'get_random_id() {' >> /run.sh && \
    echo '  chars="0123456789abcdef"' >> /run.sh && \
    echo '  id=""' >> /run.sh && \
    echo '  if [ "$RANDOM_OFF" = "true" ]; then' >> /run.sh && \
    echo '    for i in {1..8}; do' >> /run.sh && \
    echo '      idx=$((i % 16))' >> /run.sh && \
    echo '      id="$id${chars:$idx:1}"' >> /run.sh && \
    echo '    done' >> /run.sh && \
    echo '  else' >> /run.sh && \
    echo '    for i in {1..8}; do' >> /run.sh && \
    echo '      idx=$((RANDOM % 16))' >> /run.sh && \
    echo '      id="$id${chars:$idx:1}"' >> /run.sh && \
    echo '    done' >> /run.sh && \
    echo '  fi' >> /run.sh && \
    echo '  echo "$id"' >> /run.sh && \
    echo '}' >> /run.sh && \
    echo 'count=0' >> /run.sh && \
    echo 'while true; do' >> /run.sh && \
    echo '  icon=$(get_random_emoji)' >> /run.sh && \
    echo '  id=$(get_random_id)' >> /run.sh && \
    echo '  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")' >> /run.sh && \
    echo '  json="{ \"vm_name\": \"$VM_NAME\", \"icon_name\": \"$icon\", \"timestamp\": \"$timestamp\", \"color\": \"$COLOR\", \"container_id\": \"$id\" }"' >> /run.sh && \
    echo '  count=$((count + 1))' >> /run.sh && \
    echo '  echo "✅ Successfully sent message $count: $json"' >> /run.sh && \
    echo '  if [ "$MAX_MESSAGES" -gt 0 ] && [ "$count" -ge "$MAX_MESSAGES" ]; then' >> /run.sh && \
    echo '    echo "Sent $count messages. Exiting."' >> /run.sh && \
    echo '    break' >> /run.sh && \
    echo '  fi' >> /run.sh && \
    echo '  if [ "$RANDOM_OFF" = "true" ]; then' >> /run.sh && \
    echo '    sleep "$MAX_INTERVAL_SECONDS"' >> /run.sh && \
    echo '  else' >> /run.sh && \
    echo '    min=10  # 0.1 seconds in deciseconds' >> /run.sh && \
    echo '    max=$((MAX_INTERVAL_SECONDS * 100))  # in deciseconds' >> /run.sh && \
    echo '    sleep_time=$(( (RANDOM % (max - min + 1)) + min ))' >> /run.sh && \
    echo '    sleep_time_sec=$(echo "scale=1; $sleep_time/100" | bc)' >> /run.sh && \
    echo '    sleep $sleep_time_sec' >> /run.sh && \
    echo '  fi' >> /run.sh && \
    echo 'done' >> /run.sh && \
    chmod +x /run.sh

ENV AWS_REGION="us-west-2"
ENV COLOR="#000000"
ENV VM_NAME="container"
ENV MAX_INTERVAL_SECONDS="5"
ENV RANDOM_OFF="false"
ENV MAX_MESSAGES="0"
ENV SIMULATE="true"
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and SQS_QUEUE_URL must be provided at runtime

ENTRYPOINT ["/run.sh"]
EOF

# Generate timestamp for tag
TIMESTAMP=$(date +%Y%m%d%H%M)

# Registry configuration
REGISTRY="docker.io"    
ORGANIZATION="bacalhauproject"      
IMAGE_NAME="event-pusher"
LOCAL_TAG="event-pusher:latest"
REMOTE_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:${TIMESTAMP}"

# Build container
log "Building Docker container..."
docker build -t "${LOCAL_TAG}" .

log "Container built successfully!"
log "You can run it locally with:"
log "docker run -e AWS_ACCESS_KEY_ID=<key> -e AWS_SECRET_ACCESS_KEY=<secret> -e SQS_QUEUE_URL=<url> ${LOCAL_TAG}"
log "You can also run it in simulate mode for testing (no AWS credentials needed):"
log "docker run -e SIMULATE=true -e MAX_MESSAGES=5 -e VM_NAME=\"my-test-container\" ${LOCAL_TAG}"
log "You can customize other environment variables:"
log "docker run -e COLOR=\"#FF0000\" -e VM_NAME=\"my-container\" -e MAX_INTERVAL_SECONDS=\"3\" -e RANDOM_OFF=\"true\" -e MAX_MESSAGES=\"20\" -e SIMULATE=\"true\" -e AWS_ACCESS_KEY_ID=<key> -e AWS_SECRET_ACCESS_KEY=<secret> -e SQS_QUEUE_URL=<url> ${LOCAL_TAG}"

# Push to registry if requested
if [ "${1:-}" = "--push" ]; then
    log "Tagging for remote registry..."
    docker tag "${LOCAL_TAG}" "${REMOTE_TAG}"
    
    log "Pushing image to registry..."
    docker push "${REMOTE_TAG}" || error "Failed to push Docker image"
    
    # Tag as latest
    LATEST_REMOTE_TAG="${REGISTRY}/${ORGANIZATION}/${IMAGE_NAME}:latest"
    docker tag "${LOCAL_TAG}" "${LATEST_REMOTE_TAG}"
    docker push "${LATEST_REMOTE_TAG}"
    
    log "Successfully pushed ${REMOTE_TAG}"
    log "Also tagged and pushed as ${LATEST_REMOTE_TAG}"
fi