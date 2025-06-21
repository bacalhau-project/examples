#!/bin/bash

# Test runner script for the unified log processor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running tests for Unified Log Processor${NC}"
echo "========================================"

# Activate virtual environment
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo -e "${RED}Error: Virtual environment not found at $PROJECT_ROOT/.venv${NC}"
    echo "Please create a virtual environment first:"
    echo "  python -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r tests/requirements.txt"
    exit 1
fi

# Run the tests
echo -e "${GREEN}Running all tests...${NC}"
cd "$PROJECT_ROOT"

# Set required environment variables for tests
export CONFIG_FILE="demo-network/files/config.yaml"
export EXECUTABLE_DIR="bigquery-uploader"

# Run tests with verbose output using virtual environment and show skip reasons
# Capture test results for analysis
TEST_OUTPUT=$(python -m pytest tests/ -v -rs 2>&1)
TEST_EXIT_CODE=$?

echo "$TEST_OUTPUT"

# Analyze test results
TOTAL_TESTS=$(echo "$TEST_OUTPUT" | grep -o '[0-9]\+ passed' | head -1 | cut -d' ' -f1)
SKIPPED_TESTS=$(echo "$TEST_OUTPUT" | grep -o '[0-9]\+ skipped' | head -1 | cut -d' ' -f1)
BIGQUERY_TESTS_RAN=$(echo "$TEST_OUTPUT" | grep -c "test_bigquery\|TestBigQueryIntegration" || echo "0")

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All $TOTAL_TESTS tests passed!${NC}"

    if [ "$BIGQUERY_TESTS_RAN" -gt 0 ]; then
        echo -e "${GREEN}✓ BigQuery connectivity tests completed successfully${NC}"
    else
        echo -e "${YELLOW}⚠ BigQuery connectivity tests were skipped${NC}"
        echo ""
        echo -e "${GREEN}To run BigQuery connectivity tests:${NC}"
        echo "1. Ensure your config.yaml has correct project_id"
        echo "2. Either:"
        echo "   - Place credentials at /var/log/app/log_uploader_credentials.json, OR"
        echo "   - Update credentials_path in config.yaml, OR"
        echo "   - Set CREDENTIALS_FILE environment variable, OR"
        echo "   - Set GOOGLE_APPLICATION_CREDENTIALS environment variable"
        echo "3. Run: source .venv/bin/activate && python -m pytest tests/test_integration.py -v -s"
    fi

    if [ ! -z "$SKIPPED_TESTS" ] && [ "$SKIPPED_TESTS" -gt 0 ]; then
        echo -e "${YELLOW}ℹ $SKIPPED_TESTS tests were skipped${NC}"
    fi
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit $TEST_EXIT_CODE
fi

echo ""
echo -e "${GREEN}Test run completed!${NC}"
