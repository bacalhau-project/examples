#!/usr/bin/env bash
set -euo pipefail

# Unified S3 Bucket Management Script
# Handles creation, deletion, and listing of project S3 buckets

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
print_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Default values
ACTION=""
FORCE=false
PARALLEL=false
AWS_REGION="${AWS_REGION:-us-west-2}"

# Show usage
usage() {
    cat << EOF
Usage: $0 [ACTION] [OPTIONS]

Actions:
  create    Create all project S3 buckets
  delete    Delete all project S3 buckets
  list      List all project S3 buckets
  clean     Delete bucket contents only (keep buckets)

Options:
  --force        Skip confirmation prompts
  --parallel     Use parallel processing for faster operations
  --region       AWS region (default: us-west-2)
  --help         Show this help message

Examples:
  $0 create                    # Create all buckets
  $0 delete --force            # Delete all buckets without confirmation
  $0 list                      # List all project buckets
  $0 clean --parallel          # Clean bucket contents in parallel

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        create|delete|list|clean)
            ACTION="$1"
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
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

# Check if action is specified
if [ -z "$ACTION" ]; then
    print_error "No action specified"
    usage
fi

# Load environment if exists
if [ -f .env ]; then
    source .env
fi

# Define bucket names
declare -a BUCKETS=(
    "expanso-databricks-ingestion-${AWS_REGION}"
    "expanso-databricks-validated-${AWS_REGION}"
    "expanso-databricks-enriched-${AWS_REGION}"
    "expanso-databricks-aggregated-${AWS_REGION}"
    "expanso-databricks-checkpoints-${AWS_REGION}"
    "expanso-databricks-output-${AWS_REGION}"
    "expanso-databricks-anomalies-${AWS_REGION}"
)

# Additional buckets for raw data
declare -a RAW_BUCKETS=(
    "expanso-raw-data-${AWS_REGION}"
)

ALL_BUCKETS=("${BUCKETS[@]}" "${RAW_BUCKETS[@]}")

# Function to check if bucket exists
bucket_exists() {
    local bucket=$1
    aws s3api head-bucket --bucket "$bucket" --no-paginate 2>/dev/null
}

# Function to delete bucket with all versions
delete_bucket_completely() {
    local bucket=$1
    
    if ! bucket_exists "$bucket"; then
        print_info "Bucket $bucket does not exist"
        return 0
    fi
    
    print_info "Deleting bucket: $bucket"
    
    # Delete all object versions
    print_info "  Removing all object versions..."
    aws s3api list-object-versions --bucket "$bucket" --no-paginate \
        --query 'Versions[].{Key:Key,VersionId:VersionId}' \
        --output json 2>/dev/null | \
    jq -r '.[] | "--key \"\(.Key)\" --version-id \(.VersionId)"' | \
    while read -r args; do
        eval aws s3api delete-object --bucket "$bucket" $args --no-paginate 2>/dev/null
    done
    
    # Delete all delete markers
    print_info "  Removing delete markers..."
    aws s3api list-object-versions --bucket "$bucket" --no-paginate \
        --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' \
        --output json 2>/dev/null | \
    jq -r '.[] | "--key \"\(.Key)\" --version-id \(.VersionId)"' | \
    while read -r args; do
        eval aws s3api delete-object --bucket "$bucket" $args --no-paginate 2>/dev/null
    done
    
    # Delete the bucket
    aws s3api delete-bucket --bucket "$bucket" --no-paginate 2>/dev/null
    print_success "  Bucket $bucket deleted"
}

# Function to create bucket
create_bucket() {
    local bucket=$1
    
    if bucket_exists "$bucket"; then
        print_info "Bucket $bucket already exists"
        return 0
    fi
    
    print_info "Creating bucket: $bucket"
    
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$bucket" --no-paginate
    else
        aws s3api create-bucket --bucket "$bucket" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION" \
            --no-paginate
    fi
    
    # Enable versioning
    aws s3api put-bucket-versioning --bucket "$bucket" \
        --versioning-configuration Status=Enabled --no-paginate
    
    print_success "Bucket $bucket created with versioning enabled"
}

# Create action
if [ "$ACTION" = "create" ]; then
    print_info "Creating all project buckets in region $AWS_REGION..."
    
    for bucket in "${ALL_BUCKETS[@]}"; do
        create_bucket "$bucket"
    done
    
    print_success "All buckets created successfully"
    
# Delete action
elif [ "$ACTION" = "delete" ]; then
    print_warning "This will PERMANENTLY DELETE all project buckets and their contents!"
    
    if [ "$FORCE" != true ]; then
        read -p "Are you sure? Type 'yes' to confirm: " confirm
        if [ "$confirm" != "yes" ]; then
            print_info "Deletion cancelled"
            exit 0
        fi
    fi
    
    print_info "Deleting all project buckets..."
    
    if [ "$PARALLEL" = true ]; then
        # Parallel deletion
        export -f bucket_exists delete_bucket_completely print_info print_success print_error
        export AWS_REGION NC RED GREEN YELLOW BLUE
        printf '%s\n' "${ALL_BUCKETS[@]}" | \
            xargs -P 8 -I {} bash -c 'delete_bucket_completely "$@"' _ {}
    else
        # Sequential deletion
        for bucket in "${ALL_BUCKETS[@]}"; do
            delete_bucket_completely "$bucket"
        done
    fi
    
    print_success "All buckets deleted successfully"
    
# List action
elif [ "$ACTION" = "list" ]; then
    print_info "Listing project buckets in region $AWS_REGION..."
    
    for bucket in "${ALL_BUCKETS[@]}"; do
        if bucket_exists "$bucket"; then
            size=$(aws s3api list-objects-v2 --bucket "$bucket" \
                --query 'sum(Contents[].Size)' --output text --no-paginate 2>/dev/null || echo "0")
            count=$(aws s3api list-objects-v2 --bucket "$bucket" \
                --query 'length(Contents)' --output text --no-paginate 2>/dev/null || echo "0")
            
            if [ "$size" = "None" ]; then size=0; fi
            if [ "$count" = "None" ]; then count=0; fi
            
            size_mb=$(echo "scale=2; $size / 1048576" | bc 2>/dev/null || echo "0")
            echo -e "${GREEN}✓${NC} $bucket - ${count} objects, ${size_mb}MB"
        else
            echo -e "${RED}✗${NC} $bucket - does not exist"
        fi
    done
    
# Clean action
elif [ "$ACTION" = "clean" ]; then
    print_info "Cleaning contents of all project buckets (keeping buckets)..."
    
    for bucket in "${ALL_BUCKETS[@]}"; do
        if bucket_exists "$bucket"; then
            print_info "Cleaning bucket: $bucket"
            aws s3 rm "s3://$bucket" --recursive --no-paginate 2>/dev/null || true
            print_success "  Bucket $bucket cleaned"
        fi
    done
    
    print_success "All buckets cleaned successfully"
fi