# Databricks Auto Loader Setup Guide

This guide walks you through setting up Databricks Auto Loader to ingest sensor data from S3 into Delta tables.

## Prerequisites

1. Databricks workspace with SQL warehouse or cluster
2. S3 buckets with data (already set up)
3. IAM permissions for Databricks to access S3

## Step 1: Test Databricks Connection

First, verify your Databricks connection and S3 access:

```bash
# From project root
uv run -s test-databricks-connection.py
```

This will:
- Test connection to Databricks
- Verify S3 bucket access
- Create test database
- Show existing tables

## Step 2: Configure S3 Access in Databricks

### Option A: Instance Profile (Recommended)
1. Create an IAM role with S3 access
2. Attach to Databricks cluster as instance profile
3. No credentials needed in code

### Option B: Access Keys (Not recommended for production)
```sql
-- In Databricks notebook
spark.conf.set("fs.s3a.access.key", "<your-access-key>")
spark.conf.set("fs.s3a.secret.key", "<your-secret-key>")
```

### Option C: Unity Catalog External Location
```sql
-- Create external location
CREATE EXTERNAL LOCATION IF NOT EXISTS sensor_data_location
URL 's3://expanso-databricks-raw-us-west-2/'
WITH (STORAGE CREDENTIAL sensor_data_credential);
```

## Step 3: Upload Notebooks to Databricks

1. **Upload SQL Setup Notebook**
   - File: `databricks-notebooks/setup-autoloader-tables.sql`
   - Creates database and table structure
   - Run this first to set up schema

2. **Upload Auto Loader Notebook**
   - File: `databricks-notebooks/autoloader-json-ingestion.py`
   - Configures streaming ingestion
   - Processes JSON files from S3

## Step 4: Run Setup Notebook

In Databricks:
1. Open `setup-autoloader-tables.sql`
2. Run all cells to create:
   - `sensor_data` database
   - Bronze tables (raw, schematized, filtered, emergency)
   - Silver table (cleaned data)
   - Gold tables (aggregations)
   - Views for easy querying

## Step 5: Start Auto Loader

In Databricks:
1. Open `autoloader-json-ingestion.py`
2. Update S3 bucket names if needed (cell 1)
3. Run all cells to start streaming

The notebook will:
- Read JSON files from S3 buckets
- Parse and validate data
- Write to Bronze → Silver → Gold layers
- Create hourly/daily aggregations

## Step 6: Monitor Ingestion

### Check Streaming Status
```python
# In notebook
for stream in spark.streams.active:
    print(f"Stream: {stream.id} - Status: {stream.status}")
```

### Query Data
```sql
-- Check record counts
SELECT 
  'Bronze' as layer, COUNT(*) as records
FROM sensor_data.sensor_readings_bronze_raw
UNION ALL
SELECT 
  'Silver' as layer, COUNT(*) as records  
FROM sensor_data.sensor_readings_silver;

-- View latest data
SELECT * FROM sensor_data.sensor_readings_silver
ORDER BY timestamp DESC
LIMIT 10;

-- Check for anomalies
SELECT * FROM sensor_data.v_sensor_anomalies
WHERE processing_date = current_date();
```

## Step 7: Verify End-to-End Flow

1. **Upload new data from local**
   ```bash
   # Generate and upload test data
   uv run -s run-pipeline.py --once
   ```

2. **Wait 30-60 seconds** for Auto Loader to pick up files

3. **Query in Databricks**
   ```sql
   -- Check latest ingestion
   SELECT 
     MAX(ingestion_timestamp) as last_ingestion,
     COUNT(*) as total_records
   FROM sensor_data.sensor_readings_bronze_raw
   WHERE ingestion_timestamp > current_timestamp() - INTERVAL 5 MINUTES;
   ```

## Troubleshooting

### No Data Appearing
1. Check S3 permissions:
   ```sql
   LIST 's3://expanso-databricks-raw-us-west-2/raw/'
   ```

2. Check streaming status:
   ```python
   spark.streams.active[0].status
   ```

3. Check checkpoint location for errors:
   ```python
   dbutils.fs.ls("/tmp/sensor_data/checkpoints/")
   ```

### S3 Access Denied
1. Verify IAM role has permissions:
   - `s3:GetObject`
   - `s3:ListBucket`
   - `s3:GetBucketLocation`

2. Check bucket policy allows Databricks

3. Ensure correct region (us-west-2)

### Schema Mismatch
1. Clear schema location:
   ```python
   dbutils.fs.rm("/tmp/sensor_data/schemas/", True)
   ```

2. Restart streams with fresh schema

## Production Considerations

1. **Optimize File Sizes**
   - Target 128-256 MB per file
   - Use Auto Loader's `maxFilesPerTrigger`

2. **Set Trigger Intervals**
   ```python
   .trigger(processingTime="5 minutes")  # Adjust based on latency needs
   ```

3. **Enable Auto Optimize**
   ```sql
   ALTER TABLE sensor_readings_silver
   SET TBLPROPERTIES (
     'delta.autoOptimize.optimizeWrite' = 'true',
     'delta.autoOptimize.autoCompact' = 'true'
   );
   ```

4. **Monitor Costs**
   - Track S3 API calls
   - Monitor cluster utilization
   - Use spot instances for non-critical workloads

## Next Steps

1. **Create Dashboards**
   - Use Databricks SQL for visualizations
   - Connect to BI tools

2. **Set Up Alerts**
   - Monitor anomalies
   - Track sensor health
   - Alert on data delays

3. **Implement Data Quality**
   - Add expectations to Delta tables
   - Track data quality metrics
   - Quarantine bad data

4. **Scale Out**
   - Add more sensors
   - Process historical data
   - Implement real-time analytics