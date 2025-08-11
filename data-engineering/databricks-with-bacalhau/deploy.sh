#!/bin/bash
# Deploy script for Databricks-Bacalhau pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[DEPLOY]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Default values
TARGET=""
ENV_FILE=".env"
SKIP_VALIDATION=""
SKIP_BUILD=""
DRY_RUN=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --skip-validation)
            SKIP_VALIDATION="true"
            shift
            ;;
        --skip-build)
            SKIP_BUILD="true"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --help)
            echo "Usage: $0 --target TARGET [OPTIONS]"
            echo ""
            echo "Targets:"
            echo "  databricks          Deploy Databricks notebooks and setup"
            echo "  bacalhau           Deploy to Bacalhau network"
            echo "  docker             Deploy using Docker"
            echo "  aws                Deploy AWS infrastructure (S3, IAM)"
            echo "  full               Deploy everything"
            echo ""
            echo "Options:"
            echo "  --target TARGET     Deployment target (required)"
            echo "  --env-file FILE     Environment file (default: .env)"
            echo "  --skip-validation   Skip validation checks"
            echo "  --skip-build       Skip building Docker images"
            echo "  --dry-run          Show what would be deployed without \
deploying"
            echo "  --help             Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --target databricks"
            echo "  $0 --target full --skip-validation"
            echo "  $0 --target bacalhau --dry-run"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if target is specified
if [ -z "$TARGET" ]; then
    print_error "Target is required. Use --help for usage information."
    exit 1
fi

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    print_error "Environment file not found: $ENV_FILE"
    print_info "Copy .env.example to .env and configure it"
    exit 1
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

# Function to validate environment
validate_environment() {
    print_status "Validating environment..."
    
    local validation_failed=false
    
    # Check required environment variables
    local required_vars=(
        "DATABRICKS_HOST"
        "DATABRICKS_TOKEN"
        "DATABRICKS_DATABASE"
        "AWS_REGION"
        "S3_BUCKET_PREFIX"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            print_error "$var is not set in $ENV_FILE"
            validation_failed=true
        fi
    done
    
    # Run validation script
    if [ -f "scripts/validate-all.py" ]; then
        print_info "Running validation checks..."
        if ! uv run -s scripts/validate-all.py; then
            validation_failed=true
        fi
    fi
    
    if [ "$validation_failed" == "true" ]; then
        print_error "Validation failed. Fix issues before deploying."
        exit 1
    fi
    
    print_status "Validation passed!"
}

# Function to deploy Databricks components
deploy_databricks() {
    print_status "Deploying to Databricks..."
    
    if [ "$DRY_RUN" == "true" ]; then
        print_info "[DRY RUN] Would deploy the following notebooks:"
        echo "  - databricks-notebooks/flexible-autoloader.py"
        echo "  - databricks-notebooks/setup-and-run-autoloader.py"
        print_info "[DRY RUN] Would create Unity Catalog resources:"
        echo "  - Schema: ${DATABRICKS_DATABASE}"
        echo "  - External locations for S3 buckets"
        echo "  - Storage credentials"
        return
    fi
    
    # Upload notebooks
    print_status "Uploading notebooks to Databricks..."
    uv run -s scripts/upload-and-run-notebook.py \
        --notebook databricks-notebooks/flexible-autoloader.py \
        --workspace-path /Shared/sensor-pipeline/flexible-autoloader
    
    uv run -s scripts/upload-and-run-notebook.py \
        --notebook databricks-notebooks/setup-and-run-autoloader.py \
        --workspace-path /Shared/sensor-pipeline/setup-and-run-autoloader
    
    # Setup Unity Catalog
    print_status "Setting up Unity Catalog..."
    uv run -s scripts/setup-unity-catalog-storage.py
    
    # Create external locations
    print_status "Creating external locations..."
    uv run -s scripts/setup-external-locations.py
    
    # Start SQL warehouse if needed
    print_status "Starting SQL warehouse..."
    uv run -s scripts/start-sql-warehouse.py
    
    print_status "Databricks deployment complete!"
}

# Function to deploy to Bacalhau
deploy_bacalhau() {
    print_status "Deploying to Bacalhau..."
    
    if [ "$DRY_RUN" == "true" ]; then
        print_info "[DRY RUN] Would submit the following Bacalhau jobs:"
        echo "  - jobs/databricks-uploader-job.yaml"
        return
    fi
    
    # Check if Bacalhau is installed
    if ! command -v bacalhau &> /dev/null; then
        print_error "Bacalhau is not installed"
        print_info "Install from: https://docs.bacalhau.org/getting-started/installation"
        exit 1
    fi
    
    # Build Docker image if not skipped
    if [ "$SKIP_BUILD" != "true" ]; then
        print_status "Building Docker image for Bacalhau..."
        ./build.sh --component databricks-uploader --push
    fi
    
    # Submit job to Bacalhau
    print_status "Submitting job to Bacalhau..."
    bacalhau job run jobs/databricks-uploader-job.yaml
    
    print_status "Bacalhau deployment complete!"
}

# Function to deploy with Docker
deploy_docker() {
    print_status "Deploying with Docker..."
    
    if [ "$DRY_RUN" == "true" ]; then
        print_info "[DRY RUN] Would start the following containers:"
        echo "  - databricks-uploader"
        echo "  - pipeline-manager"
        return
    fi
    
    # Build images if not skipped
    if [ "$SKIP_BUILD" != "true" ]; then
        print_status "Building Docker images..."
        ./build.sh --component all
    fi
    
    # Start all containers
    print_status "Starting Docker containers..."
    ./docker-run-helper.sh start-all
    
    print_status "Docker deployment complete!"
}

# Function to deploy AWS infrastructure
deploy_aws() {
    print_status "Deploying AWS infrastructure..."
    
    if [ "$DRY_RUN" == "true" ]; then
        print_info "[DRY RUN] Would create the following AWS resources:"
        echo "  - S3 buckets: ${S3_BUCKET_PREFIX}-*"
        echo "  - IAM roles for Databricks access"
        echo "  - S3 lifecycle policies"
        return
    fi
    
    # Create S3 buckets
    print_status "Creating S3 buckets..."
    ./scripts/create-pipeline-buckets.sh
    
    # Setup Databricks S3 access
    print_status "Setting up Databricks S3 access..."
    ./scripts/setup-databricks-s3-access.sh
    
    # Update IAM roles
    print_status "Updating IAM roles..."
    ./scripts/update-iam-role-for-new-buckets.sh
    
    print_status "AWS deployment complete!"
}

# Function to deploy everything
deploy_full() {
    print_status "Starting full deployment..."
    
    # Deploy in order
    deploy_aws
    deploy_databricks
    deploy_docker
    
    print_status "Full deployment complete!"
    
    # Show status
    print_info "Deployment Summary:"
    echo ""
    echo "  AWS Resources:     ✓ Created"
    echo "  Databricks Setup:  ✓ Configured"
    echo "  Docker Containers: ✓ Running"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor logs: ./docker-run-helper.sh logs -f"
    echo "  2. Check status: ./docker-run-helper.sh status"
    echo "  3. View Databricks: ${DATABRICKS_HOST}"
}

# Main execution
if [ "$SKIP_VALIDATION" != "true" ]; then
    validate_environment
fi

case $TARGET in
    databricks)
        deploy_databricks
        ;;
    bacalhau)
        deploy_bacalhau
        ;;
    docker)
        deploy_docker
        ;;
    aws)
        deploy_aws
        ;;
    full)
        deploy_full
        ;;
    *)
        print_error "Unknown target: $TARGET"
        print_error "Valid targets: databricks, bacalhau, docker, aws, full"
        exit 1
        ;;
esac

if [ "$DRY_RUN" == "true" ]; then
    print_info "This was a dry run. No changes were made."
fi