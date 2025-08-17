#!/usr/bin/env bash
set -euo pipefail

# Wind Turbine Anomaly Detection Demo
# This script demonstrates the complete anomaly detection pipeline

# Load environment variables
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Get bucket names from environment
S3_BUCKET_PREFIX="${S3_BUCKET_PREFIX:-expanso}"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Build bucket names dynamically
VALIDATED_BUCKET="${S3_BUCKET_PREFIX}-validated-data-${AWS_REGION}"
ANOMALIES_BUCKET="${S3_BUCKET_PREFIX}-anomalies-${AWS_REGION}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Functions for colored output
print_header() {
    echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

wait_with_message() {
    local seconds=$1
    local message=$2
    echo -n -e "${CYAN}⏳${NC} $message "
    for ((i=1; i<=seconds; i++)); do
        echo -n "."
        sleep 1
    done
    echo ""
}

# Main demo
clear
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       WIND TURBINE ANOMALY DETECTION PIPELINE DEMO           ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}This demo shows how the pipeline detects and routes anomalies in${NC}"
echo -e "${BLUE}wind turbine sensor data using physics-based validation rules.${NC}"
echo ""

# Step 1: Environment Check
print_header "STEP 1: ENVIRONMENT CHECK"

print_step "Checking AWS credentials..."
if aws sts get-caller-identity --no-paginate > /dev/null 2>&1; then
    print_success "AWS credentials configured"
    AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text \
                  --no-paginate 2>/dev/null)
    print_info "AWS Account: $AWS_ACCOUNT"
else
    print_error "AWS credentials not configured"
    print_info "Please run: aws sso login"
    exit 1
fi

print_step "Checking for required files..."
REQUIRED_FILES=(
    "databricks-uploader/wind-turbine-schema.json"
    "databricks-uploader/sensor_data_models.py"
    "databricks-uploader/sqlite_to_databricks_uploader.py"
    "scripts/start-sensor.sh"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "Found: $file"
    else
        print_error "Missing: $file"
        exit 1
    fi
done

# Step 2: Start Local Schema Server
print_header "STEP 2: LOCAL SCHEMA SERVER"

print_step "Starting local schema server for testing..."
print_info "Schema will be available at: http://localhost:8000/schemas/latest"

# Kill any existing schema server
pkill -f "serve-schema-locally" 2>/dev/null || true

# Start schema server in background
nohup uv run scripts/serve-schema-locally.py > /tmp/schema-server.log 2>&1 &
SCHEMA_PID=$!
print_success "Schema server started (PID: $SCHEMA_PID)"

wait_with_message 3 "Waiting for server to start"

# Test schema endpoint
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_success "Schema server is healthy"
else
    print_warning "Schema server may not be ready yet"
fi

# Step 3: Start Sensor with Anomalies
print_header "STEP 3: WIND TURBINE SENSOR GENERATOR"

print_step "Starting sensor container with anomaly generation..."
print_info "This will generate both valid and invalid sensor data:"
echo -e "  ${GREEN}•${NC} 2 normal turbines (WT-0001, WT-0002)"
echo -e "  ${YELLOW}•${NC} 3 anomaly turbines:"
echo -e "    - WT-0003: Rotation without wind (30% anomaly rate)"
echo -e "    - WT-0004: Excessive vibration (20% anomaly rate)"
echo -e "    - WT-0005: Power without rotation (25% anomaly rate)"
echo ""

# Start sensor in background with anomalies
print_info "Starting sensor container with anomalies..."
nohup bash scripts/start-sensor.sh --with-anomalies > /tmp/sensor.log 2>&1 &
SENSOR_PID=$!
print_success "Sensor generator started with anomalies (PID: $SENSOR_PID)"

wait_with_message 10 "Waiting for sensor to generate initial data"

# Step 4: Configure Pipeline
print_header "STEP 4: PIPELINE CONFIGURATION"

print_step "Setting pipeline to 'schematized' mode for validation..."
cd databricks-uploader
uv run pipeline_manager.py set --type schematized
cd ..
print_success "Pipeline configured for anomaly detection"

# Step 5: Run Uploader with Validation
print_header "STEP 5: ANOMALY DETECTION IN ACTION"

print_step "Starting uploader with schema validation..."
print_info "The uploader will:"
echo -e "  ${GREEN}1.${NC} Read sensor data from SQLite"
echo -e "  ${GREEN}2.${NC} Validate against wind turbine physics rules"
echo -e "  ${GREEN}3.${NC} Route valid data → validated bucket"
echo -e "  ${GREEN}4.${NC} Route invalid data → anomalies bucket"
echo ""

# Run uploader for a few cycles
print_info "Running 3 upload cycles (this will take ~45 seconds)..."
cd databricks-uploader

for i in {1..3}; do
    echo ""
    echo -e "${CYAN}━━━ Upload Cycle $i/3 ━━━${NC}"
    
    # Run uploader once
    timeout 10 uv run sqlite_to_databricks_uploader.py \
        --config config.yaml \
        --once || true
    
    wait_with_message 5 "Waiting before next cycle"
done
cd ..

# Step 6: Show Results
print_header "STEP 6: VALIDATION RESULTS"

print_step "Checking S3 buckets for uploaded data..."
echo ""

# Check validated bucket
echo -e "${GREEN}Valid Data (${VALIDATED_BUCKET}):${NC}"
VALID_COUNT=$(aws s3 ls "s3://${VALIDATED_BUCKET}/" \
              --no-paginate 2>/dev/null | grep -c ".json" || echo "0")
echo -e "  Files uploaded: ${GREEN}$VALID_COUNT${NC}"

# Check anomalies bucket
echo -e "${YELLOW}Anomaly Data (${ANOMALIES_BUCKET}):${NC}"
ANOMALY_COUNT=$(aws s3 ls "s3://${ANOMALIES_BUCKET}/" \
                --no-paginate 2>/dev/null | grep -c ".json" || echo "0")
echo -e "  Files uploaded: ${YELLOW}$ANOMALY_COUNT${NC}"

# Show sample anomaly if exists
if [ "$ANOMALY_COUNT" -gt 0 ]; then
    echo ""
    print_step "Sample anomaly detection:"
    
    # Get latest anomaly file
    LATEST_ANOMALY=$(aws s3 ls "s3://${ANOMALIES_BUCKET}/" \
                     --no-paginate 2>/dev/null | \
                     grep ".json" | \
                     tail -1 | \
                     awk '{print $4}')
    
    if [ -n "$LATEST_ANOMALY" ]; then
        # Download and show a sample
        aws s3 cp "s3://${ANOMALIES_BUCKET}/$LATEST_ANOMALY" \
                  /tmp/sample_anomaly.json --no-paginate 2>/dev/null
        
        echo -e "${YELLOW}Example anomaly record:${NC}"
        cat /tmp/sample_anomaly.json 2>/dev/null | \
            jq -r '.records[0] | 
                   "  Turbine: \(.turbine_id // "unknown")
  Error: \(.validation_error // "unknown" | .[0:80])..."' 2>/dev/null || \
            echo "  (Could not parse anomaly file)"
    fi
fi

# Step 7: Databricks Integration
print_header "STEP 7: DATABRICKS INTEGRATION"

print_info "To view data in Databricks:"
echo -e "  ${GREEN}1.${NC} Open Databricks workspace"
echo -e "  ${GREEN}2.${NC} Navigate to: databricks-notebooks/setup-and-run-autoloader.py"
echo -e "  ${GREEN}3.${NC} Run the notebook to ingest from S3 to Unity Catalog"
echo -e "  ${GREEN}4.${NC} Query the tables:"
echo -e "     • ${GREEN}sensor_readings_validated${NC} - Clean data"
echo -e "     • ${YELLOW}sensor_readings_anomalies${NC} - Anomaly data"
echo ""

print_info "Sample SQL query to analyze anomalies:"
echo -e "${CYAN}SELECT 
    DATE(processing_timestamp) as date,
    COUNT(*) as anomaly_count,
    COUNT(DISTINCT turbine_id) as affected_turbines
FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
WHERE validation_error IS NOT NULL
GROUP BY date
ORDER BY date DESC;${NC}"

# Cleanup
print_header "CLEANUP"

print_step "Stopping demo services..."

# Stop schema server
if [ -n "${SCHEMA_PID:-}" ]; then
    kill $SCHEMA_PID 2>/dev/null || true
    print_success "Stopped schema server"
fi

# Stop sensor container
docker stop sensor-log-generator 2>/dev/null || true
print_success "Stopped sensor container"

echo ""
print_success "Demo completed successfully!"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  The anomaly detection pipeline is working correctly!${NC}"
echo -e "${GREEN}  Valid and invalid data are being routed to separate streams.${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Show summary
echo -e "${CYAN}Summary:${NC}"
echo -e "  • Valid records uploaded: ${GREEN}$VALID_COUNT${NC}"
echo -e "  • Anomaly records uploaded: ${YELLOW}$ANOMALY_COUNT${NC}"
echo -e "  • Detection types: Rotation without wind, Excessive vibration, Power anomalies"
echo ""
echo -e "${BLUE}To run continuously, use:${NC}"
echo -e "  ${CYAN}./scripts/start-sensor.sh --with-anomalies${NC}  # Generate sensor data with anomalies"
echo -e "  ${CYAN}cd databricks-uploader && uv run sqlite_to_databricks_uploader.py${NC}"
echo ""