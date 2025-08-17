#!/bin/bash
# spot-sso - AWS SSO wrapper for spot-deployer Docker container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="${SPOT_REGISTRY:-ghcr.io}"
IMAGE_NAME="${SPOT_IMAGE:-bacalhau-project/aws-spot-deployer}"
VERSION="${SPOT_VERSION:-latest}"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

# Check if AWS CLI is available
if ! command -v aws >/dev/null 2>&1; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check if logged in with SSO
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Not logged in to AWS SSO${NC}"
    echo "Please run: aws sso login"
    exit 1
fi

echo -e "${GREEN}✅ AWS SSO session active${NC}"

# Export SSO credentials
echo "Exporting SSO credentials..."
eval $(aws configure export-credentials --format env)

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo -e "${RED}❌ Failed to export SSO credentials${NC}"
    exit 1
fi

# Default directories
CONFIG_FILE="${SPOT_CONFIG:-./config.yaml}"
FILES_DIR="${SPOT_FILES:-./files}"
OUTPUT_DIR="${SPOT_OUTPUT:-./output}"

# Build volume mounts
VOLUMES=""

# Mount SSH directory for key access
if [ -d "$HOME/.ssh" ]; then
    VOLUMES="$VOLUMES -v $HOME/.ssh:/root/.ssh:ro"
fi

# Mount config file if it exists (not needed for setup/help)
if [ -f "$CONFIG_FILE" ]; then
    VOLUMES="$VOLUMES -v $(realpath $CONFIG_FILE):/app/config/config.yaml:ro"
fi

# Mount files directory if it exists
if [ -d "$FILES_DIR" ]; then
    VOLUMES="$VOLUMES -v $(realpath $FILES_DIR):/app/files:ro"
fi

# Mount output directory
mkdir -p "$OUTPUT_DIR"
VOLUMES="$VOLUMES -v $(realpath $OUTPUT_DIR):/app/output"

# Run the container with SSO credentials
exec docker run --rm -it \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    -e AWS_SESSION_TOKEN \
    -e AWS_DEFAULT_REGION \
    -e AWS_REGION \
    -e TERM=xterm-256color \
    -e COLUMNS=$(tput cols) \
    -e LINES=$(tput lines) \
    $VOLUMES \
    "$FULL_IMAGE" \
    "$@"