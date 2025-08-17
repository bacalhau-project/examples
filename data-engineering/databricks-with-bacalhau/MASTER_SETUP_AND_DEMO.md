# Wind Turbine Data Pipeline - Complete Setup and Demo Guide

This is the **single, authoritative guide** for setting up and demonstrating the wind turbine data pipeline with anomaly detection. Follow these steps in order to go from zero to a fully working demo.

## Prerequisites

Before starting, ensure you have:
- AWS CLI configured with appropriate credentials
- Databricks workspace with Unity Catalog enabled
- Docker installed and running
- Python 3.11+ with uv package manager
- Bacalhau CLI installed (v1.5.0+)

## Initial Setup

### Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your settings:
# Required variables:
# - S3_BUCKET_PREFIX (e.g., 'expanso' - no trailing dash)
# - AWS_REGION (e.g., us-west-2)
# - DATABRICKS_HOST (your workspace URL)
# - DATABRICKS_TOKEN (personal access token)
# - DATABRICKS_HTTP_PATH (e.g., /sql/1.0/warehouses/xxxxx)
# - DATABRICKS_DATABASE (database name, e.g., sensor_readings)
# - DATABRICKS_ACCOUNT_ID (from Databricks admin console)
# - DATABRICKS_EXTERNAL_ID (from Unity Catalog storage credential setup)
# - DATABRICKS_USER_EMAIL (your email)

# Validate your configuration
./scripts/validate-env.sh

# Note: The S3_BUCKET_PREFIX should be simple (e.g., 'expanso' not 'expanso-databricks')
# Buckets will be created as: prefix-raw-data-region, prefix-validated-data-region, etc.
```

## Part 1: Infrastructure Setup

### Step 1.1: Create S3 Buckets

Create all required S3 buckets for the pipeline stages:

```bash
# Clean up any old buckets from previous runs (optional but recommended)
source .env

# Remove old naming pattern buckets (e.g., expanso-databricks-*)
./scripts/turbo-delete-buckets.py --pattern "${S3_BUCKET_PREFIX}-databricks-"

# Remove current pattern buckets if doing a fresh start
./scripts/turbo-delete-buckets.py --pattern "${S3_BUCKET_PREFIX}-"

# Create ALL pipeline buckets (reads S3_BUCKET_PREFIX from .env)
./scripts/create-all-buckets.sh

# Source the generated configuration
source bucket-config.env

# Verify bucket creation - should show exactly 7 buckets
aws s3 ls --no-cli-pager | grep "${S3_BUCKET_PREFIX}-"
```

Expected output (7 buckets total):
- `[prefix]-raw-data-[region]` - Raw sensor data
- `[prefix]-validated-data-[region]` - Validated data
- `[prefix]-anomalies-[region]` - Anomaly data
- `[prefix]-schematized-data-[region]` - Schema-enforced data
- `[prefix]-aggregated-data-[region]` - Aggregated metrics
- `[prefix]-checkpoints-[region]` - AutoLoader checkpoints
- `[prefix]-metadata-[region]` - Pipeline metadata

### Step 1.2: Configure IAM Permissions

Set up IAM roles for Databricks to access S3:

```bash
# Setup Databricks S3 access (reads configuration from .env)
./scripts/setup-databricks-s3-access.sh
# This will:
# 1. Generate credential values
# 2. Create/update IAM role
# 3. Show instructions for creating storage credential in Databricks UI
# Note: The script will pause for manual steps - you can press Ctrl+C after the IAM role is created

# Update IAM role for all buckets (uses S3_BUCKET_PREFIX from .env)
./scripts/update-iam-role-for-new-buckets.sh

# Verify IAM setup (optional - can be skipped)
./scripts/check-iam-policies.sh
# IGNORE warnings about these old roles - they don't affect your setup:
# - databricks-s3-storage-role
# - databricks-unity-catalog-role
# Only databricks-unity-catalog-expanso-role matters for this setup
```

### Step 1.3: Configure Unity Catalog Storage

#### Quick Reference

| Component | Name/Value |
|-----------|------------|
| **Storage Credential** | `databricks-unity-catalog-expanso-role` |
| **IAM Role ARN** | `arn:aws:iam::767397752906:role/databricks-unity-catalog-expanso-role` |
| **External ID** | Get from `.env` file (`DATABRICKS_EXTERNAL_ID`) |
| **Bucket Prefix** | `expanso` (or your custom prefix from `S3_BUCKET_PREFIX`) |
| **Region** | `us-west-2` (or your region from `AWS_REGION`) |

#### Automated Setup (Recommended)

Run these scripts to automatically configure Unity Catalog:

```bash
# Scripts will read configuration from .env file
# Configure storage credentials
uv run scripts/setup-unity-catalog-storage.py

# Create external locations
uv run scripts/setup-external-locations.py

# Verify setup - should show all 7 locations as ACTIVE
uv run scripts/show-unity-catalog-setup.py
```

**⚠️ IMPORTANT: Verify External Location URLs**

The script may report locations as "Active" but they could be pointing to OLD bucket names. Always verify in Databricks UI:

1. Go to **Catalog → External Data → External Locations**
2. Check that each location points to the CORRECT bucket:

| External Location | Correct URL | Wrong URL (OLD) |
|------------------|-------------|-----------------|
| `expanso_ingestion_data` | `s3://expanso-raw-data-us-west-2/` | ~~`s3://expanso-databricks-ingestion-us-west-2/`~~ |
| `expanso_validated_data` | `s3://expanso-validated-data-us-west-2/` | ~~`s3://expanso-databricks-validated-us-west-2/`~~ |
| `expanso_enriched_data` | `s3://expanso-schematized-data-us-west-2/` | ~~`s3://expanso-databricks-enriched-us-west-2/`~~ |
| `expanso_aggregated_data` | `s3://expanso-aggregated-data-us-west-2/` | ~~`s3://expanso-databricks-aggregated-us-west-2/`~~ |
| `expanso_anomalies_data` | `s3://expanso-anomalies-us-west-2/` | Correct |
| `expanso_checkpoints` | `s3://expanso-checkpoints-us-west-2/` | ~~`s3://expanso-databricks-checkpoints-us-west-2/`~~ |
| `expanso_metadata` | `s3://expanso-metadata-us-west-2/` | ~~`s3://expanso-databricks-metadata-us-west-2/`~~ |

**If URLs are wrong, fix them:**

```sql
-- Option 1: Run this SQL in Databricks to fix all at once
-- Copy from: scripts/fix-external-locations.sql

-- Drop incorrect locations
DROP EXTERNAL LOCATION IF EXISTS expanso_aggregated_data;
DROP EXTERNAL LOCATION IF EXISTS expanso_checkpoints;
DROP EXTERNAL LOCATION IF EXISTS expanso_enriched_data;
DROP EXTERNAL LOCATION IF EXISTS expanso_ingestion_data;
DROP EXTERNAL LOCATION IF EXISTS expanso_metadata;
DROP EXTERNAL LOCATION IF EXISTS expanso_validated_data;

-- Recreate with correct URLs
CREATE EXTERNAL LOCATION expanso_ingestion_data
URL 's3://expanso-raw-data-us-west-2/'
WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`);

CREATE EXTERNAL LOCATION expanso_validated_data
URL 's3://expanso-validated-data-us-west-2/'
WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`);

CREATE EXTERNAL LOCATION expanso_enriched_data
URL 's3://expanso-schematized-data-us-west-2/'
WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`);

CREATE EXTERNAL LOCATION expanso_aggregated_data
URL 's3://expanso-aggregated-data-us-west-2/'
WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`);

CREATE EXTERNAL LOCATION expanso_checkpoints
URL 's3://expanso-checkpoints-us-west-2/'
WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`);

CREATE EXTERNAL LOCATION expanso_metadata
URL 's3://expanso-metadata-us-west-2/'
WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`);
```

#### Manual Setup (If Automated Fails)

If the automated scripts encounter errors, you can create the external locations manually in Databricks:

**Step 1: Verify Storage Credential**

1. Go to your Databricks workspace
2. Navigate to: **Catalog → External Data → Credentials**
3. Verify you have a storage credential named `databricks-unity-catalog-expanso-role`
   - IAM Role ARN: `arn:aws:iam::767397752906:role/databricks-unity-catalog-expanso-role`
   - External ID: Check your `.env` file for `DATABRICKS_EXTERNAL_ID`

**Step 2: Create External Locations**

For each bucket, create an external location in Databricks:

1. Navigate to: **Catalog → External Data → External Locations**
2. Click **Create External Location**
3. Create each location with these settings:

| External Location Name | S3 URL | Storage Credential |
|------------------------|--------|-------------------|
| `expanso_ingestion_data` | `s3://expanso-raw-data-us-west-2/` | `databricks-unity-catalog-expanso-role` |
| `expanso_validated_data` | `s3://expanso-validated-data-us-west-2/` | `databricks-unity-catalog-expanso-role` |
| `expanso_enriched_data` | `s3://expanso-schematized-data-us-west-2/` | `databricks-unity-catalog-expanso-role` |
| `expanso_aggregated_data` | `s3://expanso-aggregated-data-us-west-2/` | `databricks-unity-catalog-expanso-role` |
| `expanso_anomalies_data` | `s3://expanso-anomalies-us-west-2/` | `databricks-unity-catalog-expanso-role` |
| `expanso_checkpoints` | `s3://expanso-checkpoints-us-west-2/` | `databricks-unity-catalog-expanso-role` |
| `expanso_metadata` | `s3://expanso-metadata-us-west-2/` | `databricks-unity-catalog-expanso-role` |

**Step 3: Grant Permissions**

For each external location:
1. Click on the external location name
2. Go to the **Permissions** tab
3. Click **Grant**
4. Add these permissions for `account users`:
   - `CREATE_EXTERNAL_TABLE`
   - `CREATE_MANAGED_STORAGE`
   - `READ_FILES`
   - `WRITE_FILES`

**Step 4: Verify Using SQL**

Run this in a Databricks SQL editor to verify:

```sql
-- Show all storage credentials
SHOW STORAGE CREDENTIALS;

-- Show all external locations (CHECK THE URLs!)
SHOW EXTERNAL LOCATIONS;

-- Test access to each location
LIST 's3://expanso-raw-data-us-west-2/';
LIST 's3://expanso-validated-data-us-west-2/';
LIST 's3://expanso-schematized-data-us-west-2/';
LIST 's3://expanso-aggregated-data-us-west-2/';
LIST 's3://expanso-anomalies-us-west-2/';
LIST 's3://expanso-checkpoints-us-west-2/';
LIST 's3://expanso-metadata-us-west-2/';

-- If any LIST fails, the external location URL is wrong
```

#### Verification Checklist

After setup, verify everything is configured correctly:

```bash
# 1. Check environment variables are set
source .env
echo "✓ Checking environment variables..."
echo "  S3_BUCKET_PREFIX: $S3_BUCKET_PREFIX"
echo "  AWS_REGION: $AWS_REGION"
echo "  DATABRICKS_EXTERNAL_ID: $DATABRICKS_EXTERNAL_ID"

# 2. Verify all S3 buckets exist
echo "✓ Checking S3 buckets..."
for type in raw-data validated-data schematized-data aggregated-data anomalies checkpoints metadata; do
    bucket="${S3_BUCKET_PREFIX}-${type}-${AWS_REGION}"
    # Remove extra "-data" for anomalies, checkpoints, metadata
    bucket="${bucket//-data-data-/-data-}"
    bucket="${bucket//anomalies-data/anomalies}"
    bucket="${bucket//checkpoints-data/checkpoints}"
    bucket="${bucket//metadata-data/metadata}"

    if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
        echo "  ✓ $bucket exists"
    else
        echo "  ✗ $bucket missing - run: aws s3 mb s3://$bucket"
    fi
done

# 3. Verify IAM role configuration
echo "✓ Checking IAM role..."
aws iam get-role --role-name databricks-unity-catalog-expanso-role \
    --query 'Role.AssumeRolePolicyDocument.Statement[0].Condition.StringEquals."sts:ExternalId"' \
    --output text --no-paginate

# 4. Test Databricks connectivity
echo "✓ Testing Databricks connection..."
uv run scripts/test-databricks-connection.py
```

## Part 2: Deploy Databricks Components

### Step 2.1: Upload AutoLoader Notebook

Upload the AutoLoader notebook to Databricks:

```bash
# Upload the AutoLoader notebook
uv run scripts/upload-and-run-notebook.py \
    --notebook databricks-notebooks/setup-and-run-autoloader.py

# This automatically uploads to: /Users/{DATABRICKS_USER_EMAIL}/demos/setup-and-run-autoloader
# The email is read from your .env file (DATABRICKS_USER_EMAIL)

# Verify notebook is uploaded
uv run scripts/check-databricks-notebooks.py
```

### Step 2.2: Create Database and Tables

Initialize the Unity Catalog database:

```bash
# Run SQL setup
uv run scripts/run-databricks-sql.py \
    --sql-file scripts/setup-unity-catalog.sql

# Create external location mappings
uv run scripts/run-databricks-sql.py \
    --sql-file scripts/create-external-locations.sql

# Verify database structure
uv run scripts/query-data-summary.py
```

## Part 3: Start Data Generation

### Step 3.1: Launch Normal Sensor (No Anomalies)

Start a sensor generating valid data:

```bash
# Terminal 1: Start normal sensor
./scripts/start-sensor.sh \
    --duration 300 \
    --interval 2

# Verify sensor is running
docker ps | grep wind-turbine-sensor

# Check generated data
docker exec wind-turbine-sensor ls -la /data/sensor_data.db
```

### Step 3.2: Launch Anomaly Sensor (With Anomalies)

Start a second sensor with anomalies:

```bash
# Terminal 2: Start anomaly sensor
./scripts/start-sensor.sh \
    --duration 300 \
    --interval 2 \
    --with-anomalies \
    --port 8081

# Verify both sensors are running
docker ps | grep wind-turbine-sensor
```

## Part 4: Run Data Pipeline

### Step 4.1: Start Schema Server (Local Testing)

For local testing without AWS, start the schema server:

```bash
# Terminal 3: Start schema server
uv run scripts/serve-schema-locally.py

# Verify server is running
curl http://localhost:8000/wind-turbine-schema.json
```

### Step 4.2: Launch Data Uploader

Start the uploader to process sensor data:

```bash
# Terminal 4: Run uploader for normal sensor
./scripts/start-databricks-uploader.sh \
    --sensor-port 8080 \
    --schema-url http://host.docker.internal:8000/wind-turbine-schema.json

# Terminal 5: Run uploader for anomaly sensor
./scripts/start-databricks-uploader.sh \
    --sensor-port 8081 \
    --schema-url http://host.docker.internal:8000/wind-turbine-schema.json \
    --container-name wind-turbine-uploader-anomaly
```

### Step 4.3: Monitor Pipeline Progress

Watch data flow through pipeline stages:

```bash
# Source bucket configuration
source bucket-config.env

# Monitor S3 bucket contents
watch -n 5 'source bucket-config.env && \
for bucket in $S3_BUCKET_RAW $S3_BUCKET_VALIDATED $S3_BUCKET_ANOMALIES \
    $S3_BUCKET_SCHEMATIZED $S3_BUCKET_AGGREGATED; do
    echo "=== $bucket ==="
    aws s3 ls s3://$bucket/ --recursive --summarize --no-paginate | tail -5
done'

# Check specific stages
aws s3 ls s3://$S3_BUCKET_RAW/ --recursive --no-paginate
aws s3 ls s3://$S3_BUCKET_VALIDATED/ --recursive --no-paginate
aws s3 ls s3://$S3_BUCKET_ANOMALIES/ --recursive --no-paginate
```

## Part 5: Databricks Processing

### Step 5.1: Start AutoLoader Streams

Initialize streaming jobs in Databricks:

```bash
# Scripts will read DATABRICKS_HOST, DATABRICKS_TOKEN, etc. from .env
# Start master AutoLoader for all stages
uv run scripts/setup-master-autoloader.py

# Verify streams are running
uv run scripts/list-compute-resources.py
```

### Step 5.2: Monitor Data Processing

Check data flow in Databricks:

```sql
-- Run in Databricks SQL workspace
-- Check raw data
SELECT COUNT(*) as raw_count
FROM wind_turbine_catalog.wind_turbine_data.raw_sensor_data;

-- Check validated data
SELECT COUNT(*) as validated_count
FROM wind_turbine_catalog.wind_turbine_data.validated_sensor_data;

-- Check anomalies
SELECT COUNT(*) as anomaly_count
FROM wind_turbine_catalog.wind_turbine_data.anomaly_sensor_data;

-- View recent anomalies
SELECT
    timestamp,
    turbine_id,
    anomaly_type,
    anomaly_score,
    details
FROM wind_turbine_catalog.wind_turbine_data.anomaly_sensor_data
ORDER BY timestamp DESC
LIMIT 10;
```

## Part 6: Demonstrate Anomaly Detection

### Step 6.1: Query Anomaly Patterns

Run anomaly analysis queries:

```bash
# Execute anomaly monitoring queries
uv run scripts/run-databricks-sql.py \
    --sql-file scripts/anomaly-monitoring-queries.sql \
    --output-format table

# Get anomaly summary
cat <<EOF | uv run scripts/run-databricks-sql.py --sql-stdin
SELECT
    anomaly_type,
    COUNT(*) as count,
    AVG(anomaly_score) as avg_score,
    MAX(anomaly_score) as max_score
FROM wind_turbine_catalog.wind_turbine_data.anomaly_sensor_data
GROUP BY anomaly_type
ORDER BY count DESC;
EOF
```

### Step 6.2: Visualize Pipeline Stages

Check data at each pipeline stage:

```bash
# Source bucket configuration
source bucket-config.env

# Stage 1: Raw Data (all sensor readings)
echo "=== RAW DATA ==="
aws s3 ls s3://$S3_BUCKET_RAW/ --recursive --no-paginate | head -5

# Stage 2: Validated Data (physics-compliant readings)
echo "=== VALIDATED DATA ==="
aws s3 ls s3://$S3_BUCKET_VALIDATED/ --recursive --no-paginate | head -5

# Stage 3: Anomalies (physics violations)
echo "=== ANOMALIES ==="
aws s3 ls s3://$S3_BUCKET_ANOMALIES/ --recursive --no-paginate | head -5

# Stage 4: Schematized Data (structured format)
echo "=== SCHEMATIZED DATA ==="
aws s3 ls s3://$S3_BUCKET_SCHEMATIZED/ --recursive --no-paginate | head -5

# Stage 5: Aggregated Data (analytics-ready)
echo "=== AGGREGATED DATA ==="
aws s3 ls s3://$S3_BUCKET_AGGREGATED/ --recursive --no-paginate | head -5
```

## Part 7: Verify Complete Pipeline

### Step 7.1: End-to-End Validation

Verify the complete data flow:

```bash
# Run validation script
uv run scripts/validate-all.py \
    --check-buckets \
    --check-databricks \
    --check-anomalies \
    --verbose

# Check data lineage
uv run scripts/check-lineage.py \
    --turbine-id turbine_001 \
    --trace-record
```

### Step 7.2: Generate Summary Report

Create a summary of the demo:

```bash
# Generate pipeline report
cat <<EOF > demo_report.md
# Wind Turbine Pipeline Demo Report
Generated: $(date)

## Data Generation
- Normal Sensor: $(docker logs wind-turbine-sensor 2>&1 | \
    grep "Generated" | tail -1)
- Anomaly Sensor: $(docker logs wind-turbine-sensor-anomaly 2>&1 | \
    grep "Generated" | tail -1)

## S3 Storage
$(source bucket-config.env
for bucket in $S3_BUCKET_RAW $S3_BUCKET_VALIDATED $S3_BUCKET_ANOMALIES \
    $S3_BUCKET_SCHEMATIZED $S3_BUCKET_AGGREGATED; do
    count=$(aws s3 ls s3://$bucket/ --recursive --no-paginate | wc -l)
    echo "- $bucket: $count files"
done)

## Databricks Tables
$(uv run scripts/query-data-summary.py --format markdown)

## Anomaly Detection
$(cat <<SQL | uv run scripts/run-databricks-sql.py --sql-stdin --format markdown
SELECT
    'Total Anomalies' as metric,
    COUNT(*) as value
FROM wind_turbine_catalog.wind_turbine_data.anomaly_sensor_data
UNION ALL
SELECT
    'Unique Turbines with Anomalies' as metric,
    COUNT(DISTINCT turbine_id) as value
FROM wind_turbine_catalog.wind_turbine_data.anomaly_sensor_data
UNION ALL
SELECT
    'Anomaly Types Detected' as metric,
    COUNT(DISTINCT anomaly_type) as value
FROM wind_turbine_catalog.wind_turbine_data.anomaly_sensor_data;
SQL
)
EOF

cat demo_report.md
```

## Part 8: Cleanup

### Step 8.1: Stop Services

Stop all running services:

```bash
# Stop sensors
docker stop wind-turbine-sensor wind-turbine-sensor-anomaly
docker rm wind-turbine-sensor wind-turbine-sensor-anomaly

# Stop uploaders
docker stop wind-turbine-uploader wind-turbine-uploader-anomaly
docker rm wind-turbine-uploader wind-turbine-uploader-anomaly

# Stop schema server
pkill -f serve-schema-locally.py
```

### Step 8.2: Clean Resources (Optional)

Clean up AWS and Databricks resources:

```bash
# Option 1: Clean bucket data only (keeps buckets)
./scripts/clean-all-data.sh

# Option 2: Delete all buckets completely (slow method)
./scripts/delete-all-buckets.sh

# Option 3: Fast delete buckets with many versioned objects
./scripts/turbo-delete-buckets.py --pattern "${S3_BUCKET_PREFIX}-"

# Clean Databricks tables
uv run scripts/cleanup-tables.py

# Stop Databricks clusters
uv run scripts/start-cluster.py --action stop
```

## Troubleshooting

### Common Issues and Solutions

1. **S3 Access Denied / UNAUTHORIZED_ACCESS Error**
   ```bash
   # Error: "[UNAUTHORIZED_ACCESS] Unauthorized access: s3://expanso-raw-data-us-west-2/"
   
   # Solution 1: Update IAM policy with correct bucket names
   ./scripts/update-iam-role-for-new-buckets.sh
   
   # Solution 2: Wait for IAM changes to propagate (IMPORTANT!)
   echo "Waiting 2-3 minutes for IAM changes to propagate..."
   sleep 180
   
   # Solution 3: Restart your Databricks cluster
   # Go to Databricks → Compute → Your Cluster → Restart
   # This clears cached credentials
   
   # Solution 4: Test access directly in Databricks SQL:
   # Run these commands in a Databricks SQL editor:
   LIST 's3://expanso-raw-data-us-west-2/';
   LIST 's3://expanso-validated-data-us-west-2/';
   
   # If LIST works but notebook doesn't, re-upload the notebook:
   uv run scripts/upload-and-run-notebook.py \
     --notebook databricks-notebooks/setup-and-run-autoloader.py
   ```

2. **Databricks Notebook Not Found**
   ```bash
   # Re-upload the notebook
   uv run scripts/upload-and-run-notebook.py \
     --notebook databricks-notebooks/setup-and-run-autoloader.py \
     --force
   ```

3. **No Data in Anomaly Bucket**
   ```bash
   # Ensure anomaly sensor is running
   docker logs wind-turbine-sensor-anomaly | grep "anomaly"
   # Check uploader logs
   docker logs wind-turbine-uploader-anomaly | grep "Invalid"
   ```

4. **AutoLoader Not Processing**
   ```bash
   # Source bucket configuration
   source bucket-config.env

   # Restart AutoLoader
   uv run scripts/restart-autoloader.py

   # Check checkpoint location
   aws s3 ls s3://$S3_BUCKET_CHECKPOINTS/ --no-paginate
   ```

5. **External Location Errors**
   ```bash
   # If you see "External ID not found" even though it's in .env:
   source .env
   echo $DATABRICKS_EXTERNAL_ID  # Should show your external ID

   # If external locations fail to create:
   # 1. Verify storage credential exists in Databricks UI
   # 2. Check IAM role has correct trust policy:
   aws iam get-role --role-name databricks-unity-catalog-expanso-role \
     --query 'Role.AssumeRolePolicyDocument' --no-paginate

   # 3. Manually create in Databricks UI (see Step 1.3 manual instructions)
   ```

6. **Bucket Name Mismatches**
   ```bash
   # Ensure all scripts use correct bucket names
   grep "S3_BUCKET" .env

   # Buckets should follow pattern:
   # ${S3_BUCKET_PREFIX}-{type}-data-${AWS_REGION}
   # Except: anomalies and checkpoints (no "-data")

   # Verify actual bucket names:
   aws s3 ls --no-paginate | grep $S3_BUCKET_PREFIX
   ```



8. **External Locations Point to Wrong Buckets**
   ```bash
   # Symptom: Some buckets work (like anomalies) but others fail with UNAUTHORIZED_ACCESS
   # Even though the script says all locations are "Active"
   
   # The problem: External locations exist but point to OLD bucket names
   # Check in Databricks UI: Catalog → External Data → External Locations
   
   # Solution: Run the fix SQL script
   cat scripts/fix-external-locations.sql
   # Copy and run in Databricks SQL Editor
   
   # Or fix manually in UI:
   # 1. Click each external location
   # 2. Click Edit
   # 3. Update URL to correct bucket (see table in Step 1.3)
   ```

9. **IAM Role Self-Assumption Error**
   ```bash
   # Error: "The IAM role for this storage credential was found to be non self-assuming"
   # This happens when creating new external locations

   # Solution 1: Fix the IAM role to allow self-assumption
   ./scripts/fix-iam-self-assume.sh

   # Solution 2: Create the location manually in Databricks SQL
   # Run this SQL in Databricks:
   CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_anomalies_data
   URL 's3://expanso-anomalies-us-west-2/'
   WITH (STORAGE CREDENTIAL `databricks-unity-catalog-expanso-role`)
   COMMENT 'External location for anomaly data';

   # Solution 3: Use the Databricks UI
   # Go to Catalog → External Data → External Locations → Create
   ```

## Quick Demo Script

For a fully automated demo, run:

```bash
# Ensure .env is configured first
./scripts/validate-env.sh

# Run complete demo (takes ~10 minutes)
./scripts/run-anomaly-demo.sh --full

# Run quick demo (takes ~3 minutes)
./scripts/run-anomaly-demo.sh --quick
```

**Note**: All scripts in this project read configuration from the `.env` file.
No inline environment variables are needed after initial setup.

## Summary

This guide provides a complete walkthrough of:
1. **Infrastructure**: S3 buckets, IAM roles, Unity Catalog
2. **Data Generation**: Normal and anomaly sensors
3. **Pipeline Processing**: Multi-stage data transformation
4. **Anomaly Detection**: Physics-based validation
5. **Databricks Integration**: AutoLoader streaming
6. **Monitoring**: Real-time pipeline observation

The pipeline demonstrates enterprise-grade data processing with:
- Real-time streaming ingestion
- Schema validation and evolution
- Anomaly detection and segregation
- Multi-stage data transformation
- Unity Catalog governance

For development and advanced configuration, see:
- `docs/DEVELOPMENT_RULES.md` - Development guidelines
- `docs/ENVIRONMENT_SETUP.md` - Environment configuration details
- `docs/QUICK_START_CHECKLIST.md` - Infrastructure setup checklist
- `scripts/README.md` - Script documentation
- `docs/archive/` - Historical documentation and references
