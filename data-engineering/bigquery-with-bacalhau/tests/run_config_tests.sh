#!/bin/bash
# Simple test runner for configuration runtime validation tests
# This script sets up the environment and runs the configuration tests that don't require external dependencies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}Configuration Runtime Validation Test Runner${NC}"
echo -e "${BLUE}=============================================${NC}"
echo -e "${YELLOW}This script runs ONLY the configuration runtime validation tests${NC}"
echo -e "${YELLOW}These tests require NO external dependencies (no BigQuery, DuckDB, etc.)${NC}"
echo ""

# Check if we're in the right directory
if [[ ! -f "bigquery-uploader/bigquery_uploader.py" ]]; then
    echo -e "${RED}Error: Must run from bigquery-with-bacalhau directory${NC}"
    echo -e "${YELLOW}Current directory: $(pwd)${NC}"
    echo -e "${YELLOW}Expected files: bigquery-uploader/bigquery_uploader.py${NC}"
    exit 1
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found${NC}"
    echo -e "${YELLOW}Please install pytest: pip install pytest${NC}"
    exit 1
fi

# Check if PyYAML is available
python3 -c "import yaml" 2>/dev/null || {
    echo -e "${RED}Error: PyYAML not found${NC}"
    echo -e "${YELLOW}Please install PyYAML: pip install pyyaml${NC}"
    exit 1
}

echo -e "${GREEN}✓ Environment checks passed${NC}"

# Set required environment variables
export EXECUTABLE_DIR="bigquery-uploader"

echo -e "${YELLOW}Running configuration runtime validation tests...${NC}"
echo -e "${BLUE}File: tests/test_config_runtime_validation.py${NC}"
echo -e "${BLUE}Tests: 10 comprehensive configuration validation scenarios${NC}"
echo ""

# Run the configuration runtime validation tests
if pytest tests/test_config_runtime_validation.py -v; then
    echo ""
    echo -e "${GREEN}=============================================${NC}"
    echo -e "${GREEN}✓ All configuration tests PASSED${NC}"
    echo -e "${GREEN}=============================================${NC}"
    echo ""
    echo -e "${BLUE}All 10 configuration runtime validation tests completed successfully:${NC}"
    echo -e "${GREEN}  ✓ Configuration state changes (raw→schematized→sanitized→aggregated)${NC}"
    echo -e "${GREEN}  ✓ Badly formatted config detection (YAML parsing errors)${NC}"
    echo -e "${GREEN}  ✓ Invalid pipeline mode handling (BAD_FORMAT, etc.)${NC}"
    echo -e "${GREEN}  ✓ Missing required fields validation (project_id, etc.)${NC}"
    echo -e "${GREEN}  ✓ Environment variable overrides (PROJECT_ID, DATASET, etc.)${NC}"
    echo -e "${GREEN}  ✓ Rapid configuration changes simulation${NC}"
    echo -e "${GREEN}  ✓ File permission and access error handling${NC}"
    echo -e "${GREEN}  ✓ Configuration field type validation${NC}"
    echo -e "${GREEN}  ✓ Deep merge with invalid nested structures${NC}"
    echo -e "${GREEN}  ✓ Nonexistent configuration file handling${NC}"
    echo ""
    echo -e "${BLUE}NOTE: These tests validate configuration parsing and validation logic${NC}"
    echo -e "${BLUE}without requiring external dependencies like BigQuery or DuckDB.${NC}"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}=============================================${NC}"
    echo -e "${RED}✗ Some configuration tests FAILED${NC}"
    echo -e "${RED}=============================================${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting tips:${NC}"
    echo -e "${YELLOW}  - Ensure you're in the bigquery-with-bacalhau directory${NC}"
    echo -e "${YELLOW}  - Check that pytest and pyyaml are installed: pip install pytest pyyaml${NC}"
    echo -e "${YELLOW}  - Run individual tests for more details:${NC}"
    echo -e "${YELLOW}    pytest tests/test_config_runtime_validation.py::TestConfigurationRuntimeValidation::test_badly_formatted_config_detection -v${NC}"
    echo ""
    echo -e "${BLUE}For other tests that require full dependencies:${NC}"
    echo -e "${BLUE}  - Install dependencies: pip install -r tests/requirements.txt${NC}"
    echo -e "${BLUE}  - Run: EXECUTABLE_DIR=bigquery-uploader CONFIG_FILE=tests/test_config.yaml pytest tests/test_basic.py -v${NC}"
    echo ""
    exit 1
fi
