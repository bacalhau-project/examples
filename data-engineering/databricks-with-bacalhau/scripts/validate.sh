#!/usr/bin/env bash
set -euo pipefail

# Unified Validation Script
# Validates environment, configuration, and resources

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
print_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_check() { echo -e "${BLUE}[CHECK]${NC} $1"; }

# Default values
CHECK_ALL=true
CHECK_ENV=false
CHECK_AWS=false
CHECK_DATABRICKS=false
CHECK_DOCKER=false
CHECK_SENSOR=false

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  --all           Run all validation checks (default)
  --env           Check environment variables only
  --aws           Check AWS resources only
  --databricks    Check Databricks configuration only
  --docker        Check Docker setup only
  --sensor        Check sensor setup only
  --help          Show this help message

Examples:
  $0              # Run all checks
  $0 --env        # Check environment only
  $0 --aws        # Check AWS resources only

EOF
    exit 0
}

# Parse arguments
if [[ $# -gt 0 ]]; then
    CHECK_ALL=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                CHECK_ALL=true
                shift
                ;;
            --env)
                CHECK_ENV=true
                shift
                ;;
            --aws)
                CHECK_AWS=true
                shift
                ;;
            --databricks)
                CHECK_DATABRICKS=true
                shift
                ;;
            --docker)
                CHECK_DOCKER=true
                shift
                ;;
            --sensor)
                CHECK_SENSOR=true
                shift
                ;;
            --help|-h)
                usage
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                ;;
        esac
    done
fi

# If --all or no specific checks, enable all
if [ "$CHECK_ALL" = true ]; then
    CHECK_ENV=true
    CHECK_AWS=true
    CHECK_DATABRICKS=true
    CHECK_DOCKER=true
    CHECK_SENSOR=true
fi

# Track validation status
VALIDATION_FAILED=false

# Environment validation
validate_environment() {
    print_info "Validating environment configuration..."
    
    # Check .env file
    if [ -f .env ]; then
        print_success ".env file exists"
        source .env
    else
        print_error ".env file not found"
        print_info "Copy .env.example to .env and configure it"
        VALIDATION_FAILED=true
        return
    fi
    
    # Check required environment variables
    local required_vars=(
        "AWS_REGION"
        "DATABRICKS_HOST"
        "DATABRICKS_TOKEN"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            print_error "$var is not set"
            VALIDATION_FAILED=true
        else
            print_success "$var is set"
        fi
    done
    
    # Check AWS credentials
    if [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
        print_success "AWS credentials found in environment"
    elif [ -f credentials/expanso-s3-env.sh ]; then
        print_success "AWS credentials file found"
        source credentials/expanso-s3-env.sh
    else
        print_warning "AWS credentials not found in environment or credentials file"
    fi
}

# AWS validation
validate_aws() {
    print_info "Validating AWS resources..."
    
    # Check AWS CLI
    if ! command -v aws &>/dev/null; then
        print_error "AWS CLI not installed"
        VALIDATION_FAILED=true
        return
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --no-paginate &>/dev/null; then
        print_error "Unable to authenticate with AWS"
        VALIDATION_FAILED=true
        return
    fi
    
    local account_id=$(aws sts get-caller-identity --query Account --output text --no-paginate)
    print_success "AWS Account: $account_id"
    
    # Check S3 buckets
    local region="${AWS_REGION:-us-west-2}"
    local buckets=(
        "expanso-raw-data-${region}"
        "expanso-databricks-ingestion-${region}"
        "expanso-databricks-validated-${region}"
        "expanso-databricks-enriched-${region}"
        "expanso-databricks-aggregated-${region}"
    )
    
    print_check "Checking S3 buckets..."
    for bucket in "${buckets[@]}"; do
        if aws s3api head-bucket --bucket "$bucket" --no-paginate 2>/dev/null; then
            print_success "Bucket exists: $bucket"
        else
            print_warning "Bucket missing: $bucket"
        fi
    done
    
    # Check IAM user
    if aws iam get-user --user-name expanso-databricks-s3-user --no-paginate &>/dev/null; then
        print_success "IAM user exists: expanso-databricks-s3-user"
    else
        print_warning "IAM user missing: expanso-databricks-s3-user"
    fi
}

# Databricks validation
validate_databricks() {
    print_info "Validating Databricks configuration..."
    
    # Check Databricks CLI
    if ! command -v databricks &>/dev/null; then
        print_warning "Databricks CLI not installed"
        return
    fi
    
    # Check connection
    if [ -n "${DATABRICKS_HOST:-}" ] && [ -n "${DATABRICKS_TOKEN:-}" ]; then
        if databricks current-user me 2>/dev/null | grep -q userName; then
            print_success "Databricks connection successful"
        else
            print_error "Unable to connect to Databricks"
            VALIDATION_FAILED=true
        fi
    else
        print_warning "Databricks credentials not configured"
    fi
    
    # Check notebooks directory
    if [ -d databricks-notebooks ]; then
        local notebook_count=$(find databricks-notebooks -name "*.py" | wc -l)
        print_success "Found $notebook_count Databricks notebooks"
    else
        print_warning "databricks-notebooks directory not found"
    fi
}

# Docker validation
validate_docker() {
    print_info "Validating Docker setup..."
    
    # Check Docker
    if ! command -v docker &>/dev/null; then
        print_error "Docker not installed"
        VALIDATION_FAILED=true
        return
    fi
    
    # Check Docker daemon
    if ! docker info &>/dev/null; then
        print_error "Docker daemon not running"
        VALIDATION_FAILED=true
        return
    fi
    
    print_success "Docker is running"
    
    # Check for sensor image
    if docker images | grep -q "sensor-log-generator"; then
        print_success "Sensor image found"
    else
        print_warning "Sensor image not found locally"
    fi
    
    # Check running containers
    local container_count=$(docker ps -q | wc -l)
    if [ "$container_count" -gt 0 ]; then
        print_info "$container_count container(s) running"
    fi
}

# Sensor validation
validate_sensor() {
    print_info "Validating sensor setup..."
    
    # Check sensor config
    if [ -f sample-sensor/sensor-config.yaml ]; then
        print_success "Sensor config found"
    else
        print_error "sample-sensor/sensor-config.yaml not found"
        VALIDATION_FAILED=true
    fi
    
    # Check identity file
    if [ -f sample-sensor/identity.json ] || [ -f sample-sensor/node-identity.json ]; then
        print_success "Sensor identity file found"
    else
        print_error "No identity file found in sample-sensor/"
        VALIDATION_FAILED=true
    fi
    
    # Check sensor database
    if [ -f sample-sensor/data/sensor_data.db ]; then
        local record_count=$(sqlite3 sample-sensor/data/sensor_data.db \
            "SELECT COUNT(*) FROM sensor_readings" 2>/dev/null || echo "0")
        print_success "Sensor database exists with $record_count records"
    else
        print_info "Sensor database not yet created"
    fi
    
    # Check if sensor is running
    if docker ps | grep -q sensor-log-generator; then
        print_success "Sensor container is running"
    else
        print_info "Sensor container not running"
    fi
}

# Main validation
echo "================================"
echo "   System Validation Report"
echo "================================"
echo ""

if [ "$CHECK_ENV" = true ]; then
    validate_environment
    echo ""
fi

if [ "$CHECK_AWS" = true ]; then
    validate_aws
    echo ""
fi

if [ "$CHECK_DATABRICKS" = true ]; then
    validate_databricks
    echo ""
fi

if [ "$CHECK_DOCKER" = true ]; then
    validate_docker
    echo ""
fi

if [ "$CHECK_SENSOR" = true ]; then
    validate_sensor
    echo ""
fi

# Final report
echo "================================"
if [ "$VALIDATION_FAILED" = true ]; then
    print_error "Validation FAILED - Some issues need to be resolved"
    exit 1
else
    print_success "Validation PASSED - System is ready"
    exit 0
fi