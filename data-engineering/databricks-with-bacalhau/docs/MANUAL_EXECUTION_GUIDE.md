# 🚀 Complete Manual Execution Guide
## Autoloader-Only Sensor Data Pipeline

This guide provides step-by-step instructions to manually execute and test the complete Autoloader pipeline.

**⚡ SINGLE EXECUTION METHOD: All operations use `uv run -s autoloader_main.py`**

---

## 🎯 Prerequisites

### 1. Install uv
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart terminal
```

### 2. Verify Environment
```bash
# Ensure you're in the correct directory
cd /Users/daaronch/code/bacalhau-examples/data-engineering/databricks-with-bacalhau/databricks-uploader

# Verify uv installation
uv --version
```

---

## 📋 Step 1: Environment Configuration

### Set Required Environment Variables
```bash
# Databricks Configuration
export DATABRICKS_HOST="your-workspace.databricks.com"
export DATABRICKS_HTTP_PATH="/sql/1.0/endpoints/your-endpoint"
export DATABRICKS_TOKEN="your-databricks-token"

# AWS Configuration  
export AWS_REGION="us-east-1"
export DATABRICKS_IAM_ROLE="arn:aws:iam::123456789012:role/databricks-unity-catalog-role"

# Unity Catalog Configuration (optional - uses defaults if not set)
export UC_CATALOG="sensor_data_catalog"
export UC_SCHEMA="sensor_pipeline"
export UC_STORAGE_CREDENTIAL="sensor_pipeline_storage_cred"

# S3 Bucket Configuration (optional - uses defaults if not set)
export S3_BUCKET_RAW="s3://sensor-data-raw-us-east-1"
export S3_BUCKET_SCHEMATIZED="s3://sensor-data-schematized-us-east-1"
export S3_BUCKET_FILTERED="s3://sensor-data-filtered-us-east-1"
export S3_BUCKET_EMERGENCY="s3://sensor-data-emergency-us-east-1"
export S3_BUCKET_CHECKPOINTS="s3://sensor-data-checkpoints-us-east-1"

# Permissions (optional - uses defaults if not set)
export DATA_TEAM_GROUP="data_team"
export SERVICE_PRINCIPAL="autoloader_service"
```

### Verify Environment Variables
```bash
# Verify all required variables are set
env | grep -E "(DATABRICKS|AWS|UC_|S3_)" | sort
```

**Expected Output:**
```
AWS_REGION=us-east-1
DATABRICKS_HOST=your-workspace.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/endpoints/your-endpoint
DATABRICKS_IAM_ROLE=arn:aws:iam::123456789012:role/databricks-unity-catalog-role
DATABRICKS_TOKEN=your-databricks-token
S3_BUCKET_RAW=s3://sensor-data-raw-us-east-1
[... other variables ...]
```

---

## 🏗️ Step 2: Infrastructure Setup

### Run Complete Infrastructure Setup
```bash
uv run -s autoloader_main.py setup
```

**Expected Output:**
```
🚀 Setting up Autoloader infrastructure...
📋 Setting up Unity Catalog...
✅ Storage credential 'sensor_pipeline_storage_cred' created
✅ External location 'sensor_data_raw_location' created
✅ External location 'sensor_data_schematized_location' created
✅ External location 'sensor_data_filtered_location' created
✅ External location 'sensor_data_emergency_location' created
✅ External location 'autoloader_checkpoints_location' created
✅ UC Volume 'autoloader_checkpoints' created
✅ UC Volume 'schema_evolution' created
✅ Permissions granted for data_team
✅ Permissions granted for autoloader_service
⚡ Setting up Autoloader pipelines...
✅ Autoloader table 'sensor_readings_raw' created
✅ Autoloader table 'sensor_readings_schematized' created
✅ Autoloader table 'sensor_readings_filtered' created
✅ Autoloader table 'sensor_readings_emergency' created
🔍 Validating setup...
✅ Autoloader infrastructure setup completed!

Next steps:
  uv run -s autoloader_main.py process --db-path sensor_data.db
  uv run -s autoloader_main.py monitor
```

### Test Infrastructure Setup
```bash
# Verify infrastructure was created correctly
uv run -s autoloader_main.py status
```

**Expected Output:**
```
📊 Autoloader System Status
========================================

🏗️  Unity Catalog Infrastructure:
Timestamp: 2025-01-03 10:30:45
Tables: 4
  ✅ sensor_readings_raw: 0 records
  ✅ sensor_readings_schematized: 0 records
  ✅ sensor_readings_filtered: 0 records
  ✅ sensor_readings_emergency: 0 records

📁 S3 Landing Service:
  ✅ S3 Access: Valid

📊 Monitoring:
  ✅ Overall Status: healthy
  📡 Databricks: connected
  🗄️  S3 Buckets: 5/5
```

---

## 📊 Step 3: Prepare Test Data

### Create Test Database
```bash
# Create test sensor data (uses existing script)
python create_test_sensor_data.py

# Verify test data was created
ls -la sensor_data.db
sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_data;"
```

**Expected Output:**
```
-rw-r--r--  1 user  staff  24576 Jan  3 10:35 sensor_data.db
1000
```

---

## 🚀 Step 4: Process Data Through Autoloader

### Single Batch Processing
```bash
# Process one batch of data
uv run -s autoloader_main.py process --db-path sensor_data.db
```

**Expected Output:**
```
📊 Processing data with Autoloader...
📈 Processing single batch from sensor_data.db

📊 Processing Results:
Pipeline: schematized
Records: 1000
Uploads: 4
  - raw: s3://sensor-data-raw-us-east-1/year=2025/month=01/day=03/batch_20250103_103045.json
  - schematized: s3://sensor-data-schematized-us-east-1/year=2025/month=01/day=03/batch_20250103_103045.json
  - filtered: s3://sensor-data-filtered-us-east-1/year=2025/month=01/day=03/batch_20250103_103045.json
  - emergency: s3://sensor-data-emergency-us-east-1/year=2025/month=01/day=03/batch_20250103_103045.json
```

### Verify Data Processing
```bash
# Check system status after processing
uv run -s autoloader_main.py status
```

**Expected Output (after Autoloader processes):**
```
📊 Autoloader System Status
========================================

🏗️  Unity Catalog Infrastructure:
Timestamp: 2025-01-03 10:32:15
Tables: 4
  ✅ sensor_readings_raw: 1000 records
  ✅ sensor_readings_schematized: 850 records
  ✅ sensor_readings_filtered: 720 records
  ✅ sensor_readings_emergency: 15 records

📁 S3 Landing Service:
  ✅ S3 Access: Valid

📊 Monitoring:
  ✅ Overall Status: healthy
  📡 Databricks: connected
  🗄️  S3 Buckets: 5/5
```

---

## 📊 Step 5: Start Monitoring

### Launch Monitoring Dashboard
```bash
# Start monitoring dashboard (in separate terminal)
uv run -s autoloader_main.py monitor --port 8000
```

**Expected Output:**
```
📊 Starting Autoloader monitoring dashboard...
🚀 Dashboard starting at http://0.0.0.0:8000
📋 API docs at http://0.0.0.0:8000/docs
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Test Monitoring Endpoints
```bash
# Test API health (in another terminal)
curl http://localhost:8000/api/health
```

**Expected Output:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-03T15:32:00Z",
  "version": "1.0.0",
  "components": {
    "databricks": {"status": "connected"},
    "s3": {"status": "accessible", "accessible_buckets": 5, "total_buckets": 5}
  }
}
```

### Test Pipeline Status API
```bash
curl http://localhost:8000/api/pipelines/status
```

**Expected Output:**
```json
{
  "pipelines": [
    {
      "name": "sensor_readings_raw",
      "status": "active",
      "record_count": 1000,
      "last_update": "2025-01-03T15:30:45Z"
    },
    {
      "name": "sensor_readings_schematized", 
      "status": "active",
      "record_count": 850,
      "last_update": "2025-01-03T15:30:45Z"
    }
  ]
}
```

---

## 🧪 Step 6: Run Comprehensive Tests

### Run All Tests
```bash
uv run -s autoloader_main.py test --type all
```

**Expected Output:**
```
🧪 Running Autoloader tests...
🚀 Setting up test environment...
✅ Test databases created
✅ Mock S3 services initialized
✅ Test configurations loaded

🧪 Running Raw Pipeline Test...
✅ Raw data processing test passed

🧪 Running Schematized Pipeline Test...
✅ Schema validation test passed
✅ Data transformation test passed

🧪 Running Emergency Detection Test...
✅ Anomaly detection test passed
✅ Emergency routing test passed

🧪 Running S3 Access Validation Test...
✅ S3 bucket access test passed
✅ Permission validation test passed

🧪 Running Data Partitioning Test...
✅ Date partitioning test passed
✅ Data routing test passed

✅ All tests completed successfully!
```

### Run Individual Tests
```bash
# Test specific components
uv run -s autoloader_main.py test --type raw
uv run -s autoloader_main.py test --type schematized
uv run -s autoloader_main.py test --type emergency
uv run -s autoloader_main.py test --type s3-access
uv run -s autoloader_main.py test --type partitioning
```

---

## 🔄 Step 7: Continuous Processing (Optional)

### Start Continuous Processing
```bash
# Start continuous processing (every 60 seconds)
uv run -s autoloader_main.py process --continuous --interval 60
```

**Expected Output:**
```
📊 Processing data with Autoloader...
🔄 Starting continuous processing (every 60s)
📈 Processing batch at 2025-01-03 15:35:00
📊 Processing Results: 1000 records processed
📈 Processing batch at 2025-01-03 15:36:00
📊 Processing Results: 1000 records processed
[... continues every 60 seconds ...]
```

### Stop Continuous Processing
```bash
# Press Ctrl+C to stop
# Expected output:
🛑 Interrupted by user
```

---

## ✅ Verification Checklist

### Infrastructure Verification
- [ ] All environment variables are set correctly
- [ ] `uv run -s autoloader_main.py setup` completes successfully
- [ ] `uv run -s autoloader_main.py status` shows all components as healthy
- [ ] Unity Catalog tables are created and accessible
- [ ] S3 buckets are accessible from Databricks

### Processing Verification  
- [ ] Test data is created successfully
- [ ] Single batch processing completes without errors
- [ ] Data appears in all 4 Autoloader tables (raw, schematized, filtered, emergency)
- [ ] Record counts match expected values
- [ ] S3 files are created with proper partitioning

### Monitoring Verification
- [ ] Monitoring dashboard starts successfully
- [ ] API endpoints respond correctly
- [ ] Dashboard shows real-time data
- [ ] Health checks pass

### Testing Verification
- [ ] All comprehensive tests pass
- [ ] Individual component tests pass
- [ ] Mock services work correctly
- [ ] No test failures or errors

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Setup Fails
```bash
# Check environment variables
env | grep -E "(DATABRICKS|AWS)" | sort

# Verify Databricks connectivity
curl -H "Authorization: Bearer $DATABRICKS_TOKEN" \
     "https://$DATABRICKS_HOST/api/2.0/clusters/list"

# Check AWS credentials
aws sts get-caller-identity
```

#### Processing Fails
```bash
# Check S3 access
uv run -s autoloader_main.py test --type s3-access

# Verify database file exists and is readable
ls -la sensor_data.db
sqlite3 sensor_data.db "SELECT COUNT(*) FROM sensor_data LIMIT 1;"
```

#### Monitoring Issues
```bash
# Check if port is available
lsof -i :8000

# Test basic connectivity
curl http://localhost:8000/api/health

# Check logs
uv run -s autoloader_main.py monitor --port 8001
```

#### Test Failures
```bash
# Run tests with verbose output
uv run -s autoloader_main.py test --type all --verbose

# Check individual components
uv run -s autoloader_main.py status
```

---

## 📚 Next Steps

After successful execution:

1. **Deploy to Production**: Use the same commands in your production environment
2. **Schedule Continuous Processing**: Set up cron jobs or orchestration tools
3. **Configure Monitoring**: Set up alerts and notifications
4. **Scale**: Adjust batch sizes and processing intervals based on load

---

## 🚨 Important Notes

- **ONLY use `uv run -s autoloader_main.py`** - no other execution methods are supported
- All configuration is done via environment variables and YAML files
- The system is completely stateless - you can run commands independently
- Autoloader provides exactly-once processing guarantees
- All data is processed through S3 → Autoloader → Delta Tables pipeline

---

**Remember: This is the ONLY supported execution method. No legacy scripts or alternative paths are maintained.**
