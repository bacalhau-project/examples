#!/usr/bin/env bash
set -euo pipefail

# Unified IAM Management Script for Databricks Integration
# Handles IAM users, roles, and policies for S3 and Unity Catalog access

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
AWS_REGION="${AWS_REGION:-us-west-2}"
IAM_USER="expanso-databricks-s3-user"
IAM_ROLE="expanso-databricks-unity-catalog-role"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --no-paginate 2>/dev/null || echo "")

# Show usage
usage() {
    cat << EOF
Usage: $0 [ACTION] [OPTIONS]

Actions:
  setup-user       Setup IAM user with S3 permissions
  setup-role       Setup IAM role for Unity Catalog
  fix-permissions  Fix all IAM permissions
  show-status      Show current IAM configuration
  cleanup          Remove IAM resources

Options:
  --user NAME      IAM user name (default: expanso-databricks-s3-user)
  --role NAME      IAM role name (default: expanso-databricks-unity-catalog-role)
  --region REGION  AWS region (default: us-west-2)
  --help           Show this help message

Examples:
  $0 setup-user              # Setup S3 user with permissions
  $0 setup-role              # Setup Unity Catalog role
  $0 fix-permissions         # Fix all permissions
  $0 show-status             # Show current configuration

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        setup-user|setup-role|fix-permissions|show-status|cleanup)
            ACTION="$1"
            shift
            ;;
        --user)
            IAM_USER="$2"
            shift 2
            ;;
        --role)
            IAM_ROLE="$2"
            shift 2
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

# Check AWS credentials
if [ -z "$ACCOUNT_ID" ]; then
    print_error "Unable to get AWS account ID. Check your AWS credentials."
    exit 1
fi

# Define S3 buckets
declare -a BUCKETS=(
    "expanso-databricks-ingestion-${AWS_REGION}"
    "expanso-databricks-validated-${AWS_REGION}"
    "expanso-databricks-enriched-${AWS_REGION}"
    "expanso-databricks-aggregated-${AWS_REGION}"
    "expanso-databricks-checkpoints-${AWS_REGION}"
    "expanso-databricks-output-${AWS_REGION}"
    "expanso-databricks-anomalies-${AWS_REGION}"
    "expanso-raw-data-${AWS_REGION}"
)

# Setup IAM user for S3 access
setup_iam_user() {
    print_info "Setting up IAM user: $IAM_USER"
    
    # Check if user exists
    if aws iam get-user --user-name "$IAM_USER" --no-paginate &>/dev/null; then
        print_info "User $IAM_USER already exists"
    else
        aws iam create-user --user-name "$IAM_USER" --no-paginate
        print_success "Created IAM user: $IAM_USER"
    fi
    
    # Create S3 access policy
    local policy_name="${IAM_USER}-s3-policy"
    local policy_doc=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetBucketVersioning"
            ],
            "Resource": [
$(printf '                "arn:aws:s3:::%s",\n' "${BUCKETS[@]}" | sed '$ s/,$//')
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:GetObjectVersion",
                "s3:DeleteObjectVersion"
            ],
            "Resource": [
$(printf '                "arn:aws:s3:::%s/*",\n' "${BUCKETS[@]}" | sed '$ s/,$//')
            ]
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListAllMyBuckets",
            "Resource": "*"
        }
    ]
}
EOF
)
    
    # Attach policy to user
    aws iam put-user-policy \
        --user-name "$IAM_USER" \
        --policy-name "$policy_name" \
        --policy-document "$policy_doc" \
        --no-paginate
    
    print_success "Attached S3 policy to user $IAM_USER"
    
    # Check for access keys
    local keys=$(aws iam list-access-keys --user-name "$IAM_USER" \
        --query 'AccessKeyMetadata[].AccessKeyId' --output text --no-paginate)
    
    if [ -z "$keys" ]; then
        print_warning "No access keys found for $IAM_USER"
        print_info "Run: aws iam create-access-key --user-name $IAM_USER"
    else
        print_info "Access keys exist for $IAM_USER"
    fi
}

# Setup IAM role for Unity Catalog
setup_iam_role() {
    print_info "Setting up IAM role: $IAM_ROLE"
    
    # Create trust policy for Unity Catalog
    local trust_policy=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::414351767826:root"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "databricks-unity-catalog"
                }
            }
        },
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::${ACCOUNT_ID}:role/${IAM_ROLE}"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
)
    
    # Check if role exists
    if aws iam get-role --role-name "$IAM_ROLE" --no-paginate &>/dev/null; then
        print_info "Updating trust policy for existing role"
        aws iam update-assume-role-policy \
            --role-name "$IAM_ROLE" \
            --policy-document "$trust_policy" \
            --no-paginate
    else
        aws iam create-role \
            --role-name "$IAM_ROLE" \
            --assume-role-policy-document "$trust_policy" \
            --no-paginate
        print_success "Created IAM role: $IAM_ROLE"
    fi
    
    # Create S3 access policy for role
    local policy_doc=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetLifecycleConfiguration",
                "s3:PutLifecycleConfiguration"
            ],
            "Resource": [
$(printf '                "arn:aws:s3:::%s",\n' "${BUCKETS[@]}" | sed '$ s/,$//')
$(printf '                "arn:aws:s3:::%s/*",\n' "${BUCKETS[@]}" | sed '$ s/,$//')
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Resource": [
                "arn:aws:iam::${ACCOUNT_ID}:role/${IAM_ROLE}"
            ]
        }
    ]
}
EOF
)
    
    # Attach policy to role
    aws iam put-role-policy \
        --role-name "$IAM_ROLE" \
        --policy-name "${IAM_ROLE}-policy" \
        --policy-document "$policy_doc" \
        --no-paginate
    
    print_success "Attached S3 policy to role $IAM_ROLE"
    print_info "Role ARN: arn:aws:iam::${ACCOUNT_ID}:role/${IAM_ROLE}"
}

# Fix all permissions
fix_all_permissions() {
    print_info "Fixing all IAM permissions..."
    setup_iam_user
    setup_iam_role
    print_success "All permissions fixed"
}

# Show current status
show_status() {
    print_info "Current IAM Configuration:"
    echo ""
    
    # Check user
    if aws iam get-user --user-name "$IAM_USER" --no-paginate &>/dev/null; then
        echo -e "${GREEN}✓${NC} IAM User: $IAM_USER exists"
        
        # Check policies
        local policies=$(aws iam list-user-policies --user-name "$IAM_USER" \
            --query 'PolicyNames[]' --output text --no-paginate)
        if [ -n "$policies" ]; then
            echo -e "  ${BLUE}Policies:${NC} $policies"
        fi
        
        # Check access keys
        local keys=$(aws iam list-access-keys --user-name "$IAM_USER" \
            --query 'AccessKeyMetadata[].AccessKeyId' --output text --no-paginate)
        if [ -n "$keys" ]; then
            echo -e "  ${BLUE}Access Keys:${NC} $keys"
        else
            echo -e "  ${YELLOW}No access keys${NC}"
        fi
    else
        echo -e "${RED}✗${NC} IAM User: $IAM_USER does not exist"
    fi
    
    echo ""
    
    # Check role
    if aws iam get-role --role-name "$IAM_ROLE" --no-paginate &>/dev/null; then
        echo -e "${GREEN}✓${NC} IAM Role: $IAM_ROLE exists"
        echo -e "  ${BLUE}ARN:${NC} arn:aws:iam::${ACCOUNT_ID}:role/${IAM_ROLE}"
        
        # Check policies
        local policies=$(aws iam list-role-policies --role-name "$IAM_ROLE" \
            --query 'PolicyNames[]' --output text --no-paginate)
        if [ -n "$policies" ]; then
            echo -e "  ${BLUE}Policies:${NC} $policies"
        fi
    else
        echo -e "${RED}✗${NC} IAM Role: $IAM_ROLE does not exist"
    fi
}

# Cleanup IAM resources
cleanup_iam() {
    print_warning "This will remove IAM user and role!"
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Cleanup cancelled"
        exit 0
    fi
    
    # Delete user
    if aws iam get-user --user-name "$IAM_USER" --no-paginate &>/dev/null; then
        # Delete access keys
        aws iam list-access-keys --user-name "$IAM_USER" \
            --query 'AccessKeyMetadata[].AccessKeyId' --output text --no-paginate | \
        while read -r key; do
            aws iam delete-access-key --user-name "$IAM_USER" --access-key-id "$key" --no-paginate
        done
        
        # Delete policies
        aws iam list-user-policies --user-name "$IAM_USER" \
            --query 'PolicyNames[]' --output text --no-paginate | \
        while read -r policy; do
            aws iam delete-user-policy --user-name "$IAM_USER" --policy-name "$policy" --no-paginate
        done
        
        # Delete user
        aws iam delete-user --user-name "$IAM_USER" --no-paginate
        print_success "Deleted IAM user: $IAM_USER"
    fi
    
    # Delete role
    if aws iam get-role --role-name "$IAM_ROLE" --no-paginate &>/dev/null; then
        # Delete policies
        aws iam list-role-policies --role-name "$IAM_ROLE" \
            --query 'PolicyNames[]' --output text --no-paginate | \
        while read -r policy; do
            aws iam delete-role-policy --role-name "$IAM_ROLE" --policy-name "$policy" --no-paginate
        done
        
        # Delete role
        aws iam delete-role --role-name "$IAM_ROLE" --no-paginate
        print_success "Deleted IAM role: $IAM_ROLE"
    fi
}

# Execute action
case "$ACTION" in
    setup-user)
        setup_iam_user
        ;;
    setup-role)
        setup_iam_role
        ;;
    fix-permissions)
        fix_all_permissions
        ;;
    show-status)
        show_status
        ;;
    cleanup)
        cleanup_iam
        ;;
esac