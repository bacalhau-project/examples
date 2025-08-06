# Setup Complete! 🎉

Your Databricks Pipeline v2 infrastructure is now fully configured and ready to use.

## What Was Created

### 1. S3 Buckets (All in us-west-2)
- ✅ `expanso-databricks-raw-us-west-2` - Raw sensor data
- ✅ `expanso-databricks-schematized-us-west-2` - Validated data
- ✅ `expanso-databricks-error-us-west-2` - Validation failures
- ✅ `expanso-databricks-archival-us-west-2` - Long-term storage
- ✅ `expanso-databricks-aggregated-us-west-2` - Windowed aggregations

### 2. IAM Role
- ✅ `arn:aws:iam::767397752906:role/expanso-databricks-s3-access-role`
- Configured with trust relationship for Databricks account: 414351767826

### 3. Databricks Database & Tables
- ✅ Database: `sensor_data`
- ✅ Tables:
  - `raw_sensor_data` - Raw data with lineage
  - `schematized_sensor_data` - Validated data
  - `aggregated_sensor_data` - 1-minute aggregations
  - `error_sensor_data` - Validation errors
  - `anomaly_notifications` - SQS notification log

### 4. SQS Queue
- ✅ `sensor-anomaly-notifications` in us-west-2
- URL: `https://sqs.us-west-2.amazonaws.com/767397752906/sensor-anomaly-notifications`

### 5. SQL Warehouse
- ✅ Serverless Starter Warehouse (Running)
- Endpoint: `/sql/1.0/warehouses/6a80650f34fb7115`

## Quick Test Commands

### 1. Test Pipeline Configuration
```bash
# Set initial scenarios
./pipeline_manager_v2.py set raw schematized lineage --by "$USER"

# Check configuration
./pipeline_manager_v2.py get
```

### 2. Test Dry Run
```bash
# Run once without uploading
./pipeline_orchestrator.py --dry-run --once
```

### 3. Run Live Pipeline
```bash
# Start the pipeline (uploads to S3)
./pipeline_orchestrator.py
```

### 4. Monitor Progress
```bash
# In another terminal
./monitoring_dashboard.py

# Check S3 uploads
aws s3 ls s3://expanso-databricks-raw-us-west-2/raw/ --recursive | tail -5
aws s3 ls s3://expanso-databricks-schematized-us-west-2/validated/ --recursive | tail -5
```

### 5. Query Databricks
```sql
-- In Databricks SQL Editor
USE sensor_data;

-- Check if data is arriving
SELECT COUNT(*) FROM raw_sensor_data;

-- View recent records
SELECT * FROM raw_sensor_data 
ORDER BY processed_at DESC 
LIMIT 10;
```

## Next Steps

### 1. Configure Databricks Auto Loader
1. Go to Databricks workspace
2. Create a new notebook
3. Copy content from `databricks_autoloader_configs/autoloader_raw.py`
4. Update the IAM role ARN in the notebook
5. Run the notebook to start streaming from S3

### 2. Set Up Instance Profile (One Time)
1. In Databricks Admin Console → Instance Profiles
2. Add: `arn:aws:iam::767397752906:role/expanso-databricks-s3-access-role`
3. Attach to your cluster

### 3. Test End-to-End Flow
1. Ensure `sensor_data.db` has test data
2. Run pipeline: `./pipeline_orchestrator.py`
3. Monitor S3 uploads
4. Check Databricks tables for ingested data

## Troubleshooting

### Pipeline Not Processing
```bash
# Check state
cat state/orchestrator_state.json

# Reset if needed
rm state/orchestrator_state.json
```

### S3 Access Issues
```bash
# Verify credentials
aws sts get-caller-identity

# Test bucket access
aws s3 ls s3://expanso-databricks-raw-us-west-2/
```

### Databricks Connection
```bash
# Test connection
databricks current-user me

# Check warehouse status
databricks warehouses get 6a80650f34fb7115
```

## Environment Variables Summary
All configuration is in `.env`:
- ✅ AWS Account: 767397752906
- ✅ S3 Prefix: expanso
- ✅ Region: us-west-2
- ✅ Databricks Host: dbc-ae5355ab-8b4e.cloud.databricks.com
- ✅ SQL Warehouse: 6a80650f34fb7115
- ✅ Database: sensor_data

## Support Commands
```bash
# Full status check
./start-pipeline.sh status

# Monitor uploads
./start-pipeline.sh monitor

# Quick help
./start-pipeline.sh help
```

Your pipeline is ready to process sensor data! 🚀